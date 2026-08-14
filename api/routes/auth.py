"""Autenticacao — login e emissao de token JWT."""
from fastapi import APIRouter, HTTPException, status

from auth import criar_token, verificar_senha
from database import get_db
from models.schemas import LoginRequest, TokenResponse, UsuarioToken

router = APIRouter(prefix="/auth", tags=["autenticacao"])


@router.post("/login", response_model=TokenResponse)
def login(dados: LoginRequest):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT u.id, u.nome, u.senha_hash, u.ativo, p.nome AS perfil
                FROM ihm.usuarios u
                JOIN ihm.perfis p ON p.id = u.perfil_id
                WHERE u.email = %s
                """,
                (dados.email,),
            )
            usuario = cur.fetchone()

            if usuario is None or not verificar_senha(dados.senha, usuario["senha_hash"]):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="E-mail ou senha invalidos",
                )

            if not usuario["ativo"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="Usuario inativo"
                )

            cur.execute(
                "UPDATE ihm.usuarios SET ultimo_acesso = NOW() WHERE id = %s",
                (usuario["id"],),
            )

    token = criar_token(
        {"sub": str(usuario["id"]), "nome": usuario["nome"], "perfil": usuario["perfil"]}
    )

    return TokenResponse(
        access_token=token,
        usuario=UsuarioToken(nome=usuario["nome"], perfil=usuario["perfil"]),
    )
