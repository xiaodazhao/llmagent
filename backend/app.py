from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes.tbm import register_tbm_routes
from services.tbm_analysis_service import (
    analyze_tbm_data,
    build_risk_profile,
    build_speed_profile,
)


# =========================
# FastAPI 初始化
# =========================
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================
# API 路由注册
# =========================
register_tbm_routes(
    app,
    analyze_tbm_data=analyze_tbm_data,
    build_risk_profile=build_risk_profile,
    build_speed_profile=build_speed_profile,
)


# 启动：
# uvicorn app:app --reload --port 8000