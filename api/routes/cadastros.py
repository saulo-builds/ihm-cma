"""Endpoints de cadastros — MDAs, status, tipos de equipamento, localidades,
linhas e grupos de notificacao."""
import psycopg2
import psycopg2.errors
from fastapi import APIRouter, Depends, HTTPException, status

from auth import get_usuario_atual
from database import get_db
from models.schemas import (
    AdicionarMembroRequest,
    AtualizarGrupoNotificacaoRequest,
    AtualizarMdaRequest,
    AtualizarStatusOperacionalRequest,
    AtualizarTipoEquipamentoRequest,
    CriarGrupoNotificacaoRequest,
    CriarMdaRequest,
    CriarStatusRequest,
    CriarTipoEquipamentoRequest,
    GrupoNotificacaoResponse,
    LinhaResponse,
    LocalidadeResponse,
    MdaResponse,
    MembroGrupoResponse,
    StatusOperacionalResponse,
    TipoEquipamentoResponse,
)

router = APIRouter(dependencies=[Depends(get_usuario_atual)])

# ---------------------------------------------------------------------------
# MDAs
# ---------------------------------------------------------------------------

_MDA_SELECT = """
    SELECT
        m.id, m.nome, m.mac_address::text AS mac_address,
        m.localidade_id, l.nome AS localidade_nome,
        m.ultima_comun, m.ativo, m.criado_em, m.atualizado_em
    FROM ihm.mdas m
    LEFT JOIN ihm.localidades l ON l.id = m.localidade_id
"""


@router.get("/mdas", response_model=list[MdaResponse])
def listar_mdas():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(_MDA_SELECT + " ORDER BY m.nome")
            return cur.fetchall()


@router.post("/mdas", response_model=MdaResponse, status_code=status.HTTP_201_CREATED)
def criar_mda(dados: CriarMdaRequest):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ihm.mdas (nome, mac_address, localidade_id)
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                (dados.nome, dados.mac_address, dados.localidade_id),
            )
            novo_id = cur.fetchone()["id"]

            cur.execute(_MDA_SELECT + " WHERE m.id = %s", (novo_id,))
            mda = cur.fetchone()

    return mda


@router.patch("/mdas/{mda_id}", response_model=MdaResponse)
def atualizar_mda(mda_id: int, dados: AtualizarMdaRequest):
    campos = []
    valores = []

    if dados.nome is not None:
        campos.append("nome = %s")
        valores.append(dados.nome)
    if dados.mac_address is not None:
        campos.append("mac_address = %s")
        valores.append(dados.mac_address)
    if dados.localidade_id is not None:
        campos.append("localidade_id = %s")
        valores.append(dados.localidade_id)
    if dados.ativo is not None:
        campos.append("ativo = %s")
        valores.append(dados.ativo)

    with get_db() as conn:
        with conn.cursor() as cur:
            if campos:
                campos.append("atualizado_em = NOW()")
                valores.append(mda_id)
                cur.execute(
                    f"UPDATE ihm.mdas SET {', '.join(campos)} WHERE id = %s", valores
                )
                if cur.rowcount == 0:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND, detail="MDA nao encontrado"
                    )

            cur.execute(_MDA_SELECT + " WHERE m.id = %s", (mda_id,))
            mda = cur.fetchone()

    if mda is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="MDA nao encontrado")

    return mda


@router.delete("/mdas/{mda_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_mda(mda_id: int):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE ihm.mdas SET ativo = false, atualizado_em = NOW() WHERE id = %s",
                (mda_id,),
            )
            if cur.rowcount == 0:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="MDA nao encontrado"
                )


# ---------------------------------------------------------------------------
# Status operacional
# ---------------------------------------------------------------------------


@router.get("/status", response_model=list[StatusOperacionalResponse])
def listar_status():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM ihm.status_operacional ORDER BY ordem")
            return cur.fetchall()


@router.post("/status", response_model=StatusOperacionalResponse, status_code=status.HTTP_201_CREATED)
def criar_status(dados: CriarStatusRequest):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ihm.status_operacional (nome, cor_hex, ordem)
                VALUES (%s, %s, %s)
                RETURNING *
                """,
                (dados.nome, dados.cor_hex, dados.ordem),
            )
            return cur.fetchone()


@router.patch("/status/{status_id}", response_model=StatusOperacionalResponse)
def atualizar_status(status_id: int, dados: AtualizarStatusOperacionalRequest):
    campos = []
    valores = []

    if dados.nome is not None:
        campos.append("nome = %s")
        valores.append(dados.nome)
    if dados.cor_hex is not None:
        campos.append("cor_hex = %s")
        valores.append(dados.cor_hex)
    if dados.ordem is not None:
        campos.append("ordem = %s")
        valores.append(dados.ordem)
    if dados.ativo is not None:
        campos.append("ativo = %s")
        valores.append(dados.ativo)

    if not campos:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Nenhum campo para atualizar"
        )

    valores.append(status_id)

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE ihm.status_operacional SET {', '.join(campos)} WHERE id = %s RETURNING *",
                valores,
            )
            status_atualizado = cur.fetchone()

    if status_atualizado is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Status nao encontrado"
        )

    return status_atualizado


@router.delete("/status/{status_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_status(status_id: int):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE ihm.status_operacional SET ativo = false WHERE id = %s",
                (status_id,),
            )
            if cur.rowcount == 0:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Status nao encontrado"
                )


# ---------------------------------------------------------------------------
# Tipos de equipamento
# ---------------------------------------------------------------------------


@router.get("/tipos-equipamento", response_model=list[TipoEquipamentoResponse])
def listar_tipos_equipamento():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM ihm.tipos_equipamento ORDER BY nome")
            return cur.fetchall()


@router.post(
    "/tipos-equipamento",
    response_model=TipoEquipamentoResponse,
    status_code=status.HTTP_201_CREATED,
)
def criar_tipo_equipamento(dados: CriarTipoEquipamentoRequest):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ihm.tipos_equipamento (nome, descricao, cor_hex)
                VALUES (%s, %s, %s)
                RETURNING *
                """,
                (dados.nome, dados.descricao, dados.cor_hex),
            )
            return cur.fetchone()


@router.patch("/tipos-equipamento/{tipo_id}", response_model=TipoEquipamentoResponse)
def atualizar_tipo_equipamento(tipo_id: int, dados: AtualizarTipoEquipamentoRequest):
    campos = []
    valores = []

    if dados.nome is not None:
        campos.append("nome = %s")
        valores.append(dados.nome)
    if dados.descricao is not None:
        campos.append("descricao = %s")
        valores.append(dados.descricao)
    if dados.cor_hex is not None:
        campos.append("cor_hex = %s")
        valores.append(dados.cor_hex)
    if dados.ativo is not None:
        campos.append("ativo = %s")
        valores.append(dados.ativo)

    if not campos:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Nenhum campo para atualizar"
        )

    valores.append(tipo_id)

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE ihm.tipos_equipamento SET {', '.join(campos)} WHERE id = %s RETURNING *",
                valores,
            )
            tipo = cur.fetchone()

    if tipo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tipo de equipamento nao encontrado"
        )

    return tipo


@router.delete("/tipos-equipamento/{tipo_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_tipo_equipamento(tipo_id: int):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE ihm.tipos_equipamento SET ativo = false WHERE id = %s", (tipo_id,)
            )
            if cur.rowcount == 0:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Tipo de equipamento nao encontrado",
                )


# ---------------------------------------------------------------------------
# Localidades (somente leitura — sem tela de cadastro)
# ---------------------------------------------------------------------------


@router.get("/localidades", response_model=list[LocalidadeResponse])
def listar_localidades():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    l.id, l.nome, l.tipo, l.linha_id, li.nome AS linha_nome,
                    l.latitude, l.longitude, l.ativo, l.criado_em
                FROM ihm.localidades l
                JOIN ihm.linhas li ON li.id = l.linha_id
                ORDER BY l.nome
                """
            )
            return cur.fetchall()


# ---------------------------------------------------------------------------
# Linhas (somente leitura)
# ---------------------------------------------------------------------------


@router.get("/linhas", response_model=list[LinhaResponse])
def listar_linhas():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM ihm.linhas ORDER BY nome")
            return cur.fetchall()


# ---------------------------------------------------------------------------
# Grupos de notificacao
# ---------------------------------------------------------------------------

_GRUPO_SELECT = """
    SELECT
        g.id, g.nome, g.ativo, g.criado_em,
        COUNT(mn.usuario_id) AS total_membros
    FROM ihm.grupos_notificacao g
    LEFT JOIN ihm.membros_notificacao mn ON mn.grupo_id = g.id
"""
_GRUPO_GROUP_BY = " GROUP BY g.id, g.nome, g.ativo, g.criado_em"


@router.get("/grupos-notificacao", response_model=list[GrupoNotificacaoResponse])
def listar_grupos_notificacao():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(_GRUPO_SELECT + _GRUPO_GROUP_BY + " ORDER BY g.criado_em")
            return cur.fetchall()


@router.post(
    "/grupos-notificacao",
    response_model=GrupoNotificacaoResponse,
    status_code=status.HTTP_201_CREATED,
)
def criar_grupo_notificacao(dados: CriarGrupoNotificacaoRequest):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO ihm.grupos_notificacao (nome) VALUES (%s) RETURNING id",
                (dados.nome,),
            )
            novo_id = cur.fetchone()["id"]

            cur.execute(_GRUPO_SELECT + " WHERE g.id = %s" + _GRUPO_GROUP_BY, (novo_id,))
            grupo = cur.fetchone()

    return grupo


@router.patch("/grupos-notificacao/{grupo_id}", response_model=GrupoNotificacaoResponse)
def atualizar_grupo_notificacao(grupo_id: int, dados: AtualizarGrupoNotificacaoRequest):
    campos = []
    valores = []

    if dados.nome is not None:
        campos.append("nome = %s")
        valores.append(dados.nome)
    if dados.ativo is not None:
        campos.append("ativo = %s")
        valores.append(dados.ativo)

    with get_db() as conn:
        with conn.cursor() as cur:
            if campos:
                valores.append(grupo_id)
                cur.execute(
                    f"UPDATE ihm.grupos_notificacao SET {', '.join(campos)} WHERE id = %s",
                    valores,
                )
                if cur.rowcount == 0:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Grupo de notificacao nao encontrado",
                    )

            cur.execute(
                _GRUPO_SELECT + " WHERE g.id = %s" + _GRUPO_GROUP_BY,
                (grupo_id,),
            )
            grupo = cur.fetchone()

    if grupo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Grupo de notificacao nao encontrado"
        )

    return grupo


@router.delete("/grupos-notificacao/{grupo_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_grupo_notificacao(grupo_id: int):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE ihm.grupos_notificacao SET ativo = false WHERE id = %s", (grupo_id,)
            )
            if cur.rowcount == 0:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Grupo de notificacao nao encontrado",
                )


@router.get("/grupos-notificacao/{grupo_id}/membros", response_model=list[MembroGrupoResponse])
def listar_membros_grupo(grupo_id: int):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM ihm.grupos_notificacao WHERE id = %s", (grupo_id,)
            )
            if cur.fetchone() is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Grupo de notificacao nao encontrado",
                )

            cur.execute(
                """
                SELECT mn.usuario_id, u.nome, u.email, mn.adicionado_em
                FROM ihm.membros_notificacao mn
                JOIN ihm.usuarios u ON u.id = mn.usuario_id
                WHERE mn.grupo_id = %s
                ORDER BY u.nome
                """,
                (grupo_id,),
            )
            return cur.fetchall()


@router.post(
    "/grupos-notificacao/{grupo_id}/membros",
    response_model=MembroGrupoResponse,
    status_code=status.HTTP_201_CREATED,
)
def adicionar_membro_grupo(grupo_id: int, dados: AdicionarMembroRequest):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM ihm.grupos_notificacao WHERE id = %s", (grupo_id,)
            )
            if cur.fetchone() is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Grupo de notificacao nao encontrado",
                )

            try:
                cur.execute(
                    """
                    INSERT INTO ihm.membros_notificacao (grupo_id, usuario_id)
                    VALUES (%s, %s)
                    """,
                    (grupo_id, dados.usuario_id),
                )
            except psycopg2.errors.UniqueViolation:
                conn.rollback()
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Usuario ja e membro deste grupo",
                )

            cur.execute(
                """
                SELECT mn.usuario_id, u.nome, u.email, mn.adicionado_em
                FROM ihm.membros_notificacao mn
                JOIN ihm.usuarios u ON u.id = mn.usuario_id
                WHERE mn.grupo_id = %s AND mn.usuario_id = %s
                """,
                (grupo_id, dados.usuario_id),
            )
            membro = cur.fetchone()

    return membro


@router.delete(
    "/grupos-notificacao/{grupo_id}/membros/{usuario_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remover_membro_grupo(grupo_id: int, usuario_id: int):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM ihm.membros_notificacao WHERE grupo_id = %s AND usuario_id = %s",
                (grupo_id, usuario_id),
            )
            if cur.rowcount == 0:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Membro nao encontrado neste grupo",
                )
