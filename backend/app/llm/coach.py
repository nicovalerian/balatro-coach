"""
Balatro coaching via DigitalOcean Serverless Inference.

Flow:
  1. Build query from game_state JSON + user message
  2. Retrieve relevant RAG context
  3. Call chat completions API with:
     - System prompt (Balatro expert persona)
     - Game state JSON (structured)
     - RAG context (top-k chunks)
     - User question
     - Optional: raw image as vision fallback when CV confidence < threshold
  4. Stream response back
"""
from __future__ import annotations

import base64
import json
import logging
from typing import AsyncIterator

from openai import AuthenticationError, OpenAI

from ..config import settings
from ..rag.retriever import RAGRetriever

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert Balatro coach. Balatro is a poker-based roguelike where \
players build joker synergies to score chips × multiplier against escalating blind targets.

Your role:
- Analyse the player's current game state and give clear, specific coaching advice
- Prioritise plays/decisions that maximise the player's chances of beating the blind
- Explain *why* a play is good, referencing relevant joker/card mechanics
- If the game state is ambiguous, ask for clarification on the specific missing info only
- Be concise and direct; advanced players want reasoning, not hand-holding

Key mechanics you know deeply:
- Scoring: (base chips + card chips) × (base mult + additive mult) × (multiplicative mult jokers)
- Joker activation order matters: +Chips → +Mult → xMult (left to right)
- Hand types and their base chips/mult values
- Planet cards scale specific hand types permanently
- Tarot cards modify cards or provide mult; Spectral cards are powerful but unpredictable
- Interest mechanic: $1 per $5 held, max $25 interest per round
- Boss blinds and their debuff effects
- Skip blind rewards vs beating the blind tradeoffs

When a game state JSON is provided, use it as the ground truth. When a retrieved context \
chunk is relevant, integrate it naturally without citing chunk numbers.
"""

LOW_CONFIDENCE_MESSAGE = (
    "I couldn't read your screenshot clearly enough to be confident "
    "about the details. Could you tell me:\n"
    "- What jokers do you currently have?\n"
    "- What hand are you playing / what's in the shop?\n"
    "- Your current score, chips needed, hands/discards remaining?"
)


class BalatroCoach:
    def __init__(self, retriever: RAGRetriever):
        base_url = settings.inference_base_url.rstrip("/") + "/"
        self._client = OpenAI(api_key=settings.model_access_key, base_url=base_url)
        self._retriever = retriever
        self._models = self._build_model_candidates()

    async def stream_response(
        self,
        user_message: str,
        game_state: dict | None = None,
        image_bytes: bytes | None = None,
        low_confidence: bool = False,
    ) -> AsyncIterator[str]:
        """Yield text chunks as they stream from the configured inference model."""

        # ── Low confidence: ask for clarification ────────────────────────────
        if low_confidence and game_state and game_state.get("low_confidence"):
            yield LOW_CONFIDENCE_MESSAGE
            return

        # ── Build retrieval query ─────────────────────────────────────────────
        rag_query = self._build_rag_query(user_message, game_state)
        context_chunks = self._retriever.retrieve(rag_query, top_k=settings.retrieval_top_k)
        rag_context = _format_context(context_chunks)

        # ── Build user turn content ───────────────────────────────────────────
        user_content: list[dict] = []

        if game_state:
            state_text = json.dumps(game_state, indent=2)
            user_content.append({
                "type": "text",
                "text": f"**Current game state (extracted from screenshot):**\n```json\n{state_text}\n```\n",
            })

        if rag_context:
            user_content.append({
                "type": "text",
                "text": f"**Relevant game knowledge:**\n{rag_context}\n",
            })

        # Vision fallback: attach image if CV failed or no game state
        if image_bytes and (low_confidence or not game_state):
            b64 = base64.standard_b64encode(image_bytes).decode()
            user_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
            })
            user_content.append({
                "type": "text",
                "text": "(Screenshot attached for reference – please read the game state directly from the image.)",
            })

        user_content.append({"type": "text", "text": user_message})

        # ── Stream from serverless inference chat completions API ────────────
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

        last_error: Exception | None = None
        for index, model_name in enumerate(self._models):
            is_last = index == len(self._models) - 1
            try:
                stream = self._client.chat.completions.create(
                    model=model_name,
                    max_completion_tokens=settings.max_output_tokens,
                    messages=messages,
                    stream=True,
                )
                if model_name != settings.model:
                    logger.warning(
                        "Primary model unavailable; using fallback model '%s'",
                        model_name,
                    )
                for chunk in stream:
                    if not chunk.choices:
                        continue
                    text = chunk.choices[0].delta.content
                    if text:
                        yield text
                return
            except AuthenticationError as exc:
                last_error = exc
                msg = str(exc).lower()
                if "not available for your subscription tier" in msg and not is_last:
                    logger.warning(
                        "Model '%s' unavailable for current tier, trying next fallback",
                        model_name,
                    )
                    continue
                raise
            except Exception as exc:
                last_error = exc
                raise

        if last_error is not None:
            raise last_error

    def _build_rag_query(self, user_message: str, game_state: dict | None) -> str:
        """Enrich retrieval query with joker names from game state."""
        parts = [user_message]
        if game_state:
            jokers = [j.get("name", "") for j in game_state.get("jokers", [])]
            parts.extend(jokers)
            shop_items = [i.get("name", "") for i in game_state.get("shop", {}).get("items", [])]
            parts.extend(shop_items)
            if game_state.get("ante") is not None:
                parts.append(f"ante {game_state['ante']}")
            blind = game_state.get("blind", {}) or {}
            if blind.get("name"):
                parts.append(str(blind["name"]))
            resources = game_state.get("resources", {}) or {}
            for key in ("hands", "discards", "money"):
                if resources.get(key) is not None:
                    parts.append(f"{key} {resources[key]}")
        message_lower = user_message.lower()
        mechanic_terms = ("rarity", "order", "position", "xmult", "mult", "synergy", "anti-synergy")
        if any(term in message_lower for term in mechanic_terms):
            parts.extend(["joker rarity", "activation timing", "left to right order", "synergy"])
        return " ".join(p for p in parts if p)

    def _build_model_candidates(self) -> list[str]:
        candidates: list[str] = [settings.model.strip()]
        fallbacks = [
            m.strip()
            for m in settings.model_fallbacks.split(",")
            if m.strip()
        ]
        for model_name in fallbacks:
            if model_name not in candidates:
                candidates.append(model_name)
        return candidates


def _format_context(chunks: list[dict]) -> str:
    if not chunks:
        return ""
    parts = []
    for i, chunk in enumerate(chunks, 1):
        src = chunk["metadata"].get("source", "")
        name = chunk["metadata"].get("name", "")
        header = f"[{name or src}]"
        # Trim to ~400 chars per chunk to stay within token budget
        text = chunk["text"][:400].strip()
        parts.append(f"{header}\n{text}")
    return "\n\n".join(parts)


