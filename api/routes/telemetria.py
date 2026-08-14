"""Endpoints de telemetria do AMV — le a tabela public.dados_monitoramento."""
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from auth import get_usuario_atual
from database import get_db
from models.schemas import TelemetriaAMVResponse

router = APIRouter(dependencies=[Depends(get_usuario_atual)])


@router.get("/amv/{dispositivo_id}", response_model=TelemetriaAMVResponse)
def obter_ultima_leitura(dispositivo_id: str):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT dispositivo_id, corrente, temperatura, tensao, nivel, bateria, tempo
                FROM public.dados_monitoramento
                WHERE dispositivo_id = %s
                ORDER BY tempo DESC
                LIMIT 1
                """,
                (dispositivo_id,),
            )
            leitura = cur.fetchone()

    if leitura is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nenhuma leitura encontrada para este dispositivo",
        )

    return leitura


@router.get("/amv/{dispositivo_id}/historico", response_model=list[TelemetriaAMVResponse])
def obter_historico_leituras(
    dispositivo_id: str,
    inicio: Optional[datetime] = Query(None),
    fim: Optional[datetime] = Query(None),
):
    if fim is None:
        fim = datetime.now(timezone.utc)
    if inicio is None:
        inicio = fim - timedelta(hours=24)

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT dispositivo_id, corrente, temperatura, tensao, nivel, bateria, tempo
                FROM public.dados_monitoramento
                WHERE dispositivo_id = %s AND tempo BETWEEN %s AND %s
                ORDER BY tempo ASC
                """,
                (dispositivo_id, inicio, fim),
            )
            return cur.fetchall()
