# 🏗️ Kiến trúc Hệ thống — VirFriendo (AI Anime Companion)

> **Đề tài:** Nghiên cứu và xây dựng **VirFriendo** — AI Anime Companion: Tích hợp Intent Classification, Emotion Detection, RAG tri thức chuyên sâu và Module tương tác cảm xúc cho hội thoại đa ngữ cảnh.

> **Xem trước:** [01_project_plan.md](01_project_plan.md) để nắm tổng quan tính năng và tech stack.

---

## 0. Tổng quan hệ thống (System Overview)

Hệ thống gồm 3 service chính chạy trên Docker, giao tiếp qua REST/gRPC nội bộ:

```
┌─────────────────────────────────────────────────────────────────────┐
│                     FRONTEND (React + Vite + TS)                    │
│  ┌──────────┐  ┌───────────────┐  ┌──────────┐  ┌──────────────┐  │
│  │ Chat UI  │  │ Avatar Canvas │  │ Game UI  │  │ Mood Chart   │  │
│  │ messages │  │ emotion-driven│  │ chess +  │  │ timeline +   │  │
│  │ + input  │  │ sprite anim   │  │ quiz     │  │ summary      │  │
│  └────┬─────┘  └──────┬────────┘  └────┬─────┘  └──────┬───────┘  │
│       └────────────────┴────────────────┴───────────────┘          │
│                        WebSocket + REST API                         │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│                    API GATEWAY (FastAPI)                             │
│  /auth  /chat  /ws/chat  /game  /mood  /history                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │
│  │ JWT Auth │  │ Session  │  │ Rate     │  │ Request Routing  │   │
│  │          │  │ (Redis)  │  │ Limiter  │  │ → Intent Service │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────────┘   │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│                  INTENT SERVICE (LangGraph Agent Core)               │
│                                                                      │
│  ┌────────────┐  ┌──────────────┐  ┌────────────┐  ┌────────────┐  │
│  │Translation │─▶│ Intent       │─▶│ Emotion    │─▶│ Avatar     │  │
│  │ (VN→EN)    │  │ Classifier   │  │ Detector   │  │ Action Map │  │
│  └────────────┘  └──────┬───────┘  └────────────┘  └────────────┘  │
│                          │                                           │
│        ┌─────────────────┼─────────────────────────┐                │
│        ▼                 ▼                          ▼                │
│  ┌───────────┐  ┌──────────────┐  ┌──────────────────────────────┐ │
│  │chit_chat  │  │comfort_agent │  │ comic_expert (RAG Pipeline)  │ │
│  │guardrail  │  │advice_agent  │  │ embed → retrieve → rerank    │ │
│  │           │  │crisis_agent  │  │          → LLM generate      │ │
│  │           │  │              │  │                               │ │
│  └───────────┘  └──────────────┘  └──────────────────────────────┘ │
│                          │                                           │
│                    ┌─────▼─────┐                                     │
│                    │ Mood      │                                     │
│                    │ Logger    │                                     │
│                    └───────────┘                                     │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│                        GAME SERVICE                                  │
│  ┌──────────────────┐  ┌──────────────────────────────────────┐    │
│  │ Chess Engine      │  │ Anime Quiz Engine                    │    │
│  │ (Stockfish +      │  │ (RAG-powered question generation)   │    │
│  │  python-chess)    │  │                                      │    │
│  └──────────────────┘  └──────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│                         DATA LAYER                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │
│  │PostgreSQL│  │ ChromaDB │  │  Redis   │  │    MLflow        │   │
│  │• users   │  │• manga   │  │• session │  │ • model versions │   │
│  │• messages│  │  vectors │  │• cache   │  │ • experiments    │   │
│  │• mood    │  │• psych   │  │• rate    │  │ • metrics        │   │
│  │• games   │  │  vectors │  │  limit   │  │                  │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 1. Pipeline chi tiết — Dữ liệu & Huấn luyện Model

> Luồng từ thu thập dữ liệu → xử lý → lưu trữ → huấn luyện → đăng ký model

```mermaid
graph LR
    subgraph "🔄 Orchestration"
        AF["☁️ Apache Airflow<br/>─────────────<br/>Điều phối quy trình<br/>thu thập dữ liệu,<br/>xử lý & huấn luyện"]
    end

    subgraph "📥 Thu thập dữ liệu"
        SC["🕷️ Scrapy<br/>─────────────<br/>Crawl dữ liệu<br/>manga/anime<br/>(MyAnimeList,<br/>AniList, Wiki)"]
        NEWS["📰 Web Sources<br/>─────────────<br/>Tâm lý học,<br/>bài viết sức khỏe<br/>tinh thần"]
        SYNTH["🤖 GPT-4o-mini<br/>─────────────<br/>Synthetic data<br/>generation cho<br/>intent & emotion"]
    end

    subgraph "⚙️ Xử lý dữ liệu"
        PY1["🐍 Python Scripts<br/>─────────────<br/>Làm sạch, chuẩn hóa<br/>format dữ liệu"]
        PY2["🐍 Python Scripts<br/>─────────────<br/>Chunking văn bản<br/>+ tạo embeddings<br/>(nomic-embed)"]
    end

    subgraph "💾 Lưu trữ"
        PG["🐘 PostgreSQL<br/>─────────────<br/>Lưu metadata,<br/>chat history,<br/>user data,<br/>mood entries"]
        CHROMA["🔮 ChromaDB<br/>─────────────<br/>Lưu vector<br/>embeddings<br/>(manga + psych)"]
    end

    subgraph "🧪 Huấn luyện"
        HF_INTENT["🤗 RoBERTa/Qwen<br/>─────────────<br/>Fine-tune:<br/>6-class Intent<br/>Classification"]
        HF_EMO["🤗 RoBERTa<br/>─────────────<br/>Fine-tune:<br/>7-class Emotion<br/>Detection"]
    end

    subgraph "📦 Model Registry"
        MLF["📊 MLflow<br/>─────────────<br/>• Model versions<br/>• Experiments<br/>• Metrics/params<br/>• Model staging"]
    end

    AF -.->|"trigger"| SC
    AF -.->|"trigger"| NEWS
    AF -.->|"trigger"| SYNTH
    AF -.->|"trigger"| HF_INTENT

    SC -->|"Raw JSON/CSV"| PY1
    NEWS -->|"Raw articles"| PY1
    SYNTH -->|"JSONL dataset"| HF_INTENT
    SYNTH -->|"JSONL dataset"| HF_EMO
    PY1 -->|"Cleaned data"| PG
    PY1 -->|"Cleaned text"| PY2
    PY2 -->|"Vectors"| CHROMA
    PG -->|"Training data"| HF_INTENT
    HF_INTENT -->|"Model + metrics"| MLF
    HF_EMO -->|"Model + metrics"| MLF
```

---

## 2. Pipeline chi tiết — Backend Application (Request Flow)

> Luồng xử lý từ user message → qua Agent Core → response + emotion + avatar action

```mermaid
graph TB
    subgraph "🌐 API Gateway"
        API["🐍 FastAPI<br/>─────────────<br/>WebSocket /ws/chat<br/>REST POST /chat<br/>JWT Auth check"]
    end

    subgraph "🔤 Translation Layer"
        TRANS["🔤 NLLB-200 / Google API<br/>─────────────<br/>Vietnamese → English<br/>(cho model lõi xử lý)"]
    end

    subgraph "🧠 LangGraph Agent Core"
        LG["🔗 LangGraph Router<br/>─────────────<br/>Stateful workflow<br/>Conditional routing"]
    end

    subgraph "🎯 Classification Layer"
        INTENT["🤖 Intent Classifier<br/>(RoBERTa / Qwen)<br/>─────────────<br/>6 classes:<br/>greeting, comic,<br/>venting, advice,<br/>crisis, ood"]
        EMOTION["😊 Emotion Detector<br/>(RoBERTa / LLM)<br/>─────────────<br/>7 classes:<br/>neutral, happy,<br/>sad, angry,<br/>anxious, surprised,<br/>crisis"]
    end

    subgraph "🎭 Avatar System"
        AVATAR["🎭 Avatar Action Mapper<br/>─────────────<br/>Emotion → Animation:<br/>• sad → comfort pose<br/>• happy → wave/jump<br/>• crisis → serious face<br/>• neutral → typing"]
    end

    subgraph "🤖 Specialized Agents (6)"
        A1["💬 chit_chat_agent<br/>Small talk, greeting"]
        A2["🛡️ guardrail_agent<br/>Out-of-domain reject"]
        A3["📖 comic_expert_agent<br/>RAG → manga/anime"]
        A4["🫂 comfort_agent<br/>Empathy, validation"]
        A5["🧠 advice_agent<br/>CBT + bibliotherapy"]
        A6["🚨 crisis_agent<br/>Emergency hotline"]
    end

    subgraph "📚 RAG Pipeline"
        EMB["📊 Embedding (nomic-embed)<br/>Query → Vector"]
        RET["🔍 Retriever (ChromaDB)<br/>Similarity search"]
        RR["⚖️ Re-ranker (Cohere)<br/>Re-rank top-k"]
    end

    subgraph "🤖 LLM Generation"
        LLM["💬 GPT-4o / Gemini<br/>─────────────<br/>Context + emotion<br/>→ Generate response<br/>(Vietnamese output)"]
    end

    subgraph "📊 Mood Logger"
        MOOD["📈 Mood Logger<br/>─────────────<br/>Save emotion_score<br/>per message to<br/>PostgreSQL"]
    end

    subgraph "💾 Data Stores"
        REDIS["⚡ Redis (Session)"]
        PG2["🐘 PostgreSQL"]
        CHR2["🔮 ChromaDB"]
    end

    API -->|"message"| TRANS
    TRANS -->|"EN text"| LG
    LG --> INTENT
    LG --> EMOTION
    EMOTION --> AVATAR
    EMOTION --> MOOD

    INTENT -->|"greeting/ood"| A1
    INTENT -->|"out_of_domain"| A2
    INTENT -->|"comic"| A3
    INTENT -->|"venting"| A4
    INTENT -->|"advice"| A5
    INTENT -->|"crisis"| A6

    A3 --> EMB
    A5 -->|"bibliotherapy"| EMB
    EMB --> RET --> RR --> LLM

    A1 --> LLM
    A2 --> LLM
    A4 --> LLM
    A6 --> LLM

    RET <-->|"query"| CHR2
    LG <-->|"session"| REDIS
    MOOD -->|"save"| PG2
    LLM -->|"save history"| PG2

    MLF2["📊 MLflow<br/>Load trained models"]
    MLF2 -->|"load"| INTENT
    MLF2 -->|"load"| EMOTION
```

### Response Format

Mỗi response từ backend trả về cho frontend:

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

Frontend sử dụng `avatar_action` để trigger animation cho avatar, `detected_emotion` để hiển thị emotion badge.

---

## 3. Pipeline chi tiết — Containerization & Deployment

> Đóng gói → Triển khai → Networking → User

```mermaid
graph LR
    subgraph "📦 Containerization"
        GW["🐍 API Gateway<br/>(FastAPI)"]
        IS["🧠 Intent Service<br/>(LangGraph + Models)"]
        GS["🎮 Game Service<br/>(Stockfish + Quiz)"]
        FE["⚛️ React Frontend<br/>(Vite build)"]
        
        D1["🐳 Docker"]
        D2["🐳 Docker"]
        D3["🐳 Docker"]
        D4["🐳 Docker"]
    end

    subgraph "🚀 Container Registry"
        ECR["📦 AWS ECR<br/>Docker images"]
    end

    subgraph "☸️ Orchestration"
        K8S["☸️ Kubernetes (EKS)<br/>Container orchestration"]
    end

    subgraph "🔀 Service Mesh & Routing"
        ISTIO["🔷 Istio<br/>Service mesh"]
        ING["🚪 NGINX Ingress<br/>Load balancing"]
    end

    subgraph "🌐 Edge & CDN"
        CF["☁️ CloudFlare<br/>SSL + CDN + DDoS"]
    end

    subgraph "👤 End User"
        USER["🧑 Browser / Mobile"]
    end

    GW --> D1
    IS --> D2
    GS --> D3
    FE --> D4
    D1 -->|"Push"| ECR
    D2 -->|"Push"| ECR
    D3 -->|"Push"| ECR
    D4 -->|"Push"| ECR
    ECR -->|"Pull & deploy"| K8S
    K8S --> ISTIO
    ISTIO --> ING
    ING --> CF
    CF -->|"HTTPS"| USER
```

---

## 4. Pipeline chi tiết — Monitoring & Logging

> Giám sát hệ thống, logs, và hiệu suất model

```mermaid
graph TB
    subgraph "📡 Data Sources"
        APP["🐍 FastAPI Services<br/>/metrics endpoint"]
        MODELS["🤖 ML Models<br/>Inference latency,<br/>accuracy metrics"]
        K8S2["☸️ Kubernetes<br/>Pod CPU/RAM"]
        APPLOG["📝 Application Logs<br/>Request/response"]
    end

    subgraph "📊 Monitoring Stack"
        PROM["🔥 Prometheus<br/>Metrics collection (15s)"]
        GRAF["📉 Grafana<br/>Dashboards:<br/>• API latency<br/>• Request rate<br/>• Emotion distribution<br/>• Game sessions<br/>• Model inference time"]
        ALERT["🚨 Alertmanager<br/>Email / Discord"]
    end

    subgraph "📝 Logging Stack (ELK)"
        LS["🔧 Logstash"]
        ES["🔍 Elasticsearch"]
        KIB["📊 Kibana"]
    end

    subgraph "🧪 ML Monitoring"
        MLFLOW2["📊 MLflow<br/>Training metrics,<br/>model comparison"]
        EVID["📈 Evidently AI<br/>Data drift,<br/>prediction drift"]
    end

    APP --> PROM
    MODELS --> PROM
    K8S2 --> PROM
    PROM --> GRAF
    PROM --> ALERT

    APPLOG --> LS --> ES --> KIB

    MODELS --> EVID
    MODELS --> MLFLOW2
```

---

## 5. Pipeline chi tiết — CI/CD

> Từ code commit → test → build → deploy tự động

```mermaid
graph LR
    subgraph "👨‍💻 Development"
        DEV["💻 Developer<br/>Push to GitHub"]
    end

    subgraph "🔄 GitHub Actions CI/CD"
        TEST["✅ Tests<br/>pytest + ruff + mypy"]
        BUILD["🔨 Docker Build<br/>3 services + frontend"]
        PUSH["📤 Push to ECR"]
        DEPLOY["🚀 kubectl apply<br/>Rolling update"]
    end

    subgraph "☁️ Production"
        PROD["☸️ K8S Cluster<br/>Zero-downtime deploy"]
    end

    DEV -->|"git push"| TEST
    TEST -->|"pass"| BUILD
    BUILD --> PUSH
    PUSH --> DEPLOY
    DEPLOY --> PROD
```

---

## 6. Emotion-Driven Avatar System (Unique Feature)

Đây là tính năng cốt lõi để phân biệt với Character.ai:

```mermaid
graph LR
    subgraph "Input"
        MSG["User Message"]
    end

    subgraph "Detection"
        ED["Emotion Detector<br/>(RoBERTa)"]
    end

    subgraph "Mapping"
        AM["Avatar Action<br/>Mapper"]
    end

    subgraph "Frontend Rendering"
        SPRITE["Sprite Engine<br/>(PixiJS/Spine)"]
    end

    MSG --> ED
    ED -->|"emotion label"| AM
    AM -->|"avatar_action"| SPRITE
```

### Emotion → Avatar Action Mapping Table

| Detected Emotion | Avatar Action Key | Animation Description |
|:-----------------|:------------------|:---------------------|
| `neutral` | `idle_typing` | Ngồi gõ keyboard, thỉnh thoảng nhìn lên |
| `happy` | `excited_wave` | Mắt sáng, vẫy tay, nhảy nhẹ |
| `sad` | `comfort_sit` | Nghiêng đầu, mắt buồn, ngồi cạnh |
| `angry` | `crossed_arms` | Khoanh tay, nhăn mặt nhẹ, tỏ vẻ bực mình cùng user |
| `anxious` | `hold_hand` | Nắm tay (symbolic), biểu cảm lo lắng |
| `surprised` | `shocked_face` | Mắt tròn, miệng O, tay giơ lên |
| `crisis` | `serious_alert` | Biểu cảm nghiêm túc, icon hotline xuất hiện |

### Sprite Sheet Structure

```
frontend/public/sprites/
├── idle/
│   ├── idle_typing_01.png → idle_typing_12.png
│   └── idle_look_around_01.png → idle_look_around_08.png
├── emotions/
│   ├── happy_wave_01.png → happy_wave_10.png
│   ├── sad_comfort_01.png → sad_comfort_08.png
│   ├── angry_arms_01.png → angry_arms_06.png
│   ├── anxious_hold_01.png → anxious_hold_08.png
│   ├── surprised_01.png → surprised_06.png
│   └── crisis_serious_01.png → crisis_serious_04.png
├── game/
│   ├── chess_thinking_01.png → chess_thinking_06.png
│   ├── chess_happy_01.png → chess_happy_04.png
│   └── quiz_excited_01.png → quiz_excited_06.png
└── transitions/
    └── ... (animation transitions between states)
```

---

## 7. Game Integration Architecture

### Chess

```mermaid
graph LR
    USER["User<br/>(click move)"] -->|"POST /game/chess/move"| GW["API Gateway"]
    GW --> GS["Game Service"]
    GS --> SF["Stockfish Engine<br/>(python-chess)"]
    SF -->|"AI move"| GS
    GS -->|"board state +<br/>avatar_action"| GW
    GW -->|"render board +<br/>avatar reaction"| USER
```

Avatar reactions khi chơi Chess:
- User đi hay → `surprised` → "Nước đi đẹp đấy!"
- AI đang nghĩ → `chess_thinking` animation
- AI ăn quân → `happy` → "Hehe, bắt được rồi~"
- AI sắp thua → `anxious` → "Khoan... cậu giỏi thật đấy 😤"

### Anime Quiz

```mermaid
graph LR
    USER["User"] -->|"POST /game/quiz/start"| GW["API Gateway"]
    GW --> GS["Game Service"]
    GS --> RAG["RAG Pipeline<br/>(generate question<br/>from comic knowledge)"]
    RAG -->|"question + options"| GS
    GS -->|"quiz card +<br/>avatar_action"| USER
```

---

## 8. Tech Stack tổng hợp

| Layer | Technology | Vai trò |
|:------|:-----------|:--------|
| **Frontend** | React 18 + Vite + TypeScript | SPA responsive |
| **UI/Animation** | TailwindCSS + Framer Motion | Styling + transitions |
| **Avatar Engine** | PixiJS / Spine | Sprite rendering & animation |
| **State (Client)** | Zustand | Client-side state management |
| **API Gateway** | FastAPI | REST + WebSocket + JWT Auth |
| **Agent Core** | LangGraph | Stateful graph-based agent routing |
| **Intent Model** | RoBERTa / Qwen 2.5 (fine-tuned) | 6-class intent classification |
| **Emotion Model** | RoBERTa (fine-tuned) | 7-class emotion detection |
| **LLM** | GPT-4o / Gemini | Response generation |
| **RAG Embedding** | nomic-embed / all-MiniLM-L6 | Text → vector |
| **RAG Store** | ChromaDB | Vector similarity search |
| **RAG Re-rank** | Cohere Rerank / Cross-encoder | Re-rank results |
| **Translation** | NLLB-200 / Google Translate API | VN ↔ EN |
| **TTS** | VOICEVOX / Edge TTS | Anime voice output (P2) |
| **Chess Engine** | Stockfish + python-chess | Chess AI |
| **Database** | PostgreSQL 16 | Users, chat, mood, games |
| **Cache** | Redis 7 | Session, rate limiting |
| **ML Registry** | MLflow | Model versioning |
| **Data Pipeline** | Apache Airflow + Scrapy | Data collection & processing |
| **Containerization** | Docker + Docker Compose | Service packaging |
| **Registry** | AWS ECR | Docker image storage |
| **Orchestration** | Kubernetes (EKS) | Production deployment |
| **Service Mesh** | Istio | Inter-service traffic |
| **Ingress** | NGINX Ingress | Load balancing |
| **CDN/Edge** | CloudFlare | SSL, CDN, DDoS |
| **Monitoring** | Prometheus + Grafana | Metrics & dashboards |
| **Logging** | ELK Stack | Centralized logging |
| **ML Monitoring** | Evidently AI | Drift detection |
| **CI/CD** | GitHub Actions | Automated pipeline |
| **IaC** | Terraform | Infrastructure provisioning |

---

## 9. Mapping bài toán CS221

| # | Bài toán | Module | Tech | Unique Value |
|:-:|:---------|:-------|:-----|:-------------|
| 1 | **RAG** | RAG Pipeline | nomic-embed + ChromaDB + Re-ranker + LLM | Comic knowledge + Bibliotherapy |
| 2 | **Chọn lọc thông tin** | Retriever + Re-ranker | Cohere Rerank / Cross-encoder | Top-k ranking cho manga data |
| 3 | **Phân tích cảm xúc** | Emotion Detection + Mood Tracking | RoBERTa fine-tuned 7-class | Drive avatar animation |
| 4 | **Quản lý ngữ cảnh** | Context Manager + Relationship | Redis + PostgreSQL + LangGraph State | Adaptive personality |
| 5 | **Nhận định định tuyến** | Intent Classification + Translation | NLLB → RoBERTa 8-class → LangGraph Router | 8 agent routing |
