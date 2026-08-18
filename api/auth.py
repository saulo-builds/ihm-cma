"""Hash de senha e geracao/validacao de tokens JWT."""
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from config import settings
import bcrypt

security = HTTPBearer()


def hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verificar_senha(senha: str, senha_hash: str) -> bool:
    return bcrypt.checkpw(senha.encode('utf-8'), senha_hash.encode('utf-8'))


def criar_token(dados: dict) -> str:
    payload = dados.copy()
    expira = datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRE_HOURS)
    payload.update({"exp": expira})
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def verificar_token(token: str) -> dict:
    try:
        return jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalido ou expirado",
        )


def get_usuario_atual(
        credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """Dependency para proteger endpoints - retorna o payload do token (sub, nome, perfil)."""
    payload = verificar_token(credentials.credentials)
    if payload.get("sub") is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalido"
        )
    return payload