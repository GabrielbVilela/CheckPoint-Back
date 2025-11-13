from pydantic import BaseModel, EmailStr, Field, AliasChoices, field_validator
from typing import Literal, Optional, Union, List
from datetime import date, datetime, time
from enum import Enum
import json
import unicodedata

# ------------------------------------------------------------
# Tipos e UsuÃ¡rios
# ------------------------------------------------------------
class TipoUsuario(str, Enum):
    aluno = "aluno"
    professor = "professor"
    admin = "admin"
    coordenador = "coordenador"
    supervisor = "supervisor"


class UsuarioCreate(BaseModel):
    nome: str
    matricula: str
    senha: str
    contato: str
    email: EmailStr
    turma: str
    periodo: Optional[str] = None
    tipo_acesso: Literal["aluno", "professor", "admin", "coordenador", "supervisor"] = "aluno"


class UsuarioOut(BaseModel):
    id: int
    nome: str
    matricula: str
    email: EmailStr
    turma: Optional[str] = None
    periodo: Optional[str] = None
    tipo_acesso: str

    class Config:
        from_attributes = True


# ------------------------------------------------------------
# Cursos e Turmas
# ------------------------------------------------------------
class CursoCreate(BaseModel):
    nome: str
    carga_horaria_total: Optional[int] = None
    competencias: Optional[str] = None


class CursoOut(CursoCreate):
    id: int

    class Config:
        from_attributes = True


class TurmaCreate(BaseModel):
    nome: str
    ano: Optional[int] = None
    semestre: Optional[int] = None
    turno: Optional[str] = None
    id_curso: int


class TurmaOut(TurmaCreate):
    id: int
    curso: Optional[CursoOut] = None

    class Config:
        from_attributes = True


# ------------------------------------------------------------
# Empresas e Supervisores
# ------------------------------------------------------------
class EmpresaCreate(BaseModel):
    razao_social: str
    nome_fantasia: Optional[str] = None
    cnpj: Optional[str] = None
    telefone: Optional[str] = None
    email: Optional[EmailStr] = None


class EmpresaOut(EmpresaCreate):
    id: int

    class Config:
        from_attributes = True


class UsuarioUpdate(BaseModel):
    nome: Optional[str] = None
    matricula: Optional[str] = None
    senha: Optional[str] = None
    contato: Optional[str] = None
    email: Optional[EmailStr] = None
    turma: Optional[str] = None
    periodo: Optional[str] = None


class EmpresaUpdate(BaseModel):
    razao_social: Optional[str] = None
    nome_fantasia: Optional[str] = None
    cnpj: Optional[str] = None
    telefone: Optional[str] = None
    email: Optional[EmailStr] = None


class SupervisorExternoCreate(BaseModel):
    nome: str
    email: Optional[EmailStr] = None
    telefone: Optional[str] = None
    cargo: Optional[str] = None
    id_empresa: int


class SupervisorExternoOut(SupervisorExternoCreate):
    id: int
    empresa: Optional[EmpresaOut] = None

    class Config:
        from_attributes = True


class SupervisorExternoUpdate(BaseModel):
    nome: Optional[str] = None
    email: Optional[EmailStr] = None
    telefone: Optional[str] = None
    cargo: Optional[str] = None
    id_empresa: Optional[int] = None


# ------------------------------------------------------------
# ConvÃªnios
# ------------------------------------------------------------
class ConvenioCreate(BaseModel):
    id_empresa: int
    id_curso: int
    data_inicio: Optional[date] = None
    data_fim: Optional[date] = None
    status: Optional[bool] = True
    descricao: Optional[str] = None


class ConvenioOut(ConvenioCreate):
    id: int
    empresa: Optional[EmpresaOut] = None
    curso: Optional[CursoOut] = None

    class Config:
        from_attributes = True


class ConvenioUpdate(BaseModel):
    id_empresa: Optional[int] = None
    id_curso: Optional[int] = None
    data_inicio: Optional[date] = None
    data_fim: Optional[date] = None
    status: Optional[bool] = None
    descricao: Optional[str] = None


# ------------------------------------------------------------
# Justificativas
# ------------------------------------------------------------
class JustificativaStatus(str, Enum):
    pendente = "pendente"
    aprovado = "aprovado"
    rejeitado = "rejeitado"
    expirado = "expirado"


class JustificativaBase(BaseModel):
    tipo: str
    motivo: str
    id_contrato: int
    id_ponto: Optional[int] = None
    data_referencia: Optional[date] = None
    evidencia_url: Optional[str] = None


class JustificativaCreate(JustificativaBase):
    pass


class JustificativaStatusUpdate(BaseModel):
    status: Literal["aprovado", "rejeitado"]
    comentario: Optional[str] = None


class JustificativaLogOut(BaseModel):
    id: int
    status: str
    mensagem: str
    criado_em: datetime

    class Config:
        from_attributes = True


class JustificativaOut(JustificativaBase):
    id: int
    id_aluno: int
    status: JustificativaStatus
    comentario_resolucao: Optional[str] = None
    prazo_resposta: Optional[datetime] = None
    resolvido_em: Optional[datetime] = None
    criado_automaticamente: bool
    criado_em: datetime
    atualizado_em: datetime
    logs: List[JustificativaLogOut] = []

    class Config:
        from_attributes = True


class DiarioStatus(str, Enum):
    pendente = "pendente"
    aprovado = "aprovado"
    rejeitado = "rejeitado"


class DiarioAtividadeCreate(BaseModel):
    id_contrato: int
    data_referencia: date
    resumo: str
    detalhes: Optional[str] = None
    anexo_url: Optional[str] = None


class DiarioAtividadeStatusUpdate(BaseModel):
    status: Literal["aprovado", "rejeitado"]
    comentario: Optional[str] = None


class DiarioAtividadeOut(BaseModel):
    id: int
    id_aluno: int
    id_contrato: int
    data_referencia: date
    resumo: str
    detalhes: Optional[str] = None
    anexo_url: Optional[str] = None
    status: DiarioStatus
    comentario_avaliador: Optional[str] = None
    criado_em: datetime
    atualizado_em: datetime

    class Config:
        from_attributes = True


# ------------------------------------------------------------
# AvaliaÃ§Ãµes
# ------------------------------------------------------------
class AvaliacaoRubricaCreate(BaseModel):
    nome: str
    descricao: Optional[str] = None
    criterios: Optional[str] = None  # JSON string com pesos/descriÃ§Ãµes


class AvaliacaoRubricaOut(AvaliacaoRubricaCreate):
    id: int
    ativo: bool
    criado_em: datetime
    atualizado_em: datetime

    class Config:
        from_attributes = True


class AvaliacaoStatus(str, Enum):
    pendente = "pendente"
    concluida = "concluida"


class AvaliacaoCreate(BaseModel):
    id_contrato: int
    id_rubrica: int
    periodo: Optional[str] = None
    notas: Optional[dict] = None
    feedback: Optional[str] = None
    plano_acao: Optional[str] = None


class AvaliacaoOut(AvaliacaoCreate):
    id: int
    id_avaliador: int
    status: AvaliacaoStatus
    exportado: bool
    criado_em: datetime
    atualizado_em: datetime
    rubrica: Optional[AvaliacaoRubricaOut] = None

    @field_validator("notas", mode="before")
    @classmethod
    def ensure_notas_dict(cls, value):
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return None
        return value

    @field_validator("status", mode="before")
    @classmethod
    def normalize_status_value(cls, value):
        if isinstance(value, str):
            normalized = (
                unicodedata.normalize("NFKD", value)
                .encode("ascii", "ignore")
                .decode("ascii")
                .lower()
                .strip()
            )
            return normalized
        return value

    class Config:
        from_attributes = True


# ------------------------------------------------------------
# EndereÃ§os
# ------------------------------------------------------------
class EnderecoCreate(BaseModel):
    cep: Optional[str] = None
    logradouro: str
    cidade: str
    estado: str
    numero: Optional[str] = None
    bairro: Optional[str] = None


class EnderecoOut(EnderecoCreate):
    id: int
    lat: Optional[float] = None
    long: Optional[float] = None

    class Config:
        from_attributes = True


# ------------------------------------------------------------
# Contratos
# ------------------------------------------------------------
class ContratoCreate(BaseModel):
    # aceita snake_case e camelCase
    id_aluno: int = Field(validation_alias=AliasChoices("id_aluno", "idAluno"))
    id_professor: int = Field(validation_alias=AliasChoices("id_professor", "idProfessor"))
    id_endereco: int = Field(validation_alias=AliasChoices("id_endereco", "idEndereco"))
    data_inicio: Optional[date] = Field(default=None, validation_alias=AliasChoices("data_inicio", "dataInicio"))
    data_final: Optional[date] = Field(default=None, validation_alias=AliasChoices("data_final", "dataFinal"))
    status: Optional[bool] = Field(default=True, validation_alias=AliasChoices("status", "ativo"))
    hora_inicio_prevista: Optional[time] = Field(
        default=None, validation_alias=AliasChoices("hora_inicio_prevista", "horaInicioPrevista")
    )
    hora_fim_prevista: Optional[time] = Field(
        default=None, validation_alias=AliasChoices("hora_fim_prevista", "horaFimPrevista")
    )
    tolerancia_minutos: Optional[int] = Field(
        default=None, validation_alias=AliasChoices("tolerancia_minutos", "toleranciaMinutos")
    )
    raio_permitido_metros: Optional[int] = Field(
        default=None, validation_alias=AliasChoices("raio_permitido_metros", "raioPermitidoMetros")
    )
    id_turma: Optional[int] = Field(default=None, validation_alias=AliasChoices("id_turma", "idTurma"))
    id_convenio: Optional[int] = Field(default=None, validation_alias=AliasChoices("id_convenio", "idConvenio"))
    id_supervisor_externo: Optional[int] = Field(
        default=None, validation_alias=AliasChoices("id_supervisor_externo", "idSupervisorExterno")
    )

    @field_validator("status", mode="before")
    @classmethod
    def coerce_status(cls, v):
        if v is None:
            return True
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            val = v.strip().lower()
            if val in {"ativo", "true", "1", "on", "yes", "y"}:
                return True
            if val in {"inativo", "false", "0", "off", "no", "n"}:
                return False
        raise ValueError("status deve ser booleano ou 'Ativo'/'Inativo'")

    @staticmethod
    def _parse_time(value: Union[str, time, None]) -> Optional[time]:
        if value in (None, ""):
            return None
        if isinstance(value, time):
            return value
        if isinstance(value, str):
            text = value.strip()
            for fmt in ("%H:%M", "%H:%M:%S"):
                try:
                    return datetime.strptime(text, fmt).time()
                except ValueError:
                    continue
        raise ValueError("HorÃ¡rio invÃ¡lido. Use HH:MM.")

    @field_validator("hora_inicio_prevista", "hora_fim_prevista", mode="before")
    @classmethod
    def coerce_time(cls, v):
        return cls._parse_time(v)


class ContratoOut(BaseModel):
    id: int
    id_aluno: int
    id_professor: int
    id_endereco: int
    data_inicio: Optional[date] = None
    data_final: Optional[date] = None
    status: bool
    hora_inicio_prevista: Optional[time] = None
    hora_fim_prevista: Optional[time] = None
    tolerancia_minutos: Optional[int] = None
    raio_permitido_metros: Optional[int] = None
    id_turma: Optional[int] = None
    id_convenio: Optional[int] = None
    id_supervisor_externo: Optional[int] = None
    aluno: Optional[UsuarioOut] = None
    professor: Optional[UsuarioOut] = None
    endereco: Optional[EnderecoOut] = None
    turma: Optional[TurmaOut] = None
    convenio: Optional[ConvenioOut] = None
    supervisor_externo: Optional[SupervisorExternoOut] = None

    class Config:
        from_attributes = True


# ------------------------------------------------------------
# Ponto EletrÃ´nico
# ------------------------------------------------------------
class PontoLocalizacaoIn(BaseModel):
    """Payload de entrada do cliente: apenas a localizaÃ§Ã£o atual."""
    latitude_atual: float = Field(validation_alias=AliasChoices("latitude_atual", "latitudeAtual"))
    longitude_atual: float = Field(validation_alias=AliasChoices("longitude_atual", "longitudeAtual"))
    precisao_metros: Optional[float] = Field(
        default=None, validation_alias=AliasChoices("precisao_metros", "precisaoMetros")
    )


class PontoCheckLocation(BaseModel):
    """Payload interno: inclui id_aluno + localizaÃ§Ã£o (compat com legado)."""
    id_aluno: int = Field(validation_alias=AliasChoices("id_aluno", "idAluno"))
    latitude_atual: float = Field(validation_alias=AliasChoices("latitude_atual", "latitudeAtual"))
    longitude_atual: float = Field(validation_alias=AliasChoices("longitude_atual", "longitudeAtual"))
    precisao_metros: Optional[float] = Field(
        default=None, validation_alias=AliasChoices("precisao_metros", "precisaoMetros")
    )


class PontoOut(BaseModel):
    id: int
    id_contrato: int
    data: date
    hora_entrada: datetime
    hora_saida: Optional[datetime] = None
    tempo_trabalhado_minutos: Optional[int] = None
    ativo: bool
    entrada_latitude: Optional[float] = None
    entrada_longitude: Optional[float] = None
    saida_latitude: Optional[float] = None
    saida_longitude: Optional[float] = None
    validado_localizacao: bool
    alerta: Optional[str] = None

    class Config:
        from_attributes = True


class PontoToggleOut(BaseModel):
    acao: Literal["aberto", "fechado"]
    ponto: PontoOut


class PontoVerificacaoOut(BaseModel):
    dentro_area: bool
    distancia_m: Optional[float] = None
    raio_permitido_m: Optional[float] = None
    mensagem: str
    alerta: Optional[str] = None


class PontoTimelineOut(BaseModel):
    data: date
    total_minutos: int
    esperado_minutos: Optional[int] = None
    saldo_minutos: Optional[int] = None
    pontos: List[PontoOut]
    justificativas: List[JustificativaOut]
    diarios: List[DiarioAtividadeOut]
    avaliacoes: List[AvaliacaoOut]
    contratos: List[ContratoOut] = []


# ------------------------------------------------------------
# Documentos
# ------------------------------------------------------------
class DocumentoTipo(str, Enum):
    tce = "tce"
    plano_atividades = "plano_atividades"
    aditivo = "aditivo"
    outro = "outro"


def normalize_documento_tipo(value: Optional[Union[str, "DocumentoTipo"]]) -> Optional["DocumentoTipo"]:
    if value is None or isinstance(value, DocumentoTipo):
        return value
    normalized = (
        unicodedata.normalize("NFKD", value)
        .encode("ascii", "ignore")
        .decode("ascii")
        .strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )
    mapping = {
        "tce": DocumentoTipo.tce,
        "termo_compromisso": DocumentoTipo.tce,
        "termo_de_compromisso": DocumentoTipo.tce,
        "plano_atividades": DocumentoTipo.plano_atividades,
        "plano_de_atividades": DocumentoTipo.plano_atividades,
        "plano_de_atividade": DocumentoTipo.plano_atividades,
        "plano_de_atividades_do_estagio": DocumentoTipo.plano_atividades,
        "plano_de_atividades_do_estagio_supervisionado": DocumentoTipo.plano_atividades,
        "aditivo": DocumentoTipo.aditivo,
        "aditivo_contrato": DocumentoTipo.aditivo,
        "aditivo_de_contrato": DocumentoTipo.aditivo,
        "outro": DocumentoTipo.outro,
    }
    return mapping.get(normalized, DocumentoTipo.outro)


class DocumentoStatus(str, Enum):
    pendente = "pendente"
    aprovado = "aprovado"
    rejeitado = "rejeitado"


class DocumentoCreate(BaseModel):
    id_contrato: int
    tipo: DocumentoTipo
    arquivo_url: Optional[str] = None
    observacoes: Optional[str] = None
    status: Optional[DocumentoStatus] = DocumentoStatus.pendente

    @field_validator("tipo", mode="before")
    @classmethod
    def validate_tipo(cls, value):
        normalized = normalize_documento_tipo(value)
        if normalized is None:
            raise ValueError("Tipo de documento invalido.")
        return normalized


class DocumentoUpdate(BaseModel):
    tipo: Optional[DocumentoTipo] = None
    arquivo_url: Optional[str] = None
    status: Optional[DocumentoStatus] = None
    observacoes: Optional[str] = None
    comentario: Optional[str] = None

    @field_validator("tipo", mode="before")
    @classmethod
    def validate_tipo(cls, value):
        return normalize_documento_tipo(value)


class DocumentoLogOut(BaseModel):
    id: int
    status: DocumentoStatus
    comentario: Optional[str] = None
    usuario: Optional[UsuarioOut] = None
    criado_em: datetime

    class Config:
        from_attributes = True


class DocumentoOut(DocumentoCreate):
    id: int
    status: DocumentoStatus
    criado_em: datetime
    atualizado_em: datetime
    logs: List[DocumentoLogOut] = []

    class Config:
        from_attributes = True

    @field_validator("tipo", mode="before")
    @classmethod
    def validate_tipo(cls, value):
        normalized = normalize_documento_tipo(value)
        if normalized is None:
            raise ValueError("Tipo de documento invalido.")
        return normalized


class DocumentoResumoOut(BaseModel):
    pendentes: int
    aprovados: int
    rejeitados: int


class DocumentoUploadIn(BaseModel):
    filename: str
    content_base64: str


class DocumentoUploadOut(BaseModel):
    url: str


class DocumentoAnalyticsGroup(str, Enum):
    curso = "curso"
    empresa = "empresa"
    periodo = "periodo"


class DocumentoAnalyticsItem(BaseModel):
    chave: Optional[str] = None
    label: str
    pendentes: int
    aprovados: int
    rejeitados: int


class DocumentoExportInlineOut(BaseModel):
    filename: str
    mime_type: str
    content_base64: str


class AlunoImportRequest(BaseModel):
    registros: List["AlunoCadastroIn"]


class AlunoImportResponse(BaseModel):
    total: int
    importados: int
    erros: List[str]


# ------------------------------------------------------------
# Cadastro Agregado de Aluno
# ------------------------------------------------------------
class AlunoCadastroIn(BaseModel):
    nome: str
    matricula: str
    senha: Optional[str] = None
    celular: str
    email: EmailStr
    turma: str
    periodo: Optional[str] = None
    cep: Optional[str] = None
    logradouro: str
    numero: Optional[str] = None
    bairro: Optional[str] = None
    cidade: str
    estado: str
    data_inicio: Optional[date] = Field(default=None, validation_alias=AliasChoices("data_inicio", "dataInicio"))
    data_final: Optional[date] = Field(default=None, validation_alias=AliasChoices("data_final", "dataFim"))
    id_professor: Optional[int] = Field(default=None, validation_alias=AliasChoices("id_professor", "idProfessor"))
    hora_inicio_prevista: Optional[time] = Field(
        default=None, validation_alias=AliasChoices("hora_inicio_prevista", "horaInicioPrevista")
    )
    hora_fim_prevista: Optional[time] = Field(
        default=None, validation_alias=AliasChoices("hora_fim_prevista", "horaFimPrevista")
    )
    tolerancia_minutos: Optional[int] = Field(
        default=None, validation_alias=AliasChoices("tolerancia_minutos", "toleranciaMinutos")
    )
    raio_permitido_metros: Optional[int] = Field(
        default=None, validation_alias=AliasChoices("raio_permitido_metros", "raioPermitidoMetros")
    )
    id_turma: Optional[int] = Field(default=None, validation_alias=AliasChoices("id_turma", "idTurma"))
    id_convenio: Optional[int] = Field(default=None, validation_alias=AliasChoices("id_convenio", "idConvenio"))
    id_supervisor_externo: Optional[int] = Field(
        default=None, validation_alias=AliasChoices("id_supervisor_externo", "idSupervisorExterno")
    )

    @field_validator("data_inicio", "data_final", mode="before")
    @classmethod
    def parse_br_date(cls, v):
        if v is None or v == "":
            return None
        if isinstance(v, date):
            return v
        if isinstance(v, datetime):
            return v.date()
        if isinstance(v, str):
            text = v.strip()
            for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
                try:
                    return datetime.strptime(text, fmt).date()
                except ValueError:
                    continue
        raise ValueError("Data invÃ¡lida. Use dd/mm/aaaa ou ISO (YYYY-MM-DD).")

    @field_validator("estado", mode="before")
    @classmethod
    def uppercase_estado(cls, v):
        if v is None:
            return v
        if isinstance(v, str):
            return v.strip().upper()
        return v

    @staticmethod
    def _parse_time(value: Union[str, time, None]) -> Optional[time]:
        if value in (None, ""):
            return None
        if isinstance(value, time):
            return value
        if isinstance(value, str):
            text = value.strip()
            for fmt in ("%H:%M", "%H:%M:%S"):
                try:
                    return datetime.strptime(text, fmt).time()
                except ValueError:
                    continue
        raise ValueError("HorÃ¡rio invÃ¡lido. Use HH:MM.")

    @field_validator("hora_inicio_prevista", "hora_fim_prevista", mode="before")
    @classmethod
    def coerce_time(cls, v):
        return cls._parse_time(v)


class AlunoCadastroResponse(BaseModel):
    usuario: UsuarioOut
    endereco: EnderecoOut
    contrato: ContratoOut


# ------------------------------------------------------------
# Auth
# ------------------------------------------------------------
class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    matricula: Optional[str] = None
    uid: Optional[int] = None

