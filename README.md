# 🃏 Balatro Coach

AI coaching for [Balatro](https://www.playbalatro.com/): upload a screenshot, extract game state with CV, retrieve strategy context with RAG, and stream actionable advice.

---

## Stack

| Layer | Technology |
|---|---|
| Frontend | React 18 + Vite |
| Backend | FastAPI + uvicorn |
| CV | YOLO11n ONNX + RapidOCR |
| Retrieval | ChromaDB + BM25 (RRF merge) |
| LLM | DigitalOcean Serverless Inference (`/v1/chat/completions`) |
| CI/CD | GitHub Actions |
| Hosting | Docker Compose locally, Render (example cloud deploy) |

---

## Quick start

### 1) Clone and configure

```bash
git clone https://github.com/nicovalerian/balatro-coach.git
cd balatro-coach
cp .env.example .env
# Edit .env and set MODEL_ACCESS_KEY
```

`MODEL_ACCESS_KEY` is your DigitalOcean Gradient AI Platform model access key.

### 2) Backend setup

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/download_models.py
```

### 3) Build RAG index

```bash
# Wiki corpus only
python scripts/build_index.py

# Include generated synergy notes (uses inference credits)
python scripts/build_index.py --synergies
```

### 4) Run with Docker Compose

```bash
cd ..
docker-compose up
```

- Frontend: `http://localhost:5173`
- Backend: `http://localhost:8000`
- Health: `http://localhost:8000/api/health`

### 5) Run without Docker

```bash
# Terminal 1
cd backend
uvicorn app.main:app --reload --port 8000

# Terminal 2
cd frontend
npm install && npm run dev
```

---

## Environment variables

See `.env.example`. Main settings:

- `MODEL_ACCESS_KEY` (required)
- `INFERENCE_BASE_URL` (default: `https://inference.do-ai.run/v1`)
- `MODEL` (default: `openai-gpt-oss-120b`)
- `MODEL_FALLBACKS` (default: `nvidia-nemotron-3-super-120b,llama3.3-70b-instruct,glm-5`)
- `CHAT_HISTORY_MAX_TURNS` (default: `12`, per-session memory window)
- `VISION_MODELS` (default: empty; comma-separated model IDs allowed to receive `image_url` payloads. Leave empty when relying on CV-only screenshot parsing)
- `SYNERGY_MODEL` (default: `anthropic-claude-3.5-haiku`)

---

## RAG sources

| Source | Type | Collection path |
|---|---|---|
| Balatro Wiki | Card-level chunks | `build_index.py` |
| Mechanics corpus (rarity/activation tags) | Card-level chunks | `build_index.py` |
| Curated strategy guides | Guide-level chunks | `build_index.py` |
| Synergy corpus (LLM-generated) | Card-level chunks | `build_index.py --synergies` |

Cached JSONL lives in `backend/data/` and can be rebuilt with `--force`.

---

## Deployment (non-Railway example: Render)

This repo includes a GitHub Actions deploy job that can trigger a Render deploy hook.

1. Create your Render service(s) for backend/frontend.
2. Add backend env vars (`MODEL_ACCESS_KEY`, optional model overrides).
3. Create a deploy hook in Render.
4. Add `RENDER_DEPLOY_HOOK_URL` to GitHub Actions secrets.
5. Push to `main` to run CI and trigger deploy hook.

---

## Project structure

```text
balatro-coach/
├── backend/
│   ├── app/
│   │   ├── cv/
│   │   ├── llm/
│   │   ├── rag/
│   │   ├── config.py
│   │   └── main.py
│   ├── scripts/
│   │   ├── download_models.py
│   │   └── build_index.py
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
├── .github/workflows/ci.yml
├── docker-compose.yml
└── .env.example
```
