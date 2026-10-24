-- ============================================================================
--  SCHEMA ihm — Sistema IHM CMA · CPTM Linha 10
--  Banco: telemetria_amv · PostgreSQL 15 · VM monitdev (192.168.43.200)
--  Executado por api/db/init_db.py
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS ihm;

-- ============================================================================
--  DOMÍNIO: CONFIGURAÇÃO DO SISTEMA
-- ============================================================================

-- perfis: perfis de acesso dos usuarios
CREATE TABLE ihm.perfis (
    id          SERIAL PRIMARY KEY,
    nome        VARCHAR(50) NOT NULL UNIQUE,
    descricao   TEXT,
    ativo       BOOLEAN NOT NULL DEFAULT true,
    criado_em   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- usuarios: usuarios do sistema com controle de acesso
CREATE TABLE ihm.usuarios (
    id              SERIAL PRIMARY KEY,
    nome            VARCHAR(100) NOT NULL,
    email           VARCHAR(150) NOT NULL UNIQUE,
    senha_hash      VARCHAR(255) NOT NULL,
    perfil_id       INTEGER NOT NULL REFERENCES ihm.perfis(id),
    ativo           BOOLEAN NOT NULL DEFAULT true,
    ultimo_acesso   TIMESTAMPTZ,
    criado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_usuarios_perfil_id ON ihm.usuarios(perfil_id);

-- status_operacional: estados operacionais possiveis para os ativos
CREATE TABLE ihm.status_operacional (
    id          SERIAL PRIMARY KEY,
    nome        VARCHAR(50) NOT NULL UNIQUE,
    cor_hex     CHAR(7) NOT NULL,
    ordem       SMALLINT NOT NULL,
    ativo       BOOLEAN NOT NULL DEFAULT true,
    criado_em   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- tipos_equipamento: categorias dos equipamentos monitorados
CREATE TABLE ihm.tipos_equipamento (
    id          SERIAL PRIMARY KEY,
    nome        VARCHAR(80) NOT NULL UNIQUE,
    descricao   TEXT,
    cor_hex     CHAR(7) NOT NULL,
    ativo       BOOLEAN NOT NULL DEFAULT true,
    criado_em   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- linhas: linhas ferroviarias monitoradas
CREATE TABLE ihm.linhas (
    id          SERIAL PRIMARY KEY,
    codigo      VARCHAR(10) NOT NULL UNIQUE,
    nome        VARCHAR(80) NOT NULL,
    cor_hex     CHAR(7) NOT NULL,
    ativo       BOOLEAN NOT NULL DEFAULT true
);

-- localidades: estacoes, salas tecnicas e trechos onde os ativos estao instalados
CREATE TABLE ihm.localidades (
    id          SERIAL PRIMARY KEY,
    nome        VARCHAR(120) NOT NULL,
    tipo        VARCHAR(50) NOT NULL,
    linha_id    INTEGER NOT NULL REFERENCES ihm.linhas(id),
    latitude    DECIMAL(9,6),
    longitude   DECIMAL(9,6),
    ativo       BOOLEAN NOT NULL DEFAULT true,
    criado_em   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_localidades_linha_id ON ihm.localidades(linha_id);

-- ============================================================================
--  DOMÍNIO: HARDWARE DE CAMPO
-- ============================================================================

-- mdas: gateways fisicos de coleta (Monitor de Ativos)
-- NOTA: o MDA nao tem dispositivo_id — esse ID pertence a cada sensor logico
-- (equipamento) dentro do gateway. Ver coluna dispositivo_id em ihm.equipamentos.
CREATE TABLE ihm.mdas (
    id              SERIAL PRIMARY KEY,
    nome            VARCHAR(80) NOT NULL,
    mac_address     MACADDR NOT NULL UNIQUE,
    localidade_id   INTEGER REFERENCES ihm.localidades(id),
    ultima_comun    TIMESTAMPTZ,
    ativo           BOOLEAN NOT NULL DEFAULT true,
    criado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_mdas_localidade_id ON ihm.mdas(localidade_id);

-- ============================================================================
--  DOMÍNIO: EQUIPAMENTOS (coração do sistema)
-- ============================================================================

-- equipamentos: ativos monitorados — cada linha e um ativo do CMA
-- dispositivo_id e a ponte com public.dados_monitoramento (telemetria MQTT)
CREATE TABLE ihm.equipamentos (
    id              SERIAL PRIMARY KEY,
    codigo          VARCHAR(30) NOT NULL UNIQUE,
    nome            VARCHAR(150) NOT NULL,
    descricao       TEXT,
    tipo_id         INTEGER NOT NULL REFERENCES ihm.tipos_equipamento(id),
    localidade_id   INTEGER NOT NULL REFERENCES ihm.localidades(id),
    mda_id          INTEGER REFERENCES ihm.mdas(id),
    dispositivo_id  VARCHAR(50) UNIQUE,
    status_id       INTEGER NOT NULL REFERENCES ihm.status_operacional(id),
    maturidade      VARCHAR(20) NOT NULL CHECK (maturidade IN ('Concluido','Parcial','Implantacao')),
    horario_op      VARCHAR(20),
    responsavel     VARCHAR(100),
    valor_atual     VARCHAR(50),
    ultima_comun    TIMESTAMPTZ,
    ativo           BOOLEAN NOT NULL DEFAULT true,
    criado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_equipamentos_tipo_id ON ihm.equipamentos(tipo_id);
CREATE INDEX idx_equipamentos_localidade_id ON ihm.equipamentos(localidade_id);
CREATE INDEX idx_equipamentos_status_id ON ihm.equipamentos(status_id);
CREATE INDEX idx_equipamentos_mda_id ON ihm.equipamentos(mda_id);

-- ============================================================================
--  DOMÍNIO: EVENTOS E HISTÓRICO
-- ============================================================================

-- historico_status: registro de cada mudanca de status de um equipamento
CREATE TABLE ihm.historico_status (
    id              BIGSERIAL PRIMARY KEY,
    equipamento_id  INTEGER NOT NULL REFERENCES ihm.equipamentos(id),
    status_ant_id   INTEGER REFERENCES ihm.status_operacional(id),
    status_novo_id  INTEGER NOT NULL REFERENCES ihm.status_operacional(id),
    usuario_id      INTEGER REFERENCES ihm.usuarios(id),
    observacao      TEXT,
    origem          VARCHAR(20) NOT NULL CHECK (origem IN ('manual','api','sistema')),
    ocorrido_em     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_historico_status_equip_ocorrido ON ihm.historico_status(equipamento_id, ocorrido_em DESC);

-- alarmes: eventos de alarme ativos e historico completo
-- alarme ativo = resolvido_em IS NULL
CREATE TABLE ihm.alarmes (
    id                  BIGSERIAL PRIMARY KEY,
    equipamento_id      INTEGER NOT NULL REFERENCES ihm.equipamentos(id),
    tipo                VARCHAR(50) NOT NULL,
    criticidade         VARCHAR(20) NOT NULL CHECK (criticidade IN ('Critico','Alerta','Normal')),
    titulo              VARCHAR(150) NOT NULL,
    descricao           TEXT,
    iniciado_em         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolvido_em        TIMESTAMPTZ,
    reconhecido_em      TIMESTAMPTZ,
    reconhecido_por     INTEGER REFERENCES ihm.usuarios(id),
    resolvido_por       INTEGER REFERENCES ihm.usuarios(id),
    observacao          TEXT
);
CREATE INDEX idx_alarmes_equipamento_id ON ihm.alarmes(equipamento_id);
CREATE INDEX idx_alarmes_iniciado_em ON ihm.alarmes(iniciado_em DESC);
CREATE INDEX idx_alarmes_resolvido_em ON ihm.alarmes(resolvido_em);

-- ============================================================================
--  DOMÍNIO: NOTIFICAÇÕES
-- ============================================================================

-- grupos_notificacao: grupos que recebem alertas de determinados ativos
CREATE TABLE ihm.grupos_notificacao (
    id          SERIAL PRIMARY KEY,
    nome        VARCHAR(100) NOT NULL UNIQUE,
    ativo       BOOLEAN NOT NULL DEFAULT true,
    criado_em   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- membros_notificacao: usuarios membros de grupos de notificacao (N:N)
CREATE TABLE ihm.membros_notificacao (
    grupo_id        INTEGER NOT NULL REFERENCES ihm.grupos_notificacao(id),
    usuario_id      INTEGER NOT NULL REFERENCES ihm.usuarios(id),
    adicionado_em   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (grupo_id, usuario_id)
);

-- ============================================================================
--  DADOS INICIAIS (seed)
-- ============================================================================

-- Perfis
INSERT INTO ihm.perfis (nome, descricao) VALUES
  ('Administrador', 'Acesso completo incluindo cadastro e gestao de usuarios'),
  ('Operador CMA',  'Acesso a monitoramento, alarmes e relatorios');

-- Status operacional
INSERT INTO ihm.status_operacional (nome, cor_hex, ordem) VALUES
  ('Online',   '#2FD4A0', 1),
  ('Alerta',   '#F0A830', 2),
  ('Critico',  '#F05050', 3),
  ('Offline',  '#404468', 4),
  ('Parcial',  '#BFA0E8', 5);

-- Tipos de equipamento
INSERT INTO ihm.tipos_equipamento (nome, descricao, cor_hex) VALUES
  ('Fibra',        'Sistemas de fibra optica e comunicacao',      '#5AAEFF'),
  ('Hidraulico',   'Bombas e reservatorios',                      '#40C0D0'),
  ('Energia',      'Sistemas eletricos e geradores',              '#D4A030'),
  ('Sinalizacao',  'Equipamentos de sinalizacao ferroviaria',     '#C070E0'),
  ('Fibra/Comun.', 'Fibra e comunicacao entre estacoes',          '#8090F0');

-- Linha
INSERT INTO ihm.linhas (codigo, nome, cor_hex) VALUES
  ('L10', 'Linha 10 - Turquesa', '#00A89D');

-- Localidades
INSERT INTO ihm.localidades (nome, tipo, linha_id) VALUES
  ('Sala Tecnica LUZ',  'Sala Tecnica', 1),
  ('Est. Tamanduatei',  'Estacao',      1),
  ('CCO Bras',          'CCO',          1),
  ('Bras - Linha 10',   'Trecho',       1),
  ('Linha 10',          'Trecho',       1);

-- MDAs (gateways de campo)
INSERT INTO ihm.mdas (nome, mac_address, localidade_id) VALUES
  ('MDA-TAM-01', 'A4:CF:12:3B:00:01', 2),
  ('MDA-BRS-01', 'A4:CF:12:3B:00:02', 4),
  ('MDA-LUZ-01', 'A4:CF:12:3B:00:03', 1);

-- Equipamentos (os 8 ativos reais do CMA)
-- status_id: 1=Online 2=Alerta 3=Critico 4=Offline 5=Parcial
-- tipo_id:   1=Fibra 2=Hidraulico 3=Energia 4=Sinalizacao 5=Fibra/Comun.
INSERT INTO ihm.equipamentos
  (codigo, nome, descricao, tipo_id, localidade_id, mda_id, dispositivo_id, status_id, maturidade, horario_op, responsavel)
VALUES
  ('LUZ-FIB-01','Mon. Fibra Ebilock Luz L10','Enlace de fibra optica - sinalizacao CCO',
   1,1,3,'LUZ-FIB-01',5,'Parcial','24h','GOT/CMA'),
  ('TAM-BOM-01','Sist. Acionamento de Bombas','Bombas hidraulicas e reservatorios',
   2,2,1,'TAM-BOM-01',1,'Concluido','24h','GOT/CMA'),
  ('TAM-ELE-01','Sistemas Eletricos','Quadros e paineis de distribuicao eletrica - Tamanduatei',
   3,2,1,'TAM-ELE-01',1,'Concluido','24h','GOT/CMA'),
  ('TAM-GER-01','Grupo Gerador','Grupo motogerador de emergencia - Tamanduatei',
   3,2,1,'TAM-GER-01',1,'Concluido','24h','GOT/CMA'),
  ('BRS-ELE-01','Sistemas Eletricos','Concessionaria, disjuntores e gerador - CCO Bras',
   3,3,2,'BRS-ELE-01',1,'Concluido','24h','GOT/CMA'),
  ('TAM-CTC-01','Monitoramento CTC','Alimentacao eletrica dos equip. de sinalizacao',
   4,2,1,'TAM-CTC-01',1,'Concluido','24h','GOT/CMA'),
  ('AMV-BRS-01','Monitoramento AMV','Aparelho de Mudanca de Via - chaveamento',
   4,4,2,'AMV39A-BAS',1,'Concluido','06-22h','GOT/CMA'),
  ('STO-L10-01','STO L10','Comunicacao entre STOs das estacoes da L10',
   5,5,2,'STO-L10-01',5,'Parcial','24h','GOT/CMA');

-- Usuarios iniciais (senha bcrypt real gerada e aplicada por api/db/init_db.py)
INSERT INTO ihm.usuarios (nome, email, senha_hash, perfil_id) VALUES
  ('Saulo Lima',
   'saulo.lima@cptm.sp.gov.br',
   '$2b$12$PLACEHOLDER_HASH_SAULO',
   1),
  ('Wellingto Rios',
   'wellingto.rios@cptm.sp.gov.br',
   '$2b$12$PLACEHOLDER_HASH_WELLINGTO',
   2),
  ('Fernando Vieira',
   'fernando.vieira@cptm.sp.gov.br',
   '$2b$12$PLACEHOLDER_HASH_FERNANDO',
   2);

-- Alarmes iniciais (os 2 de maturidade parcial)
INSERT INTO ihm.alarmes (equipamento_id, tipo, criticidade, titulo, descricao) VALUES
  (1,'Maturidade Parcial','Normal',
   'Sistema parcialmente implantado',
   'Mon. Fibra Ebilock Luz L10 - monitoramento ativo apenas nas estacoes concluidas'),
  (8,'Maturidade Parcial','Normal',
   'Sistema em fase de testes',
   'STO L10 - dados podem ser inconsistentes durante o periodo de testes');

-- Grupos de notificacao
INSERT INTO ihm.grupos_notificacao (nome) VALUES
  ('GOT-CMA Operacao'),
  ('GOT-CMA Manutencao');

-- Membros dos grupos de notificacao
-- grupo 1 = GOT-CMA Operacao (todos) | grupo 2 = GOT-CMA Manutencao (administradores)
INSERT INTO ihm.membros_notificacao (grupo_id, usuario_id) VALUES
  (1,1),(1,2),(1,3),
  (2,1),(2,2);
