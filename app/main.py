import base64
import os
import uuid
from contextlib import asynccontextmanager
from datetime import date, timedelta
from pathlib import Path
from typing import List, Optional, Union

from fastapi import Depends, FastAPI, HTTPException, Query, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

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
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount(f"/{UPLOAD_DIR}", StaticFiles(directory=UPLOAD_DIR), name="uploads")

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
    if not payload.filename or not payload.content_base64:
        raise HTTPException(status_code=400, detail="Arquivo inválido.")
    try:
        data = base64.b64decode(payload.content_base64)
    except Exception:
        raise HTTPException(status_code=400, detail="Não foi possível decodificar o arquivo.")
    safe_name = Path(payload.filename).name or "arquivo.bin"
    final_name = f"{uuid.uuid4().hex}_{safe_name}"
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_path = Path(UPLOAD_DIR) / final_name
    with open(file_path, "wb") as f:
        f.write(data)
    return DocumentoUploadOut(url=f"/{UPLOAD_DIR}/{final_name}")


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
        documento = crud.create_documento(db=db, data=payload)
        return DocumentoOut.model_validate(documento)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/documentos", response_model=List[DocumentoOut], tags=["Documentos"])
def listar_documentos(
    contrato_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(require_roles(*ACADEMIC_VIEW_ROLES)),
):
    try:
        documentos = crud.list_documentos(db=db, contrato_id=contrato_id)
        return [DocumentoOut.model_validate(doc) for doc in documentos]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
        documento = crud.update_documento(db=db, documento_id=documento_id, data=payload)
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
