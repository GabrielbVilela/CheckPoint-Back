from sqlalchemy import Column, Integer, String, Date, DateTime, Boolean, Float, ForeignKey, Time, Text
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
    periodo = Column(String(30), nullable=True)
    tipo_acesso = Column(String(20), nullable=False, default="aluno")

    contratos_aluno = relationship("Contrato", back_populates="aluno", foreign_keys="Contrato.id_aluno")
    contratos_professor = relationship("Contrato", back_populates="professor", foreign_keys="Contrato.id_professor")
    justificativas = relationship("Justificativa", back_populates="aluno", foreign_keys="Justificativa.id_aluno")
    diarios = relationship("DiarioAtividade", back_populates="aluno", foreign_keys="DiarioAtividade.id_aluno")
    avaliacoes_realizadas = relationship("Avaliacao", back_populates="avaliador", foreign_keys="Avaliacao.id_avaliador")


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
    hora_inicio_prevista = Column(Time, nullable=True)
    hora_fim_prevista = Column(Time, nullable=True)
    tolerancia_minutos = Column(Integer, nullable=True)
    raio_permitido_metros = Column(Integer, nullable=True)
    id_turma = Column(Integer, ForeignKey("turmas.id"), nullable=True)
    id_convenio = Column(Integer, ForeignKey("convenios.id"), nullable=True)
    id_supervisor_externo = Column(Integer, ForeignKey("supervisores_externos.id"), nullable=True)

    aluno = relationship("Usuario", foreign_keys=[id_aluno], back_populates="contratos_aluno")
    professor = relationship("Usuario", foreign_keys=[id_professor], back_populates="contratos_professor")
    endereco = relationship("Endereco", back_populates="contratos")
    pontos = relationship("Ponto", back_populates="contrato")
    turma = relationship("Turma", back_populates="contratos")
    convenio = relationship("Convenio", back_populates="contratos")
    supervisor_externo = relationship("SupervisorExterno", back_populates="contratos")
    justificativas = relationship("Justificativa", back_populates="contrato")
    diarios = relationship("DiarioAtividade", back_populates="contrato")
    avaliacoes = relationship("Avaliacao", back_populates="contrato")


class Ponto(Base):
    __tablename__ = "pontos"

    id = Column(Integer, primary_key=True, index=True)
    id_contrato = Column(Integer, ForeignKey("contratos.id"), nullable=False)  # <- existe
    data = Column(Date, nullable=False)
    hora_entrada = Column(DateTime, nullable=False, default=datetime.utcnow)
    hora_saida = Column(DateTime, nullable=True)
    tempo_trabalhado_minutos = Column(Integer, nullable=True)
    ativo = Column(Boolean, nullable=False, default=True)
    entrada_latitude = Column(Float, nullable=True)
    entrada_longitude = Column(Float, nullable=True)
    saida_latitude = Column(Float, nullable=True)
    saida_longitude = Column(Float, nullable=True)
    validado_localizacao = Column(Boolean, nullable=False, default=False)
    alerta = Column(String(255), nullable=True)

    contrato = relationship("Contrato", back_populates="pontos")
    justificativas = relationship("Justificativa", back_populates="ponto")


class Curso(Base):
    __tablename__ = "cursos"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(255), nullable=False, unique=True)
    carga_horaria_total = Column(Integer, nullable=True)
    competencias = Column(Text, nullable=True)

    turmas = relationship("Turma", back_populates="curso")
    convenios = relationship("Convenio", back_populates="curso")


class Turma(Base):
    __tablename__ = "turmas"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(255), nullable=False)
    ano = Column(Integer, nullable=True)
    semestre = Column(Integer, nullable=True)
    turno = Column(String(50), nullable=True)
    id_curso = Column(Integer, ForeignKey("cursos.id"), nullable=False)

    curso = relationship("Curso", back_populates="turmas")
    contratos = relationship("Contrato", back_populates="turma")


class Empresa(Base):
    __tablename__ = "empresas"

    id = Column(Integer, primary_key=True, index=True)
    razao_social = Column(String(255), nullable=False)
    nome_fantasia = Column(String(255), nullable=True)
    cnpj = Column(String(20), nullable=True, unique=True)
    telefone = Column(String(30), nullable=True)
    email = Column(String(255), nullable=True)

    supervisores = relationship("SupervisorExterno", back_populates="empresa")
    convenios = relationship("Convenio", back_populates="empresa")


class SupervisorExterno(Base):
    __tablename__ = "supervisores_externos"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    telefone = Column(String(30), nullable=True)
    cargo = Column(String(120), nullable=True)
    id_empresa = Column(Integer, ForeignKey("empresas.id"), nullable=False)

    empresa = relationship("Empresa", back_populates="supervisores")
    contratos = relationship("Contrato", back_populates="supervisor_externo")


class Convenio(Base):
    __tablename__ = "convenios"

    id = Column(Integer, primary_key=True, index=True)
    id_empresa = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    id_curso = Column(Integer, ForeignKey("cursos.id"), nullable=False)
    data_inicio = Column(Date, nullable=True)
    data_fim = Column(Date, nullable=True)
    status = Column(Boolean, nullable=False, default=True)
    descricao = Column(Text, nullable=True)

    empresa = relationship("Empresa", back_populates="convenios")
    curso = relationship("Curso", back_populates="convenios")
    contratos = relationship("Contrato", back_populates="convenio")

class Justificativa(Base):
    __tablename__ = "justificativas"

    id = Column(Integer, primary_key=True, index=True)
    id_aluno = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    id_contrato = Column(Integer, ForeignKey("contratos.id"), nullable=False)
    id_ponto = Column(Integer, ForeignKey("pontos.id"), nullable=True)
    tipo = Column(String(50), nullable=False)
    motivo = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="pendente")
    comentario_resolucao = Column(Text, nullable=True)
    evidencia_url = Column(String(255), nullable=True)
    data_referencia = Column(Date, nullable=True)
    prazo_resposta = Column(DateTime, nullable=True)
    resolvido_em = Column(DateTime, nullable=True)
    criado_automaticamente = Column(Boolean, nullable=False, default=False)
    criado_em = Column(DateTime, nullable=False, default=datetime.utcnow)
    atualizado_em = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    aluno = relationship("Usuario", back_populates="justificativas", foreign_keys=[id_aluno])
    contrato = relationship("Contrato", back_populates="justificativas")
    ponto = relationship("Ponto", back_populates="justificativas")
    logs = relationship("JustificativaLog", back_populates="justificativa", cascade="all, delete-orphan")


class JustificativaLog(Base):
    __tablename__ = "justificativa_logs"

    id = Column(Integer, primary_key=True, index=True)
    justificativa_id = Column(Integer, ForeignKey("justificativas.id"), nullable=False)
    status = Column(String(20), nullable=False)
    mensagem = Column(Text, nullable=False)
    criado_em = Column(DateTime, nullable=False, default=datetime.utcnow)

    justificativa = relationship("Justificativa", back_populates="logs")


class DiarioAtividade(Base):
    __tablename__ = "diarios_atividade"

    id = Column(Integer, primary_key=True, index=True)
    id_aluno = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    id_contrato = Column(Integer, ForeignKey("contratos.id"), nullable=False)
    data_referencia = Column(Date, nullable=False)
    resumo = Column(String(255), nullable=False)
    detalhes = Column(Text, nullable=True)
    anexo_url = Column(String(255), nullable=True)
    status = Column(String(20), nullable=False, default="pendente")
    comentario_avaliador = Column(Text, nullable=True)
    criado_em = Column(DateTime, nullable=False, default=datetime.utcnow)
    atualizado_em = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    aluno = relationship("Usuario", back_populates="diarios", foreign_keys=[id_aluno])
    contrato = relationship("Contrato", back_populates="diarios")


class AvaliacaoRubrica(Base):
    __tablename__ = "avaliacao_rubricas"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(255), nullable=False, unique=True)
    descricao = Column(Text, nullable=True)
    criterios = Column(Text, nullable=True)
    ativo = Column(Boolean, nullable=False, default=True)
    criado_em = Column(DateTime, nullable=False, default=datetime.utcnow)
    atualizado_em = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    avaliacoes = relationship("Avaliacao", back_populates="rubrica")


class Avaliacao(Base):
    __tablename__ = "avaliacoes"

    id = Column(Integer, primary_key=True, index=True)
    id_contrato = Column(Integer, ForeignKey("contratos.id"), nullable=False)
    id_rubrica = Column(Integer, ForeignKey("avaliacao_rubricas.id"), nullable=False)
    id_avaliador = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    periodo = Column(String(50), nullable=True)
    notas = Column(Text, nullable=True)
    feedback = Column(Text, nullable=True)
    plano_acao = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="pendente")
    exportado = Column(Boolean, nullable=False, default=False)
    criado_em = Column(DateTime, nullable=False, default=datetime.utcnow)
    atualizado_em = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    contrato = relationship("Contrato", back_populates="avaliacoes")
    rubrica = relationship("AvaliacaoRubrica", back_populates="avaliacoes")
    avaliador = relationship("Usuario", back_populates="avaliacoes_realizadas", foreign_keys=[id_avaliador])


class Documento(Base):
    __tablename__ = "documentos"

    id = Column(Integer, primary_key=True, index=True)
    id_contrato = Column(Integer, ForeignKey("contratos.id"), nullable=False)
    tipo = Column(String(50), nullable=False)
    arquivo_url = Column(String(255), nullable=True)
    status = Column(String(20), nullable=False, default="pendente")
    observacoes = Column(Text, nullable=True)
    criado_em = Column(DateTime, default=datetime.utcnow)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    contrato = relationship("Contrato")
