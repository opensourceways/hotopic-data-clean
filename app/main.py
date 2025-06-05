from fastapi import FastAPI
from config.settings import settings

app = FastAPI(title="数据清洗服务",
              description="提供数据清洗处理API",
              version="1.0.0")


@app.get("/health", tags=["监控"])
async def health_check():
    return {
        "status": "ok",
        "environment": settings.env}
