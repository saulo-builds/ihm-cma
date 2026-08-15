# Documentação Técnica — Sistema de Monitoramento de Ativos
## CMA · CPTM Linha 10

**Versão:** 1.0  
**Data:** Agosto/2026  
**Desenvolvedor:** Saulo Lima · GOT/CMA

---

## 1. Visão geral da arquitetura

O sistema é uma aplicação web offline composta por três camadas independentes:

```
┌─────────────────────────────────────────────────────────────┐
│  CAMADA DE APRESENTAÇÃO (Frontend)                          │
│  HTML + CSS + JavaScript puro · roda no browser             │
│  Estação do operador + VideoWall Barco                      │
└───────────────────────┬─────────────────────────────────────┘
                        │ HTTP / JSON
┌───────────────────────▼─────────────────────────────────────┐
│  CAMADA DE INTEGRAÇÃO (API)                                 │
│  Python · FastAPI · a implementar (Conversa 8)              │
│  Lê PostgreSQL (AMV) + MySQL/MariaDB (demais ativos)        │
└───────────┬───────────────────────────┬─────────────────────┘
            │                           │
┌───────────▼──────────┐   ┌────────────▼────────────────────┐
│  PostgreSQL 15        │   │  MySQL / MariaDB                │
│  Telemetria AMV       │   │  SCADA LTS (colega)             │
│  VM monitdev          │   │  Demais ativos da Linha 10      │
│  192.168.43.200       │   │                                 │
└──────────────────────┘   └─────────────────────────────────┘
```

**Princípio central:** cada camada tem responsabilidade única. O frontend não conhece os bancos de dados. A API não conhece a interface. Os bancos não conhecem a aplicação. Isso permite evoluir cada camada independentemente.

---

## 2. Infraestrutura de rede

```
Internet
  (sem acesso — rede isolada)

Rede interna CPTM (10.148.53.x)
  ├── Servidor físico Nayoro (10.148.53.125 / 192.168.43.214)
  │     └── KVM / VMs
  │           ├── monitdev (10.148.53.111 / 192.168.43.200)
  │           │     ├── Docker: Mosquitto (1883)
  │           │     ├── Docker: PostgreSQL 15 (5432)
  │           │     ├── Docker: Grafana (3000)
  │           │     └── Python: integrador_mqtt.py
  │           └── monitoramento-ativos (10.148.53.161)
  │
  └── CMA (sala de controle)
        ├── Estação do operador → browser → IHM
        └── VideoWall Barco → browser → /pages/videowall/index.html
```

**Regra importante:** a VM `monitdev` não tem acesso à internet. Todos os arquivos (código, dependências, fontes) precisam ser transferidos via pendrive ou rede interna. O comando de transferência de arquivos usa `netcat` com o servidor buscando da VM (não o contrário).

---

## 3. Estrutura do projeto

```
ihm-cma/
├── frontend/                  ← aplicação web completa
│   ├── index.html             ← entry point — carrega o shell
│   ├── tokens/
│   │   ├── design-tokens.css  ← todos os tokens de cor, tipografia e dimensão
│   │   └── reset.css          ← reset universal
│   ├── components/            ← componentes CSS reutilizáveis
│   │   ├── badge.css          ← badges de status e maturidade
│   │   ├── button.css         ← variantes de botão
│   │   ├── card.css           ← container de conteúdo
│   │   ├── input.css          ← inputs, selects e labels
│   │   └── table.css          ← tabelas e categorias cromáticas
│   ├── shell/
│   │   ├── header.html        ← fragmento do header
│   │   ├── sidebar.html       ← fragmento da sidebar
│   │   └── shell.html         ← shell completo (alternativa)
│   ├── js/
│   │   ├── router.js          ← SPA router (fetch + history API)
│   │   ├── clock.js           ← relógio em tempo real
│   │   └── notifications.js   ← painel de notificações
│   └── pages/
│       ├── monitoramento/     ← dashboard, mapeamento, tabela,
│       │                         disponibilidade, localidade, alarmes
│       ├── cadastro/          ← mda, status, tipo-equipamento,
│       │                         equipamento, notificacao, usuarios
│       ├── relatorios/        ← disponibilidade, historico-alarmes,
│       │                         mtbf-mttr, resumo-mensal,
│       │                         indisponibilidade-linha
│       └── videowall/
│           └── index.html     ← documento autônomo, sem shell
├── api/                       ← a implementar
│   ├── main.py
│   ├── routes/
│   ├── db/
│   └── models/
└── docs/                      ← esta documentação
```

---

## 4. Stack tecnológica — decisões e justificativas

### 4.1 Frontend

| Tecnologia | Decisão | Por quê |
|---|---|---|
| HTML5 + CSS3 + JS puro | ✅ Adotado | Zero dependências externas em runtime. Roda offline sem npm, CDN ou build step |
| CSS Custom Properties | ✅ Adotado | Design system via tokens — mudança de cor ou dimensão em um lugar reflete em todo o sistema |
| Canvas API (nativo) | ✅ Adotado | Gráficos sem biblioteca — sem Chart.js, D3 ou similar. Reduz dependências e funciona offline |
| SVG inline | ✅ Adotado | Mapas esquemáticos e ícones vetoriais sem imagens externas |
| History API + fetch | ✅ Adotado | SPA router sem React Router, Vue Router ou similar |
| `<dialog>` nativo | ✅ Adotado | Modais sem biblioteca — suporte nativo em todos os browsers modernos |
| React / Vue / Angular | ❌ Não adotado | Exigem build step (npm), node_modules pesado, incompatíveis com o fluxo de transferência via pendrive |
| Bootstrap / Tailwind | ❌ Não adotado | Dependências externas desnecessárias dado o design system próprio já implementado |
| jQuery | ❌ Não adotado | Obsoleto — o DOM moderno e o JS puro cobrem todos os casos de uso |

### 4.2 Backend (a implementar)

| Tecnologia | Decisão | Por quê |
|---|---|---|
| Python 3 | ✅ Planejado | Já presente no servidor (integrador_mqtt.py). Sem nova linguagem para a equipe aprender |
| FastAPI | ✅ Planejado | Async nativo, documentação automática (Swagger), tipagem com Pydantic, performance superior ao Flask |
| psycopg2 / asyncpg | ✅ Planejado | Conectores PostgreSQL maduros e bem documentados |
| PyMySQL | ✅ Planejado | Conector MySQL/MariaDB puro Python, sem dependências de sistema |
| Flask | ⚠️ Alternativa | Funciona, mas sem async nativo e documentação automática do FastAPI |
| Django | ❌ Não recomendado | Pesado demais para uma API de leitura de dados — overhead desnecessário |
| Node.js / Express | ❌ Não recomendado | Adiciona outra linguagem ao stack sem benefício técnico para este caso |

### 4.3 Banco de dados

| Sistema | Papel | Status |
|---|---|---|
| PostgreSQL 15 | Telemetria do AMV — dados de corrente, temperatura, vibração | Ativo em produção |
| MySQL / MariaDB | Dados dos demais ativos via SCADA LTS | Gerenciado pelo colega |
| Grafana | Análise técnica do AMV — curvas de corrente, histórico | Permanece ativo — complementar à IHM |
| TimescaleDB | Extensão planejada para séries temporais | Não ativa no PostgreSQL atual (confirmado via \dx) |

### 4.4 Infraestrutura de serviços

| Serviço | Tecnologia | Porta | Função |
|---|---|---|---|
| Broker MQTT | Mosquitto | 1883 | Recebe dados dos AMVs de campo |
| Banco AMV | PostgreSQL 15 | 5432 | Armazena telemetria |
| Dashboards técnicos | Grafana OSS | 3000 | Análise de curvas de corrente |
| Servidor web (dev) | npx serve | 3000 | Desenvolvimento local |
| Servidor web (prod) | Nginx (recomendado) | 80/443 | Servir o frontend em produção |
| API (planejado) | FastAPI + uvicorn | 8000 | Endpoints de dados para o frontend |

---

## 5. Design system

O design system é a fundação visual do sistema. Todos os valores de cor, tipografia e dimensão estão em `frontend/tokens/design-tokens.css` como CSS Custom Properties.

### 5.1 Paleta de cores

```
Superfícies (do mais escuro ao mais claro):
--bg:         #0D0D1A  ← fundo da aplicação
--surface-1:  #13132A  ← cards e sidebar
--surface-2:  #1A1A35  ← inputs e hover
--surface-3:  #222240  ← hover ativo

Texto:
--text-hi:    #E8EEF8  ← texto principal
--text-md:    #8A94B0  ← texto secundário
--text-lo:    #404468  ← labels e placeholders

Marca CPTM:
--cptm-red:   #E63229  ← diamante e faixa do header

Status operacional:
--ok:         #1D9E75  ← online / normal
--alert:      #D4891A  ← alerta / atenção
--crit:       #C0392B  ← crítico / falha
--offline:    #404468  ← offline / desconhecido

Maturidade:
--parcial:    #7B5EA7  ← sistema em implantação parcial

Módulos (acento da sidebar):
--mon:        #1A6EC2  ← Monitoramento
--cad:        #2E7D32  ← Cadastro
--rel:        #7B5EA7  ← Relatórios
--vw:         #C0392B  ← VideoWall
```

### 5.2 Tipografia

```
--font:       'Inter', system-ui, sans-serif
--font-mono:  'JetBrains Mono', monospace

Inter       → navegação, labels, texto geral
JetBrains Mono → valores numéricos, KPIs, relógio, IDs técnicos
```

### 5.3 Componentes

| Arquivo | Componentes |
|---|---|
| `badge.css` | `.badge` (ok/alert/crit/offline) · `.badge-mat` (concluido/parcial/implantacao) |
| `button.css` | `.btn-primary` · `.btn-ghost` · `.btn-danger` · `.btn-sm` |
| `card.css` | `.card` · `.card-header` · `.card-body` · `.card-title` |
| `input.css` | `.input` · `.select` · `.form-label` |
| `table.css` | `table` · `.td-mono` · `.td-cat` (fibra/hidraulico/energia/mecanico/sinalizacao/fibra-com) |

---

## 6. Roteamento SPA

O frontend usa um SPA router implementado em `frontend/js/router.js`. Funciona via `fetch` + `history.pushState`:

```
Usuário clica em "Mapeamento" na sidebar
    → router.navigate('/mapeamento')
    → fetch('/pages/monitoramento/mapeamento.html')
    → injeta HTML em <main id="content">
    → re-executa <script> tags do HTML injetado
    → atualiza breadcrumb do header
    → atualiza item ativo da sidebar
    → history.pushState('/mapeamento')
```

**Correção importante aplicada:** scripts injetados via `innerHTML` não executam por especificação do HTML. O router recria os elementos `<script>` como nós DOM novos após a injeção, forçando a execução.

**Caminhos das rotas:** todos os caminhos de arquivo usam `/` absoluto (ex: `/pages/cadastro/usuarios.html`). Caminhos relativos causam erro 404 quando a URL atual já contém segmentos de path.

---

## 7. VideoWall — arquitetura especial

O VideoWall (`frontend/pages/videowall/index.html`) é um documento HTML autônomo — não usa o shell da aplicação. Importa os tokens via caminho absoluto `/tokens/design-tokens.css`.

```
Carrossel de painéis:
┌─────────────────┐
│ Painel 1 (30s)  │ → Georreferenciamento
└────────┬────────┘
         │ fade 600ms
┌────────▼────────┐
│ Painel 2 (25s)  │ → Recursos e Insumos
└────────┬────────┘
         │ fade 600ms
┌────────▼────────┐
│ Painel 3 (20s)  │ → Disponibilidade
└────────┬────────┘
         │ volta ao início
         ▼
    (a cada 5s)
    verificarFalhas()
         │
    window.ATIVOS_EM_FALHA.length > 0?
         │
    Sim → Modo Crise (carrossel para)
    Não → continua
```

**Modo crise:** controlado pela variável global `window.ATIVOS_EM_FALHA`. Quando populada pela API com ativos em falha, o carrossel para e a tela exibe os cards de crise com cronômetro. Quando o array volta a ser vazio, retorna ao Painel 1.

---

## 8. Integração com sistemas de ativos

### 8.1 Sistemas compatíveis (testados ou planejados)

| Sistema | Protocolo | Banco | Status |
|---|---|---|---|
| AMV (ESP32 + LoRa) | MQTT → PostgreSQL | PostgreSQL 15 | ✅ Em produção |
| SCADA LTS | HTTP / API interna | MySQL / MariaDB | ✅ Planejado |
| Grafana | — | PostgreSQL (fonte) | ✅ Complementar |

### 8.2 Integrações recomendadas

**OPC-UA**  
Protocolo industrial padrão para comunicação com PLCs, CLPs e sistemas SCADA de diferentes fabricantes. Indicado para integrar equipamentos elétricos (disjuntores, retificadores) que já têm suporte a OPC-UA. Existem bibliotecas Python maduras (`opcua-asyncio`).

**MQTT com QoS 1**  
Já em uso para o AMV. Recomendado para qualquer sensor de campo com conectividade IoT. QoS 1 garante entrega pelo menos uma vez — importante para não perder leituras em caso de reconexão. Requer sessão persistente no broker (`clean_session=False`).

**REST API**  
Para sistemas que já expõem uma API HTTP (como o SCADA LTS). A API Python do sistema faz fetch dos dados e os normaliza para o formato do banco.

**JDBC / ODBC**  
Para integração direta com bancos de dados de sistemas legados. O FastAPI pode conectar diretamente via `psycopg2` (PostgreSQL), `PyMySQL` (MySQL/MariaDB) ou `pyodbc` (ODBC genérico).

### 8.3 Integrações não recomendadas

**WebSocket direto do browser para o banco**  
O frontend nunca deve conectar diretamente ao banco de dados. Toda comunicação passa pela API Python. Isso garante segurança, controle de acesso e desacoplamento.

**Polling de alta frequência sem cache**  
Consultas ao banco sem filtro de tempo (`WHERE tempo > ...`) em tabelas grandes (como `dados_monitoramento` com 10M+ linhas) causam CPU spike. Lição aprendida na fase de desenvolvimento do AMV — sempre incluir filtro temporal e índice composto.

**CDN ou dependências externas em produção**  
A rede é isolada. Qualquer biblioteca carregada de CDN externo (Google Fonts, Chart.js via CDN) vai falhar silenciosamente. Todas as dependências devem ser embarcadas localmente.

**TimescaleDB sem validação prévia**  
A extensão TimescaleDB aparece na documentação do sistema mas não está ativa no PostgreSQL atual (confirmado via `\dx`). Não assumir que está ativa sem verificar.

---

## 9. Padrões de desenvolvimento

### 9.1 Cada página é um fragmento HTML
As páginas do módulo de monitoramento, cadastro e relatórios são fragmentos — sem `<html>`, `<head>` ou `<body>`. São carregadas dinamicamente pelo router no `<main>` do shell. Podem ter `<style>` e `<script>` próprios.

### 9.2 JS em IIFE com delegação de eventos
Scripts das páginas são encapsulados em IIFE `(function(){ ... })()` para evitar vazamento de variáveis globais. Eventos em tabelas usam delegação no container pai (não em cada linha) para compatibilidade com conteúdo dinâmico.

### 9.3 Zero hardcode de cor
Nenhum valor de cor é escrito diretamente no CSS ou JS das páginas. Tudo via `var(--token)`. Cores lidas no canvas via `getComputedStyle(document.documentElement).getPropertyValue('--token')`.

### 9.4 ResizeObserver nos canvas
Todos os gráficos em canvas usam `ResizeObserver` para redesenhar ao redimensionar a janela. Essencial para o VideoWall que pode rodar em resoluções muito diferentes entre desenvolvimento (1920×1080) e produção (61440×2160).

---

## 10. Pendências técnicas (próximas etapas)

```
CONVERSA 8 — API Python (FastAPI)
├── Endpoint GET /api/ativos          → lista de ativos com status
├── Endpoint GET /api/ativos/{id}     → detalhe de um ativo
├── Endpoint GET /api/alarmes         → alarmes ativos
├── Endpoint GET /api/disponibilidade → histórico por período
├── Endpoint GET /api/dashboard       → dados agregados para KPIs
├── Fonte 1: PostgreSQL (AMV)         → validar primeiro
└── Fonte 2: MySQL/MariaDB (SCADA)    → após validação do AMV

CONVERSA 9 — Integração final
├── Substituir dados mockados por chamadas fetch() à API
├── VideoWall lê window.ATIVOS_EM_FALHA da API (polling 5s)
├── Dashboard atualiza KPIs em tempo real
└── Testes de performance com dados reais

PENDÊNCIAS DE INFRAESTRUTURA
├── MQTT persistent session (QoS 1) — requer janela de manutenção
├── Gateway firmware v2.0 — corrige dirty dispositivo_id
├── Amostragem 100-200ms — deploy pendente
├── UFW no servidor Nayoro
├── Restringir porta 5432 no docker-compose.yml
└── Nginx para servir o frontend em produção
```

---

## 11. Fluxo de trabalho de desenvolvimento

```
Claude.ai (planejamento)              Claude Code no VSCode (execução)
        │                                          │
  Discutir arquitetura              Recebe prompt estruturado
  Montar prompt detalhado  ──────►  Gera código
  Revisar decisões                  Executa e valida
        │                                          │
  Validar resultado        ◄──────  Reporta decisões tomadas
  Próximo prompt
```

Fluxo de transferência para a VM de produção:
```
Desenvolvimento (Windows/notebook)
    → pendrive (transferência física)
    → VM monitdev (192.168.43.200)
    → npx serve / nginx
```

---

*CPTM · GOT · CMA — Documentação Técnica v1.0 · Agosto/2026*
