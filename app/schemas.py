from pydantic import BaseModel, EmailStr, Field, AliasChoices, field_validator
from typing import Literal, Optional, Union
from datetime import date, datetime
from enum import Enum

# ------------------------------------------------------------
# Tipos e Usuários
# ------------------------------------------------------------
class TipoUsuario(str, Enum):
    aluno = "aluno"
    professor = "professor"
    admin = "admin"
    coordenador = "coordenador"


class UsuarioCreate(BaseModel):
    nome: str
    matricula: str
    senha: str
    contato: str
    email: EmailStr
    turma: str
    tipo_acesso: Literal["aluno", "professor", "admin", "coordenador"] = "aluno"


class UsuarioOut(BaseModel):
    id: int
    nome: str
    matricula: str
    email: EmailStr
    tipo_acesso: str

    class Config:
        from_attributes = True


# ------------------------------------------------------------
# Endereços
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


class ContratoOut(BaseModel):
    id: int
    id_aluno: int
    id_professor: int
    id_endereco: int
    data_inicio: Optional[date] = None
    data_final: Optional[date] = None
    status: bool
    aluno: Optional[UsuarioOut] = None
    professor: Optional[UsuarioOut] = None
    endereco: Optional[EnderecoOut] = None

    class Config:
        from_attributes = True


# ------------------------------------------------------------
# Ponto Eletrônico
# ------------------------------------------------------------
class PontoLocalizacaoIn(BaseModel):
    """Payload de entrada do cliente: apenas a localização atual."""
    latitude_atual: float = Field(validation_alias=AliasChoices("latitude_atual", "latitudeAtual"))
    longitude_atual: float = Field(validation_alias=AliasChoices("longitude_atual", "longitudeAtual"))


class PontoCheckLocation(BaseModel):
    """Payload interno: inclui id_aluno + localização (compat com legado)."""
    id_aluno: int = Field(validation_alias=AliasChoices("id_aluno", "idAluno"))
    latitude_atual: float = Field(validation_alias=AliasChoices("latitude_atual", "latitudeAtual"))
    longitude_atual: float = Field(validation_alias=AliasChoices("longitude_atual", "longitudeAtual"))


class PontoOut(BaseModel):
    id: int
    id_contrato: int
    data: date
    hora_entrada: datetime
    hora_saida: Optional[datetime] = None
    tempo_trabalhado_minutos: Optional[int] = None
    ativo: bool

    class Config:
        from_attributes = True


# ------------------------------------------------------------
# Auth
# ------------------------------------------------------------
class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    matricula: Optional[str] = None
