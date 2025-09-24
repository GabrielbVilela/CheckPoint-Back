from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey, Enum, DateTime, Boolean, func
from sqlalchemy.orm import relationship
from .database import Base
import enum
from datetime import date

class TipoUsuario(str, enum.Enum):
    aluno = "aluno"
    professor = "professor"

class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False)
    matricula = Column(String, unique=True, index=True, nullable=False)
    senha_hash = Column(String, nullable=False)
    contato = Column(String, nullable=True)
    email = Column(String, unique=True, index=True, nullable=False)
    turma = Column(String, nullable=True)
    tipo_acesso = Column(String, nullable=False, default="aluno")

    contratos_aluno = relationship("Contrato", foreign_keys="[Contrato.id_aluno]", back_populates="aluno")
    contratos_professor = relationship("Contrato", foreign_keys="[Contrato.id_professor]", back_populates="professor")


class Endereco(Base):
    __tablename__ = "enderecos"
    id = Column(Integer, primary_key=True, index=True)
    cep = Column(String, nullable=True)
    logradouro = Column(String, nullable=False)
    cidade = Column(String, nullable=False)
    estado = Column(String, nullable=False)
    numero = Column(String, nullable=True)
    bairro = Column(String, nullable=True)
    lat = Column(Float, nullable=True)
    long = Column("long", Float, nullable=True)

    contratos = relationship("Contrato", back_populates="endereco")


class Contrato(Base):
    __tablename__ = "contratos"
    id = Column(Integer, primary_key=True, index=True)
    id_aluno = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    id_professor = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    id_endereco = Column(Integer, ForeignKey("enderecos.id"), nullable=False)
    data_inicio = Column(Date, nullable=True)
    data_final = Column(Date, nullable=True)
    status = Column(String, nullable=True)

    aluno = relationship("Usuario", foreign_keys=[id_aluno], back_populates="contratos_aluno")
    professor = relationship("Usuario", foreign_keys=[id_professor], back_populates="contratos_professor")
    endereco = relationship("Endereco", back_populates="contratos")
    pontos = relationship("Ponto", back_populates="contrato")

# ADICIONE A CLASSE ABAIXO
class Ponto(Base):
    __tablename__ = "pontos"

    id = Column(Integer, primary_key=True, index=True)
    id_contrato = Column(Integer, ForeignKey("contratos.id"), nullable=False)
    data = Column(Date, nullable=False, default=date.today)
    hora_entrada = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    hora_saida = Column(DateTime(timezone=True), nullable=True)
    tempo_trabalhado_minutos = Column(Integer, nullable=True)
    ativo = Column(Boolean, default=True, nullable=False)

    contrato = relationship("Contrato", back_populates="pontos")
