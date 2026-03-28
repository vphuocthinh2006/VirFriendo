# 📋 Project Plan — VirFriendo (AI Anime Companion)

> **Đề tài:** Nghiên cứu và xây dựng **VirFriendo** — AI Anime Companion: Tích hợp Intent Classification, Emotion Detection, RAG tri thức chuyên sâu và Module tương tác cảm xúc cho hội thoại đa ngữ cảnh.

---

## 1. Tầm nhìn sản phẩm (Product Vision)

Xây dựng một **AI Anime Companion** — không phải chatbot thông thường, mà là một người bạn đồng hành ảo dưới dạng nhân vật anime, có khả năng:

- **Nhận diện cảm xúc** của người dùng và phản ứng bằng avatar animation tương ứng
- **Tư vấn tâm lý nhẹ** (empathy, CBT exercises, crisis alert) kết hợp với anime bibliotherapy
- **Trò chuyện về entertainment** (anime, manga, game, phim) với kiến thức chuyên sâu qua RAG pipeline
- **Chơi mini-game** cùng người dùng (Chess, Anime Quiz)
- **Theo dõi mood** theo thời gian và phát triển mối quan hệ (adaptive personality)

### Thesis Statement

> *"Emotion-driven AI Anime Companion: Kết hợp Multi-task Intent Classification, Emotion Detection, RAG Knowledge Retrieval và Adaptive Avatar Interaction cho Mental Wellness"*

---

## 2. Tính năng chính (Feature Breakdown)

### 2.1. Core Chat System
| Feature | Mô tả | Priority |
|---------|--------|----------|
| User Auth | Login/Logout, JWT-based, user profile | P0 |
| Chat Interface | Conversation UI với message history | P0 |
| Chat History | Lưu trữ conversation theo user_id, PostgreSQL | P0 |
| WebSocket | Real-time messaging, streaming response | P0 |
| Session Management | Redis-based session cache | P0 |

### 2.2. Intent Classification & Routing (LangGraph)
| Feature | Mô tả | Priority |
|---------|--------|----------|
| Intent Classifier | RoBERTa/Qwen fine-tuned, 8 intent classes | P0 |
| Emotion Detector | Detect emotion từ message (sad, excited, angry, anxious, neutral, crisis) | P0 |
| LangGraph Router | Conditional routing tới specialized agents | P0 |
| Translation Layer | Vietnamese ↔ English (NLLB-200 / API) | P1 |

### 2.3. Specialized Agents
| Agent | Intent Trigger | Chức năng | Priority |
|-------|---------------|-----------|----------|
| `chit_chat_agent` | greeting_chitchat | Trò chuyện thân thiện, small talk | P0 |
| `comfort_agent` | psychology_venting | Empathy, validation cảm xúc, KHÔNG khuyên bảo | P0 |
| `advice_agent` | psychology_advice_seeking | CBT exercises, coping strategies + anime bibliotherapy | P0 |
| `crisis_agent` | crisis_alert | Emergency hotline, can ngăn khẩn cấp | P0 |
| `entertainment_expert_agent` | entertainment_knowledge | RAG truy xuất kiến thức entertainment (anime, manga, game, phim) | P0 |
| `guardrail_agent` | out_of_domain | Từ chối lịch sự, redirect về domain | P0 |

### 2.4. Emotion-Aware Avatar System
| Feature | Mô tả | Priority |
|---------|--------|----------|
| Avatar Display | Anime character hiển thị giữa màn hình | P0 |
| Emotion-Driven Animation | Avatar phản ứng theo detected emotion | P0 |
| Idle Animations | Gõ keyboard, nhìn quanh, chờ đợi | P1 |
| Action Sprites | Bộ sprite/animation cho mỗi emotion state | P1 |

**Emotion → Avatar Mapping:**

| Detected Emotion | Avatar Action | Trigger Example |
|-----------------|---------------|-----------------|
| `neutral` | Gõ keyboard, bình thường | "Hello!" |
| `happy/excited` | Mắt sáng, vẫy tay, nhảy nhẹ | "One Piece chapter mới!" |
| `sad` | Nghiêng đầu, mắt buồn, ngồi cạnh | "Hôm nay mệt quá..." |
| `angry` | Khoanh tay, nhăn mặt nhẹ | "Ghét thằng bạn quá" |
| `anxious` | Nắm tay (symbolic), lo lắng | "Mai thi rồi sợ quá" |
| `surprised` | Mắt tròn, miệng O | "Không ngờ luôn!" |
| `crisis` | Biểu cảm nghiêm túc, hiện hotline | "Không muốn sống nữa" |

### 2.5. Mini-Games
| Game | Mô tả | Priority |
|------|--------|----------|
| Chess | Chơi cờ vua với AI (Stockfish engine), avatar react theo thế cờ | P1 |
| Anime Quiz | AI hỏi đố kiến thức anime/manga, dùng RAG data | P1 |

### 2.6. Wellness & Relationship Features
| Feature | Mô tả | Priority |
|---------|--------|----------|
| Mood Tracking | Lưu emotion_score mỗi conversation, hiển thị timeline | P1 |
| Entertainment Bibliotherapy | Recommend anime/manga/game/phim phù hợp tâm trạng | P1 |
| Adaptive Personality | Avatar thay đổi cách xưng hô theo relationship_level | P2 |
| TTS (Text-to-Speech) | Avatar "nói" response bằng giọng anime | P2 |

---

## 3. Kiến trúc tổng quan

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React + Vite + TS)             │
│  ┌──────────┐  ┌──────────────┐  ┌───────────┐  ┌───────────┐  │
│  │ Chat UI  │  │ Avatar View  │  │ Game UI   │  │ Mood Chart│  │
│  │ (messages│  │ (sprite      │  │ (chess    │  │ (emotion  │  │
│  │  + input)│  │  animations) │  │  + quiz)  │  │  timeline)│  │
│  └────┬─────┘  └──────┬───────┘  └─────┬─────┘  └─────┬─────┘  │
│       └────────────────┴────────────────┴──────────────┘        │
│                            WebSocket + REST API                  │
└────────────────────────────────┬────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────┐
│                     API GATEWAY (FastAPI)                        │
│  /chat  /auth  /games  /mood  /history                          │
└────────────────────────────────┬────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────┐
│                    AGENT CORE (LangGraph)                        │
│                                                                  │
│  ┌────────────┐    ┌──────────────┐    ┌─────────────────────┐  │
│  │ Translation│───▶│Intent        │───▶│  Conditional Router  │  │
│  │ (VN→EN)   │    │Classifier    │    │                      │  │
│  └────────────┘    └──────────────┘    └──┬──┬──┬──┬──┬──┬───┘  │
│                                           │  │  │  │  │  │      │
│  ┌────────────┐  ┌──────┐  ┌──────┐  ┌───┴──┴──┴──┴──┴──┴───┐  │
│  │Emotion     │  │Mood  │  │Avatar│  │  Specialized Agents   │  │
│  │Detector    │  │Logger│  │Action│  │  (8 agents)           │  │
│  │            │  │      │  │Mapper│  │                       │  │
│  └────────────┘  └──────┘  └──────┘  └───────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────┐
│                       DATA LAYER                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────────┐  │
│  │PostgreSQL│  │ ChromaDB │  │  Redis   │  │ Stockfish API  │  │
│  │(users,   │  │(RAG      │  │(session, │  │ (chess engine) │  │
│  │ history, │  │ vectors) │  │ cache)   │  │                │  │
│  │ mood)    │  │          │  │          │  │                │  │
│  └──────────┘  └──────────┘  └──────────┘  └────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Updated Intent Taxonomy (6 Classes)

| # | Intent Label | Domain | Trigger | Target Agent |
|:-:|:-------------|:-------|:--------|:-------------|
| 1 | `greeting_chitchat` | General | Chào hỏi, small talk | `chit_chat_agent` |
| 2 | `out_of_domain` | General | Code, toán, tin tức... | `guardrail_agent` |
| 3 | `entertainment_knowledge` | Entertainment | Hỏi kiến thức entertainment (anime, manga, game, phim) | `entertainment_expert_agent` |
| 4 | `psychology_venting` | Psych | Xả cảm xúc, kể lể | `comfort_agent` |
| 5 | `psychology_advice_seeking` | Psych | Xin lời khuyên, coping tips | `advice_agent` |
| 6 | `crisis_alert` | Critical | Tự tử, tự hại | `crisis_agent` |

---

## 5. Tech Stack

| Layer | Technology | Vai trò |
|:------|:-----------|:--------|
| **Frontend** | React 18 + Vite + TypeScript | SPA, responsive UI |
| **UI Framework** | TailwindCSS + Framer Motion | Styling + animation |
| **Avatar Engine** | PixiJS / Spine / Sprite Sheets | Anime character rendering & animation |
| **State Management** | Zustand | Client-side state |
| **Backend Framework** | FastAPI | REST API + WebSocket |
| **Agent Orchestration** | LangGraph | Stateful graph-based workflow |
| **Intent Classification** | RoBERTa / Qwen 2.5 (fine-tuned) | 6-class intent detection |
| **Emotion Detection** | RoBERTa (fine-tuned) / LLM | 7-level emotion classification |
| **LLM Generation** | GPT-4o / Gemini | Response generation |
| **RAG - Embedding** | nomic-embed / all-MiniLM-L6 | Text → vector |
| **RAG - Vector Store** | ChromaDB | Similarity search |
| **RAG - Re-ranker** | Cohere Rerank / Cross-encoder | Re-rank retrieved docs |
| **Translation** | NLLB-200 / Google Translate API | Vietnamese ↔ English |
| **TTS** | VOICEVOX / Edge TTS | Text-to-speech (anime voice) |
| **Chess Engine** | Stockfish (python-chess) | Chess AI opponent |
| **Database** | PostgreSQL 16 | Users, chat history, mood data |
| **Cache** | Redis 7 | Session, rate limiting |
| **ML Registry** | MLflow | Model versioning, experiment tracking |
| **Data Pipeline** | Apache Airflow | Orchestrate crawl + training |
| **Web Scraping** | Scrapy | Crawl anime/manga data |
| **Containerization** | Docker + Docker Compose | Dev & prod packaging |
| **Container Registry** | AWS ECR | Docker image storage |
| **Orchestration** | Kubernetes (EKS) | Production deployment |
| **Service Mesh** | Istio | Traffic management |
| **Ingress** | NGINX Ingress Controller | Load balancing |
| **CDN/Edge** | CloudFlare | SSL, CDN, DDoS protection |
| **Monitoring** | Prometheus + Grafana | System metrics & dashboards |
| **Logging** | ELK Stack (Logstash, Elasticsearch, Kibana) | Centralized logging |
| **ML Monitoring** | Evidently AI | Data/model drift detection |
| **CI/CD** | GitHub Actions | Automated test, build, deploy |
| **IaC** | Terraform | Infrastructure as Code |

---

## 6. Cấu trúc thư mục (Updated)

```
project-root/
│
├── frontend/                          # React + Vite + TypeScript
│   ├── public/
│   │   └── sprites/                   # Avatar sprite sheets & animations
│   ├── src/
│   │   ├── components/
│   │   │   ├── chat/                  # ChatBubble, MessageList, InputBar
│   │   │   ├── avatar/               # AvatarCanvas, EmotionSprite, IdleAnimation
│   │   │   ├── game/                 # ChessBoard, QuizCard
│   │   │   ├── mood/                 # MoodTimeline, EmotionBadge
│   │   │   └── auth/                 # LoginForm, RegisterForm
│   │   ├── pages/                    # Landing, Chat, History, Profile, Game
│   │   ├── hooks/                    # useChat, useWebSocket, useAvatar, useMood
│   │   ├── services/                 # API clients (REST + WebSocket)
│   │   ├── store/                    # Zustand stores (chat, auth, game, mood)
│   │   ├── types/                    # TypeScript interfaces
│   │   └── styles/                   # TailwindCSS theme & global styles
│   ├── package.json
│   └── vite.config.ts
│
├── services/
│   ├── api-gateway/                   # FastAPI main entry point
│   │   ├── app/
│   │   │   ├── api/
│   │   │   │   ├── main.py           # FastAPI app, CORS, lifespan
│   │   │   │   ├── chat.py           # POST /chat, WebSocket /ws/chat
│   │   │   │   ├── auth.py           # POST /auth/login, /auth/register
│   │   │   │   ├── game.py           # POST /game/chess, /game/quiz
│   │   │   │   ├── mood.py           # GET /mood/timeline, POST /mood/log
│   │   │   │   └── history.py        # GET /history/conversations
│   │   │   ├── core/
│   │   │   │   ├── config.py         # Settings, env vars
│   │   │   │   ├── security.py       # JWT, password hashing
│   │   │   │   └── database.py       # SQLAlchemy / asyncpg setup
│   │   │   └── models/
│   │   │       ├── user.py           # User ORM model
│   │   │       ├── conversation.py   # Conversation + Message models
│   │   │       └── mood.py           # MoodEntry model
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   ├── agent-service/                  # LangGraph Agent Core
│   │   ├── app/
│   │   │   ├── core/
│   │   │   │   ├── state.py          # AgentState with emotion, mood, relationship
│   │   │   │   └── graph.py          # LangGraph workflow (8 agents)
│   │   │   ├── services/
│   │   │   │   ├── intent_router.py  # Intent classification + routing
│   │   │   │   ├── emotion_detector.py # Emotion detection from message
│   │   │   │   ├── avatar_mapper.py  # Emotion → avatar action mapping
│   │   │   │   └── agents/
│   │   │   │       ├── chit_chat.py
│   │   │   │       ├── comfort.py
│   │   │   │       ├── advice.py
│   │   │   │       ├── crisis.py
│   │   │   │       ├── entertainment_expert.py
│   │   │   │       ├── guardrail.py
│   │   │   │       ├── game.py
│   │   │   │       └── roleplay.py
│   │   │   └── rag/
│   │   │       ├── embedder.py       # Text → vector embedding
│   │   │       ├── retriever.py      # ChromaDB similarity search
│   │   │       └── reranker.py       # Cohere/Cross-encoder rerank
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   └── game-service/                  # Game Engine Service
│       ├── app/
│       │   ├── chess_engine.py       # Stockfish wrapper
│       │   ├── quiz_engine.py        # Anime quiz generator from RAG
│       │   └── main.py              # FastAPI game endpoints
│       ├── Dockerfile
│       └── requirements.txt
│
├── ml/                                # ML Training & Pipelines
│   ├── configs/
│   │   ├── intent_classifier.yaml    # Training config for intent model
│   │   └── emotion_detector.yaml     # Training config for emotion model
│   ├── pipelines/
│   │   ├── generate_dataset.py       # GPT-4o synthetic data generation
│   │   ├── train_intent.py           # Fine-tune RoBERTa for intent
│   │   └── train_emotion.py          # Fine-tune for emotion detection
│   ├── scripts/
│   │   ├── evaluate_model.py         # Model evaluation & metrics
│   │   └── export_model.py           # Export to ONNX / MLflow
│   └── requirements-training.txt
│
├── data/
│   ├── raw/                           # Raw scraped data
│   ├── processed/                     # Cleaned & chunked data
│   ├── embeddings/                    # Pre-computed vectors
│   ├── models/                        # Exported model artifacts
│   └── datasets/                      # Generated training datasets
│
├── shared/
│   ├── schemas/
│   │   ├── chat.py                   # ChatRequest, ChatResponse Pydantic models
│   │   ├── emotion.py                # EmotionLabel, AvatarAction enums
│   │   ├── game.py                   # ChessMove, QuizQuestion models
│   │   └── user.py                   # UserCreate, UserResponse models
│   └── utils/
│       ├── logger.py                 # Structured logging setup
│       └── constants.py              # Shared constants, intent labels
│
├── notebooks/                         # Jupyter notebooks
│   ├── 01_eda_dataset.ipynb          # Exploratory data analysis
│   ├── 02_model_evaluation.ipynb     # Model performance analysis
│   └── 03_rag_experiment.ipynb       # RAG pipeline experiments
│
├── k8s/                               # Kubernetes manifests
│   ├── api-gateway.yaml
│   ├── agent-service.yaml
│   ├── game-service.yaml
│   ├── postgresql.yaml
│   ├── redis.yaml
│   ├── chromadb.yaml
│   └── ingress.yaml
│
├── terraform/                         # Infrastructure as Code
│   ├── main.tf
│   ├── variables.tf
│   ├── eks.tf
│   └── ecr.tf
│
├── monitoring/                        # Observability configs
│   ├── prometheus/
│   │   └── prometheus.yml
│   ├── grafana/
│   │   └── dashboards/
│   └── elk/
│       └── logstash.conf
│
├── scripts/                           # DevOps & utility scripts
│   ├── setup_dev.sh                  # Local dev environment setup
│   ├── seed_database.py              # Seed initial data
│   └── crawl_anime_data.py           # Scrapy crawl runner
│
├── docs/
│   ├── 01_project_plan.md            # This file
│   ├── 02_system_architecture.md     # Detailed architecture diagrams
│   ├── 03_taxonomy_and_dataset.md    # Intent & emotion taxonomy
│   ├── 04_api_documentation.md       # API endpoints reference
│   └── assets/                       # Images, diagrams
│
├── .github/
│   └── workflows/
│       ├── ci.yml                    # Test + lint on PR
│       └── cd.yml                    # Build + deploy on merge
│
├── docker-compose.yml                 # Local dev orchestration
├── docker-compose.prod.yml            # Production compose
├── Makefile                           # Dev commands
├── .env.example                       # Environment variables template
├── .gitignore
└── README.md
```

---

## 7. Database Schema (PostgreSQL)

```sql
-- Users
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    relationship_level INT DEFAULT 1,
    total_messages INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Conversations
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Messages
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    role VARCHAR(10) NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    detected_intent VARCHAR(50),
    detected_emotion VARCHAR(50),
    avatar_action VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Mood entries
CREATE TABLE mood_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    emotion VARCHAR(50) NOT NULL,
    emotion_score FLOAT,
    source_message_id UUID REFERENCES messages(id),
    recorded_at TIMESTAMPTZ DEFAULT NOW()
);

-- Game sessions
CREATE TABLE game_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    game_type VARCHAR(20) NOT NULL CHECK (game_type IN ('chess', 'quiz')),
    state JSONB,
    result VARCHAR(20),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    ended_at TIMESTAMPTZ
);
```

---

## 8. API Endpoints

### Auth
| Method | Endpoint | Mô tả |
|--------|----------|--------|
| POST | `/auth/register` | Đăng ký user mới |
| POST | `/auth/login` | Đăng nhập, trả JWT |
| POST | `/auth/logout` | Invalidate session |

### Chat
| Method | Endpoint | Mô tả |
|--------|----------|--------|
| POST | `/chat` | Gửi message, nhận response + emotion + avatar action |
| WS | `/ws/chat` | WebSocket real-time chat |
| GET | `/chat/history/{conversation_id}` | Lấy lịch sử chat |
| GET | `/chat/conversations` | Lấy danh sách conversations |

### Mood
| Method | Endpoint | Mô tả |
|--------|----------|--------|
| GET | `/mood/timeline` | Emotion timeline theo tuần/tháng |
| GET | `/mood/summary` | Tổng kết mood gần nhất |

### Game
| Method | Endpoint | Mô tả |
|--------|----------|--------|
| POST | `/game/chess/start` | Bắt đầu game cờ |
| POST | `/game/chess/move` | Đi nước cờ |
| POST | `/game/quiz/start` | Bắt đầu quiz anime |
| POST | `/game/quiz/answer` | Trả lời câu hỏi |

---

## 9. Chat Response Format

```json
{
    "reply": "Ê, hôm nay sao rồi? Mặt cậu trông buồn buồn thế?",
    "detected_intent": "greeting_chitchat",
    "detected_emotion": "neutral",
    "avatar_action": "wave_greeting",
    "mood_score": 0.6,
    "bibliotherapy_suggestion": null,
    "metadata": {
        "relationship_level": 2,
        "response_time_ms": 245
    }
}
```

---

## 10. Milestones & Phân chia công việc

### Phase 1 — Foundation (Tuần 1-3)
- [ ] Setup monorepo, Docker Compose, CI/CD skeleton
- [ ] Database schema migration (PostgreSQL)
- [ ] User auth (register/login/JWT)
- [ ] Basic chat endpoint (FastAPI + LangGraph boilerplate)
- [ ] Frontend scaffold (React + Vite + routing)

### Phase 2 — Core AI (Tuần 4-7)
- [ ] Fine-tune Intent Classifier (RoBERTa, 8-class)
- [ ] Fine-tune Emotion Detector
- [ ] Build RAG pipeline (embedding + ChromaDB + retriever)
- [ ] Implement all 8 specialized agents
- [ ] Connect LLM generation (GPT-4o/Gemini)
- [ ] Translation layer (NLLB-200)

### Phase 3 — Avatar & Frontend (Tuần 8-10)
- [ ] Avatar sprite system (PixiJS/Spine)
- [ ] Emotion → Avatar animation mapping
- [ ] Chat UI with message bubbles
- [ ] Mood tracking dashboard
- [ ] Responsive layout

### Phase 4 — Games & Extras (Tuần 11-12)
- [ ] Chess integration (Stockfish + UI)
- [ ] Anime Quiz (RAG-powered question generation)
- [ ] Anime Bibliotherapy recommendation engine
- [ ] Adaptive personality system
- [ ] TTS integration (optional)

### Phase 5 — Production & Polish (Tuần 13-15)
- [ ] Kubernetes deployment manifests
- [ ] Monitoring setup (Prometheus + Grafana)
- [ ] Load testing & optimization
- [ ] Documentation hoàn chỉnh
- [ ] Demo preparation

---

## 11. Trạng thái triển khai thực tế (2026-03)

Bảng milestone ở **§10** là kế hoạch gốc. Thực tế repo đã vượt một phần Phase 1–2 (auth, chat, LangGraph, RAG, WebSocket, nhiều route `/game`, tests pytest). Chi tiết phần trăm phase, backlog và checklist vận hành: **[04_current_status.md](04_current_status.md)** và **[05_checklist.md](05_checklist.md)**.

| Mục kế hoạch §10 | Ghi chú nhanh |
|------------------|---------------|
| Phase 1 — Foundation | Gần xong; thiếu CI/CD |
| Phase 2 — Core AI | MVP AI xong; Chroma vector RAG “đúng bài” vẫn tùy chọn |
| Phase 3 — Avatar | UI có; animation nâng cao chưa đủ |
| Phase 4 — Games | Chess/caro backend + nhiều mini-game FE; quiz/bibliotherapy đầy đủ theo spec còn mở |
| Phase 5 — Production | Docker Compose dev có; K8s/monitoring/CI chưa |

Cấu trúc thư mục trong **§6** (api-gateway / agent-service tách container) mô tả kiến trúc mục tiêu dài hạn; **triển khai hiện tại** là monolith FastAPI trong `services/core` + package `services/agent_service` trong cùng process.
