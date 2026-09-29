"""Detector de anomalias do AMV - CPTM Linha 10.

Roda em loop continuo lendo a telemetria em public.dados_monitoramento e
aplica deteccao orientada a eventos de acionamento (nao por janela fixa):
acumula amostras enquanto a corrente esta acima do gatilho de acionamento
e, quando o acionamento encerra, classifica o evento completo (normal,
obstrucao, embreagem patinando ou fim de curso nao atingido), mantendo o
status operacional, o historico e os alarmes do equipamento em ihm em
sincronia.

Uso: python detector_amv.py
"""
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# ============================================================================
# Configuracao
# ============================================================================

load_dotenv(Path(__file__).resolve().parent / ".env")

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://cptm:senha@localhost:5432/telemetria_amv"
)

# Dispositivos monitorados
DISPOSITIVOS = ["AMV_TESTE"]  # adicionar "AMV_39B" quando pronto para producao

CICLO_S = 1              # segundos entre cada ciclo do loop principal
JANELA_INICIAL_S = 30    # segundos de historico buscados ao iniciar (recuperacao de estado)
OFFLINE_TIMEOUT_S = int(os.getenv("OFFLINE_TIMEOUT_S", "120"))  # segundos sem amostra nova -> Offline

# Gatilho de inicio de acionamento
GATILHO_ACIONAMENTO = 3.0  # A - acima disso considera-se acionamento em curso

# Thresholds (baseados em Sergio Barbosa)
CORRENTE_OBSTRU_MIN = 9.0   # A
OBSTRU_AMOSTRAS_MIN = 3     # amostras consecutivas

CORRENTE_EMBRE_MIN = 5.0    # A
EMBRE_DURACAO_MIN_S = 6.0   # s

CORRENTE_FIM_CURSO_MIN = 3.5  # A — captura toda a fase de trabalho prolongada
FIM_CURSO_DURACAO_S    = 8.0  # s — mantém (cenário 4 dura ~10s, passa folgado)

# IDs dos status em ihm.status_operacional
STATUS_ONLINE = 1
STATUS_ALERTA = 2
STATUS_CRITICO = 3
STATUS_OFFLINE = 4

# Mensagens e criticidade dos alarmes de falha operacional
_MENSAGENS_ANOMALIA = {
    "obstrucao": "Possivel obstrucao no AMV",
    "embreagem": "Possivel embreagem patinando",
    "fim_curso": "Fim de curso nao atingido",
}

_CRITICIDADE_ANOMALIA = {
    "obstrucao": "Critico",  # sem acento -- respeita o CHECK constraint da tabela
    "embreagem": "Alerta",
    "fim_curso": "Alerta",
}

# ============================================================================
# Logging
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("detector_amv")


# ============================================================================
# Conexao
# ============================================================================

def conectar():
    """Conecta ao PostgreSQL usando DATABASE_URL lido de ~/ihm-cma/api/.env."""
    conn = psycopg2.connect(DATABASE_URL)
    with conn.cursor() as cur:
        cur.execute("SET search_path TO ihm, public")
    return conn


# ============================================================================
# Consultas
# ============================================================================

def buscar_equipamento(cur, dispositivo_id):
    """Busca o equipamento em ihm.equipamentos pelo dispositivo_id.

    Retorna (id, status_id, nome) ou None se nao houver cadastro.
    """
    cur.execute(
        """
        SELECT id, status_id, nome
        FROM ihm.equipamentos
        WHERE dispositivo_id = %s
        """,
        (dispositivo_id,),
    )
    row = cur.fetchone()
    if row is None:
        return None
    return (row["id"], row["status_id"], row["nome"])


def buscar_amostras_novas(cur, dispositivo_id, desde_tempo):
    """Busca amostras novas de um dispositivo em ordem cronologica.

    Se desde_tempo for None (primeira execucao), busca os ultimos
    JANELA_INICIAL_S segundos -- usado para reconstruir o estado ao iniciar.
    Caso contrario, busca tudo que chegou apos desde_tempo.

    Retorna lista de (corrente, tensao, tempo).
    """
    if desde_tempo is None:
        cur.execute(
            """
            SELECT corrente, tensao, tempo AT TIME ZONE 'UTC' AS tempo
            FROM public.dados_monitoramento
            WHERE dispositivo_id = %s
              AND tempo >= NOW() - (%s * INTERVAL '1 second')
            ORDER BY tempo ASC
            """,
            (dispositivo_id, JANELA_INICIAL_S),
        )
    else:
        cur.execute(
            """
            SELECT corrente, tensao, tempo AT TIME ZONE 'UTC' AS tempo
            FROM public.dados_monitoramento
            WHERE dispositivo_id = %s
              AND tempo > %s
            ORDER BY tempo ASC
            """,
            (dispositivo_id, desde_tempo),
        )
    amostras = []
    for row in cur.fetchall():
        tempo = row["tempo"]
        if tempo.tzinfo is None:
            tempo = tempo.replace(tzinfo=timezone.utc)
        amostras.append((row["corrente"], row["tensao"], tempo))
    return amostras


# ============================================================================
# Analise do acionamento
# ============================================================================

def duracao_segmento_continuo(amostras, limiar):
    """Encontra o segmento continuo mais longo com corrente > limiar.

    amostras: lista de (corrente, tensao, tempo) em ordem cronologica.
    Retorna (duracao_s, corrente_media) do melhor segmento encontrado.
    """
    melhor_dur = 0.0
    melhor_soma = 0.0
    melhor_n = 0
    dur_atual = 0.0
    soma_atual = 0.0
    n_atual = 0

    for i in range(len(amostras) - 1):
        corrente = amostras[i][0]
        dt = (amostras[i + 1][2] - amostras[i][2]).total_seconds()
        if corrente > limiar:
            dur_atual += dt
            soma_atual += corrente
            n_atual += 1
        else:
            if dur_atual > melhor_dur:
                melhor_dur = dur_atual
                melhor_soma = soma_atual
                melhor_n = n_atual
            dur_atual = 0.0
            soma_atual = 0.0
            n_atual = 0

    if dur_atual > melhor_dur:
        melhor_dur = dur_atual
        melhor_soma = soma_atual
        melhor_n = n_atual

    media = melhor_soma / melhor_n if melhor_n > 0 else 0.0
    return melhor_dur, media


def analisar_acionamento(amostras):
    """Classifica um acionamento completo (do inicio ao fim do gatilho).

    amostras: lista de (corrente, tensao, tempo) em ordem cronologica.
    Retorna (tipo, corrente_caracteristica, duracao_s, amostras).
    """
    correntes = [amostra[0] for amostra in amostras]
    duracao_total = (amostras[-1][2] - amostras[0][2]).total_seconds()

    # 1. Obstrucao: >= OBSTRU_AMOSTRAS_MIN amostras consecutivas acima do
    #    limite, em qualquer ponto do acionamento.
    consecutivas = 0
    max_consecutivas = 0
    for corrente in correntes:
        if corrente > CORRENTE_OBSTRU_MIN:
            consecutivas += 1
            max_consecutivas = max(max_consecutivas, consecutivas)
        else:
            consecutivas = 0
    if max_consecutivas >= OBSTRU_AMOSTRAS_MIN:
        return ("obstrucao", max(correntes), duracao_total, amostras)

    # 2. Embreagem patinando: segmento continuo longo acima do limite.
    dur_embre, media_embre = duracao_segmento_continuo(amostras, CORRENTE_EMBRE_MIN)
    if dur_embre > EMBRE_DURACAO_MIN_S:
        return ("embreagem", media_embre, duracao_total, amostras)

    # 3. Fim de curso nao atingido: segmento continuo longo acima do limite.
    dur_fim, media_fim = duracao_segmento_continuo(amostras, CORRENTE_FIM_CURSO_MIN)
    if dur_fim > FIM_CURSO_DURACAO_S:
        return ("fim_curso", media_fim, duracao_total, amostras)

    # 4. Normal
    corrente_media_geral = sum(correntes) / len(correntes) if correntes else 0.0
    return ("normal", corrente_media_geral, duracao_total, amostras)


# ============================================================================
# Escrita: status, historico e alarmes
# ============================================================================

def atualizar_status(cur, equipamento_id, status_novo_id, status_atual_id, origem="sistema"):
    """Atualiza ihm.equipamentos.status_id e registra a mudanca em historico_status."""
    cur.execute(
        """
        UPDATE ihm.equipamentos
        SET status_id = %s, atualizado_em = NOW()
        WHERE id = %s
        """,
        (status_novo_id, equipamento_id),
    )
    cur.execute(
        """
        INSERT INTO ihm.historico_status
            (equipamento_id, status_ant_id, status_novo_id, origem)
        VALUES (%s, %s, %s, %s)
        """,
        (equipamento_id, status_atual_id, status_novo_id, origem),
    )


def abrir_alarme(cur, equipamento_id, tipo_anomalia, corrente, duracao_s):
    """Abre um alarme de falha operacional a cada ocorrência detectada."""
    titulo = _MENSAGENS_ANOMALIA[tipo_anomalia]
    criticidade = _CRITICIDADE_ANOMALIA[tipo_anomalia]
    descricao = f"Corrente: {corrente:.2f}A · Duração: {duracao_s:.1f}s"

    cur.execute(
        """
        INSERT INTO ihm.alarmes (equipamento_id, tipo, criticidade, titulo, descricao)
        VALUES (%s, 'Falha Operacional', %s, %s, %s)
        """,
        (equipamento_id, criticidade, titulo, descricao),
    )

def resolver_alarmes(cur, equipamento_id):
    """Fecha automaticamente todos os alarmes ativos do equipamento.

    Retorna a quantidade de alarmes resolvidos.
    """
    cur.execute(
        """
        UPDATE ihm.alarmes
        SET resolvido_em = NOW(), resolvido_por = NULL
        WHERE equipamento_id = %s AND resolvido_em IS NULL
        """,
        (equipamento_id,),
    )
    return cur.rowcount


def processar_resultado(cur, dispositivo_id, equipamento_id, status_atual_id, tipo, corrente, duracao):
    """Aplica o resultado de analisar_acionamento no banco e no log.

    Retorna o status_id vigente apos o processamento (para o chamador manter
    o estado local em dia caso mais de um acionamento seja processado no
    mesmo ciclo).
    """  
   
    if tipo == "normal":
        if status_atual_id != STATUS_ONLINE:
            atualizar_status(cur, equipamento_id, STATUS_ONLINE, status_atual_id)
            status_atual_id = STATUS_ONLINE
        log.info(
            f"[{dispositivo_id}] Acionamento normal · duração {duracao:.1f}s · corrente média {corrente:.2f}A"
        )
        return status_atual_id

    if tipo == "obstrucao":
        atualizar_status(cur, equipamento_id, STATUS_CRITICO, status_atual_id)
        abrir_alarme(cur, equipamento_id, "obstrucao", corrente, duracao)
        log.info(
            f"[{dispositivo_id}] OBSTRUÇÃO detectada · corrente máx {corrente:.2f}A · duração {duracao:.1f}s"
        )
        return STATUS_CRITICO

    if tipo == "embreagem":
        atualizar_status(cur, equipamento_id, STATUS_ALERTA, status_atual_id)
        abrir_alarme(cur, equipamento_id, "embreagem", corrente, duracao)
        log.info(
            f"[{dispositivo_id}] EMBREAGEM PATINANDO · corrente média {corrente:.2f}A · duração {duracao:.1f}s"
        )
        return STATUS_ALERTA

    if tipo == "fim_curso":
        atualizar_status(cur, equipamento_id, STATUS_ALERTA, status_atual_id)
        abrir_alarme(cur, equipamento_id, "fim_curso", corrente, duracao)
        log.info(
            f"[{dispositivo_id}] FIM DE CURSO NÃO ATINGIDO · corrente média {corrente:.2f}A · duração {duracao:.1f}s"
        )
        return STATUS_ALERTA

    return status_atual_id


# ============================================================================
# Ciclo do detector
# ============================================================================

def ciclo_detector(cur, dispositivo_id, estado):
    """Executa um ciclo completo de deteccao para um dispositivo."""
     # LOG DIAGNÓSTICO TEMPORÁRIO
    log.info(f"[{dispositivo_id}] Ciclo. ultimo_tempo: {estado['ultimo_tempo_verificado']} · em_acionamento: {estado['em_acionamento']}")
    equipamento = buscar_equipamento(cur, dispositivo_id)
    if equipamento is None:
        log.warning(
            f"[{dispositivo_id}] Equipamento nao cadastrado em ihm.equipamentos. "
            f"Cadastre um registro com dispositivo_id='{dispositivo_id}' "
            f"para habilitar o monitoramento deste dispositivo."
        )
        return

    equipamento_id, status_atual_id, _nome = equipamento

    novas = buscar_amostras_novas(cur, dispositivo_id, estado["ultimo_tempo_verificado"])
    # LOG DIAGNÓSTICO TEMPORÁRIO
    log.info(f"[{dispositivo_id}] {len(novas)} amostras novas. Primeiras correntes: {[round(a[0],2) for a in novas[:5]]}")
    if novas:
        estado["ultimo_tempo_verificado"] = novas[-1][2]

    # Timeout offline: sem amostra nova ha mais de OFFLINE_TIMEOUT_S segundos.
    ultimo_tempo = estado["ultimo_tempo_verificado"]
    if ultimo_tempo is None:
        segundos_sem_dados = None
    else:
        segundos_sem_dados = (datetime.now(timezone.utc) - ultimo_tempo).total_seconds()

    if segundos_sem_dados is None or segundos_sem_dados > OFFLINE_TIMEOUT_S:
        if status_atual_id != STATUS_OFFLINE:
            atualizar_status(cur, equipamento_id, STATUS_OFFLINE, status_atual_id)
            log.info(f"[{dispositivo_id}] OFFLINE · sem dados ha mais de {OFFLINE_TIMEOUT_S}s")
            status_atual_id = STATUS_OFFLINE
        return

    for corrente, tensao, tempo in novas:
        if corrente > GATILHO_ACIONAMENTO:
            if not estado["em_acionamento"]:
                estado["em_acionamento"] = True
                estado["amostras_acionamento"] = []
            estado["amostras_acionamento"].append((corrente, tensao, tempo))
        else:
            if estado["em_acionamento"]:
                tipo, corrente_c, duracao, amostras_evento = analisar_acionamento(
                    estado["amostras_acionamento"]
                )
                status_atual_id = processar_resultado(
                    cur, dispositivo_id, equipamento_id, status_atual_id,
                    tipo, corrente_c, duracao,
                )
                estado["em_acionamento"] = False
                estado["amostras_acionamento"] = []

    # Se ainda em acionamento ao fim do lote, mantem acumulando -- sera
    # analisado quando a corrente cair no proximo ciclo.


# ============================================================================
# Loop principal
# ============================================================================

def main():
    estados = {
        dispositivo_id: {
            "em_acionamento": False,
            "amostras_acionamento": [],
            "ultimo_tempo_verificado": None,
        }
        for dispositivo_id in DISPOSITIVOS
    }

    log.info(f"Detector AMV iniciado. Dispositivos: {DISPOSITIVOS}")

    while True:
        conn = None
        try:
            conn = conectar()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                for dispositivo_id in DISPOSITIVOS:
                    ciclo_detector(cur, dispositivo_id, estados[dispositivo_id])
            conn.commit()
        except KeyboardInterrupt:
            log.info("Detector encerrado pelo usuário.")
            break
        except Exception as e:
            import traceback
            log.error(f"Erro no ciclo: {e}")
            log.error(traceback.format_exc())
            try:
                conn.rollback()
            except Exception:
                pass
        finally:
            try:
                conn.close()
            except Exception:
                pass
        time.sleep(CICLO_S)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("Detector AMV encerrado pelo usuário.")
