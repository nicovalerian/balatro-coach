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
from PIL import Image

from .config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Lazy singletons ───────────────────────────────────────────────────────────

_detector = None
_extractor = None
_retriever = None
_coach = None


def _format_stream_error(exc: Exception) -> str:
    msg = str(exc)
    if "not available for your subscription tier" in msg.lower():
        return (
            "Your current MODEL is not available for this API key tier. "
            "Set a model your key can access in `.env` (for example via `MODEL=...`) and retry."
        )
    return f"Coaching request failed: {msg}"


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
    data = await file.read()
    try:
        image = Image.open(io.BytesIO(data)).convert("RGB")
    except Exception:
        raise HTTPException(400, "Invalid image file")

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
    file: UploadFile | None = File(default=None),
):
    """
    Full coaching pipeline. Returns SSE stream of text chunks.
    Accepts optional screenshot upload alongside the text message.
    """
    image_bytes: bytes | None = None
    game_state: dict | None = None
    low_confidence = False

    if file:
        image_bytes = await file.read()
        try:
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            state = _get_extractor().extract(image)
            game_state = state.to_dict()
            low_confidence = state.low_confidence
        except (FileNotFoundError, RuntimeError) as e:
            logger.warning("CV failed, will use vision fallback: %s", e)
            # No game_state → coach will use raw image as fallback
            game_state = None

    async def event_stream() -> AsyncIterator[str]:
        # First: send game_state so UI can render it
        if game_state:
            yield f"data: {json.dumps({'type': 'state', 'data': game_state})}\n\n"

        # Then: stream LLM response
        async for chunk in _stream_coach(message, game_state, image_bytes, low_confidence):
            payload = json.dumps({"type": "text", "data": chunk})
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
    game_state: dict | None,
    image_bytes: bytes | None,
    low_confidence: bool,
) -> AsyncIterator[str]:
    """Run coach.stream_response in a thread pool (sync inference SDK)."""
    coach = _get_coach()
    loop = asyncio.get_event_loop()
    queue: asyncio.Queue[str | None] = asyncio.Queue()

    def _run():
        import asyncio as _asyncio
        gen = coach.stream_response(
            message,
            game_state=game_state,
            image_bytes=image_bytes,
            low_confidence=low_confidence,
        )
        # coach.stream_response is an async generator – run it synchronously
        new_loop = _asyncio.new_event_loop()
        try:
            async def _collect():
                async for chunk in gen:
                    loop.call_soon_threadsafe(queue.put_nowait, chunk)
                loop.call_soon_threadsafe(queue.put_nowait, None)
            new_loop.run_until_complete(_collect())
        except Exception as exc:
            logger.exception("Coach stream failed")
            loop.call_soon_threadsafe(queue.put_nowait, _format_stream_error(exc))
            loop.call_soon_threadsafe(queue.put_nowait, None)
        finally:
            new_loop.close()

    import concurrent.futures
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    loop.run_in_executor(executor, _run)

    while True:
        chunk = await queue.get()
        if chunk is None:
            break
        yield chunk
