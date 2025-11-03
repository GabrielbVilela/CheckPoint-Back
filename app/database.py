# database.py
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    DB_USER = os.getenv("POSTGRES_USER", "postgres")
    DB_PASS = os.getenv("POSTGRES_PASSWORD", "postgres")
    DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
    DB_PORT = os.getenv("POSTGRES_PORT", "5432")
    DB_NAME = os.getenv("POSTGRES_DB", "backend_db")
    DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

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
