"""Endpoints de gestao de usuarios do sistema."""
from fastapi import APIRouter, Depends, HTTPException, status

from auth import get_usuario_atual, hash_senha
from database import get_db
from models.schemas import (
    AtualizarAtivoRequest,
    AtualizarSenhaRequest,
    AtualizarUsuarioRequest,
    UsuarioResponse,
)

router = APIRouter(dependencies=[Depends(get_usuario_atual)])

_USUARIO_SELECT = """
    SELECT
        u.id, u.nome, u.email, u.perfil_id, p.nome AS perfil_nome,
        u.ativo, u.ultimo_acesso, u.criado_em
    FROM ihm.usuarios u
    JOIN ihm.perfis p ON p.id = u.perfil_id
"""


@router.get("/usuarios", response_model=list[UsuarioResponse])
def listar_usuarios():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(_USUARIO_SELECT + " ORDER BY u.nome")
            return cur.fetchall()


@router.patch("/usuarios/{usuario_id}", response_model=UsuarioResponse)
def atualizar_usuario(usuario_id: int, dados: AtualizarUsuarioRequest):
    campos = []
    valores = []

    if dados.nome is not None:
        campos.append("nome = %s")
        valores.append(dados.nome)
    if dados.email is not None:
        campos.append("email = %s")
        valores.append(dados.email)
    if dados.perfil_id is not None:
        campos.append("perfil_id = %s")
        valores.append(dados.perfil_id)

    with get_db() as conn:
        with conn.cursor() as cur:
            if campos:
                campos.append("atualizado_em = NOW()")
                valores.append(usuario_id)
                cur.execute(
                    f"UPDATE ihm.usuarios SET {', '.join(campos)} WHERE id = %s",
                    valores,
                )
                if cur.rowcount == 0:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Usuario nao encontrado",
                    )

            cur.execute(_USUARIO_SELECT + " WHERE u.id = %s", (usuario_id,))
            usuario = cur.fetchone()

    if usuario is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Usuario nao encontrado"
        )

    return usuario


@router.patch("/usuarios/{usuario_id}/ativo", response_model=UsuarioResponse)
def atualizar_ativo_usuario(usuario_id: int, dados: AtualizarAtivoRequest):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE ihm.usuarios SET ativo = %s, atualizado_em = NOW() WHERE id = %s",
                (dados.ativo, usuario_id),
            )
            if cur.rowcount == 0:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Usuario nao encontrado",
                )

            cur.execute(_USUARIO_SELECT + " WHERE u.id = %s", (usuario_id,))
            usuario = cur.fetchone()

    return usuario


@router.patch("/usuarios/{usuario_id}/senha", response_model=UsuarioResponse)
def atualizar_senha_usuario(usuario_id: int, dados: AtualizarSenhaRequest):
    senha_hash = hash_senha(dados.senha)

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE ihm.usuarios SET senha_hash = %s, atualizado_em = NOW() WHERE id = %s",
                (senha_hash, usuario_id),
            )
            if cur.rowcount == 0:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Usuario nao encontrado",
                )

            cur.execute(_USUARIO_SELECT + " WHERE u.id = %s", (usuario_id,))
            usuario = cur.fetchone()

    return usuario
