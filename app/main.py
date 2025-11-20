import base64
import csv
import io
import os
import uuid
import time
import mimetypes
import logging
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import date, timedelta, datetime
from pathlib import Path
from typing import Dict, List, Optional, Union

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
try:
    import redis
except ImportError:  # pragma: no cover
    redis = None

# --- Imports locais ---
from . import crud, schemas, models, auth
from .database import (
    engine,
    ensure_enderecos_columns,
    ensure_contratos_columns_and_boolean_status,
    ensure_usuarios_columns,
    ensure_pontos_columns,
    ensure_justificativas_columns,
    ensure_diarios_columns,
    ensure_avaliacoes_columns,
    get_db,
)
from .models import Base
from .schemas import (
    TipoUsuario,
    DocumentoCreate,
    DocumentoOut,
    DocumentoUpdate,
    DocumentoUploadIn,
    DocumentoUploadOut,
    DocumentoAnalyticsGroup,
    DocumentoAnalyticsItem,
    DocumentoExportInlineOut,
    DocumentoStatus,
)
from .permissions import require_roles

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

    try:
        ensure_usuarios_columns()
    except Exception as e:
        print(f"WARN: failed to ensure usuarios columns: {e}")

    try:
        ensure_pontos_columns()
    except Exception as e:
        print(f"WARN: failed to ensure pontos columns: {e}")

    try:
        ensure_justificativas_columns()
    except Exception as e:
        print(f"WARN: failed to ensure justificativas columns: {e}")

    try:
        ensure_diarios_columns()
    except Exception as e:
        print(f"WARN: failed to ensure diarios columns: {e}")

    try:
        ensure_avaliacoes_columns()
    except Exception as e:
        print(f"WARN: failed to ensure avaliacoes columns: {e}")

    yield
    print("INFO: Encerrando aplicação.")

app = FastAPI(lifespan=lifespan, title="API de Gestão de Estágios", version="1.3.0")

USER_MANAGEMENT_ROLES = (
    TipoUsuario.professor.value,
    TipoUsuario.coordenador.value,
    TipoUsuario.admin.value,
)

CONTRATO_WRITE_ROLES = (
    TipoUsuario.coordenador.value,
    TipoUsuario.admin.value,
)

CONTRATO_VIEW_ROLES = (
    TipoUsuario.professor.value,
    TipoUsuario.coordenador.value,
    TipoUsuario.admin.value,
    TipoUsuario.supervisor.value,
)

ACADEMIC_WRITE_ROLES = (
    TipoUsuario.coordenador.value,
    TipoUsuario.admin.value,
)

ACADEMIC_VIEW_ROLES = (
    TipoUsuario.professor.value,
    TipoUsuario.coordenador.value,
    TipoUsuario.admin.value,
    TipoUsuario.supervisor.value,
)

JUSTIFICATIVA_APPROVER_ROLES = (
    TipoUsuario.professor.value,
    TipoUsuario.coordenador.value,
    TipoUsuario.admin.value,
    TipoUsuario.supervisor.value,
)

DIARIO_APPROVER_ROLES = JUSTIFICATIVA_APPROVER_ROLES
AVALIACAO_MANAGE_ROLES = (
    TipoUsuario.coordenador.value,
    TipoUsuario.admin.value,
)
AVALIACAO_WRITE_ROLES = JUSTIFICATIVA_APPROVER_ROLES
AVALIACAO_VIEW_ROLES = (
    TipoUsuario.professor.value,
    TipoUsuario.supervisor.value,
    TipoUsuario.coordenador.value,
    TipoUsuario.admin.value,
    TipoUsuario.aluno.value,
)

ROLE_CREATION_MATRIX = {
    TipoUsuario.admin.value: {
        TipoUsuario.admin.value,
        TipoUsuario.coordenador.value,
        TipoUsuario.professor.value,
        TipoUsuario.supervisor.value,
        TipoUsuario.aluno.value,
    },
    TipoUsuario.coordenador.value: {
        TipoUsuario.professor.value,
        TipoUsuario.supervisor.value,
        TipoUsuario.aluno.value,
    },
    TipoUsuario.professor.value: {TipoUsuario.aluno.value},
}


def ensure_role_creation_allowed(requested_role: str, creator: models.Usuario) -> None:
    allowed_roles = ROLE_CREATION_MATRIX.get(creator.tipo_acesso, set())
    if requested_role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Perfil informado não é permitido para o seu nível de acesso.",
        )


SECURITY_LOGGER = logging.getLogger("security")
logging.basicConfig(level=logging.INFO)

# Upload config
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
UPLOAD_MAX_BYTES = int(os.getenv("UPLOAD_MAX_BYTES", 10 * 1024 * 1024))  # padrão 10MB
ALLOWED_UPLOAD_EXTENSIONS = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".doc",
    ".docx",
}

# Redis opcional para bloqueio de login
REDIS_URL = os.getenv("REDIS_URL")
REDIS_PREFIX = "cp_login"
if not REDIS_URL:
    raise RuntimeError("REDIS_URL é obrigatório para controle de tentativas de login.")
if not redis:
    raise RuntimeError("Biblioteca redis não instalada; instale requirements.")
redis_client = redis.Redis.from_url(REDIS_URL)
redis_client.ping()
SECURITY_LOGGER.info("Redis habilitado para controle de tentativas de login.")

# -----------------------------------------------------------------------------
# CORS
# -----------------------------------------------------------------------------
allowed_origins_env = os.getenv("CORS_ALLOWED_ORIGINS", "")
ALLOWED_ORIGINS = [origin.strip() for origin in allowed_origins_env.split(",") if origin.strip()] or [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
    max_age=86400,
)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    return response

# -----------------------------------------------------------------------------
# Controles de autenticação
# -----------------------------------------------------------------------------
FAILED_LOGIN_ATTEMPTS: Dict[str, deque] = defaultdict(deque)
LOCKED_UNTIL: Dict[str, float] = {}
LOGIN_FAIL_WINDOW_SEC = int(os.getenv("LOGIN_FAIL_WINDOW_SEC", 900))  # 15 minutos
LOGIN_FAIL_LIMIT = 5  # Limite fixo de 5 tentativas
LOGIN_LOCK_TIME_SEC = int(os.getenv("LOGIN_LOCK_TIME_SEC", 900))  # 15 minutos


def _cleanup_attempts(identifier: str, now: float) -> deque:
    attempts = FAILED_LOGIN_ATTEMPTS[identifier]
    cutoff = now - LOGIN_FAIL_WINDOW_SEC
    while attempts and attempts[0] < cutoff:
        attempts.popleft()
    return attempts


def _register_failed_login(identifier: str) -> int:
    now = time.time()
    if redis_client:
        attempts_key = f"{REDIS_PREFIX}:attempts:{identifier}"
        lock_key = f"{REDIS_PREFIX}:lock:{identifier}"
        attempts = int(redis_client.incr(attempts_key))
        redis_client.expire(attempts_key, LOGIN_FAIL_WINDOW_SEC)
        if attempts >= LOGIN_FAIL_LIMIT:
            redis_client.setex(lock_key, LOGIN_LOCK_TIME_SEC, "1")
        return attempts

    attempts = _cleanup_attempts(identifier, now)
    attempts.append(now)
    if len(attempts) >= LOGIN_FAIL_LIMIT:
        LOCKED_UNTIL[identifier] = now + LOGIN_LOCK_TIME_SEC
    return len(attempts)


def _clear_login_state(identifier: str) -> None:
    if redis_client:
        redis_client.delete(f"{REDIS_PREFIX}:attempts:{identifier}")
        redis_client.delete(f"{REDIS_PREFIX}:lock:{identifier}")
        return
    FAILED_LOGIN_ATTEMPTS.pop(identifier, None)
    LOCKED_UNTIL.pop(identifier, None)


def _is_locked(identifier: str) -> Optional[int]:
    now = time.time()
    if redis_client:
        lock_key = f"{REDIS_PREFIX}:lock:{identifier}"
        ttl = redis_client.ttl(lock_key)
        if ttl and ttl > 0:
            return ttl
        return None
    locked_until = LOCKED_UNTIL.get(identifier)
    if locked_until and locked_until > now:
        return int(locked_until - now)
    return None


# -----------------------------------------------------------------------------
# Dependencia de sessao do Banco
# -----------------------------------------------------------------------------
# A dependencia get_db e importada de app.database para evitar duplicidade.
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
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    forwarded_for = request.headers.get("x-forwarded-for", "")
    forwarded_ip = forwarded_for.split(",")[0].strip() if forwarded_for else None
    client_ip = forwarded_ip or (request.client.host if request.client else "unknown")
    candidate_user = crud.get_usuario_by_matricula(db, matricula=form_data.username)
    identifier = (
        f"{client_ip}:uid:{candidate_user.id}"
        if candidate_user
        else f"{client_ip}:user:{form_data.username}"
    )
    lock_ttl = _is_locked(identifier)
    if lock_ttl:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Muitas tentativas de login. Tente novamente em alguns minutos.",
            headers={"Retry-After": str(lock_ttl)},
        )

    user = auth.authenticate_user(db, matricula=form_data.username, password=form_data.password)
    if not user:
        attempts = _register_failed_login(identifier)
        if attempts > 1:
            time.sleep(min(attempts, 3))  # pequeno atraso progressivo
        headers = {"WWW-Authenticate": "Bearer"}
        lock_ttl = _is_locked(identifier)
        if lock_ttl:
            headers["Retry-After"] = str(lock_ttl)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Matrícula ou senha inválida",
            headers=headers,
        )

    _clear_login_state(identifier)

    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token_payload = {
        "sub": str(user.id),
        "uid": user.id,
        "matricula": user.matricula,
        "scope": user.tipo_acesso,
    }
    access_token = auth.create_access_token(
        data=access_token_payload,
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
    current_user: models.Usuario = Depends(require_roles(*USER_MANAGEMENT_ROLES)),
):
    ensure_role_creation_allowed(usuario.tipo_acesso, current_user)

    duplicate_message = "Não foi possível criar usuário com os dados fornecidos."
    if crud.get_usuario_by_email(db, email=usuario.email):
        raise HTTPException(status_code=400, detail=duplicate_message)
    if crud.get_usuario_by_matricula(db, matricula=usuario.matricula):
        raise HTTPException(status_code=400, detail=duplicate_message)
    if crud.get_usuario_by_contato(db, contato=usuario.contato):
        raise HTTPException(status_code=400, detail=duplicate_message)

    try:
        return crud.create_usuario(db=db, usuario=usuario)
    except Exception:
        raise HTTPException(status_code=400, detail="Não foi possível criar usuário.")

@app.get("/utilizadores", response_model=List[schemas.UsuarioOut], tags=["Gestão de Utilizadores"])
def list_users(
    tipo: Optional[TipoUsuario] = Query(None, description="Filtra por tipo de utilizador"),
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(require_roles(*USER_MANAGEMENT_ROLES)),
):
    try:
        return crud.list_usuarios(db, tipo=tipo.value if tipo else None)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# -----------------------------------------------------------------------------
# Cursos e Turmas
# -----------------------------------------------------------------------------
@app.post(
    "/cursos",
    response_model=schemas.CursoOut,
    status_code=status.HTTP_201_CREATED,
    tags=["Cursos"],
)
def create_curso_endpoint(
    curso: schemas.CursoCreate,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(require_roles(*ACADEMIC_WRITE_ROLES)),
):
    try:
        return crud.create_curso(db=db, data=curso)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@app.get("/cursos", response_model=List[schemas.CursoOut], tags=["Cursos"])
def list_cursos_endpoint(
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(require_roles(*ACADEMIC_VIEW_ROLES)),
):
    try:
        return crud.list_cursos(db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/turmas",
    response_model=schemas.TurmaOut,
    status_code=status.HTTP_201_CREATED,
    tags=["Turmas"],
)
def create_turma_endpoint(
    turma: schemas.TurmaCreate,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(require_roles(*ACADEMIC_WRITE_ROLES)),
):
    try:
        return crud.create_turma(db=db, data=turma)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/turmas", response_model=List[schemas.TurmaOut], tags=["Turmas"])
def list_turmas_endpoint(
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(require_roles(*ACADEMIC_VIEW_ROLES)),
):
    try:
        return crud.list_turmas(db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# -----------------------------------------------------------------------------
# Empresas, Supervisores e Convênios
# -----------------------------------------------------------------------------
@app.post(
    "/empresas",
    response_model=schemas.EmpresaOut,
    status_code=status.HTTP_201_CREATED,
    tags=["Empresas"],
)
def create_empresa_endpoint(
    empresa: schemas.EmpresaCreate,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(require_roles(*ACADEMIC_WRITE_ROLES)),
):
    try:
        return crud.create_empresa(db=db, data=empresa)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/empresas", response_model=List[schemas.EmpresaOut], tags=["Empresas"])
def list_empresas_endpoint(
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(require_roles(*ACADEMIC_VIEW_ROLES)),
):
    try:
        return crud.list_empresas(db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.patch(
    "/empresas/{empresa_id}",
    response_model=schemas.EmpresaOut,
    tags=["Empresas"],
)
def update_empresa_endpoint(
    empresa_id: int,
    payload: schemas.EmpresaUpdate,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(require_roles(*ACADEMIC_WRITE_ROLES)),
):
    try:
        empresa = crud.update_empresa(db=db, empresa_id=empresa_id, data=payload)
        return schemas.EmpresaOut.model_validate(empresa)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/documentos/upload",
    response_model=DocumentoUploadOut,
    tags=["Documentos"],
)
def upload_documento_arquivo(
    payload: DocumentoUploadIn,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(require_roles(*ACADEMIC_WRITE_ROLES)),
):
    # Validações básicas de segurança
    if not payload.filename or not payload.content_base64:
        raise HTTPException(status_code=400, detail="Arquivo inválido.")

    # Verifica extensão permitida
    safe_name = Path(payload.filename).name or "arquivo.bin"
    ext = Path(safe_name).suffix.lower()
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Extensão de arquivo não permitida.")

    # Estimativa do tamanho antes de decodificar (base64 aumenta ~33%)
    estimated_bytes = len(payload.content_base64) * 3 // 4
    if estimated_bytes > UPLOAD_MAX_BYTES:
        raise HTTPException(status_code=400, detail="Arquivo excede o tamanho máximo permitido.")

    try:
        data = base64.b64decode(payload.content_base64)
    except Exception:
        raise HTTPException(status_code=400, detail="Não foi possível decodificar o arquivo.")

    if len(data) > UPLOAD_MAX_BYTES:
        raise HTTPException(status_code=400, detail="Arquivo excede o tamanho máximo permitido.")

    final_name = f"{uuid.uuid4().hex}_{safe_name}"
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_path = Path(UPLOAD_DIR) / final_name
    with open(file_path, "wb") as f:
        f.write(data)
    return DocumentoUploadOut(url=f"/documentos/download/{final_name}")


@app.delete(
    "/empresas/{empresa_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Empresas"],
)
def delete_empresa_endpoint(
    empresa_id: int,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(require_roles(*ACADEMIC_WRITE_ROLES)),
):
    try:
        crud.delete_empresa(db=db, empresa_id=empresa_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/supervisores-externos",
    response_model=schemas.SupervisorExternoOut,
    status_code=status.HTTP_201_CREATED,
    tags=["Supervisores Externos"],
)
def create_supervisor_externo_endpoint(
    supervisor: schemas.SupervisorExternoCreate,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(require_roles(*ACADEMIC_WRITE_ROLES)),
):
    try:
        return crud.create_supervisor_externo(db=db, data=supervisor)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/supervisores-externos",
    response_model=List[schemas.SupervisorExternoOut],
    tags=["Supervisores Externos"],
)
def list_supervisores_externos_endpoint(
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(require_roles(*ACADEMIC_VIEW_ROLES)),
):
    try:
        return crud.list_supervisores_externos(db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/documentos/download/{filename}",
    response_class=StreamingResponse,
    tags=["Documentos"],
)
def download_documento(
    filename: str,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(require_roles(*ACADEMIC_VIEW_ROLES)),
):
    base_path = Path(UPLOAD_DIR).resolve()
    target_path = (base_path / filename).resolve()
    if not str(target_path).startswith(str(base_path)):
        raise HTTPException(status_code=400, detail="Caminho de arquivo inválido.")
    if not target_path.exists() or not target_path.is_file():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado.")

    mime_type, _ = mimetypes.guess_type(str(target_path))
    mime_type = mime_type or "application/octet-stream"
    return StreamingResponse(
        target_path.open("rb"),
        media_type=mime_type,
        headers={"Content-Disposition": f'attachment; filename=\"{target_path.name}\"'},
    )


@app.patch(
    "/supervisores-externos/{supervisor_id}",
    response_model=schemas.SupervisorExternoOut,
    tags=["Supervisores Externos"],
)
def update_supervisor_externo_endpoint(
    supervisor_id: int,
    payload: schemas.SupervisorExternoUpdate,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(require_roles(*ACADEMIC_WRITE_ROLES)),
):
    try:
        supervisor = crud.update_supervisor_externo(db=db, supervisor_id=supervisor_id, data=payload)
        return schemas.SupervisorExternoOut.model_validate(supervisor)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete(
    "/supervisores-externos/{supervisor_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Supervisores Externos"],
)
def delete_supervisor_externo_endpoint(
    supervisor_id: int,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(require_roles(*ACADEMIC_WRITE_ROLES)),
):
    try:
        crud.delete_supervisor_externo(db=db, supervisor_id=supervisor_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/convenios",
    response_model=schemas.ConvenioOut,
    status_code=status.HTTP_201_CREATED,
    tags=["Convênios"],
)
def create_convenio_endpoint(
    convenio: schemas.ConvenioCreate,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(require_roles(*ACADEMIC_WRITE_ROLES)),
):
    try:
        return crud.create_convenio(db=db, data=convenio)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/convenios", response_model=List[schemas.ConvenioOut], tags=["Convênios"])
def list_convenios_endpoint(
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(require_roles(*ACADEMIC_VIEW_ROLES)),
):
    try:
        return crud.list_convenios(db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.patch(
    "/convenios/{convenio_id}",
    response_model=schemas.ConvenioOut,
    tags=["Convênios"],
)
def update_convenio_endpoint(
    convenio_id: int,
    payload: schemas.ConvenioUpdate,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(require_roles(*ACADEMIC_WRITE_ROLES)),
):
    try:
        convenio = crud.update_convenio(db=db, convenio_id=convenio_id, data=payload)
        return schemas.ConvenioOut.model_validate(convenio)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete(
    "/convenios/{convenio_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Convênios"],
)
def delete_convenio_endpoint(
    convenio_id: int,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(require_roles(*ACADEMIC_WRITE_ROLES)),
):
    try:
        crud.delete_convenio(db=db, convenio_id=convenio_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -----------------------------------------------------------------------------
# Documentos
# -----------------------------------------------------------------------------
@app.post(
    "/documentos",
    response_model=DocumentoOut,
    status_code=status.HTTP_201_CREATED,
    tags=["Documentos"],
)
def criar_documento(
    payload: DocumentoCreate,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(require_roles(*ACADEMIC_WRITE_ROLES)),
):
    try:
        documento = crud.create_documento(db=db, data=payload, usuario=current_user)
        return DocumentoOut.model_validate(documento)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/documentos", response_model=List[DocumentoOut], tags=["Documentos"])
def listar_documentos(
    contrato_id: Optional[int] = Query(default=None),
    status_filter: Optional[DocumentoStatus] = Query(default=None),
    tipo: Optional[str] = Query(default=None),
    curso_id: Optional[int] = Query(default=None),
    empresa_id: Optional[int] = Query(default=None),
    periodo: Optional[str] = Query(default=None),
    data_inicio: Optional[date] = Query(default=None, description="Filtra documentos criados a partir desta data."),
    data_fim: Optional[date] = Query(default=None, description="Filtra documentos criados até esta data."),
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(require_roles(*ACADEMIC_VIEW_ROLES)),
):
    try:
        documentos = crud.list_documentos(
            db=db,
            contrato_id=contrato_id,
            status=status_filter.value if status_filter else None,
            tipo=tipo,
            curso_id=curso_id,
            empresa_id=empresa_id,
            periodo=periodo,
            data_inicio=data_inicio,
            data_fim=data_fim,
        )
        return [DocumentoOut.model_validate(doc) for doc in documentos]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/documentos/resumo", response_model=schemas.DocumentoResumoOut, tags=["Documentos"])
def resumo_documentos(
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(require_roles(*ACADEMIC_VIEW_ROLES)),
):
    try:
        resumo = crud.documentos_resumo(db)
        return schemas.DocumentoResumoOut(
            pendentes=resumo.get("pendente", 0),
            aprovados=resumo.get("aprovado", 0),
            rejeitados=resumo.get("rejeitado", 0),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/documentos/analytics", response_model=List[DocumentoAnalyticsItem], tags=["Documentos"])
def documentos_analytics_endpoint(
    group_by: DocumentoAnalyticsGroup = Query(default=DocumentoAnalyticsGroup.curso),
    limit: int = Query(default=5, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(require_roles(*ACADEMIC_VIEW_ROLES)),
):
    try:
        itens = crud.documentos_analytics(db=db, group_by=group_by.value, limit=limit)
        return [DocumentoAnalyticsItem(**item) for item in itens]
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/documentos/export", tags=["Documentos"])
def exportar_documentos(
    formato: str = Query(default="csv", pattern="^(csv|pdf)$"),
    inline: bool = Query(
        default=False,
        description="Quando verdadeiro, retorna o arquivo em base64 no corpo da resposta.",
    ),
    contrato_id: Optional[int] = Query(default=None),
    status_filter: Optional[DocumentoStatus] = Query(default=None),
    tipo: Optional[str] = Query(default=None),
    curso_id: Optional[int] = Query(default=None),
    empresa_id: Optional[int] = Query(default=None),
    periodo: Optional[str] = Query(default=None),
    data_inicio: Optional[date] = Query(default=None),
    data_fim: Optional[date] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(require_roles(*ACADEMIC_VIEW_ROLES)),
):
    documentos = crud.list_documentos(
        db=db,
        contrato_id=contrato_id,
        status=status_filter.value if status_filter else None,
        tipo=tipo,
        curso_id=curso_id,
        empresa_id=empresa_id,
        periodo=periodo,
        data_inicio=data_inicio,
        data_fim=data_fim,
    )
    if not documentos:
        raise HTTPException(status_code=404, detail="Nenhum documento encontrado para os filtros informados.")

    linhas = []
    for doc in documentos:
        contrato = doc.contrato
        aluno = contrato.aluno if contrato else None
        turma = contrato.turma if contrato else None
        curso = turma.curso if turma else None
        convenio = contrato.convenio if contrato else None
        empresa = convenio.empresa if convenio else None
        logs = sorted(doc.logs or [], key=lambda l: l.criado_em or datetime.min)
        trilha = " | ".join(
            f"{(log.criado_em or datetime.utcnow()).strftime('%d/%m/%Y %H:%M')} - {log.status} - {(log.comentario or '').strip()}"
            for log in logs
        )
        linhas.append(
            {
                "id": doc.id,
                "contrato": doc.id_contrato,
                "tipo": doc.tipo.value if hasattr(doc.tipo, "value") else doc.tipo,
                "status": doc.status,
                "aluno": aluno.nome if aluno else None,
                "turma": turma.nome if turma else None,
                "curso": curso.nome if curso else None,
                "empresa": (empresa.nome_fantasia or empresa.razao_social) if empresa else None,
                "criado_em": doc.criado_em.strftime("%d/%m/%Y %H:%M"),
                "atualizado_em": doc.atualizado_em.strftime("%d/%m/%Y %H:%M"),
                "observacoes": doc.observacoes or "",
                "trilha": trilha,
            }
        )

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    if formato == "csv":
        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter=";")
        writer.writerow(
            ["ID", "Contrato", "Tipo", "Status", "Aluno", "Turma", "Curso", "Empresa", "Criado em", "Atualizado em", "Observações", "Trilha"]
        )
        for linha in linhas:
            writer.writerow(
                [
                    linha["id"],
                    linha["contrato"],
                    linha["tipo"],
                    linha["status"],
                    linha["aluno"] or "",
                    linha["turma"] or "",
                    linha["curso"] or "",
                    linha["empresa"] or "",
                    linha["criado_em"],
                    linha["atualizado_em"],
                    linha["observacoes"],
                    linha["trilha"],
                ]
            )
        data_bytes = buffer.getvalue().encode("utf-8-sig")
        mime_type = "text/csv"
        filename = f"documentos_{timestamp}.csv"
    else:
        pdf_buffer = io.BytesIO()
        pdf = canvas.Canvas(pdf_buffer, pagesize=A4)
        width, height = A4
        y = height - 40
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(40, y, "Relatório de Documentos Institucionais")
        y -= 24
        pdf.setFont("Helvetica", 9)
        for linha in linhas:
            bloco = [
                f"Documento #{linha['id']} - Contrato {linha['contrato']} ({linha['status']})",
                f"Aluno: {linha['aluno'] or 'N/D'} | Curso: {linha['curso'] or 'N/D'} | Empresa: {linha['empresa'] or 'N/D'}",
                f"Tipo: {linha['tipo']} | Criado em: {linha['criado_em']} | Atualizado em: {linha['atualizado_em']}",
                f"Observações: {linha['observacoes'] or '---'}",
                f"Trilha: {linha['trilha'] or '---'}",
            ]
            for texto in bloco:
                if y < 60:
                    pdf.showPage()
                    pdf.setFont("Helvetica", 9)
                    y = height - 40
                pdf.drawString(40, y, texto[:120])
                y -= 14
            y -= 8
        pdf.save()
        data_bytes = pdf_buffer.getvalue()
        pdf_buffer.close()
        mime_type = "application/pdf"
        filename = f"documentos_{timestamp}.pdf"

    if inline:
        encoded = base64.b64encode(data_bytes).decode("utf-8")
        return DocumentoExportInlineOut(filename=filename, mime_type=mime_type, content_base64=encoded)

    return StreamingResponse(
        iter([data_bytes]),
        media_type=mime_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.patch(
    "/documentos/{documento_id}",
    response_model=DocumentoOut,
    tags=["Documentos"],
)
def atualizar_documento(
    documento_id: int,
    payload: DocumentoUpdate,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(require_roles(*ACADEMIC_WRITE_ROLES)),
):
    try:
        documento = crud.update_documento(
            db=db,
            documento_id=documento_id,
            data=payload,
            usuario=current_user,
        )
        return DocumentoOut.model_validate(documento)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete(
    "/documentos/{documento_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Documentos"],
)
def remover_documento(
    documento_id: int,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(require_roles(*ACADEMIC_WRITE_ROLES)),
):
    try:
        crud.delete_documento(db=db, documento_id=documento_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -----------------------------------------------------------------------------
# Importação de alunos
# -----------------------------------------------------------------------------
@app.post(
    "/alunos/import",
    response_model=schemas.AlunoImportResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Alunos"],
)
def importar_alunos(
    payload: schemas.AlunoImportRequest,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(require_roles(*USER_MANAGEMENT_ROLES)),
):
    total = len(payload.registros)
    importados = 0
    erros: List[str] = []

    for idx, registro in enumerate(payload.registros, start=1):
        try:
            crud.create_aluno_completo(db, registro, current_user.id)
            importados += 1
        except Exception as e:
            db.rollback()
            erros.append(f"Linha {idx}: {str(e)}")

    return schemas.AlunoImportResponse(total=total, importados=importados, erros=erros)


@app.get("/aluno/contratos/ativos", response_model=List[schemas.ContratoOut], tags=["Contratos e Endere��os"])
def listar_contratos_ativos_do_aluno(
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(auth.get_current_active_aluno),
):
    try:
        contratos = crud.list_contratos_ativos_do_aluno(db, current_user.id)
        return [schemas.ContratoOut.model_validate(c) for c in contratos]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

# -----------------------------------------------------------------------------
# Justificativas
# -----------------------------------------------------------------------------
@app.post(
    "/justificativas",
    response_model=schemas.JustificativaOut,
    status_code=status.HTTP_201_CREATED,
    tags=["Justificativas"],
)
def criar_justificativa(
    payload: schemas.JustificativaCreate,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(auth.get_current_active_aluno),
):
    try:
        justificativa = crud.create_justificativa(
            db=db,
            aluno_id=current_user.id,
            data=payload,
        )
        return schemas.JustificativaOut.model_validate(justificativa)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.get("/justificativas", response_model=List[schemas.JustificativaOut], tags=["Justificativas"])
def listar_justificativas(
    status_filter: Optional[schemas.JustificativaStatus] = Query(
        default=None, description="Filtrar por status (pendente, aprovado, rejeitado)"
    ),
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(auth.get_current_active_user),
):
    try:
        items = crud.list_justificativas(
            db=db,
            current_user=current_user,
            status=status_filter.value if status_filter else None,
        )
        return [schemas.JustificativaOut.model_validate(j) for j in items]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

# -----------------------------------------------------------------------------
# Diario de atividades
# -----------------------------------------------------------------------------
@app.post(
    "/diarios",
    response_model=schemas.DiarioAtividadeOut,
    status_code=status.HTTP_201_CREATED,
    tags=["Diarios"],
)
def criar_diario(
    payload: schemas.DiarioAtividadeCreate,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(auth.get_current_active_aluno),
):
    try:
        diario = crud.create_diario(db=db, aluno_id=current_user.id, data=payload)
        return schemas.DiarioAtividadeOut.model_validate(diario)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.get("/diarios", response_model=List[schemas.DiarioAtividadeOut], tags=["Diarios"])
def listar_diarios(
    status_filter: Optional[schemas.DiarioStatus] = Query(default=None),
    data_referencia: Optional[date] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(auth.get_current_active_user),
):
    try:
        items = crud.list_diarios(
            db=db,
            current_user=current_user,
            status=status_filter.value if status_filter else None,
            data_referencia=data_referencia,
        )
        return [schemas.DiarioAtividadeOut.model_validate(d) for d in items]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.patch(
    "/diarios/{diario_id}",
    response_model=schemas.DiarioAtividadeOut,
    tags=["Diarios"],
)
def atualizar_status_diario(
    diario_id: int,
    payload: schemas.DiarioAtividadeStatusUpdate,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(require_roles(*DIARIO_APPROVER_ROLES)),
):
    try:
        novo_status = (
            schemas.DiarioStatus.aprovado if payload.status == "aprovado" else schemas.DiarioStatus.rejeitado
        )
        diario = crud.update_diario_status(
            db=db,
            diario_id=diario_id,
            status=novo_status,
            comentario=payload.comentario,
        )
        return schemas.DiarioAtividadeOut.model_validate(diario)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

# -----------------------------------------------------------------------------
# Avaliações e Rubricas
# -----------------------------------------------------------------------------
@app.post(
    "/avaliacao/rubricas",
    response_model=schemas.AvaliacaoRubricaOut,
    status_code=status.HTTP_201_CREATED,
    tags=["Avaliacoes"],
)
def criar_rubrica(
    payload: schemas.AvaliacaoRubricaCreate,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(require_roles(*AVALIACAO_MANAGE_ROLES)),
):
    try:
        rubrica = crud.create_rubrica(db=db, data=payload)
        return schemas.AvaliacaoRubricaOut.model_validate(rubrica)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@app.get("/avaliacao/rubricas", response_model=List[schemas.AvaliacaoRubricaOut], tags=["Avaliacoes"])
def listar_rubricas(
    somente_ativas: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(require_roles(*AVALIACAO_VIEW_ROLES)),
):
    try:
        rubricas = crud.list_rubricas(db=db, somente_ativas=somente_ativas)
        return [schemas.AvaliacaoRubricaOut.model_validate(r) for r in rubricas]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.post(
    "/avaliacoes",
    response_model=schemas.AvaliacaoOut,
    status_code=status.HTTP_201_CREATED,
    tags=["Avaliacoes"],
)
def criar_avaliacao(
    payload: schemas.AvaliacaoCreate,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(require_roles(*AVALIACAO_WRITE_ROLES)),
):
    try:
        avaliacao = crud.create_avaliacao(
            db=db,
            contrato_id=payload.id_contrato,
            rubrica_id=payload.id_rubrica,
            avaliador_id=current_user.id,
            payload=payload,
        )
        return schemas.AvaliacaoOut.model_validate(avaliacao)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.get("/avaliacoes", response_model=List[schemas.AvaliacaoOut], tags=["Avaliacoes"])
def listar_avaliacoes(
    contrato_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(auth.get_current_active_user),
):
    try:
        avaliacoes = crud.list_avaliacoes(
            db=db,
            current_user=current_user,
            contrato_id=contrato_id,
        )
        return [schemas.AvaliacaoOut.model_validate(a) for a in avaliacoes]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.get(
    "/avaliacoes/export/csv",
    response_class=Response,
    tags=["Avaliacoes"],
)
def exportar_avaliacoes_csv(
    contrato_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(require_roles(*AVALIACAO_MANAGE_ROLES)),
):
    try:
        avaliacoes = crud.list_avaliacoes(db=db, current_user=current_user, contrato_id=contrato_id)
        csv_content = crud.export_avaliacoes_csv(avaliacoes)
        crud.mark_avaliacoes_exportadas(db, avaliacoes)
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=avaliacoes.csv"},
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.patch(
    "/justificativas/{justificativa_id}",
    response_model=schemas.JustificativaOut,
    tags=["Justificativas"],
)
def atualizar_status_justificativa(
    justificativa_id: int,
    payload: schemas.JustificativaStatusUpdate,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(require_roles(*JUSTIFICATIVA_APPROVER_ROLES)),
):
    try:
        novo_status = (
            schemas.JustificativaStatus.aprovado
            if payload.status == "aprovado"
            else schemas.JustificativaStatus.rejeitado
        )
        updated = crud.update_justificativa_status(
            db=db,
            justificativa_id=justificativa_id,
            status=novo_status,
            comentario=payload.comentario,
        )
        return schemas.JustificativaOut.model_validate(updated)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

# -----------------------------------------------------------------------------
# Cadastro agregado de alunos
# -----------------------------------------------------------------------------
@app.get(
    "/alunos",
    response_model=List[schemas.UsuarioOut],
    tags=["Alunos"],
)
def list_alunos_endpoint(
    search: Optional[str] = Query(default=None, description="Filtra por nome, matricula, email ou turma."),
    limit: int = Query(default=100, ge=1, le=500, description="Limite maximo de registros retornados."),
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(require_roles(*USER_MANAGEMENT_ROLES)),
):
    try:
        alunos = crud.list_usuarios(
            db=db,
            tipo=TipoUsuario.aluno.value,
            search=search,
            limit=limit,
        )
        return [schemas.UsuarioOut.model_validate(aluno) for aluno in alunos]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.post(
    "/alunos",
    response_model=schemas.AlunoCadastroResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Alunos"],
)
def create_aluno_completo_endpoint(
    payload: schemas.AlunoCadastroIn,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(require_roles(*USER_MANAGEMENT_ROLES)),
):
    professor_id = payload.id_professor or current_user.id
    try:
        aluno, endereco, contrato = crud.create_aluno_completo(db, payload, professor_id)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    return schemas.AlunoCadastroResponse(
        usuario=schemas.UsuarioOut.model_validate(aluno),
        endereco=schemas.EnderecoOut.model_validate(endereco),
        contrato=schemas.ContratoOut.model_validate(contrato),
    )


@app.patch(
    "/usuarios/{usuario_id}",
    response_model=schemas.UsuarioOut,
    tags=["Usuarios"],
    dependencies=[Depends(require_roles(*USER_MANAGEMENT_ROLES))],
)
def atualizar_usuario(
    usuario_id: int,
    payload: schemas.UsuarioUpdate,
    db: Session = Depends(get_db),
):
    try:
        usuario = crud.update_usuario(db=db, usuario_id=usuario_id, data=payload)
        return schemas.UsuarioOut.model_validate(usuario)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.delete(
    "/usuarios/{usuario_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Usuarios"],
    dependencies=[Depends(require_roles(*USER_MANAGEMENT_ROLES))],
)
def remover_usuario(usuario_id: int, db: Session = Depends(get_db)):
    try:
        crud.delete_usuario(db=db, usuario_id=usuario_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

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
    current_user: models.Usuario = Depends(require_roles(*CONTRATO_WRITE_ROLES)),
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
    current_user: models.Usuario = Depends(require_roles(*CONTRATO_WRITE_ROLES)),
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
    current_user: models.Usuario = Depends(require_roles(*CONTRATO_VIEW_ROLES)),
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
    response_model=schemas.PontoToggleOut,
    status_code=status.HTTP_200_OK,
    tags=["Ponto Eletrônico"],
)
def registrar_ponto_entrada(
    # Aceita tanto só coords quanto coords+id_aluno (legado)
    location_data: Union[schemas.PontoLocalizacaoIn, schemas.PontoCheckLocation],
    response: Response,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(auth.get_current_active_aluno),
):
    try:
        # Normaliza: id_aluno sempre do token (ignora do body se vier)
        ponto_check_data = schemas.PontoCheckLocation(
            id_aluno=current_user.id,
            latitude_atual=location_data.latitude_atual,
            longitude_atual=location_data.longitude_atual,
            precisao_metros=getattr(location_data, "precisao_metros", None),
        )
        ponto, finalizou = crud.ponto_entrada(
            db=db,
            matricula=current_user.matricula,
            payload=ponto_check_data,
        )
        ponto_out = schemas.PontoOut.model_validate(ponto)
        acao = "fechado" if finalizou else "aberto"
        if response is not None:
            response.status_code = status.HTTP_200_OK if finalizou else status.HTTP_201_CREATED
        return schemas.PontoToggleOut(acao=acao, ponto=ponto_out)
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
        lowered = detail.lower()
        if (
            "não há ponto aberto" in lowered
            or "nenhum ponto aberto" in lowered
            or "nenhum ponto em aberto" in lowered
        ):
            raise HTTPException(status_code=404, detail=detail)
        raise HTTPException(status_code=400, detail=detail)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post(
    "/ponto/verificar-localizacao",
    response_model=schemas.PontoVerificacaoOut,
    tags=["Ponto Eletr??nico"],
)
def verificar_localizacao_aluno(
    location_data: schemas.PontoLocalizacaoIn,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(auth.get_current_active_aluno),
):
    try:
        resultado = crud.verificar_localizacao_para_aluno(
            db=db, aluno_id=current_user.id, payload=location_data
        )
        return schemas.PontoVerificacaoOut(**resultado)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.get(
    "/ponto/timeline",
    response_model=schemas.PontoTimelineOut,
    tags=["Ponto Eletr��nico"],
)
def obter_timeline_ponto(
    data: Optional[date] = Query(
        default=None, description="Data no formato YYYY-MM-DD. Padr�o: hoje."
    ),
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(auth.get_current_active_aluno),
):
    dia = data or date.today()
    try:
        pontos, justificativas, diarios, avaliacoes, total, esperado, saldo = crud.obter_timeline_do_dia(
            db=db, aluno_id=current_user.id, dia=dia
        )
        pontos_out = [schemas.PontoOut.model_validate(p) for p in pontos]
        justificativas_out = [schemas.JustificativaOut.model_validate(j) for j in justificativas]
        diarios_out = [schemas.DiarioAtividadeOut.model_validate(d) for d in diarios]
        avaliacoes_out = [schemas.AvaliacaoOut.model_validate(a) for a in avaliacoes]
        contratos_ativos = crud.list_contratos_ativos_do_aluno(db, current_user.id)
        contratos_out = [schemas.ContratoOut.model_validate(c) for c in contratos_ativos]
        return schemas.PontoTimelineOut(
            data=dia,
            total_minutos=total,
            esperado_minutos=esperado,
            saldo_minutos=saldo,
            pontos=pontos_out,
            justificativas=justificativas_out,
            diarios=diarios_out,
            avaliacoes=avaliacoes_out,
            contratos=contratos_out,
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# -----------------------------------------------------------------------------
# Handler para detalhar 422 (debug)
# -----------------------------------------------------------------------------
@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    SECURITY_LOGGER.error("Erro não tratado em %s: %s", request.url.path, exc, exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Erro interno. Tente novamente mais tarde."},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code >= 500:
        SECURITY_LOGGER.error("Erro HTTP interno em %s: %s", request.url.path, exc.detail)
        return JSONResponse(status_code=exc.status_code, content={"detail": "Erro interno"})
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    """
    Handler de 422 que evita incluir o corpo da requisição na resposta.
    """
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
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
