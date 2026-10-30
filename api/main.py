"""Ponto de entrada da API IHM CMA — FastAPI + uvicorn na porta 8000."""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes import alarmes, ativos, auth, cadastros, supressoes, telemetria, usuarios

app = FastAPI(title="IHM CMA - API", version="1.0.0")

# CORS — origens do frontend. CORS_ORIGINS (separadas por virgula, no .env, ja
# carregado por config.py via routes) substitui o padrao (dev local e VM monitdev).
ORIGENS_PADRAO = ["http://localhost:3000", "http://localhost:8080",
                  "http://192.168.43.200", "http://192.168.43.200:8080",
                  "http://10.148.53.111:8080"]
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS or ORIGENS_PADRAO,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(ativos.router, prefix="/api")
app.include_router(alarmes.router, prefix="/api")
app.include_router(usuarios.router, prefix="/api")
app.include_router(cadastros.router, prefix="/api")
app.include_router(supressoes.router, prefix="/api")
app.include_router(telemetria.router, prefix="/api/telemetria")


@app.get("/api/health")
def health_check():
    return {"status": "ok", "versao": "1.0.0"}
