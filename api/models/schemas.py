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
# Usuarios
# ---------------------------------------------------------------------------


class UsuarioResponse(BaseModel):
    id: int
    nome: str
    email: str
    perfil_id: int
    perfil_nome: str
    ativo: bool
    ultimo_acesso: Optional[datetime] = None
    criado_em: datetime


class AtualizarUsuarioRequest(BaseModel):
    nome: Optional[str] = None
    email: Optional[str] = None
    perfil_id: Optional[int] = None


class AtualizarAtivoRequest(BaseModel):
    ativo: bool


class AtualizarSenhaRequest(BaseModel):
    senha: str


# ---------------------------------------------------------------------------
# Cadastros — MDAs, Status, Tipos, Localidades, Linhas, Grupos
# ---------------------------------------------------------------------------


class MdaResponse(BaseModel):
    id: int
    nome: str
    mac_address: str
    localidade_id: Optional[int] = None
    localidade_nome: Optional[str] = None
    ultima_comun: Optional[datetime] = None
    ativo: bool
    criado_em: datetime
    atualizado_em: datetime


class CriarMdaRequest(BaseModel):
    nome: str
    mac_address: str
    localidade_id: Optional[int] = None


class AtualizarMdaRequest(BaseModel):
    nome: Optional[str] = None
    mac_address: Optional[str] = None
    localidade_id: Optional[int] = None
    ativo: Optional[bool] = None


class StatusOperacionalResponse(BaseModel):
    id: int
    nome: str
    cor_hex: str
    ordem: int
    ativo: bool
    criado_em: datetime


class CriarStatusRequest(BaseModel):
    nome: str
    cor_hex: str
    ordem: int


class AtualizarStatusOperacionalRequest(BaseModel):
    nome: Optional[str] = None
    cor_hex: Optional[str] = None
    ordem: Optional[int] = None
    ativo: Optional[bool] = None


class TipoEquipamentoResponse(BaseModel):
    id: int
    nome: str
    descricao: Optional[str] = None
    cor_hex: str
    ativo: bool
    criado_em: datetime


class CriarTipoEquipamentoRequest(BaseModel):
    nome: str
    descricao: Optional[str] = None
    cor_hex: str


class AtualizarTipoEquipamentoRequest(BaseModel):
    nome: Optional[str] = None
    descricao: Optional[str] = None
    cor_hex: Optional[str] = None
    ativo: Optional[bool] = None


class LocalidadeResponse(BaseModel):
    id: int
    nome: str
    tipo: str
    linha_id: int
    linha_nome: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    ativo: bool
    criado_em: datetime


class LinhaResponse(BaseModel):
    id: int
    codigo: str
    nome: str
    cor_hex: str
    ativo: bool


class GrupoNotificacaoResponse(BaseModel):
    id: int
    nome: str
    ativo: bool
    criado_em: datetime
    total_membros: int


class CriarGrupoNotificacaoRequest(BaseModel):
    nome: str


class AtualizarGrupoNotificacaoRequest(BaseModel):
    nome: Optional[str] = None
    ativo: Optional[bool] = None


class MembroGrupoResponse(BaseModel):
    usuario_id: int
    nome: str
    email: str
    adicionado_em: datetime


class AdicionarMembroRequest(BaseModel):
    usuario_id: int


# ---------------------------------------------------------------------------
# Equipamentos / Dashboard
# ---------------------------------------------------------------------------


class CriarEquipamentoRequest(BaseModel):
    codigo: str
    nome: str
    descricao: Optional[str] = None
    tipo_id: int
    localidade_id: int
    mda_id: Optional[int] = None
    dispositivo_id: Optional[str] = None
    status_id: int
    maturidade: str
    horario_op: Optional[str] = None
    responsavel: Optional[str] = None


class AtualizarEquipamentoRequest(BaseModel):
    codigo: str
    nome: str
    descricao: Optional[str] = None
    tipo_id: int
    localidade_id: int
    mda_id: Optional[int] = None
    dispositivo_id: Optional[str] = None
    status_id: int
    maturidade: str
    horario_op: Optional[str] = None
    responsavel: Optional[str] = None


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
