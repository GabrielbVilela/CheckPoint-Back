from pydantic import BaseModel, EmailStr
from typing import Literal, Optional
from datetime import date, datetime
from enum import Enum

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
    nome: str
    matricula: str
    email: EmailStr
    tipo_acesso: str
    class Config:
        from_attributes = True


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


class ContratoCreate(BaseModel):
    id_aluno: int
    id_professor: int
    id_endereco: int
    data_inicio: Optional[date] = None
    data_final: Optional[date] = None
    status: Optional[str] = None

class ContratoOut(ContratoCreate):
    id: int
    aluno: Optional[UsuarioOut]
    professor: Optional[UsuarioOut]
    endereco: Optional[EnderecoOut]
    class Config:
        from_attributes = True

# ADICIONE AS CLASSES ABAIXO

class PontoCheckLocation(BaseModel):
    id_aluno: int
    latitude_atual: float
    longitude_atual: float

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

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    matricula: Optional[str] = None