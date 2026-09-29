"""Watchdog de comunicacao dos ativos - CPTM Linha 10.

Monitora todos os equipamentos cadastrados em ihm.equipamentos e verifica
se o ultimo dado recebido esta dentro do timeout de comunicacao esperado.

A origem dos dados de cada equipamento e definida em ihm.fontes_dados --
o watchdog nao tem hardcoded de onde buscar os dados. Quando um novo ativo
entrar com fonte diferente (ex: MySQL do SCADA LTS), basta cadastrar em
ihm.fontes_dados e vincular o equipamento via fonte_id. O watchdog passa
a monitorar automaticamente sem nenhuma alteracao no codigo.

Responsabilidade unica: comunicacao. Nao analisa falhas operacionais.
Essas sao responsabilidade do detector especifico do ativo (ex: detector_amv.py).

Uso:
    python watchdog.py

Variaveis de ambiente (em ~/ihm-cma/api/.env):
    DATABASE_URL          URL de conexao PostgreSQL principal (obrigatorio)
    OFFLINE_TIMEOUT_S     Segundos sem dado novo para marcar Offline (padrao: 120)
    CICLO_S               Segundos entre cada ciclo de verificacao (padrao: 30)

    Para cada fonte adicional cadastrada em ihm.fontes_dados, adicionar
    a variavel de ambiente referenciada em credencial_env. Exemplo:
    SCADALTS_URL=mysql://usuario:senha@192.168.43.XXX:3306/scadalts
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

OFFLINE_TIMEOUT_S = int(os.getenv("OFFLINE_TIMEOUT_S", "120"))  # segundos sem dado -> Offline
CICLO_S           = int(os.getenv("CICLO_S", "30"))             # intervalo entre ciclos

# IDs dos status em ihm.status_operacional
STATUS_ONLINE  = 1
STATUS_OFFLINE = 4

# ============================================================================
# Logging
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("watchdog")


# ============================================================================
# Conexao principal (PostgreSQL IHM)
# ============================================================================

def conectar():
    """Conecta ao PostgreSQL principal usando DATABASE_URL."""
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    return conn


# ============================================================================
# Conexao dinamica por fonte
# Cada fonte em ihm.fontes_dados pode ter seu proprio banco e credencial.
# O watchdog le a credencial_env da tabela e busca a connection string
# na variavel de ambiente correspondente -- nunca armazena senhas no banco.
# ============================================================================

def conectar_fonte(fonte):
    """Conecta ao banco de dados de uma fonte especifica.

    Para tipo 'postgresql': usa psycopg2 com a URL em credencial_env.
    Para tipos futuros (ex: 'mysql'): adicionar novo bloco abaixo.

    Retorna (conn, cursor) ou (None, None) se a conexao falhar.
    """
    tipo          = fonte["tipo"]
    credencial_env = fonte["credencial_env"]

    # Busca a connection string na variavel de ambiente referenciada
    connection_string = os.getenv(credencial_env)
    if not connection_string:
        log.error(
            f"Variavel de ambiente '{credencial_env}' nao encontrada no .env. "
            f"Fonte '{fonte['nome']}' nao sera monitorada."
        )
        return None, None

    try:
        if tipo == "postgresql":
            conn = psycopg2.connect(connection_string)
            conn.autocommit = True
            cur = conn.cursor(cursor_factory=RealDictCursor)
            return conn, cur

        # Ponto de extensao para fontes futuras:
        # elif tipo == "mysql":
        #     import pymysql
        #     conn = pymysql.connect(...) 
        #     return conn, conn.cursor()

        else:
            log.warning(f"Tipo de fonte desconhecido: '{tipo}'. Ignorando.")
            return None, None

    except Exception as e:
        log.error(f"Erro ao conectar na fonte '{fonte['nome']}': {e}")
        return None, None


# ============================================================================
# Consultas
# ============================================================================

def buscar_equipamentos(cur):
    """Retorna todos os equipamentos ativos com os dados da sua fonte.

    Faz JOIN com ihm.fontes_dados para trazer schema_tabela,
    coluna_dispositivo, coluna_tempo e credencial_env de cada equipamento.
    """
    cur.execute(
        """
        SELECT 
            e.id,
            e.codigo,
            e.nome,
            e.dispositivo_id,
            e.status_id,
            f.id               AS fonte_id,
            f.nome             AS fonte_nome,
            f.tipo             AS fonte_tipo,
            f.host             AS fonte_host,
            f.porta            AS fonte_porta,
            f.banco            AS fonte_banco,
            f.schema_tabela,
            f.coluna_dispositivo,
            f.coluna_tempo,
            f.credencial_env
        FROM ihm.equipamentos e
        JOIN ihm.fontes_dados f ON f.id = e.fonte_id
        WHERE e.ativo = true
          AND f.ativo = true
        ORDER BY e.id
        """
    )
    return cur.fetchall()


def buscar_ultimo_dado(cur_fonte, dispositivo_id, schema_tabela, coluna_dispositivo, coluna_tempo):
    """Busca o timestamp do ultimo registro de um dispositivo na sua fonte.

    Usa os campos da fonte para montar a query dinamicamente --
    nao ha nenhum nome de tabela ou coluna hardcoded nesta funcao.

    Retorna datetime com timezone UTC ou None se nao houver registro.
    """
    query = f"""
        SELECT MAX({coluna_tempo}) AT TIME ZONE 'UTC' AS ultimo_tempo
        FROM {schema_tabela}
        WHERE {coluna_dispositivo} = %s
    """
    cur_fonte.execute(query, (dispositivo_id,))
    row = cur_fonte.fetchone()

    if row is None or row["ultimo_tempo"] is None:
        return None

    tempo = row["ultimo_tempo"]
    if tempo.tzinfo is None:
        tempo = tempo.replace(tzinfo=timezone.utc)
    return tempo


def alarme_comunicacao_ativo(cur, equipamento_id):
    """Verifica se ja existe um alarme de comunicacao aberto para o equipamento.

    Evita abrir alarmes duplicados a cada ciclo quando o equipamento ja
    esta Offline e o alarme anterior ainda nao foi resolvido.

    Retorna True se houver alarme ativo, False caso contrario.
    """
    cur.execute(
        """
        SELECT id FROM ihm.alarmes
        WHERE equipamento_id = %s
          AND tipo = 'Falha de Comunicacao'
          AND resolvido_em IS NULL
        LIMIT 1
        """,
        (equipamento_id,),
    )
    return cur.fetchone() is not None


# ============================================================================
# Escrita: status, historico e alarmes
# ============================================================================

def atualizar_status(cur, equipamento_id, status_novo_id, status_atual_id):
    """Atualiza ihm.equipamentos.status_id e registra em ihm.historico_status."""
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
        VALUES (%s, %s, %s, 'sistema')
        """,
        (equipamento_id, status_atual_id, status_novo_id),
    )


def abrir_alarme_comunicacao(cur, equipamento_id, descricao):
    """Abre um alarme critico de falha de comunicacao."""
    cur.execute(
        """
        INSERT INTO ihm.alarmes
            (equipamento_id, tipo, criticidade, titulo, descricao)
        VALUES (%s, 'Falha de Comunicacao', 'Critico', 'Equipamento sem comunicacao', %s)
        """,
        (equipamento_id, descricao),
    )


def fechar_alarme_comunicacao(cur, equipamento_id):
    """Fecha o alarme de comunicacao aberto quando o equipamento volta Online.

    O fechamento automatico e valido aqui porque a volta de comunicacao e
    um fato objetivo verificavel pelo sistema -- diferente de falhas
    operacionais, que exigem confirmacao da equipe de campo.

    Retorna quantidade de alarmes fechados.
    """
    cur.execute(
        """
        UPDATE ihm.alarmes
        SET resolvido_em = NOW()
        WHERE equipamento_id = %s
          AND tipo = 'Falha de Comunicacao'
          AND resolvido_em IS NULL
        """,
        (equipamento_id,),
    )
    return cur.rowcount


# ============================================================================
# Ciclo do watchdog
# ============================================================================

def ciclo_watchdog(cur_ihm):
    """Executa um ciclo completo de verificacao para todos os equipamentos.

    cur_ihm: cursor do banco principal (PostgreSQL IHM) -- usado para
    ler equipamentos e escrever status/alarmes.

    Para cada equipamento, abre uma conexao separada com a fonte de dados
    referenciada em fonte_id -- permite fontes heterogeneas (PostgreSQL,
    MySQL, etc.) sem alterar o codigo.
    """
    equipamentos = buscar_equipamentos(cur_ihm)
    agora = datetime.now(timezone.utc)

    # Agrupa equipamentos por fonte para abrir apenas uma conexao por fonte
    # em vez de abrir e fechar uma conexao por equipamento
    fontes_vistas = {}

    for eq in equipamentos:
        equipamento_id = eq["id"]
        codigo         = eq["codigo"]
        dispositivo_id = eq["dispositivo_id"]
        status_atual   = eq["status_id"]
        fonte_id       = eq["fonte_id"]

        # Reutiliza conexao com a fonte se ja foi aberta neste ciclo
        if fonte_id not in fontes_vistas:
            conn_fonte, cur_fonte = conectar_fonte(eq)
            fontes_vistas[fonte_id] = (conn_fonte, cur_fonte)
        else:
            conn_fonte, cur_fonte = fontes_vistas[fonte_id]

        # Se nao conseguiu conectar na fonte, marca Offline e continua
        if cur_fonte is None:
            if status_atual != STATUS_OFFLINE:
                atualizar_status(cur_ihm, equipamento_id, STATUS_OFFLINE, status_atual)
                log.warning(f"[{codigo}] OFFLINE · fonte '{eq['fonte_nome']}' indisponivel.")
            if not alarme_comunicacao_ativo(cur_ihm, equipamento_id):
                abrir_alarme_comunicacao(
                    cur_ihm, equipamento_id,
                    f"Fonte de dados '{eq['fonte_nome']}' indisponivel."
                )
            continue

        # Busca ultimo dado usando os campos dinamicos da fonte
        ultimo_dado = buscar_ultimo_dado(
            cur_fonte,
            dispositivo_id,
            eq["schema_tabela"],
            eq["coluna_dispositivo"],
            eq["coluna_tempo"],
        )

        # Calcula segundos sem dado
        if ultimo_dado is None:
            segundos_sem_dado = None
            ultimo_str = "nenhum registro"
        else:
            segundos_sem_dado = (agora - ultimo_dado).total_seconds()
            ultimo_str = ultimo_dado.strftime("%d/%m/%Y %H:%M:%S")

        sem_comunicacao = (
            segundos_sem_dado is None
            or segundos_sem_dado > OFFLINE_TIMEOUT_S
        )

        # --- Equipamento perdeu comunicacao ---
        if sem_comunicacao:
            if status_atual != STATUS_OFFLINE:
                atualizar_status(cur_ihm, equipamento_id, STATUS_OFFLINE, status_atual)
                log.info(f"[{codigo}] OFFLINE · ultimo contato: {ultimo_str}")

            if not alarme_comunicacao_ativo(cur_ihm, equipamento_id):
                descricao = (
                    f"Sem dados ha mais de {OFFLINE_TIMEOUT_S}s. "
                    f"Ultimo contato: {ultimo_str}."
                )
                abrir_alarme_comunicacao(cur_ihm, equipamento_id, descricao)
                log.info(f"[{codigo}] Alarme de comunicacao aberto.")

        # --- Equipamento voltou a comunicar ---
        else:
            if status_atual == STATUS_OFFLINE:
                atualizar_status(cur_ihm, equipamento_id, STATUS_ONLINE, status_atual)
                fechados = fechar_alarme_comunicacao(cur_ihm, equipamento_id)
                log.info(
                    f"[{codigo}] Online novamente · ultimo dado: {ultimo_str} "
                    f"· {fechados} alarme(s) de comunicacao fechado(s)."
                )
            else:
                log.debug(f"[{codigo}] OK · ultimo dado: {ultimo_str}")

    # Fecha todas as conexoes com fontes abertas neste ciclo
    for fonte_id, (conn_fonte, cur_fonte) in fontes_vistas.items():
        try:
            if conn_fonte:
                conn_fonte.close()
        except Exception:
            pass


# ============================================================================
# Loop principal
# ============================================================================

def main():
    log.info(
        f"Watchdog iniciado. "
        f"Timeout: {OFFLINE_TIMEOUT_S}s · Ciclo: {CICLO_S}s"
    )

    while True:
        conn_ihm = None
        try:
            conn_ihm = conectar()
            with conn_ihm.cursor(cursor_factory=RealDictCursor) as cur_ihm:
                ciclo_watchdog(cur_ihm)
            conn_ihm.commit()
        except KeyboardInterrupt:
            log.info("Watchdog encerrado pelo usuario.")
            break
        except Exception as e:
            import traceback
            log.error(f"Erro no ciclo: {e}")
            log.error(traceback.format_exc())
            try:
                conn_ihm.rollback()
            except Exception:
                pass
        finally:
            try:
                conn_ihm.close()
            except Exception:
                pass
        time.sleep(CICLO_S)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("Watchdog encerrado pelo usuario.")