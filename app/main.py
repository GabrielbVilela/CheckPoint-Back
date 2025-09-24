from contextlib import asynccontextmanager
from typing import Optional, List

from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel

# --- Imports do projeto ---
from app import crud, schemas, models
from app.database import SessionLocal, engine 

# --- Lifespan da Aplicação ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("INFO: Iniciando aplicação e criando tabelas do banco de dados...")
    models.Base.metadata.create_all(bind=engine)
    yield
    print("INFO: Encerrando aplicação.")

app = FastAPI(lifespan=lifespan)

# --- Configuração do CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Em produção, restrinja ao domínio do frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Schema para Login ---
class UsuarioLogin(BaseModel):
    matricula: str
    senha: str

# --- Dependência de sessão do Banco ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# =============================================================================
# Endpoints
# =============================================================================

@app.post("/register", response_model=schemas.UsuarioOut, status_code=status.HTTP_201_CREATED)
def register(usuario: schemas.UsuarioCreate, db: Session = Depends(get_db)):
    # Verifica duplicidade de e-mail
    if crud.get_usuario_by_email(db, email=usuario.email):
        raise HTTPException(status_code=400, detail="E-mail já cadastrado")
    # Verifica duplicidade de matrícula
    if crud.get_usuario_by_matricula(db, matricula=usuario.matricula):
        raise HTTPException(status_code=400, detail="Matrícula já cadastrada")

    return crud.create_usuario(db=db, usuario=usuario)

@app.post("/login", response_model=schemas.UsuarioOut)
def login(usuario: UsuarioLogin, db: Session = Depends(get_db)):
    db_user = crud.get_usuario_by_matricula(db, matricula=usuario.matricula)

    if not db_user or not crud.verify_password(usuario.senha, db_user.senha_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Matrícula ou senha inválida",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return db_user

@app.get("/usuarios", response_model=List[schemas.UsuarioOut])
def listar_usuarios(
    tipo: Optional[schemas.TipoUsuario] = Query(None, description="Filtra por tipo de usuário (aluno ou professor)"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    return crud.list_usuarios(db, tipo=tipo, skip=skip, limit=limit)
# =============================================================================
# Endpoints para Endereços
# =============================================================================

@app.post("/enderecos", response_model=schemas.EnderecoOut, status_code=status.HTTP_201_CREATED, tags=["Endereços"])
def create_endereco(endereco: schemas.EnderecoCreate, db: Session = Depends(get_db)):
    """
    Cria um novo endereço.
    As coordenadas de latitude e longitude são obtidas automaticamente
    através da API do Google Geocoding.
    """
    return crud.create_endereco(db=db, endereco=endereco)


# =============================================================================
# Endpoints para Contratos
# =============================================================================

@app.post("/contratos", response_model=schemas.ContratoOut, status_code=status.HTTP_201_CREATED, tags=["Contratos"])
def create_contrato(contrato: schemas.ContratoCreate, db: Session = Depends(get_db)):
    """
    Cria um novo contrato de estágio, vinculando um aluno, um professor e um endereço.
    """
    return crud.create_contrato(db=db, contrato=contrato)

@app.get("/contratos", response_model=List[schemas.ContratoOut], tags=["Contratos"])
def read_contratos(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    Retorna uma lista de todos os contratos.
    """
    contratos = crud.get_contratos(db, skip=skip, limit=limit)
    return contratos

@app.get("/contratos/{contrato_id}", response_model=schemas.ContratoOut, tags=["Contratos"])
def read_contrato(contrato_id: int, db: Session = Depends(get_db)):
    """
    Busca um contrato específico pelo seu ID.
    """
    db_contrato = crud.get_contrato_by_id(db, contrato_id=contrato_id)
    if db_contrato is None:
        raise HTTPException(status_code=404, detail="Contrato não encontrado")
    return db_contrato
