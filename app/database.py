# database.py
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
if not DATABASE_URL:
    DB_USER = os.getenv("POSTGRES_USER", "postgres")
    DB_PASS = os.getenv("POSTGRES_PASSWORD", "a91796aced16b4794fab")
    DB_HOST = os.getenv("POSTGRES_HOST", "147.93.8.172")
    DB_PORT = os.getenv("POSTGRES_PORT", "5433")
    DB_NAME = os.getenv("POSTGRES_DB", "checheckpoint_db")
    DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}?sslmode=disable"

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """
    Dependency-style session generator shared across the app.
    Keeps logic in a single place to avoid circular imports.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_enderecos_columns():
    stmts = [
        """
        CREATE TABLE IF NOT EXISTS enderecos (
            id SERIAL PRIMARY KEY
        )
        """,
        "ALTER TABLE enderecos ADD COLUMN IF NOT EXISTS cep VARCHAR(15)",
        "ALTER TABLE enderecos ADD COLUMN IF NOT EXISTS logradouro VARCHAR(255)",
        "ALTER TABLE enderecos ADD COLUMN IF NOT EXISTS cidade VARCHAR(120)",
        "ALTER TABLE enderecos ADD COLUMN IF NOT EXISTS estado VARCHAR(10)",
        "ALTER TABLE enderecos ADD COLUMN IF NOT EXISTS numero VARCHAR(30)",
        "ALTER TABLE enderecos ADD COLUMN IF NOT EXISTS bairro VARCHAR(120)",
        "ALTER TABLE enderecos ADD COLUMN IF NOT EXISTS lat DOUBLE PRECISION",
        "ALTER TABLE enderecos ADD COLUMN IF NOT EXISTS long DOUBLE PRECISION",
        "ALTER TABLE enderecos ALTER COLUMN numero TYPE VARCHAR(30) USING numero::text",
    ]
    with engine.begin() as conn:
        for s in stmts:
            conn.execute(text(s))

def ensure_contratos_columns_and_boolean_status():
    stmts = [
        "CREATE TABLE IF NOT EXISTS contratos (id SERIAL PRIMARY KEY)",
        "ALTER TABLE contratos ADD COLUMN IF NOT EXISTS id_aluno INTEGER",
        "ALTER TABLE contratos ADD COLUMN IF NOT EXISTS id_professor INTEGER",
        "ALTER TABLE contratos ADD COLUMN IF NOT EXISTS id_endereco INTEGER",
        "ALTER TABLE contratos ADD COLUMN IF NOT EXISTS data_inicio DATE",
        "ALTER TABLE contratos ADD COLUMN IF NOT EXISTS data_final DATE",
        "ALTER TABLE contratos ADD COLUMN IF NOT EXISTS status BOOLEAN",
        "ALTER TABLE contratos ADD COLUMN IF NOT EXISTS hora_inicio_prevista TIME",
        "ALTER TABLE contratos ADD COLUMN IF NOT EXISTS hora_fim_prevista TIME",
        "ALTER TABLE contratos ADD COLUMN IF NOT EXISTS tolerancia_minutos INTEGER",
        "ALTER TABLE contratos ADD COLUMN IF NOT EXISTS raio_permitido_metros INTEGER",
        "ALTER TABLE contratos ADD COLUMN IF NOT EXISTS id_turma INTEGER",
        "ALTER TABLE contratos ADD COLUMN IF NOT EXISTS id_convenio INTEGER",
        "ALTER TABLE contratos ADD COLUMN IF NOT EXISTS id_supervisor_externo INTEGER",
        """
        DO $$
        BEGIN
            BEGIN
                ALTER TABLE contratos ALTER COLUMN status TYPE BOOLEAN USING
                    CASE
                        WHEN status IN ('Ativo','ativo','TRUE','True','true','1') THEN TRUE
                        WHEN status IN ('Inativo','inativo','FALSE','False','false','0') THEN FALSE
                        ELSE status::BOOLEAN
                    END;
            EXCEPTION WHEN others THEN
                NULL;
            END;
        END $$;
        """,
        "ALTER TABLE contratos ALTER COLUMN status SET DEFAULT TRUE",
        "UPDATE contratos SET status = TRUE WHERE status IS NULL",
        "ALTER TABLE contratos ALTER COLUMN status SET NOT NULL",
    ]
    with engine.begin() as conn:
        for s in stmts:
            conn.execute(text(s))


def ensure_usuarios_columns():
    stmts = [
        "CREATE TABLE IF NOT EXISTS usuarios (id SERIAL PRIMARY KEY)",
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS periodo VARCHAR(30)",
    ]
    with engine.begin() as conn:
        for s in stmts:
            conn.execute(text(s))


def ensure_pontos_columns():
    stmts = [
        "CREATE TABLE IF NOT EXISTS pontos (id SERIAL PRIMARY KEY)",
        "ALTER TABLE pontos ADD COLUMN IF NOT EXISTS entrada_latitude DOUBLE PRECISION",
        "ALTER TABLE pontos ADD COLUMN IF NOT EXISTS entrada_longitude DOUBLE PRECISION",
        "ALTER TABLE pontos ADD COLUMN IF NOT EXISTS saida_latitude DOUBLE PRECISION",
        "ALTER TABLE pontos ADD COLUMN IF NOT EXISTS saida_longitude DOUBLE PRECISION",
        "ALTER TABLE pontos ADD COLUMN IF NOT EXISTS validado_localizacao BOOLEAN",
        "ALTER TABLE pontos ADD COLUMN IF NOT EXISTS alerta VARCHAR(255)",
        "UPDATE pontos SET validado_localizacao = FALSE WHERE validado_localizacao IS NULL",
        "ALTER TABLE pontos ALTER COLUMN validado_localizacao SET DEFAULT FALSE",
        "ALTER TABLE pontos ALTER COLUMN validado_localizacao SET NOT NULL",
    ]
    with engine.begin() as conn:
        for s in stmts:
            conn.execute(text(s))

def ensure_justificativas_columns():
    stmts = [
        "CREATE TABLE IF NOT EXISTS justificativas (id SERIAL PRIMARY KEY)",
        "ALTER TABLE justificativas ADD COLUMN IF NOT EXISTS id_aluno INTEGER",
        "ALTER TABLE justificativas ADD COLUMN IF NOT EXISTS id_contrato INTEGER",
        "ALTER TABLE justificativas ADD COLUMN IF NOT EXISTS id_ponto INTEGER",
        "ALTER TABLE justificativas ADD COLUMN IF NOT EXISTS tipo VARCHAR(50)",
        "ALTER TABLE justificativas ADD COLUMN IF NOT EXISTS motivo TEXT",
        "ALTER TABLE justificativas ADD COLUMN IF NOT EXISTS status VARCHAR(20)",
        "ALTER TABLE justificativas ADD COLUMN IF NOT EXISTS comentario_resolucao TEXT",
        "ALTER TABLE justificativas ADD COLUMN IF NOT EXISTS evidencia_url VARCHAR(255)",
        "ALTER TABLE justificativas ADD COLUMN IF NOT EXISTS data_referencia DATE",
        "ALTER TABLE justificativas ADD COLUMN IF NOT EXISTS prazo_resposta TIMESTAMP",
        "ALTER TABLE justificativas ADD COLUMN IF NOT EXISTS resolvido_em TIMESTAMP",
        "ALTER TABLE justificativas ADD COLUMN IF NOT EXISTS criado_automaticamente BOOLEAN",
        "ALTER TABLE justificativas ADD COLUMN IF NOT EXISTS criado_em TIMESTAMP",
        "ALTER TABLE justificativas ADD COLUMN IF NOT EXISTS atualizado_em TIMESTAMP",
        "UPDATE justificativas SET criado_automaticamente = FALSE WHERE criado_automaticamente IS NULL",
        "ALTER TABLE justificativas ALTER COLUMN status SET DEFAULT 'pendente'",
        "ALTER TABLE justificativas ALTER COLUMN criado_automaticamente SET DEFAULT FALSE",
        "ALTER TABLE justificativas ALTER COLUMN criado_em SET DEFAULT NOW()",
        "ALTER TABLE justificativas ALTER COLUMN atualizado_em SET DEFAULT NOW()",
    ]
    stmts_logs = [
        "CREATE TABLE IF NOT EXISTS justificativa_logs (id SERIAL PRIMARY KEY)",
        "ALTER TABLE justificativa_logs ADD COLUMN IF NOT EXISTS justificativa_id INTEGER",
        "ALTER TABLE justificativa_logs ADD COLUMN IF NOT EXISTS status VARCHAR(20)",
        "ALTER TABLE justificativa_logs ADD COLUMN IF NOT EXISTS mensagem TEXT",
        "ALTER TABLE justificativa_logs ADD COLUMN IF NOT EXISTS criado_em TIMESTAMP DEFAULT NOW()",
    ]
    with engine.begin() as conn:
        for s in stmts:
            conn.execute(text(s))
        for s in stmts_logs:
            conn.execute(text(s))

def ensure_diarios_columns():
    stmts = [
        "CREATE TABLE IF NOT EXISTS diarios_atividade (id SERIAL PRIMARY KEY)",
        "ALTER TABLE diarios_atividade ADD COLUMN IF NOT EXISTS id_aluno INTEGER",
        "ALTER TABLE diarios_atividade ADD COLUMN IF NOT EXISTS id_contrato INTEGER",
        "ALTER TABLE diarios_atividade ADD COLUMN IF NOT EXISTS data_referencia DATE",
        "ALTER TABLE diarios_atividade ADD COLUMN IF NOT EXISTS resumo VARCHAR(255)",
        "ALTER TABLE diarios_atividade ADD COLUMN IF NOT EXISTS detalhes TEXT",
        "ALTER TABLE diarios_atividade ADD COLUMN IF NOT EXISTS anexo_url VARCHAR(255)",
        "ALTER TABLE diarios_atividade ADD COLUMN IF NOT EXISTS status VARCHAR(20)",
        "ALTER TABLE diarios_atividade ADD COLUMN IF NOT EXISTS comentario_avaliador TEXT",
        "ALTER TABLE diarios_atividade ADD COLUMN IF NOT EXISTS criado_em TIMESTAMP DEFAULT NOW()",
        "ALTER TABLE diarios_atividade ADD COLUMN IF NOT EXISTS atualizado_em TIMESTAMP DEFAULT NOW()",
        "ALTER TABLE diarios_atividade ALTER COLUMN status SET DEFAULT 'pendente'",
    ]
    with engine.begin() as conn:
        for s in stmts:
            conn.execute(text(s))

def ensure_avaliacoes_columns():
    rubrica_stmts = [
        "CREATE TABLE IF NOT EXISTS avaliacao_rubricas (id SERIAL PRIMARY KEY)",
        "ALTER TABLE avaliacao_rubricas ADD COLUMN IF NOT EXISTS nome VARCHAR(255)",
        "ALTER TABLE avaliacao_rubricas ADD COLUMN IF NOT EXISTS descricao TEXT",
        "ALTER TABLE avaliacao_rubricas ADD COLUMN IF NOT EXISTS criterios TEXT",
        "ALTER TABLE avaliacao_rubricas ADD COLUMN IF NOT EXISTS ativo BOOLEAN DEFAULT TRUE",
        "ALTER TABLE avaliacao_rubricas ADD COLUMN IF NOT EXISTS criado_em TIMESTAMP DEFAULT NOW()",
        "ALTER TABLE avaliacao_rubricas ADD COLUMN IF NOT EXISTS atualizado_em TIMESTAMP DEFAULT NOW()",
    ]
    avaliacao_stmts = [
        "CREATE TABLE IF NOT EXISTS avaliacoes (id SERIAL PRIMARY KEY)",
        "ALTER TABLE avaliacoes ADD COLUMN IF NOT EXISTS id_contrato INTEGER",
        "ALTER TABLE avaliacoes ADD COLUMN IF NOT EXISTS id_rubrica INTEGER",
        "ALTER TABLE avaliacoes ADD COLUMN IF NOT EXISTS id_avaliador INTEGER",
        "ALTER TABLE avaliacoes ADD COLUMN IF NOT EXISTS periodo VARCHAR(50)",
        "ALTER TABLE avaliacoes ADD COLUMN IF NOT EXISTS notas TEXT",
        "ALTER TABLE avaliacoes ADD COLUMN IF NOT EXISTS feedback TEXT",
        "ALTER TABLE avaliacoes ADD COLUMN IF NOT EXISTS plano_acao TEXT",
        "ALTER TABLE avaliacoes ADD COLUMN IF NOT EXISTS status VARCHAR(20)",
        "ALTER TABLE avaliacoes ADD COLUMN IF NOT EXISTS exportado BOOLEAN DEFAULT FALSE",
        "ALTER TABLE avaliacoes ADD COLUMN IF NOT EXISTS criado_em TIMESTAMP DEFAULT NOW()",
        "ALTER TABLE avaliacoes ADD COLUMN IF NOT EXISTS atualizado_em TIMESTAMP DEFAULT NOW()",
    ]
    with engine.begin() as conn:
        for s in rubrica_stmts:
            conn.execute(text(s))
        for s in avaliacao_stmts:
            conn.execute(text(s))


