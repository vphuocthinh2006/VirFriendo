# Pally

AI companion chat app với giao diện Visual Novel. Backend **FastAPI** + **LangGraph**; dữ liệu **PostgreSQL**, **Redis**, **ChromaDB**.

---

## Tech Stack

### Backend
| Layer | Tech |
|-------|------|
| API | FastAPI + Uvicorn |
| Agent | LangGraph (StateGraph) |
| LLM Chat | Claude 3.5 Sonnet (Anthropic) |
| LLM Fallback | Groq Llama 3.3 70B |
| Vision | GPT-4o + GPT-4o-mini (consensus) |
| Voice | Deepgram Nova-3 → Groq Whisper |
| Image Gen | Replicate FLUX Kontext Pro |
| Web Search | Tavily |
| DB | PostgreSQL (asyncpg + SQLAlchemy) |
| Cache | Redis |
| Vector Store | ChromaDB |
| Auth | JWT (HS256) + Google OAuth |
| Migration | Alembic |

### Frontend
| Layer | Tech |
|-------|------|
| Framework | React 18 + Vite + TypeScript |
| Styling | Tailwind CSS (ONME palette) |
| Routing | React Router v6 |
| Realtime | WebSocket (native) |
| Live2D | pixi-live2d-display (Shizuku) |
| Games | Chess, Caro, Tetris, Snake |

### Infrastructure
| Layer | Tech |
|-------|------|
| Container | Docker + Docker Compose |
| Registry | Amazon ECR |
| CI | GitHub Actions |
| Cloud | AWS ECS Fargate |
| Monitoring | CloudWatch (Pally-ML-Monitor) |

---

## ML Pipeline

### Emotion Fusion
- **BERT** (local): Detect emotion từ user message
- **Groq LLM** (API): Detect emotion từ bot reply
- **Fusion**: Weighted vote (Groq 60%, BERT 30%, heuristic 10%) → Live2D avatar expression

### Character Recognition (Vision)
- **ViT Gallery** (local): Cosine similarity search trong 45 trained characters
- **GPT-4o** (API): General vision model, nhận diện bất kỳ nhân vật nào
- **Fusion Score**: ViT dùng làm confirmation signal. GPT-4o luôn ưu tiên khi disagree.
- **Web Search** (Tavily): Enrich kết quả với thông tin từ web

### Monitoring
- **CloudWatch Dashboard**: `Pally-ML-Monitor` — latency, throughput, error rate per model
- **S3 Prediction Logs**: JSONL format cho SageMaker Model Monitor
- **Metrics Namespace**: `Pally/MLInference`

---

## Tài liệu chi tiết

| # | Tài liệu | Mô tả |
|---|----------|-------|
| 01 | [Kiến trúc hệ thống](./docs/01-architecture.md) | Stack, luồng dữ liệu, LLM providers |
| 03 | [Dữ liệu & lưu trữ](./docs/03-data-and-storage.md) | PostgreSQL, Redis, ChromaDB |
| 04 | [API & WebSocket](./docs/04-api-overview.md) | Endpoints, WS protocol |
| 05 | [Pipeline agent](./docs/05-agent-pipeline.md) | LangGraph, intent routing, RAG |

---

## API Endpoints

| Method | Path | Mô tả |
|--------|------|-------|
| WS | `/chat/ws` | Stream chat |
| POST | `/chat` | REST chat |
| POST | `/chat/transcribe` | Voice → text |
| POST | `/chat/analyze-media` | Vision analysis |
| POST | `/chat/imagine` | Text → image |
| POST | `/chat/feedback` | RLHF feedback (👍/👎) |
| GET | `/health` | Health check |

---

## Cấu trúc thư mục

```
├── docs/
├── frontend/          # React + Vite + TypeScript
├── services/
│   ├── core/          # FastAPI — auth, chat, API
│   ├── agent_service/ # LangGraph — agents, RAG, LLM
│   └── ml/            # BERT, ViT, emotion fusion, metrics
├── infra/             # CloudFormation, deploy configs
├── migrations/        # Alembic
├── requirements.txt
├── docker-compose.yml
└── .env.example
```

---

## Environment

Copy `.env.example` → `.env`.

---

## License

MIT
