# Pally — Tài liệu kỹ thuật

| # | Tài liệu | Mô tả |
|---|----------|-------|
| 01 | [Kiến trúc hệ thống](./01-architecture.md) | Stack, luồng dữ liệu, LLM providers |
| 03 | [Dữ liệu & lưu trữ](./03-data-and-storage.md) | PostgreSQL, Redis, ChromaDB |
| 04 | [API & WebSocket](./04-api-overview.md) | Endpoints, WS protocol |
| 05 | [Pipeline agent](./05-agent-pipeline.md) | LangGraph, intent routing, RAG |

## ML Pipeline

### Emotion Fusion
- **BERT** (local): Detect emotion từ user message (~1.5s on Fargate CPU)
- **Groq LLM** (API): Detect emotion từ bot reply (~500ms)
- **Fusion**: Weighted vote (Groq 60%, BERT 30%, heuristic 10%) → Live2D avatar expression

### Character Recognition (Vision)
- **ViT Gallery** (local): Cosine similarity search trong 45 trained characters
- **GPT-4o** (API): General vision model, nhận diện bất kỳ nhân vật nào
- **Fusion Score**: ViT dùng làm confirmation signal. GPT-4o luôn ưu tiên khi disagree.
- **Web Search** (Tavily): Enrich kết quả với thông tin từ web

### Monitoring
- **CloudWatch Dashboard**: `Pally-ML-Monitor` — latency, throughput, error rate per model
- **S3 Prediction Logs**: `s3://virfriendo-media-ap-southeast-1/ml-predictions/` — JSONL format
- **Metrics Namespace**: `Pally/MLInference` — dimensions: ModelName, ModelType, Status
