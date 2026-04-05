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

from openai import APIError, AuthenticationError, OpenAI

from ..config import settings
from ..rag.retriever import RAGRetriever
from .hand_eval import (
    build_hand_eval_note_from_text,
    build_hand_eval_summary_from_text,
    parse_cards_from_text,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert Balatro coach. Balatro is a poker-based roguelike where \
players build joker synergies to score chips × multiplier against escalating blind targets.

Your role:
- Analyse the player's current game state and give clear, specific coaching advice
- Prioritise plays/decisions that maximise the player's chances of beating the blind
- Explain *why* a play is good, referencing relevant joker/card mechanics
- If the game state is ambiguous, ask for clarification on the specific missing info only
- Be concise and direct; advanced players want reasoning, not hand-holding
- Never invent game state details that were not provided
- Never assume a specific boss blind name unless explicitly shown in game_state or user text
- Never suggest skipping a Boss Blind (Boss Blinds must be played)
- For arithmetic/scoring, show assumptions explicitly and prefer deterministic values when provided
- If extracted game_state JSON is present, do not ask the user to retype image contents unless a specific required field is missing

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

Formatting guidelines:
- Use suit symbols when referring to card suits: ♥ Hearts, ♦ Diamonds, ♣ Clubs, ♠ Spades.
- Use ## for major sections and ### for sub-points when the response has multiple distinct parts.
- Use *italic* for assumptions or caveats and **bold** for key values and action items.
"""

LOW_CONFIDENCE_MESSAGE = (
    "I couldn't read your screenshot clearly enough to be confident "
    "about the details. Could you tell me:\n"
    "- What jokers do you currently have?\n"
    "- What hand are you playing / what's in the shop?\n"
    "- Your current score, chips needed, hands/discards remaining?"
)

RULES_GUARDRAILS_NOTE = (
    "**Deterministic Balatro rule guardrails:**\n"
    "- Boss Blinds cannot be skipped.\n"
    "- If user says only 'Ante X boss blind', treat boss identity as unknown unless explicitly provided.\n"
    "- Scoring formula: (base_chips + card_chips) × (base_mult + additive_mult) × xMult_jokers\n"
    "- Face cards J/Q/K count as 10 chips each; Ace counts as 11 chips.\n\n"
    "**Planet card scaling table (base chips × mult, +per level):**\n"
    "- High Card: 5×1, +10c/+1m (Pluto)\n"
    "- Pair: 10×2, +15c/+1m (Mercury)\n"
    "- Two Pair: 20×2, +20c/+1m (Uranus)\n"
    "- Three of a Kind: 30×3, +20c/+2m (Venus)\n"
    "- Straight: 30×4, +30c/+3m (Earth)\n"
    "- Flush: 35×4, +15c/+2m (Jupiter)\n"
    "- Full House: 40×4, +25c/+2m (Saturn)\n"
    "- Four of a Kind: 60×7, +30c/+3m (Mars)\n"
    "- Straight Flush: 100×8, +40c/+4m (Neptune)\n"
    "- Royal Flush: 100×8, +40c/+4m (Planet X)\n"
    "- Five of a Kind: 120×12, +35c/+3m (Eris)\n"
    "- Flush House: 140×14, +40c/+4m (Ceres)\n"
    "- Flush Five: 160×16, +50c/+3m (Black Hole)\n"
    "Formula: chips = base + (level−1) × chips_per_level; mult = base + (level−1) × mult_per_level"
)

IMAGE_UNAVAILABLE_MESSAGE = (
    "I couldn't read the screenshot for this request. Local CV extraction failed, and your current "
    "models do not support direct image input. Please retry after fixing backend CV models, or paste "
    "the key shop/joker details as text."
)


class BalatroCoach:
    def __init__(self, retriever: RAGRetriever):
        base_url = settings.inference_base_url.rstrip("/") + "/"
        self._client = OpenAI(
            api_key=settings.model_access_key,
            base_url=base_url,
            timeout=float(settings.stream_chunk_timeout),
        )
        self._retriever = retriever
        self._models = self._build_model_candidates()
        self._vision_models = self._build_vision_model_allowlist()

    async def stream_response(
        self,
        user_message: str,
        history: list[dict[str, str]] | None = None,
        game_state: dict | None = None,
        additional_game_states: list[dict] | None = None,
        image_bytes_list: list[bytes] | None = None,
        low_confidence: bool = False,
        cv_failure_reason: str | None = None,
        hand_settings: list[dict] | None = None,
    ) -> AsyncIterator[str]:
        """Yield text chunks as they stream from the configured inference model."""
        additional_game_states = additional_game_states or []
        image_bytes_list = image_bytes_list or []

        # ── Low confidence: ask for clarification only when no state at all ─────
        if low_confidence and not game_state:
            yield LOW_CONFIDENCE_MESSAGE
            return
        if image_bytes_list and not game_state and cv_failure_reason and not self._vision_models:
            yield IMAGE_UNAVAILABLE_MESSAGE
            return

        # ── Build retrieval query ─────────────────────────────────────────────
        rag_query = self._build_rag_query(user_message, game_state, additional_game_states)
        context_chunks = self._retriever.retrieve(rag_query, top_k=settings.retrieval_top_k)
        rag_context = _format_context(context_chunks)
        level_overrides = {
            hs["name"]: hs["level"]
            for hs in (hand_settings or [])
            if hs.get("level", 1) > 1
        }
        hand_eval_note = build_hand_eval_note_from_text(user_message, level_overrides=level_overrides)
        hand_eval_summary = build_hand_eval_summary_from_text(user_message, level_overrides=level_overrides)

        if hand_eval_summary:
            yield f"{hand_eval_summary}\n\n"

        # ── Build user turn content ───────────────────────────────────────────
        user_content = self._build_user_content(
            user_message=user_message,
            game_state=game_state,
            additional_game_states=additional_game_states,
            rag_context=rag_context,
            hand_eval_note=hand_eval_note,
            image_bytes_list=image_bytes_list,
            allow_image=False,
            cv_failure_reason=cv_failure_reason,
            hand_settings=hand_settings,
            level_overrides=level_overrides,
            low_confidence=low_confidence,
        )

        history_messages = self._sanitize_history(history or [])
        messages = [{"role": "system", "content": SYSTEM_PROMPT}, *history_messages]
        messages_with_current = [*messages, {"role": "user", "content": user_content}]

        last_error: Exception | None = None
        for index, model_name in enumerate(self._models):
            is_last = index == len(self._models) - 1
            has_text_output = False
            allow_image = (
                bool(image_bytes_list)
                and (low_confidence or not game_state)
                and self._supports_vision(model_name)
            )
            active_messages = messages_with_current
            if allow_image:
                content_with_image = self._build_user_content(
                    user_message=user_message,
                    game_state=game_state,
                    additional_game_states=additional_game_states,
                    rag_context=rag_context,
                    hand_eval_note=hand_eval_note,
                    image_bytes_list=image_bytes_list,
                    allow_image=True,
                    cv_failure_reason=cv_failure_reason,
                    hand_settings=hand_settings,
                    level_overrides=level_overrides,
                    low_confidence=low_confidence,
                )
                active_messages = [*messages, {"role": "user", "content": content_with_image}]
            try:
                streamed_parts: list[str] = []
                stream = self._client.chat.completions.create(
                    model=model_name,
                    max_completion_tokens=settings.max_output_tokens,
                    messages=active_messages,
                    stream=True,
                )
                if model_name != settings.model and index > 0:
                    logger.warning(
                        "Primary model unavailable; using fallback model '%s'",
                        model_name,
                    )
                for chunk in stream:
                    if not chunk.choices:
                        continue
                    text = chunk.choices[0].delta.content
                    if text:
                        has_text_output = True
                        streamed_parts.append(text)
                        yield text
                if not has_text_output:
                    if not is_last:
                        logger.warning(
                            "Model '%s' returned empty stream, trying next fallback",
                            model_name,
                        )
                        continue
                    raise RuntimeError(f"Model '{model_name}' returned empty response")
                correction = self._rule_correction(
                    response_text="".join(streamed_parts),
                    user_message=user_message,
                    game_state=game_state,
                )
                if correction:
                    yield correction
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
            except APIError as exc:
                last_error = exc
                if allow_image and self._looks_like_multimodal_rejection(exc):
                    logger.warning(
                        "Model '%s' rejected image payload, retrying without image",
                        model_name,
                    )
                    retry_stream = self._client.chat.completions.create(
                        model=model_name,
                        max_completion_tokens=settings.max_output_tokens,
                        messages=messages_with_current,
                        stream=True,
                    )
                    retry_parts: list[str] = []
                    for chunk in retry_stream:
                        if not chunk.choices:
                            continue
                        text = chunk.choices[0].delta.content
                        if text:
                            has_text_output = True
                            retry_parts.append(text)
                            yield text
                    if not has_text_output:
                        if not is_last:
                            logger.warning(
                                "Model '%s' retry returned empty stream, trying next fallback",
                                model_name,
                            )
                            continue
                        raise RuntimeError(f"Model '{model_name}' returned empty response")
                    correction = self._rule_correction(
                        response_text="".join(retry_parts),
                        user_message=user_message,
                        game_state=game_state,
                    )
                    if correction:
                        yield correction
                    return
                raise
            except Exception as exc:
                last_error = exc
                raise

        if last_error is not None:
            raise last_error

    def _build_rag_query(
        self,
        user_message: str,
        game_state: dict | None,
        additional_game_states: list[dict],
    ) -> str:
        """Enrich retrieval query with joker names from game state."""
        parts = [user_message]
        if parse_cards_from_text(user_message):
            parts.extend(["poker hands base chips mult table", "balatro hand scoring"])
        for state in [game_state, *additional_game_states]:
            if not state:
                continue
            jokers = [j.get("name", "") for j in state.get("jokers", [])]
            parts.extend(jokers)
            shop_items = [i.get("name", "") for i in state.get("shop", {}).get("items", [])]
            parts.extend(shop_items)
            if state.get("ante") is not None:
                parts.append(f"ante {state['ante']}")
            blind = state.get("blind", {}) or {}
            if blind.get("name"):
                parts.append(str(blind["name"]))
            resources = state.get("resources", {}) or {}
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
        # Public-preview models with known empty-stream issues go last.
        deprioritized = {"minimax-m2.5", "glm-5", "kimi-k2.5"}
        stable_first = [m for m in candidates if m not in deprioritized]
        unstable_tail = [m for m in candidates if m in deprioritized]
        ordered = stable_first + unstable_tail
        if ordered and ordered[0] != settings.model.strip():
            logger.warning(
                "Primary model '%s' deprioritized for reliability; trying '%s' first",
                settings.model.strip(),
                ordered[0],
            )
        return ordered

    def _build_vision_model_allowlist(self) -> set[str]:
        configured = [m.strip() for m in settings.vision_models.split(",") if m.strip()]
        return set(configured)

    def _supports_vision(self, model_name: str) -> bool:
        if not self._vision_models:
            return False
        return model_name in self._vision_models

    def _build_user_content(
        self,
        user_message: str,
        game_state: dict | None,
        additional_game_states: list[dict],
        rag_context: str,
        hand_eval_note: str,
        image_bytes_list: list[bytes],
        allow_image: bool,
        cv_failure_reason: str | None,
        hand_settings: list[dict] | None,
        level_overrides: dict[str, int] | None = None,
        low_confidence: bool = False,
    ) -> list[dict]:
        user_content: list[dict] = []
        user_content.append({"type": "text", "text": f"{RULES_GUARDRAILS_NOTE}\n"})
        if game_state and low_confidence:
            user_content.append({
                "type": "text",
                "text": "*Note: CV confidence is low — some fields may be misread. Ask for clarification only if a specific field is critical to your advice.*\n",
            })
        if game_state:
            state_text = json.dumps(game_state, indent=2)
            user_content.append(
                {
                    "type": "text",
                    "text": f"**Current game state (extracted from screenshot):**\n```json\n{state_text}\n```\n",
                }
            )
        hand_settings_text = _format_hand_settings(hand_settings)
        if hand_settings_text:
            user_content.append({"type": "text", "text": f"{hand_settings_text}\n"})
        if additional_game_states:
            extra_state_text = json.dumps(additional_game_states, indent=2)
            user_content.append(
                {
                    "type": "text",
                    "text": f"**Additional screenshot state(s):**\n```json\n{extra_state_text}\n```\n",
                }
            )
        if rag_context:
            user_content.append({"type": "text", "text": f"**Relevant game knowledge:**\n{rag_context}\n"})
        if hand_eval_note:
            user_content.append({"type": "text", "text": f"{hand_eval_note}\n"})
        if image_bytes_list and allow_image:
            for image_bytes in image_bytes_list:
                b64 = base64.standard_b64encode(image_bytes).decode()
                user_content.append(
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
                )
            user_content.append(
                {
                    "type": "text",
                    "text": "(Screenshot set attached for reference – please read the game state directly from the image set.)",
                }
            )
        elif image_bytes_list and not game_state:
            reason = ""
            if cv_failure_reason:
                reason = f" CV failure: {cv_failure_reason.strip().replace(chr(10), ' ')[:240]}."
            user_content.append(
                {
                    "type": "text",
                    "text": (
                        "(Screenshot uploaded; model image fallback is disabled for this model set."
                        f"{reason} Use extracted state/text only.)"
                    ),
                }
            )
        summary = build_hand_eval_summary_from_text(user_message, level_overrides=level_overrides)
        if summary:
            user_content.append({"type": "text", "text": summary})
        user_content.append({"type": "text", "text": user_message})
        return user_content

    def _sanitize_history(self, history: list[dict[str, str]]) -> list[dict[str, str]]:
        sanitized: list[dict[str, str]] = []
        max_items = max(0, settings.chat_history_max_turns * 2)
        for item in history[-max_items:]:
            role = item.get("role")
            content = item.get("content", "")
            if role not in {"user", "assistant"}:
                continue
            if not isinstance(content, str):
                continue
            text = content.strip()
            if not text:
                continue
            sanitized.append({"role": role, "content": text[:4000]})
        return sanitized

    def _looks_like_multimodal_rejection(self, exc: APIError) -> bool:
        msg = str(exc).lower()
        indicators = ("image_url", "unsupported", "schema", "invalid type", "vision")
        return any(token in msg for token in indicators)

    def _rule_correction(
        self,
        response_text: str,
        user_message: str,
        game_state: dict | None,
    ) -> str:
        lower = response_text.lower()
        user_lower = user_message.lower()
        issues: list[str] = []

        skip_claim_tokens = (
            "can skip boss blind",
            "you can skip boss blind",
            "skip the boss blind",
            "should skip boss blind",
            "boss blind can be skipped",
        )
        if any(token in lower for token in skip_claim_tokens):
            issues.append("- Boss blinds cannot be skipped.")

        blind_name = str((game_state or {}).get("blind", {}).get("name", "")).strip().lower()
        if "the ox" in lower and "the ox" not in user_lower and blind_name != "the ox":
            issues.append("- Do not assume the boss is The Ox unless it is explicitly identified.")

        if not issues:
            return ""

        return "\n\n**Rule correction:**\n" + "\n".join(issues)


def _format_hand_settings(hand_settings: list[dict] | None) -> str:
    """Compact, LLM-readable summary of non-default hand levels."""
    if not hand_settings:
        return ""
    non_default = [
        hs for hs in hand_settings
        if hs.get("level", 1) > 1 or hs.get("times_played", 0) > 0
    ]
    if not non_default:
        return ""
    lines = ["**Hand levels (player-configured — these override sidebar JSON defaults):**"]
    for hs in non_default:
        name = hs.get("name", "?")
        level = hs.get("level", 1)
        chips = hs.get("chips", "?")
        mult = hs.get("mult", "?")
        times_played = hs.get("times_played", 0)
        played_str = f", played {times_played}×" if times_played > 0 else ""
        lines.append(f"- {name}: Lvl {level} → {chips} chips × {mult} mult{played_str}")
    return "\n".join(lines)


def _format_context(chunks: list[dict]) -> str:
    if not chunks:
        return ""
    parts = []
    for i, chunk in enumerate(chunks, 1):
        src = chunk["metadata"].get("source", "")
        name = chunk["metadata"].get("name", "")
        header = f"[{name or src}]"
        # Trim to ~700 chars per chunk to stay within token budget
        text = chunk["text"][:700].strip()
        parts.append(f"{header}\n{text}")
    return "\n\n".join(parts)


