"""
FastAPI application entry point.

Endpoints:
  POST /api/analyze   – CV only: parse screenshot → game state JSON
  POST /api/chat      – Full pipeline: CV + RAG + LLM, SSE stream
  GET  /api/health    – Liveness check
"""
from __future__ import annotations

import asyncio
import io
import json
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from openai import APIError, AuthenticationError, RateLimitError
from PIL import Image

from .config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Lazy singletons ───────────────────────────────────────────────────────────

_detector = None
_extractor = None
_retriever = None
_coach = None
MAX_CHAT_IMAGES = 3


def _parse_history(raw_history: str | None) -> list[dict[str, str]]:
    if not raw_history:
        return []
    try:
        payload = json.loads(raw_history)
    except json.JSONDecodeError:
        logger.warning("Invalid history payload: not valid JSON")
        return []
    if not isinstance(payload, list):
        logger.warning("Invalid history payload: expected list")
        return []

    validated: list[dict[str, str]] = []
    max_items = max(0, settings.chat_history_max_turns * 2)
    for item in payload[-max_items:]:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content")
        if role not in {"user", "assistant"}:
            continue
        if not isinstance(content, str):
            continue
        text = content.strip()
        if not text:
            continue
        validated.append({"role": role, "content": text[:4000]})
    return validated


def _format_stream_error(exc: Exception) -> str:
    msg = str(exc)
    if "not available for your subscription tier" in msg.lower():
        return (
            "Your current MODEL is not available for this API key tier. "
            "Set a model your key can access in `.env` (for example via `MODEL=...`) and retry."
        )
    if isinstance(exc, AuthenticationError):
        return (
            "Authentication failed for the configured model/API key. "
            "Please verify MODEL_ACCESS_KEY and MODEL in `.env`."
        )
    if isinstance(exc, RateLimitError):
        return "The model provider rate-limited this request. Please retry in a moment."
    if isinstance(exc, APIError):
        return "Model provider returned an API error. Please retry shortly."
    return f"Coaching request failed: {msg}"


async def _read_image_uploads(
    uploads: list[UploadFile] | None,
    *,
    max_files: int,
) -> list[dict[str, object]]:
    items = [upload for upload in (uploads or []) if upload is not None]
    if len(items) > max_files:
        raise HTTPException(400, f"Up to {max_files} screenshots are allowed per request.")

    parsed: list[dict[str, object]] = []
    for upload in items:
        if upload.content_type and not upload.content_type.startswith("image/"):
            raise HTTPException(400, "Only image uploads are supported.")

        data = await upload.read()
        if not data:
            raise HTTPException(400, "Uploaded image was empty.")

        try:
            image = Image.open(io.BytesIO(data)).convert("RGB")
        except Exception as exc:
            raise HTTPException(400, f"Invalid image file: {upload.filename or 'upload'}") from exc

        parsed.append({"bytes": data, "image": image, "filename": upload.filename or "upload"})

    return parsed


def _pick_primary_state(states: list[dict]) -> tuple[dict | None, list[dict]]:
    if not states:
        return None, []

    def confidence_value(item: dict) -> float:
        confidence = item.get("confidence")
        if isinstance(confidence, (int, float)):
            return float(confidence)
        return 0.0

    best_index = max(range(len(states)), key=lambda index: confidence_value(states[index]))
    primary = states[best_index]
    remaining = [state for index, state in enumerate(states) if index != best_index]
    return primary, remaining


def _build_hand_settings() -> list[dict[str, int | str]]:
    from .llm.hand_eval import HAND_BASE, HAND_PRIORITY, compute_hand_stats

    ordered_names = sorted(
        [name for name in HAND_BASE.keys() if name != "Royal Flush"],
        key=lambda name: HAND_PRIORITY[name],
        reverse=True,
    )
    return [
        {
            "name": name,
            "level": 1,
            "times_played": 0,
            "chips": compute_hand_stats(name, 1)[0],
            "mult": compute_hand_stats(name, 1)[1],
        }
        for name in ordered_names
    ]


def _parse_hand_settings(raw: str | None) -> list[dict] | None:
    """Parse and validate a JSON hand_settings form field from the client."""
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Invalid hand_settings payload: not valid JSON")
        return None
    if not isinstance(payload, list):
        return None

    from .llm.hand_eval import HAND_BASE, compute_hand_stats

    validated: list[dict] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        level = item.get("level")
        times_played = item.get("times_played")
        if not isinstance(name, str) or name not in HAND_BASE:
            continue
        if not isinstance(level, int) or level < 1:
            continue
        if not isinstance(times_played, int) or times_played < 0:
            continue
        chips, mult = compute_hand_stats(name, level)
        validated.append({
            "name": name,
            "level": level,
            "times_played": times_played,
            "chips": chips,
            "mult": mult,
        })
    return validated if validated else None


def _build_run_brief(state: dict | None) -> dict[str, list[str]]:
    if not state:
        return {
            "reminders": [
                "Upload a screenshot to refresh this panel.",
                "Ask one tactical question at a time.",
                "Prioritize the next blind before greedier scaling.",
            ],
            "synergy_targets": [
                "Retriggers for played cards",
                "Right-side xMult finishers",
                "Economy jokers that fund rerolls",
            ],
        }

    reminders: list[str] = []
    synergy_targets: list[str] = []

    score = state.get("score", {}) or {}
    blind = state.get("blind", {}) or {}
    current_score = score.get("current")
    blind_target = blind.get("target")
    if isinstance(current_score, int) and isinstance(blind_target, int):
        gap = blind_target - current_score
        if gap > 0:
            reminders.append(f"Need {gap:,} more chips to clear the shown blind.")
        else:
            reminders.append("Current score already covers the shown blind.")

    resources = state.get("resources", {}) or {}
    hands = resources.get("hands")
    discards = resources.get("discards")
    if hands is not None or discards is not None:
        reminders.append(
            f"{hands if hands is not None else '?'} hands and {discards if discards is not None else '?'} discards remain."
        )

    money = resources.get("money")
    if isinstance(money, int):
        if money >= 25:
            reminders.append("Interest cap is live. Spend only if it clearly improves the run.")
        elif money >= 20:
            reminders.append("One clean shop can push you to max interest.")
        else:
            reminders.append("Economy is still fragile. Avoid rerolls unless the blind demands it.")

    joker_names = [
        (joker.get("name") or "").strip()
        for joker in state.get("jokers", [])
        if isinstance(joker, dict)
    ]
    joker_names = [name for name in joker_names if name]
    joker_text = " ".join(name.lower() for name in joker_names)

    if joker_names:
        reminders.append(f"Current jokers: {', '.join(joker_names[:4])}.")

    if any(token in joker_text for token in ("blueprint", "brainstorm", "mime", "baron")):
        synergy_targets.append("Look for the strongest scorer you can copy or retrigger.")
    if any(token in joker_text for token in ("sock", "buskin", "photograph", "scary face", "smiley")):
        synergy_targets.append("Face-card payoff is live. Retriggers and face support go up in value.")
    if any(token in joker_text for token in ("arrowhead", "bloodstone", "onyx", "idol", "ancient")):
        synergy_targets.append("Suit-fixing cards and deck smoothing fit this joker package.")
    if any(token in joker_text for token in ("fibonacci", "hack", "wee", "walkie", "odd todd", "even steven")):
        synergy_targets.append("Rank-focused support and retriggers fit the current shell.")
    if any(token in joker_text for token in ("bull", "bootstraps", "rocket", "cloud 9", "delayed gratification")):
        synergy_targets.append("Economy scaling matters here. Prioritize money-preserving lines.")

    hand = state.get("hand", []) or []
    suits = [card.get("suit") for card in hand if isinstance(card, dict)]
    if len(suits) >= 4 and len(set(suits)) <= 2:
        synergy_targets.append("Your hand already leans toward suit concentration. Flush support is more live.")

    defaults = [
        "Retriggers for scored cards",
        "Right-side xMult finishers",
        "Economy jokers that fund better shops",
    ]
    for item in defaults:
        if item not in synergy_targets:
            synergy_targets.append(item)

    return {
        "reminders": reminders[:4],
        "synergy_targets": synergy_targets[:3],
    }


def _decorate_game_state(state: dict | None) -> dict | None:
    if not state:
        return None

    decorated = dict(state)
    decorated["sidebar"] = {
        **_build_run_brief(state),
        "hand_settings": _build_hand_settings(),
    }
    return decorated


def _get_detector():
    global _detector
    if _detector is None:
        from .cv.detector import BalatroDetector
        _detector = BalatroDetector(
            settings.entities_model_path,
            settings.ui_model_path,
            conf_threshold=0.25,
        )
    return _detector


def _get_extractor():
    global _extractor
    if _extractor is None:
        from .cv.extractor import StateExtractor
        _extractor = StateExtractor(
            _get_detector(),
            conf_threshold=settings.cv_confidence_threshold,
        )
    return _extractor


def _get_retriever():
    global _retriever
    if _retriever is None:
        from .rag.retriever import RAGRetriever
        _retriever = RAGRetriever(
            persist_dir=settings.chroma_persist_dir,
            embed_model=settings.embed_model,
        )
    return _retriever


def _get_coach():
    global _coach
    if _coach is None:
        from .llm.coach import BalatroCoach
        _coach = BalatroCoach(_get_retriever())
    return _coach


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm up retriever on startup (loads sentence-transformers model)
    logger.info("Loading RAG retriever...")
    _get_retriever()
    logger.info("Ready.")
    yield


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(title="Balatro Coach API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {"status": "ok", "model": settings.model}


@app.post("/api/analyze")
async def analyze_screenshot(file: UploadFile = File(...)):
    """CV only: returns game state JSON for debugging / display."""
    uploads = await _read_image_uploads([file], max_files=1)
    image = uploads[0]["image"]

    try:
        state = _get_extractor().extract(image)
        return state.to_dict()
    except FileNotFoundError as e:
        raise HTTPException(503, f"CV models not loaded: {e}")
    except RuntimeError as e:
        raise HTTPException(503, str(e))


@app.post("/api/chat")
async def chat(
    message: str = Form(...),
    history: str | None = Form(default=None),
    files: list[UploadFile] | None = File(default=None),
    hand_settings: str | None = Form(default=None),
):
    """
    Full coaching pipeline. Returns SSE stream of text chunks.
    Accepts optional screenshot upload alongside the text message.
    """
    image_bytes_list: list[bytes] = []
    game_state: dict | None = None
    additional_game_states: list[dict] = []
    low_confidence = False
    cv_failure_reason: str | None = None
    chat_history = _parse_history(history)
    parsed_hand_settings = _parse_hand_settings(hand_settings)

    uploads = await _read_image_uploads(files, max_files=MAX_CHAT_IMAGES)
    image_bytes_list = [item["bytes"] for item in uploads]

    if uploads:
        extracted_states: list[dict] = []
        cv_errors: list[str] = []
        for item in uploads:
            try:
                state = _get_extractor().extract(item["image"])
                extracted_states.append(state.to_dict())
            except Exception as exc:
                logger.warning("CV failed for %s, will keep upload for vision fallback: %s", item["filename"], exc)
                cv_errors.append(f"{item['filename']}: {exc}")

        game_state, additional_game_states = _pick_primary_state(extracted_states)
        game_state = _decorate_game_state(game_state)
        additional_game_states = [
            decorated
            for decorated in (_decorate_game_state(state) for state in additional_game_states)
            if decorated is not None
        ]
        low_confidence = bool(game_state and game_state.get("low_confidence"))
        if not game_state and cv_errors:
            cv_failure_reason = " | ".join(cv_errors[:3])

    async def event_stream() -> AsyncIterator[str]:
        # First: send game_state so UI can render it
        if game_state:
            yield f"data: {json.dumps({'type': 'state', 'data': game_state})}\n\n"

        # Then: stream LLM response
        async for event in _stream_coach(
            message,
            chat_history,
            game_state,
            additional_game_states,
            image_bytes_list,
            low_confidence,
            cv_failure_reason,
            parsed_hand_settings,
        ):
            payload = json.dumps(event)
            yield f"data: {payload}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


async def _stream_coach(
    message: str,
    history: list[dict[str, str]],
    game_state: dict | None,
    additional_game_states: list[dict],
    image_bytes_list: list[bytes],
    low_confidence: bool,
    cv_failure_reason: str | None,
    hand_settings: list[dict] | None,
) -> AsyncIterator[dict]:
    """Run coach.stream_response in a thread pool (sync inference SDK)."""
    coach = _get_coach()
    loop = asyncio.get_event_loop()
    queue: asyncio.Queue[dict | None] = asyncio.Queue()

    def _run():
        import asyncio as _asyncio
        gen = coach.stream_response(
            message,
            history=history,
            game_state=game_state,
            additional_game_states=additional_game_states,
            image_bytes_list=image_bytes_list,
            low_confidence=low_confidence,
            cv_failure_reason=cv_failure_reason,
            hand_settings=hand_settings,
        )
        # coach.stream_response is an async generator – run it synchronously
        new_loop = _asyncio.new_event_loop()
        try:
            async def _collect():
                async for chunk in gen:
                    loop.call_soon_threadsafe(queue.put_nowait, {"type": "text", "data": chunk})
                loop.call_soon_threadsafe(queue.put_nowait, None)
            new_loop.run_until_complete(_collect())
        except Exception as exc:
            logger.warning("Coach stream failed: %s", exc)
            loop.call_soon_threadsafe(
                queue.put_nowait,
                {"type": "error", "data": _format_stream_error(exc)},
            )
            loop.call_soon_threadsafe(queue.put_nowait, None)
        finally:
            new_loop.close()

    import concurrent.futures
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    loop.run_in_executor(executor, _run)

    while True:
        event = await queue.get()
        if event is None:
            break
        yield event
