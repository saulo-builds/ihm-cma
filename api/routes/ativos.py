"""Endpoints de equipamentos (ativos) e dashboard agregado."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from auth import get_usuario_atual
from database import get_db
from models.schemas import (
    AtualizarEquipamentoRequest,
    AtualizarStatusRequest,
    CategoriaDashboard,
    CriarEquipamentoRequest,
    DashboardResponse,
    EquipamentoResponse,
    HistoricoStatusResponse,
)

router = APIRouter(dependencies=[Depends(get_usuario_atual)])

_EQUIPAMENTO_SELECT = """
    SELECT
        e.id, e.codigo, e.nome, e.descricao,
        e.tipo_id, te.nome AS tipo_nome, te.cor_hex AS tipo_cor,
        e.localidade_id, l.nome AS localidade_nome,
        e.mda_id, e.dispositivo_id,
        e.status_id, so.nome AS status_nome, so.cor_hex AS status_cor,
        e.maturidade, e.horario_op, e.responsavel, e.valor_atual,
        e.ultima_comun, e.ativo, e.criado_em, e.atualizado_em
    FROM ihm.equipamentos e
    JOIN ihm.tipos_equipamento te ON te.id = e.tipo_id
    JOIN ihm.localidades l ON l.id = e.localidade_id
    JOIN ihm.status_operacional so ON so.id = e.status_id
"""


@router.get("/dashboard", response_model=DashboardResponse)
def obter_dashboard():
    """Retorna contagem por status e por categoria (tipo de equipamento)."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT so.nome AS status_nome, COUNT(*) AS total
                FROM ihm.equipamentos e
                JOIN ihm.status_operacional so ON so.id = e.status_id
                WHERE e.ativo = true
                GROUP BY so.nome
                """
            )
            contagem_status = {row["status_nome"]: row["total"] for row in cur.fetchall()}

            cur.execute(
                """
                SELECT te.id AS tipo_id, te.nome AS tipo_nome, te.cor_hex AS tipo_cor,
                       COUNT(e.id) AS total
                FROM ihm.tipos_equipamento te
                LEFT JOIN ihm.equipamentos e ON e.tipo_id = te.id AND e.ativo = true
                GROUP BY te.id, te.nome, te.cor_hex
                ORDER BY te.nome
                """
            )
            categorias = cur.fetchall()

    total = sum(contagem_status.values())

    por_categoria = [
        CategoriaDashboard(
            tipo_id=c["tipo_id"],
            tipo_nome=c["tipo_nome"],
            tipo_cor=c["tipo_cor"],
            total=c["total"],
            percentual=round((c["total"] / total * 100), 1) if total else 0.0,
        )
        for c in categorias
    ]

    return DashboardResponse(
        total=total,
        online=contagem_status.get("Online", 0),
        alerta=contagem_status.get("Alerta", 0),
        critico=contagem_status.get("Critico", 0),
        offline=contagem_status.get("Offline", 0),
        parcial=contagem_status.get("Parcial", 0),
        por_categoria=por_categoria,
    )


@router.get("/equipamentos", response_model=list[EquipamentoResponse])
def listar_equipamentos(
    tipo_id: Optional[int] = Query(None),
    localidade_id: Optional[int] = Query(None),
    status_id: Optional[int] = Query(None),
    maturidade: Optional[str] = Query(None),
    ativo: Optional[bool] = Query(None),
):
    filtros = []
    valores = []

    if tipo_id is not None:
        filtros.append("e.tipo_id = %s")
        valores.append(tipo_id)
    if localidade_id is not None:
        filtros.append("e.localidade_id = %s")
        valores.append(localidade_id)
    if status_id is not None:
        filtros.append("e.status_id = %s")
        valores.append(status_id)
    if maturidade is not None:
        filtros.append("e.maturidade = %s")
        valores.append(maturidade)
    if ativo is not None:
        filtros.append("e.ativo = %s")
        valores.append(ativo)

    sql = _EQUIPAMENTO_SELECT
    if filtros:
        sql += " WHERE " + " AND ".join(filtros)
    sql += " ORDER BY e.nome"

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, valores)
            return cur.fetchall()


@router.get("/equipamentos/{equipamento_id}", response_model=EquipamentoResponse)
def obter_equipamento(equipamento_id: int):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(_EQUIPAMENTO_SELECT + " WHERE e.id = %s", (equipamento_id,))
            equipamento = cur.fetchone()

    if equipamento is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Equipamento nao encontrado"
        )

    return equipamento


@router.post("/equipamentos", response_model=EquipamentoResponse, status_code=status.HTTP_201_CREATED)
def criar_equipamento(dados: CriarEquipamentoRequest):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ihm.equipamentos
                    (codigo, nome, descricao, tipo_id, localidade_id, mda_id,
                     dispositivo_id, status_id, maturidade, horario_op, responsavel)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    dados.codigo,
                    dados.nome,
                    dados.descricao,
                    dados.tipo_id,
                    dados.localidade_id,
                    dados.mda_id,
                    dados.dispositivo_id,
                    dados.status_id,
                    dados.maturidade,
                    dados.horario_op,
                    dados.responsavel,
                ),
            )
            novo_id = cur.fetchone()["id"]

            cur.execute(_EQUIPAMENTO_SELECT + " WHERE e.id = %s", (novo_id,))
            equipamento = cur.fetchone()

    return equipamento


@router.put("/equipamentos/{equipamento_id}", response_model=EquipamentoResponse)
def atualizar_equipamento(equipamento_id: int, dados: AtualizarEquipamentoRequest):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE ihm.equipamentos
                SET codigo = %s, nome = %s, descricao = %s, tipo_id = %s,
                    localidade_id = %s, mda_id = %s, dispositivo_id = %s,
                    status_id = %s, maturidade = %s, horario_op = %s,
                    responsavel = %s, atualizado_em = NOW()
                WHERE id = %s
                """,
                (
                    dados.codigo,
                    dados.nome,
                    dados.descricao,
                    dados.tipo_id,
                    dados.localidade_id,
                    dados.mda_id,
                    dados.dispositivo_id,
                    dados.status_id,
                    dados.maturidade,
                    dados.horario_op,
                    dados.responsavel,
                    equipamento_id,
                ),
            )
            if cur.rowcount == 0:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Equipamento nao encontrado",
                )

            cur.execute(_EQUIPAMENTO_SELECT + " WHERE e.id = %s", (equipamento_id,))
            equipamento = cur.fetchone()

    return equipamento


@router.delete("/equipamentos/{equipamento_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_equipamento(equipamento_id: int):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE ihm.equipamentos SET ativo = false, atualizado_em = NOW() WHERE id = %s",
                (equipamento_id,),
            )
            if cur.rowcount == 0:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Equipamento nao encontrado",
                )


@router.patch("/equipamentos/{equipamento_id}/status", response_model=EquipamentoResponse)
def atualizar_status_equipamento(
    equipamento_id: int,
    dados: AtualizarStatusRequest,
    usuario: dict = Depends(get_usuario_atual),
):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT status_id FROM ihm.equipamentos WHERE id = %s", (equipamento_id,)
            )
            atual = cur.fetchone()

            if atual is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Equipamento nao encontrado",
                )

            cur.execute(
                "UPDATE ihm.equipamentos SET status_id = %s, atualizado_em = NOW() WHERE id = %s",
                (dados.status_id, equipamento_id),
            )

            cur.execute(
                """
                INSERT INTO ihm.historico_status
                    (equipamento_id, status_ant_id, status_novo_id, usuario_id, observacao, origem)
                VALUES (%s, %s, %s, %s, %s, 'manual')
                """,
                (
                    equipamento_id,
                    atual["status_id"],
                    dados.status_id,
                    int(usuario["sub"]),
                    dados.observacao,
                ),
            )

            cur.execute(_EQUIPAMENTO_SELECT + " WHERE e.id = %s", (equipamento_id,))
            equipamento = cur.fetchone()

    return equipamento


@router.get(
    "/equipamentos/{equipamento_id}/historico", response_model=list[HistoricoStatusResponse]
)
def obter_historico_equipamento(equipamento_id: int):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    h.id, h.equipamento_id,
                    h.status_ant_id, sa.nome AS status_ant_nome,
                    h.status_novo_id, sn.nome AS status_novo_nome,
                    h.usuario_id, u.nome AS usuario_nome,
                    h.observacao, h.origem, h.ocorrido_em
                FROM ihm.historico_status h
                LEFT JOIN ihm.status_operacional sa ON sa.id = h.status_ant_id
                JOIN ihm.status_operacional sn ON sn.id = h.status_novo_id
                LEFT JOIN ihm.usuarios u ON u.id = h.usuario_id
                WHERE h.equipamento_id = %s
                ORDER BY h.ocorrido_em DESC
                """,
                (equipamento_id,),
            )
            return cur.fetchall()
