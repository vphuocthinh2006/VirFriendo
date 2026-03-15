from fastapi import FastAPI

from config import settings
from api.routes import router as agent_router


app = FastAPI(
    title="Agent Service",
    version="0.1.0",
    debug=settings.DEBUG,
)


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": settings.APP_NAME}


app.include_router(agent_router, prefix="/agent", tags=["Agent"])