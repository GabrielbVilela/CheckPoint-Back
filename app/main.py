from contextlib import asynccontextmanager
from typing import Optional, List, Union
from datetime import timedelta

from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

# --- Imports locais ---
import crud
import schemas
import models
import auth
from database import (
    SessionLocal,
    engine,
    ensure_enderecos_columns,
    ensure_contratos_columns_and_boolean_status,
)
from models import Base, TipoUsuario

# -----------------------------------------------------------------------------
# Lifespan da Aplicação
# -----------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("INFO: Iniciando aplicação...")
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"ERRO ao criar tabelas: {e}")

    try:
        ensure_enderecos_columns()
    except Exception as e:
        print(f"WARN: failed to ensure 'enderecos' columns: {e}")

    try:
        ensure_contratos_columns_and_boolean_status()
    except Exception as e:
        print(f"WARN: failed to ensure contratos.status boolean: {e}")

    yield
    print("INFO: Encerrando aplicação.")

app = FastAPI(lifespan=lifespan, title="API de Gestão de Estágios", version="1.3.0")

# -----------------------------------------------------------------------------
# CORS
# -----------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------------------------------------------------
# Dependência de sessão do Banco
# -----------------------------------------------------------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# -----------------------------------------------------------------------------
# Health
# -----------------------------------------------------------------------------
@app.get("/")
def health_check():
    return {"status": "ok"}

# -----------------------------------------------------------------------------
# Autenticação
# -----------------------------------------------------------------------------
@app.post("/login", response_model=schemas.Token, tags=["Autenticação"])
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = auth.authenticate_user(db, matricula=form_data.username, password=form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Matrícula ou senha inválida",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.matricula, "uid": user.id, "scope": user.tipo_acesso},
        expires_delta=access_token_expires,
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/me", response_model=schemas.UsuarioOut, tags=["Utilizadores"])
async def read_users_me(current_user: models.Usuario = Depends(auth.get_current_active_user)):
    return current_user

# -----------------------------------------------------------------------------
# Gestão de Utilizadores
# -----------------------------------------------------------------------------
@app.post(
    "/utilizadores/criar",
    response_model=schemas.UsuarioOut,
    status_code=status.HTTP_201_CREATED,
    tags=["Gestão de Utilizadores"],
)
def create_user_as_admin(
    usuario: schemas.UsuarioCreate,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(auth.get_current_active_user),
):
    if current_user.tipo_acesso not in [
        TipoUsuario.professor.value,
        TipoUsuario.admin.value,
        TipoUsuario.coordenador.value,
    ]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permissão negada para criar utilizadores.",
        )

    if crud.get_usuario_by_email(db, email=usuario.email):
        raise HTTPException(status_code=400, detail="E-mail já cadastrado")
    if crud.get_usuario_by_matricula(db, matricula=usuario.matricula):
        raise HTTPException(status_code=400, detail="Matrícula já cadastrada")
    if crud.get_usuario_by_contato(db, contato=usuario.contato):
        raise HTTPException(status_code=400, detail="Número de telefone já cadastrado")

    try:
        return crud.create_usuario(db=db, usuario=usuario)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/utilizadores", response_model=List[schemas.UsuarioOut], tags=["Gestão de Utilizadores"])
def list_users(
    tipo: Optional[TipoUsuario] = Query(None, description="Filtra por tipo de utilizador"),
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(auth.get_current_active_user),
):
    try:
        return crud.list_usuarios(db, tipo=tipo.value if tipo else None)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# -----------------------------------------------------------------------------
# Contratos e Endereços
# -----------------------------------------------------------------------------
@app.post(
    "/enderecos",
    response_model=schemas.EnderecoOut,
    status_code=status.HTTP_201_CREATED,
    tags=["Contratos e Endereços"],
)
def create_endereco(
    endereco: schemas.EnderecoCreate,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(auth.get_current_active_user),
):
    try:
        return crud.create_endereco(db=db, data=endereco)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post(
    "/contratos",
    response_model=schemas.ContratoOut,
    status_code=status.HTTP_201_CREATED,
    tags=["Contratos e Endereços"],
)
def create_contrato(
    contrato: schemas.ContratoCreate,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(auth.get_current_active_user),
):
    """
    Cria um novo contrato (status boolean). Requer autenticação.
    """
    try:
        created = crud.create_contrato(db=db, data=contrato)
        db.refresh(created)
        return created  # retorna ORM direto
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/contratos", response_model=List[schemas.ContratoOut], tags=["Contratos e Endereços"])
def read_contratos(
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(auth.get_current_active_user),
):
    try:
        contratos = crud.get_contratos(db)
        return contratos
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# -----------------------------------------------------------------------------
# Ponto Eletrônico (Aluno)
# -----------------------------------------------------------------------------
@app.post(
    "/ponto/entrada",
    response_model=schemas.PontoOut,
    status_code=status.HTTP_201_CREATED,
    tags=["Ponto Eletrônico"],
)
def registrar_ponto_entrada(
    # Aceita tanto só coords quanto coords+id_aluno (legado)
    location_data: Union[schemas.PontoLocalizacaoIn, schemas.PontoCheckLocation],
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(auth.get_current_active_aluno),
):
    try:
        # Normaliza: id_aluno sempre do token (ignora do body se vier)
        ponto_check_data = schemas.PontoCheckLocation(
            id_aluno=current_user.id,
            latitude_atual=location_data.latitude_atual,
            longitude_atual=location_data.longitude_atual,
        )
        return crud.ponto_entrada(db=db, matricula=current_user.matricula, payload=ponto_check_data)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.patch(
    "/ponto/saida",
    response_model=schemas.PontoOut,
    tags=["Ponto Eletrônico"],
)
def registrar_ponto_saida(
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(auth.get_current_active_aluno),
):
    try:
        return crud.ponto_saida(db=db, matricula=current_user.matricula)
    except ValueError as ve:
        detail = str(ve)
        if "não há ponto aberto" in detail.lower() or "nenhum ponto aberto" in detail.lower():
            raise HTTPException(status_code=404, detail=detail)
        raise HTTPException(status_code=400, detail=detail)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/ponto/verificar-localizacao", tags=["Ponto Eletrônico"])
def verificar_localizacao_aluno(
    location_data: schemas.PontoLocalizacaoIn,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(auth.get_current_active_aluno),
):
    # Stub de verificação — ajuste conforme sua regra
    return {"ok": True}

# -----------------------------------------------------------------------------
# Handler para detalhar 422 (debug)
# -----------------------------------------------------------------------------
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    """
    Mostra o detalhe dos erros 422 e o body recebido (facilita debug no Cloud Run).
    Remova em produção se preferir respostas mais limpas.
    """
    return JSONResponse(
        status_code=422,
        content={
            "detail": exc.errors(),
            "body": (await request.body()).decode()
        },
    )


@app.get("/ponto/aberto", response_model=schemas.PontoOut, tags=["Ponto Eletrônico"])
def obter_ponto_aberto(
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(auth.get_current_active_aluno),
):
    p = crud.get_ponto_aberto(db, current_user.id)
    if not p:
        raise HTTPException(status_code=404, detail="Nenhum ponto em aberto para este aluno.")
    return p
