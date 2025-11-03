from sqlalchemy import Column, Integer, String, Date, DateTime, Boolean, Float, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base

class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(255), nullable=False)
    matricula = Column(String(50), unique=True, nullable=False, index=True)
    senha_hash = Column(String(255), nullable=False)
    contato = Column(String(50), nullable=True)
    email = Column(String(255), nullable=False)
    turma = Column(String(50), nullable=True)
    tipo_acesso = Column(String(20), nullable=False, default="aluno")

    contratos_aluno = relationship("Contrato", back_populates="aluno", foreign_keys="Contrato.id_aluno")
    contratos_professor = relationship("Contrato", back_populates="professor", foreign_keys="Contrato.id_professor")


class Endereco(Base):
    __tablename__ = "enderecos"

    id = Column(Integer, primary_key=True, index=True)
    cep = Column(String(15), nullable=True)
    logradouro = Column(String(255), nullable=False)
    cidade = Column(String(120), nullable=False)
    estado = Column(String(10), nullable=False)
    numero = Column(String(30), nullable=True)  # <- STRING (não numeric)
    bairro = Column(String(120), nullable=True)
    lat = Column(Float, nullable=True)
    long = Column(Float, nullable=True)

    contratos = relationship("Contrato", back_populates="endereco")


class Contrato(Base):
    __tablename__ = "contratos"

    id = Column(Integer, primary_key=True, index=True)
    id_aluno = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    id_professor = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    id_endereco = Column(Integer, ForeignKey("enderecos.id"), nullable=False)
    data_inicio = Column(Date, nullable=True)
    data_final = Column(Date, nullable=True)
    status = Column(Boolean, nullable=False, default=True)  # <- BOOLEAN

    aluno = relationship("Usuario", foreign_keys=[id_aluno], back_populates="contratos_aluno")
    professor = relationship("Usuario", foreign_keys=[id_professor], back_populates="contratos_professor")
    endereco = relationship("Endereco", back_populates="contratos")
    pontos = relationship("Ponto", back_populates="contrato")


class Ponto(Base):
    __tablename__ = "pontos"

    id = Column(Integer, primary_key=True, index=True)
    id_contrato = Column(Integer, ForeignKey("contratos.id"), nullable=False)  # <- existe
    data = Column(Date, nullable=False)
    hora_entrada = Column(DateTime, nullable=False, default=datetime.utcnow)
    hora_saida = Column(DateTime, nullable=True)
    tempo_trabalhado_minutos = Column(Integer, nullable=True)
    ativo = Column(Boolean, nullable=False, default=True)

    contrato = relationship("Contrato", back_populates="pontos")
