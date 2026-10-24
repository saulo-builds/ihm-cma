"""Endpoints de alarmes ativos e historico."""
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from auth import eh_admin, get_usuario_atual
from database import get_db
from models.schemas import (
    AlarmeHistoricoResponse,
    AlarmeResponse,
    EquipamentoAlarme,
    EquipamentoAlarmeHistorico,
    NormalizarAlarmeRequest,
)

router = APIRouter(dependencies=[Depends(get_usuario_atual)])

TIPO_COMUNICACAO = "Falha de Comunicacao"

# Fonte unica da regra "equipamento suprimido" para aba Ativos, badge do sino
# e VideoWall -- a vigencia (cancelamento/expiracao) e decidida pela view.
_SUPRIMIDO_SQL = """
    EXISTS (
        SELECT 1 FROM ihm.supressoes_ativas sa
        WHERE sa.equipamento_id = a.equipamento_id
    )
"""

_ALARME_SELECT = f"""
    SELECT
        a.id, a.tipo, a.criticidade, a.titulo, a.descricao,
        a.iniciado_em, a.resolvido_em, a.reconhecido_em,
        e.id AS equipamento_id, e.nome AS equipamento_nome,
        e.dispositivo_id, e.ativo AS equipamento_ativo, l.nome AS localidade_nome,
        {_SUPRIMIDO_SQL} AS suprimido
    FROM ihm.alarmes a
    JOIN ihm.equipamentos e ON e.id = a.equipamento_id
    JOIN ihm.localidades l ON l.id = e.localidade_id
"""

_HISTORICO_SELECT = """
    SELECT
        a.id, a.tipo, a.criticidade, a.titulo, a.descricao,
        a.iniciado_em, a.resolvido_em, a.reconhecido_em,
        ur.nome AS reconhecido_por_nome, urr.nome AS normalizado_por_nome,
        e.id AS equipamento_id, e.nome AS equipamento_nome, l.nome AS localidade_nome
    FROM ihm.alarmes a
    JOIN ihm.equipamentos e ON e.id = a.equipamento_id
    JOIN ihm.localidades l ON l.id = e.localidade_id
    LEFT JOIN ihm.usuarios ur ON ur.id = a.reconhecido_por
    LEFT JOIN ihm.usuarios urr ON urr.id = a.resolvido_por
"""


def _para_response(row) -> AlarmeResponse:
    return AlarmeResponse(
        id=row["id"],
        equipamento=EquipamentoAlarme(
            id=row["equipamento_id"],
            nome=row["equipamento_nome"],
            local=row["localidade_nome"],
            dispositivo_id=row["dispositivo_id"],
            ativo=row["equipamento_ativo"],
        ),
        tipo=row["tipo"],
        criticidade=row["criticidade"],
        titulo=row["titulo"],
        descricao=row["descricao"],
        iniciado_em=row["iniciado_em"],
        reconhecido=row["reconhecido_em"] is not None,
        suprimido=row["suprimido"],
    )


def _para_historico_response(row) -> AlarmeHistoricoResponse:
    return AlarmeHistoricoResponse(
        id=row["id"],
        equipamento=EquipamentoAlarmeHistorico(
            id=row["equipamento_id"], nome=row["equipamento_nome"], local=row["localidade_nome"]
        ),
        tipo=row["tipo"],
        criticidade=row["criticidade"],
        titulo=row["titulo"],
        descricao=row["descricao"],
        iniciado_em=row["iniciado_em"],
        normalizado_em=row["resolvido_em"],
        reconhecido_em=row["reconhecido_em"],
        reconhecido_por_nome=row["reconhecido_por_nome"],
        normalizado_por_nome=row["normalizado_por_nome"],
    )


@router.get("/alarmes", response_model=list[AlarmeResponse])
def listar_alarmes(
    ativos: bool = Query(True),
    suprimidos: Optional[bool] = Query(None),
):
    """suprimidos: True = so suprimidos, False = exclui suprimidos.
    Omitido: exclui suprimidos quando ativos=true (padrao ISA-18.2 para a
    tela de operacao); sem filtro quando ativos=false (historico completo).
    """
    if suprimidos is None and ativos:
        suprimidos = False

    condicoes = []
    if ativos:
        condicoes.append("a.resolvido_em IS NULL")
    if suprimidos is not None:
        condicoes.append(("" if suprimidos else "NOT ") + _SUPRIMIDO_SQL)

    sql = _ALARME_SELECT
    if condicoes:
        sql += " WHERE " + " AND ".join(condicoes)
    sql += " ORDER BY a.iniciado_em DESC"

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            return [_para_response(r) for r in cur.fetchall()]


@router.get("/alarmes/historico", response_model=list[AlarmeHistoricoResponse])
def historico_alarmes(
    data_inicio: Optional[date] = Query(None),
    data_fim: Optional[date] = Query(None),
    criticidade: Optional[str] = Query(None),
    tipo: Optional[str] = Query(None),
    equipamento_id: Optional[int] = Query(None),
    reconhecido: Optional[bool] = Query(None),
):
    fim = data_fim or date.today()
    inicio = data_inicio or (fim - timedelta(days=30))

    condicoes = ["(a.iniciado_em AT TIME ZONE 'America/Sao_Paulo')::date BETWEEN %s AND %s"]
    params: list = [inicio, fim]

    if criticidade:
        condicoes.append("a.criticidade = %s")
        params.append(criticidade)
    if tipo:
        condicoes.append("a.tipo = %s")
        params.append(tipo)
    if equipamento_id is not None:
        condicoes.append("a.equipamento_id = %s")
        params.append(equipamento_id)
    if reconhecido is not None:
        condicoes.append("a.reconhecido_em IS " + ("NOT NULL" if reconhecido else "NULL"))

    sql = _HISTORICO_SELECT + " WHERE " + " AND ".join(condicoes) + " ORDER BY a.iniciado_em DESC"

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return [_para_historico_response(r) for r in cur.fetchall()]


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


@router.patch("/alarmes/{alarme_id}/normalizar", response_model=AlarmeResponse)
def normalizar_alarme(
    alarme_id: int,
    dados: NormalizarAlarmeRequest,
    usuario: dict = Depends(get_usuario_atual),
):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT a.tipo, a.resolvido_em, a.reconhecido_em, e.ativo AS equipamento_ativo
                FROM ihm.alarmes a
                JOIN ihm.equipamentos e ON e.id = a.equipamento_id
                WHERE a.id = %s
                """,
                (alarme_id,),
            )
            alvo = cur.fetchone()
            if alvo is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Alarme nao encontrado"
                )

            if alvo["resolvido_em"] is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT, detail="Alarme já normalizado"
                )

            # Falha de comunicacao e fechada pelo watchdog quando a comunicacao
            # volta. Excecao: alarme orfao de equipamento desativado (o watchdog
            # nao monitora mais) -- so o Administrador pode normalizar.
            if alvo["tipo"] == TIPO_COMUNICACAO:
                if not eh_admin(usuario):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Alarmes de comunicação são normalizados automaticamente pelo watchdog",
                    )
                if alvo["equipamento_ativo"]:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Equipamento ativo — o watchdog normaliza automaticamente quando a comunicação voltar",
                    )

            if alvo["reconhecido_em"] is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Reconheça o alarme antes de normalizar",
                )

            # "resolvido_em IS NULL" no WHERE protege contra dois operadores
            # normalizando ao mesmo tempo: o segundo UPDATE nao afeta linha.
            cur.execute(
                """
                UPDATE ihm.alarmes
                SET resolvido_em = NOW(), resolvido_por = %s, observacao = %s
                WHERE id = %s AND resolvido_em IS NULL
                """,
                (int(usuario["sub"]), dados.observacao, alarme_id),
            )
            if cur.rowcount == 0:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT, detail="Alarme já normalizado"
                )

            cur.execute(_ALARME_SELECT + " WHERE a.id = %s", (alarme_id,))
            alarme = cur.fetchone()

    return _para_response(alarme)
