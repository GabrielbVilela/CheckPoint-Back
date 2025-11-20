import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from . import crud, models, schemas
from .database import get_db
from .schemas import TipoUsuario
from .security import verify_password

# Configuração de Segurança
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY environment variable is required for token signing.")

ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))

# Hash fixo usado para equilibrar tempo de resposta em autenticação falha
DUMMY_PASSWORD_HASH = "$2b$12$C6UzMDM.H6dfI/f/IKcEeO57apqAIWNUP8NO7P3R8qRzu2Jp2uH5e"

# Esquema de AutenticaÃ§Ã£o OAuth2
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Cria um novo token de acesso JWT."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def authenticate_user(db: Session, matricula: str, password: str) -> Optional[models.Usuario]:
    """Autentica um utilizador pela matrícula e mitiga enumeração por tempo."""
    user = crud.get_usuario_by_matricula(db, matricula=matricula)

    # Sempre verifica um hash (real ou dummy) para diminuir diferença de tempo
    hash_to_check = user.senha_hash if user else DUMMY_PASSWORD_HASH
    if not verify_password(password, hash_to_check):
        return None

    if not user:
        return None
    return user


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> models.Usuario:
    """Decodifica o token e retorna o utilizador correspondente."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="NÃ£o foi possÃ­vel validar as credenciais",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        raw_uid = payload.get("uid", payload.get("sub"))
        matricula = payload.get("matricula") or payload.get("sub")

        if raw_uid is None:
            raise credentials_exception

        try:
            uid = int(raw_uid)
        except (TypeError, ValueError):
            raise credentials_exception

        token_data = schemas.TokenData(uid=uid, matricula=matricula)
    except JWTError:
        raise credentials_exception

    user = crud.get_user_by_id(db, token_data.uid)
    if user is None:
        raise credentials_exception

    if token_data.matricula and user.matricula != token_data.matricula:
        raise credentials_exception

    return user


def get_current_active_user(current_user: models.Usuario = Depends(get_current_user)) -> models.Usuario:
    """Verifica se o utilizador obtido do token estÃ¡ ativo."""
    # Futuramente, pode-se adicionar uma verificaÃ§Ã£o de 'user.disabled' aqui
    return current_user

# --- FunÃ§Ãµes de DependÃªncia por Perfil ---

def get_current_active_aluno(current_user: models.Usuario = Depends(get_current_active_user)) -> models.Usuario:
    """Verifica se o utilizador logado Ã© um aluno."""
    if current_user.tipo_acesso != TipoUsuario.aluno.value:
        raise HTTPException(status_code=403, detail="Acesso restrito a alunos.")
    return current_user

def get_current_active_professor(current_user: models.Usuario = Depends(get_current_active_user)) -> models.Usuario:
    """Verifica se o utilizador logado Ã© um professor."""
    if current_user.tipo_acesso != TipoUsuario.professor.value:
        raise HTTPException(status_code=403, detail="Acesso restrito a professores.")
    return current_user


def get_current_active_supervisor(current_user: models.Usuario = Depends(get_current_active_user)) -> models.Usuario:
    """Verifica se o utilizador logado é um supervisor."""
    if current_user.tipo_acesso != TipoUsuario.supervisor.value:
        raise HTTPException(status_code=403, detail="Acesso restrito a supervisores.")
    return current_user

