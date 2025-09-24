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
    allow_origins=["*"],
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

# ... (seus endpoints de usuário, endereço e contrato existentes) ...
@app.post("/register", response_model=schemas.UsuarioOut, status_code=status.HTTP_201_CREATED)
def register(usuario: schemas.UsuarioCreate, db: Session = Depends(get_db)):
    if crud.get_usuario_by_email(db, email=usuario.email):
        raise HTTPException(status_code=400, detail="E-mail já cadastrado")
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

@app.post("/enderecos", response_model=schemas.EnderecoOut, status_code=status.HTTP_201_CREATED, tags=["Endereços"])
def create_endereco(endereco: schemas.EnderecoCreate, db: Session = Depends(get_db)):
    return crud.create_endereco(db=db, endereco=endereco)

@app.post("/contratos", response_model=schemas.ContratoOut, status_code=status.HTTP_201_CREATED, tags=["Contratos"])
def create_contrato(contrato: schemas.ContratoCreate, db: Session = Depends(get_db)):
    return crud.create_contrato(db=db, contrato=contrato)

@app.get("/contratos", response_model=List[schemas.ContratoOut], tags=["Contratos"])
def read_contratos(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    contratos = crud.get_contratos(db, skip=skip, limit=limit)
    return contratos

@app.get("/contratos/{contrato_id}", response_model=schemas.ContratoOut, tags=["Contratos"])
def read_contrato(contrato_id: int, db: Session = Depends(get_db)):
    db_contrato = crud.get_contrato_by_id(db, contrato_id=contrato_id)
    if db_contrato is None:
        raise HTTPException(status_code=404, detail="Contrato não encontrado")
    return db_contrato


# --- ADICIONE OS ENDPOINTS ABAIXO ---

# =============================================================================
# Endpoints para Registro de Ponto
# =============================================================================

@app.post("/ponto/entrada", response_model=schemas.PontoOut, status_code=status.HTTP_201_CREATED, tags=["Ponto Eletrônico"])
def registrar_ponto_entrada(location_data: schemas.PontoCheckLocation, db: Session = Depends(get_db)):
    """
    Registra a entrada de um aluno no ponto eletrônico.

    A API verifica se o aluno possui um contrato ativo e se a sua localização
    atual está dentro do raio permitido (100 metros) do endereço de estágio.
    """
    return crud.registrar_entrada(db=db, location_data=location_data)

@app.patch("/ponto/saida/{id_aluno}", response_model=schemas.PontoOut, tags=["Ponto Eletrônico"])
def registrar_ponto_saida(id_aluno: int, db: Session = Depends(get_db)):
    """
    Registra a saída de um aluno no ponto eletrônico.

    Encerra o ponto ativo do aluno, registra a hora de saída e calcula o
    tempo total trabalhado em minutos.
    """
    return crud.registrar_saida(db=db, id_aluno=id_aluno)

@app.post("/ponto/verificar-localizacao", tags=["Ponto Eletrônico"])
def verificar_localizacao_aluno(location_data: schemas.PontoCheckLocation, db: Session = Depends(get_db)):
    """
    Verifica se a localização atual do aluno está dentro da área do estágio.
    
    Este é o endpoint que o app mobile deve chamar periodicamente.
    """
    return crud.check_location(db=db, location_data=location_data)
