"""Modelos Pydantic de request/response da API."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Autenticacao
# ---------------------------------------------------------------------------


class LoginRequest(BaseModel):
    email: str
    senha: str


class UsuarioToken(BaseModel):
    nome: str
    perfil: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: UsuarioToken


# ---------------------------------------------------------------------------
# Equipamentos / Dashboard
# ---------------------------------------------------------------------------


class EquipamentoResponse(BaseModel):
    id: int
    codigo: str
    nome: str
    descricao: Optional[str] = None
    tipo_id: int
    tipo_nome: str
    tipo_cor: str
    localidade_id: int
    localidade_nome: str
    mda_id: Optional[int] = None
    dispositivo_id: Optional[str] = None
    status_id: int
    status_nome: str
    status_cor: str
    maturidade: str
    horario_op: Optional[str] = None
    responsavel: Optional[str] = None
    valor_atual: Optional[str] = None
    ultima_comun: Optional[datetime] = None
    ativo: bool
    criado_em: datetime
    atualizado_em: datetime


class CategoriaDashboard(BaseModel):
    tipo_id: int
    tipo_nome: str
    tipo_cor: str
    total: int
    percentual: float


class DashboardResponse(BaseModel):
    total: int
    online: int
    alerta: int
    critico: int
    offline: int
    parcial: int
    por_categoria: list[CategoriaDashboard]


class AtualizarStatusRequest(BaseModel):
    status_id: int
    observacao: Optional[str] = None


class HistoricoStatusResponse(BaseModel):
    id: int
    equipamento_id: int
    status_ant_id: Optional[int] = None
    status_ant_nome: Optional[str] = None
    status_novo_id: int
    status_novo_nome: str
    usuario_id: Optional[int] = None
    usuario_nome: Optional[str] = None
    observacao: Optional[str] = None
    origem: str
    ocorrido_em: datetime


# ---------------------------------------------------------------------------
# Alarmes
# ---------------------------------------------------------------------------


class EquipamentoAlarme(BaseModel):
    nome: str
    local: str


class AlarmeResponse(BaseModel):
    id: int
    equipamento: EquipamentoAlarme
    tipo: str
    criticidade: str
    titulo: str
    descricao: Optional[str] = None
    iniciado_em: datetime
    reconhecido: bool


class ResolverAlarmeRequest(BaseModel):
    observacao: Optional[str] = None


# ---------------------------------------------------------------------------
# Telemetria
# ---------------------------------------------------------------------------


class TelemetriaAMVResponse(BaseModel):
    dispositivo_id: str
    corrente: Optional[float] = None
    temperatura: Optional[float] = None
    tensao: Optional[float] = None
    nivel: Optional[float] = None
    bateria: Optional[float] = None
    tempo: datetime
