"""Endpoints de supressao de alarmes por equipamento."""
from fastapi import APIRouter, Depends, HTTPException, status

from auth import eh_admin, get_usuario_atual
from database import get_db
from models.schemas import SupressaoResponse, SuprimirEquipamentoRequest

router = APIRouter(dependencies=[Depends(get_usuario_atual)])

# PERFIL_ADMIN (e a PENDENCIA sobre comparar perfil pelo nome) fica em auth.py
LIMITE_HORAS_OPERADOR = 24

_SUPRESSAO_SELECT = """
    SELECT
        s.id, s.equipamento_id,
        e.nome AS equipamento_nome, e.dispositivo_id, l.nome AS localidade_nome,
        (
            SELECT COUNT(*) FROM ihm.alarmes a
            WHERE a.equipamento_id = s.equipamento_id AND a.resolvido_em IS NULL
        ) AS alarmes_ativos,
        s.motivo,
        s.suprimido_por, us.nome AS suprimido_por_nome, s.suprimido_em,
        s.expira_em, s.cancelado_em,
        s.cancelado_por, uc.nome AS cancelado_por_nome
    FROM ihm.supressoes s
    JOIN ihm.equipamentos e ON e.id = s.equipamento_id
    JOIN ihm.localidades l ON l.id = e.localidade_id
    LEFT JOIN ihm.usuarios us ON us.id = s.suprimido_por
    LEFT JOIN ihm.usuarios uc ON uc.id = s.cancelado_por
"""


def _buscar_supressao_ativa(cur, equipamento_id: int):
    cur.execute(
        _SUPRESSAO_SELECT
        + """
        WHERE s.id IN (SELECT id FROM ihm.supressoes_ativas WHERE equipamento_id = %s)
        ORDER BY s.suprimido_em DESC
        LIMIT 1
        """,
        (equipamento_id,),
    )
    return cur.fetchone()


def _validar_duracao_por_perfil(usuario: dict, duracao_horas):
    """Operador CMA (ou qualquer perfil nao-admin): no maximo 24h, com prazo.
    Administrador: sem limite, inclusive sem prazo (duracao_horas = None)."""
    if eh_admin(usuario):
        return
    if duracao_horas is None or duracao_horas > LIMITE_HORAS_OPERADOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Seu perfil permite suprimir por no maximo {LIMITE_HORAS_OPERADOR}h",
        )


@router.get("/supressoes", response_model=list[SupressaoResponse])
def listar_supressoes_ativas():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                _SUPRESSAO_SELECT
                + """
                WHERE s.id IN (SELECT id FROM ihm.supressoes_ativas)
                ORDER BY s.suprimido_em DESC
                """
            )
            return cur.fetchall()


@router.get("/equipamentos/{equipamento_id}/supressao", response_model=SupressaoResponse)
def obter_supressao(equipamento_id: int):
    with get_db() as conn:
        with conn.cursor() as cur:
            supressao = _buscar_supressao_ativa(cur, equipamento_id)

    if supressao is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Nenhuma supressao ativa"
        )
    return supressao


@router.post(
    "/equipamentos/{equipamento_id}/suprimir",
    response_model=SupressaoResponse,
    status_code=status.HTTP_201_CREATED,
)
def suprimir_equipamento(
    equipamento_id: int,
    dados: SuprimirEquipamentoRequest,
    usuario: dict = Depends(get_usuario_atual),
):
    _validar_duracao_por_perfil(usuario, dados.duracao_horas)

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM ihm.equipamentos WHERE id = %s", (equipamento_id,))
            if cur.fetchone() is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Equipamento nao encontrado"
                )

            if _buscar_supressao_ativa(cur, equipamento_id) is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Equipamento ja possui supressao ativa",
                )

            # Expiracao calculada pelo relogio do servidor de banco -- nunca pelo
            # cliente. duracao_horas NULL -> expira_em NULL (sem prazo).
            cur.execute(
                """
                INSERT INTO ihm.supressoes (equipamento_id, motivo, suprimido_por, expira_em)
                VALUES (%s, %s, %s, NOW() + %s::int * INTERVAL '1 hour')
                RETURNING id
                """,
                (equipamento_id, dados.motivo, int(usuario["sub"]), dados.duracao_horas),
            )
            supressao_id = cur.fetchone()["id"]

            cur.execute(_SUPRESSAO_SELECT + " WHERE s.id = %s", (supressao_id,))
            supressao = cur.fetchone()

    return supressao


@router.delete("/equipamentos/{equipamento_id}/supressao", response_model=SupressaoResponse)
def cancelar_supressao(equipamento_id: int, usuario: dict = Depends(get_usuario_atual)):
    with get_db() as conn:
        with conn.cursor() as cur:
            # Supressao sem prazo so pode ser cancelada pelo Administrador
            # (quem pode cria-la). Com prazo: qualquer usuario cancela.
            cur.execute(
                """
                SELECT COALESCE(BOOL_OR(s.expira_em IS NULL), FALSE) AS sem_prazo
                FROM ihm.supressoes s
                WHERE s.id IN (SELECT id FROM ihm.supressoes_ativas WHERE equipamento_id = %s)
                """,
                (equipamento_id,),
            )
            if cur.fetchone()["sem_prazo"] and not eh_admin(usuario):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Somente o Administrador pode cancelar supressões sem prazo",
                )

            cur.execute(
                """
                UPDATE ihm.supressoes
                SET cancelado_em = NOW(), cancelado_por = %s
                WHERE id IN (SELECT id FROM ihm.supressoes_ativas WHERE equipamento_id = %s)
                RETURNING id
                """,
                (int(usuario["sub"]), equipamento_id),
            )
            cancelada = cur.fetchone()
            if cancelada is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Nenhuma supressao ativa"
                )

            cur.execute(_SUPRESSAO_SELECT + " WHERE s.id = %s", (cancelada["id"],))
            supressao = cur.fetchone()

    return supressao
