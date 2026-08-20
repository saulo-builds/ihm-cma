"""Ponto de entrada da API IHM CMA — FastAPI + uvicorn na porta 8000."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes import alarmes, ativos, auth, cadastros, telemetria, usuarios

app = FastAPI(title="IHM CMA - API", version="1.0.0")

# CORS — origens do frontend (dev local e VM monitdev)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://192.168.43.200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(ativos.router, prefix="/api")
app.include_router(alarmes.router, prefix="/api")
app.include_router(usuarios.router, prefix="/api")
app.include_router(cadastros.router, prefix="/api")
app.include_router(telemetria.router, prefix="/api/telemetria")


@app.get("/api/health")
def health_check():
    return {"status": "ok", "versao": "1.0.0"}
