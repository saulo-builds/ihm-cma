"""Endpoints de alarmes ativos e historico."""
from fastapi import APIRouter, Depends, HTTPException, Query, status

from auth import get_usuario_atual
from database import get_db
from models.schemas import AlarmeResponse, EquipamentoAlarme, ResolverAlarmeRequest

router = APIRouter(dependencies=[Depends(get_usuario_atual)])

_ALARME_SELECT = """
    SELECT
        a.id, a.tipo, a.criticidade, a.titulo, a.descricao,
        a.iniciado_em, a.resolvido_em, a.reconhecido_em,
        e.nome AS equipamento_nome, l.nome AS localidade_nome
    FROM ihm.alarmes a
    JOIN ihm.equipamentos e ON e.id = a.equipamento_id
    JOIN ihm.localidades l ON l.id = e.localidade_id
"""


def _para_response(row) -> AlarmeResponse:
    return AlarmeResponse(
        id=row["id"],
        equipamento=EquipamentoAlarme(nome=row["equipamento_nome"], local=row["localidade_nome"]),
        tipo=row["tipo"],
        criticidade=row["criticidade"],
        titulo=row["titulo"],
        descricao=row["descricao"],
        iniciado_em=row["iniciado_em"],
        reconhecido=row["reconhecido_em"] is not None,
    )


@router.get("/alarmes", response_model=list[AlarmeResponse])
def listar_alarmes(ativos: bool = Query(True)):
    sql = _ALARME_SELECT
    if ativos:
        sql += " WHERE a.resolvido_em IS NULL"
    sql += " ORDER BY a.iniciado_em DESC"

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            return [_para_response(r) for r in cur.fetchall()]


@router.patch("/alarmes/{alarme_id}/reconhecer", response_model=AlarmeResponse)
def reconhecer_alarme(alarme_id: int, usuario: dict = Depends(get_usuario_atual)):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE ihm.alarmes
                SET reconhecido_em = NOW(), reconhecido_por = %s
                WHERE id = %s
                """,
                (int(usuario["sub"]), alarme_id),
            )
            if cur.rowcount == 0:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Alarme nao encontrado"
                )

            cur.execute(_ALARME_SELECT + " WHERE a.id = %s", (alarme_id,))
            alarme = cur.fetchone()

    return _para_response(alarme)


@router.patch("/alarmes/{alarme_id}/resolver", response_model=AlarmeResponse)
def resolver_alarme(
    alarme_id: int,
    dados: ResolverAlarmeRequest,
    usuario: dict = Depends(get_usuario_atual),
):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE ihm.alarmes
                SET resolvido_em = NOW(), resolvido_por = %s, observacao = %s
                WHERE id = %s
                """,
                (int(usuario["sub"]), dados.observacao, alarme_id),
            )
            if cur.rowcount == 0:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Alarme nao encontrado"
                )

            cur.execute(_ALARME_SELECT + " WHERE a.id = %s", (alarme_id,))
            alarme = cur.fetchone()

    return _para_response(alarme)
