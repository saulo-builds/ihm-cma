## 15. Detector de Anomalias e Fluxo de Alarmes (detector_amv.py)

### 15.1 Visão Geral

O `detector_amv.py` é um processo Python autônomo que lê continuamente os dados de telemetria do banco e classifica cada acionamento da AMV. Quando detecta uma anomalia, abre um alarme na tabela `ihm.alarmes` e atualiza o status do equipamento em `ihm.equipamentos`. Esses dados são consumidos diretamente pela IHM-CMA.

O detector roda independente do integrador MQTT e da IHM — pode ser parado e reiniciado sem afetar a coleta de dados.

**Localização:** `~/ihm-cma/api/detector_amv.py`  
**Iniciar:** `cd ~/ihm-cma/api && source ~/projeto_amv/venv/bin/activate && python detector_amv.py &`

---

### 15.2 Arquitetura Orientada a Eventos

O detector não analisa janelas de tempo fixas. Ele detecta acionamentos por **gatilho de corrente**:

```
corrente > GATILHO_ACIONAMENTO (3.0A)  →  acionamento em curso, acumula amostras
corrente ≤ GATILHO_ACIONAMENTO         →  acionamento encerrado, analisa e classifica
```

Isso garante que a análise sempre seja feita sobre um acionamento completo — do início ao fim — independente do tempo que durou.

**Ciclo de execução:**
```
a cada CICLO_S (1s):
  1. Busca amostras novas desde o último timestamp processado
  2. Para cada amostra:
     - corrente > gatilho → acumula em estado["amostras_acionamento"]
     - corrente ≤ gatilho → se havia acionamento em curso, analisa e classifica
  3. Se sem dados por OFFLINE_TIMEOUT_S (120s) → marca equipamento como Offline
```

Se o ciclo terminar com acionamento ainda em curso (corrente ainda alta), as amostras ficam acumuladas e a análise ocorre no próximo ciclo quando a corrente cair.

---

### 15.3 Classificação de Acionamentos

A função `analisar_acionamento` recebe todas as amostras do acionamento e aplica as regras em ordem de prioridade:

| Prioridade | Tipo | Condição | Corrente característica | Duração típica |
|---|---|---|---|---|
| 1 | Obstrução | >= 3 amostras consecutivas acima de 9.0A | Máxima do acionamento | < 1s |
| 2 | Embreagem patinando | Segmento contínuo acima de 5.0A por > 6s | Média do segmento | > 8s |
| 3 | Fim de curso não atingido | Segmento contínuo acima de 3.5A por > 8s | Média do segmento | > 10s |
| 4 | Normal | Nenhuma das anteriores | Média geral | ~4s |

> **Nota sobre fim de curso:** o threshold de 3.5A captura toda a fase de trabalho do acionamento (3.5–4.5A), não apenas o pico final. Isso é necessário porque o cenário de fim de curso não atingido apresenta corrente de trabalho prolongada, não necessariamente elevada.

**Constantes configuráveis (bloco de configuração do arquivo):**
```python
GATILHO_ACIONAMENTO    = 3.0   # A — inicia acumulação de amostras
CORRENTE_OBSTRU_MIN    = 9.0   # A — threshold de obstrução
OBSTRU_AMOSTRAS_MIN    = 3     # amostras consecutivas para confirmar obstrução
CORRENTE_EMBRE_MIN     = 5.0   # A — threshold de embreagem
EMBRE_DURACAO_MIN_S    = 6.0   # s — duração mínima para embreagem
CORRENTE_FIM_CURSO_MIN = 3.5   # A — threshold de fim de curso
FIM_CURSO_DURACAO_S    = 8.0   # s — duração mínima para fim de curso
OFFLINE_TIMEOUT_S      = 120   # s — tempo sem dados para marcar offline
CICLO_S                = 1     # s — intervalo entre ciclos do loop principal
```

---

### 15.4 Fluxo de Alarmes

#### Princípio fundamental

Cada **acionamento com falha gera um registro individual** na tabela `ihm.alarmes`. Acionamentos consecutivos com falha geram múltiplos registros — isso é intencional para rastrear frequência e recorrência.

Exemplo: AMV tenta mover 3 vezes com obstrução → 3 alarmes registrados com timestamps individuais. No histórico da IHM, o operador vê exatamente quantas tentativas ocorreram e em que horários.

#### Estados de um alarme

```
ABERTO (resolvido_em IS NULL)
  → detectado pelo detector_amv.py
  → aparece em "Alarmes Ativos" na IHM

RECONHECIDO (reconhecido_em preenchido, resolvido_em IS NULL)
  → operador clicou "Reconhecer" na IHM
  → registra ciência, mas falha ainda pode persistir
  → ainda aparece em "Alarmes Ativos"

RESOLVIDO (resolvido_em preenchido)
  → operador clicou "Resolver" após confirmação da equipe de campo
  → sai de "Alarmes Ativos", permanece no "Histórico"
```

> **Importante:** O detector **nunca fecha alarmes automaticamente**. Um acionamento normal após uma falha atualiza o status do equipamento para Online, mas **não resolve o alarme**. O fechamento é sempre manual — o operador resolve após confirmação da equipe de campo de que a causa foi eliminada.

#### Por que não fechar automaticamente

Cenário real que motivou essa decisão:

```
1. AMV tenta mover → obstrução detectada → alarme abre
2. Controlador manda reverso → AMV volta para posição normal
3. detector classifica como "acionamento normal"
→ se fechasse automaticamente: alarme sumiria, mas a obstrução ainda existe no trilho
```

O fechamento automático criaria uma janela de risco em que o sistema indica "tudo normal" mas a causa raiz não foi eliminada.

#### Fluxo completo na operação

```
[CAMPO]          AMV aciona → anomalia ocorre
                      ↓
[DETECTOR]       Detecta → abre alarme em ihm.alarmes
                         → atualiza status em ihm.equipamentos
                      ↓
[IHM — ATIVOS]   Alarme aparece com tipo, criticidade, corrente e duração
                      ↓
[OPERADOR]       Clica "Reconhecer" → registra ciência
                 Aciona equipe de campo
                      ↓
[CAMPO]          Equipe verifica e corrige a causa
                      ↓
[OPERADOR]       Confirma resolução → clica "Resolver" na IHM
                      ↓
[IHM — HISTÓRICO] Alarme permanece registrado com timestamps completos
```

---

### 15.5 Estrutura do Alarme no Banco

```sql
-- Tabela ihm.alarmes
id              BIGINT          -- identificador único
equipamento_id  INTEGER         -- referência ao equipamento em ihm.equipamentos
tipo            VARCHAR(50)     -- sempre 'Falha Operacional' para anomalias do detector
criticidade     VARCHAR(20)     -- 'Critico' (obstrucao) ou 'Alerta' (embreagem, fim_curso)
titulo          VARCHAR(150)    -- descrição da anomalia identificada
descricao       TEXT            -- corrente e duração registradas
iniciado_em     TIMESTAMPTZ     -- UTC — quando o alarme foi aberto
resolvido_em    TIMESTAMPTZ     -- NULL enquanto aberto
reconhecido_em  TIMESTAMPTZ     -- NULL enquanto não reconhecido
reconhecido_por INTEGER         -- FK para ihm.usuarios
resolvido_por   INTEGER         -- FK para ihm.usuarios
```

**Valores por tipo de anomalia:**

| Anomalia | criticidade | titulo |
|---|---|---|
| Obstrução | `Critico` | `Possivel obstrucao no AMV` |
| Embreagem | `Alerta` | `Possivel embreagem patinando` |
| Fim de curso | `Alerta` | `Fim de curso nao atingido` |

> **Atenção ao CHECK constraint:** o campo `criticidade` aceita apenas `'Critico'`, `'Alerta'` e `'Normal'` — sem acentos. Respeitar exatamente essa grafia ao inserir via código ou SQL manual.

---

### 15.6 Atualização de Status do Equipamento

Paralelamente ao alarme, o detector atualiza o campo `status_id` em `ihm.equipamentos`:

| Evento | status_id | Status |
|---|---|---|
| Acionamento normal (saindo de falha) | 1 | Online |
| Embreagem ou fim de curso detectado | 2 | Alerta |
| Obstrução detectada | 3 | Critico |
| Sem dados por > 120s | 4 | Offline |

A atualização de status é independente do alarme — o status reflete o **último evento conhecido**, enquanto o alarme reflete **cada ocorrência individual**.

---

### 15.7 Recuperação de Estado ao Reiniciar

Ao iniciar, o detector busca amostras dos últimos `JANELA_INICIAL_S` (30s) para cada dispositivo. Se encontrar amostras com corrente acima do gatilho, reconstrói `em_acionamento = True` com essas amostras — evita perder um acionamento em curso caso o processo tenha sido reiniciado durante uma movimentação da AMV.

---

### 15.8 Consultas Úteis

```sql
-- Alarmes ativos (abertos, não resolvidos)
SELECT tipo, criticidade, titulo, descricao, iniciado_em
FROM ihm.alarmes
WHERE resolvido_em IS NULL AND tipo = 'Falha Operacional'
ORDER BY iniciado_em DESC;

-- Historico completo de anomalias
SELECT tipo, criticidade, titulo, descricao,
       iniciado_em AT TIME ZONE 'America/Sao_Paulo' AS iniciado_sp,
       resolvido_em AT TIME ZONE 'America/Sao_Paulo' AS resolvido_sp
FROM ihm.alarmes
WHERE tipo = 'Falha Operacional'
ORDER BY iniciado_em DESC
LIMIT 20;

-- Status atual dos equipamentos
SELECT nome, dispositivo_id, status_id
FROM ihm.equipamentos
WHERE dispositivo_id IN ('AMV_39B', 'AMV_TESTE');

-- Fechar alarmes de teste manualmente
UPDATE ihm.alarmes
SET resolvido_em = NOW()
WHERE resolvido_em IS NULL AND tipo = 'Falha Operacional';
```
