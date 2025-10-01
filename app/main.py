from contextlib import asynccontextmanager
from typing import Optional, List
from datetime import timedelta

from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

# --- Imports do projeto ---
from app import crud, schemas, models, auth
from app.database import SessionLocal, engine
from app.models import TipoUsuario

# --- Lifespan da Aplicação ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Cria as tabelas no banco de dados ao iniciar a aplicação."""
    print("INFO: Iniciando aplicação e criando tabelas do banco de dados...")
    models.Base.metadata.create_all(bind=engine)
    yield
    print("INFO: Encerrando aplicação.")

app = FastAPI(lifespan=lifespan, title="API de Gestão de Estágios", version="1.1.0")

# --- Configuração do CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Em produção, restrinja para o domínio do seu front-end
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Dependência de sessão do Banco ---
def get_db():
    """Fornece uma sessão do banco de dados para os endpoints."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# =============================================================================
# Endpoints de Autenticação e Utilizadores
# =============================================================================

@app.post("/login", response_model=schemas.Token, tags=["Autenticação"])
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    Autentica um utilizador e retorna um token de acesso JWT.
    
    Use a `matrícula` como **username** e a `senha` como **password**.
    """
    user = auth.authenticate_user(db, matricula=form_data.username, password=form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Matrícula ou senha inválida",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.matricula, "scope": user.tipo_acesso}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/me", response_model=schemas.UsuarioOut, tags=["Utilizadores"])
async def read_users_me(current_user: models.Usuario = Depends(auth.get_current_active_user)):
    """Retorna os dados do utilizador atualmente logado."""
    return current_user

# =============================================================================
# Endpoints Administrativos (Professores, Coordenadores, etc.)
# =============================================================================

@app.post("/utilizadores/criar", response_model=schemas.UsuarioOut, status_code=status.HTTP_201_CREATED, tags=["Gestão de Utilizadores"])
def create_user_as_admin(
    usuario: schemas.UsuarioCreate, 
    db: Session = Depends(get_db), 
    current_user: models.Usuario = Depends(auth.get_current_active_user)
):
    """
    Cria um novo utilizador (aluno ou professor). 
    Apenas utilizadores autorizados (ex: professor, admin) podem aceder.
    """
    if current_user.tipo_acesso not in [TipoUsuario.professor, TipoUsuario.admin, TipoUsuario.coordenador]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permissão negada para criar utilizadores.")

    if crud.get_usuario_by_email(db, email=usuario.email):
        raise HTTPException(status_code=400, detail="E-mail já cadastrado")
    if crud.get_usuario_by_matricula(db, matricula=usuario.matricula):
        raise HTTPException(status_code=400, detail="Matrícula já cadastrada")
    if crud.get_usuario_by_contato(db, contato=usuario.contato):
        raise HTTPException(status_code=400, detail="Numero de telefone já cadastrada")
    
    return crud.create_usuario(db=db, usuario=usuario)

@app.get("/utilizadores", response_model=List[schemas.UsuarioOut], tags=["Gestão de Utilizadores"])
def list_users(
    tipo: Optional[TipoUsuario] = Query(None, description="Filtra por tipo de utilizador"),
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(auth.get_current_active_user)
):
    """Lista todos os utilizadores. Apenas para perfis autorizados."""
    return crud.list_usuarios(db, tipo=tipo.value if tipo else None)

# =============================================================================
# Endpoints para Contratos e Endereços
# =============================================================================

@app.post("/enderecos", response_model=schemas.EnderecoOut, status_code=status.HTTP_201_CREATED, tags=["Contratos e Endereços"])
def create_endereco(
    endereco: schemas.EnderecoCreate, 
    db: Session = Depends(get_db), 
    current_user: models.Usuario = Depends(auth.get_current_active_user)
):
    """Cria um novo endereço de estágio. Requer autenticação."""
    return crud.create_endereco(db=db, endereco=endereco)

@app.post("/contratos", response_model=schemas.ContratoOut, status_code=status.HTTP_201_CREATED, tags=["Contratos e Endereços"])
def create_contrato(
    contrato: schemas.ContratoCreate, 
    db: Session = Depends(get_db), 
    current_user: models.Usuario = Depends(auth.get_current_active_user)
):
    """Cria um novo contrato. Requer autenticação."""
    return crud.create_contrato(db=db, contrato=contrato)

@app.get("/contratos", response_model=List[schemas.ContratoOut], tags=["Contratos e Endereços"])
def read_contratos(
    db: Session = Depends(get_db), 
    current_user: models.Usuario = Depends(auth.get_current_active_user)
):
    """Lista todos os contratos. Requer autenticação."""
    return crud.get_contratos(db)

# =============================================================================
# Endpoints para Ponto Eletrônico (Apenas Alunos)
# =============================================================================

@app.post("/ponto/entrada", response_model=schemas.PontoOut, status_code=status.HTTP_201_CREATED, tags=["Ponto Eletrônico"])
def registrar_ponto_entrada(
    # O corpo da requisição só precisa da lat/long, o ID vem do token
    location_data: schemas.PontoCheckLocation, # Vamos manter o schema por enquanto, mas o ideal seria um novo só com lat/long
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(auth.get_current_active_aluno)
):
    """Registra a entrada de um aluno no ponto eletrônico."""
    # Instancia o schema correto com os dados
    ponto_check_data = schemas.PontoCheckLocation(
        id_aluno=current_user.id,
        latitude_atual=location_data.latitude_atual,
        longitude_atual=location_data.longitude_atual
    )
    # Chama o crud com o nome de argumento correto
    return crud.registrar_entrada(db=db, location_data=ponto_check_data)

@app.patch("/ponto/saida", response_model=schemas.PontoOut, tags=["Ponto Eletrônico"])
def registrar_ponto_saida(
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(auth.get_current_active_aluno)
):
    """Registra a saída de um aluno. Apenas o próprio aluno pode fechar o seu ponto."""
    return crud.registrar_saida(db=db, id_aluno=current_user.id)

@app.post("/ponto/verificar-localizacao", tags=["Ponto Eletrônico"])
def verificar_localizacao_aluno(
    location_data: schemas.PontoCheckLocation, 
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(auth.get_current_active_aluno)
):
    """Verifica se a localização atual do aluno está dentro da área do estágio."""
    check_data = schemas.PontoCheckLocationWithId(
        id_aluno=current_user.id,
        **location_data.model_dump()
    )
    return crud.check_location(db=db, location_data=check_data)

# =============================================================================
# Endpoints para Professores
# =============================================================================

@app.get("/alunos/{id_aluno}/historico-ponto", response_model=List[schemas.PontoOut], tags=["Visão do Professor"])
def get_historico_aluno(
    id_aluno: int,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(auth.get_current_active_professor)
):
    """Retorna o histórico de pontos de um aluno específico para o professor responsável."""
    is_responsavel = crud.is_professor_responsavel(db, id_professor=current_user.id, id_aluno=id_aluno)
    if not is_responsavel:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Não tem permissão para visualizar o histórico deste aluno."
        )
    return crud.get_historico_ponto_por_aluno(db=db, id_aluno=id_aluno)

