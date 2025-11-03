import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from . import crud, models, schemas
from .database import get_db
from .models import TipoUsuario

# Configuração de Segurança
SECRET_KEY = os.getenv("SECRET_KEY", "uma_chave_secreta_muito_longa_e_aleatoria")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))

# Contexto para Hashing de Senhas
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Esquema de Autenticação OAuth2
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica se a senha fornecida corresponde ao hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Gera o hash de uma senha."""
    return pwd_context.hash(password)


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
    """Autentica um utilizador pela matrícula e senha."""
    user = crud.get_usuario_by_matricula(db, matricula=matricula)
    if not user or not verify_password(password, user.senha_hash):
        return None
    return user


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> models.Usuario:
    """Decodifica o token e retorna o utilizador correspondente."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não foi possível validar as credenciais",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        matricula: str = payload.get("sub")
        if matricula is None:
            raise credentials_exception
        token_data = schemas.TokenData(matricula=matricula)
    except JWTError:
        raise credentials_exception
    
    user = crud.get_usuario_by_matricula(db, matricula=token_data.matricula)
    if user is None:
        raise credentials_exception
    return user


def get_current_active_user(current_user: models.Usuario = Depends(get_current_user)) -> models.Usuario:
    """Verifica se o utilizador obtido do token está ativo."""
    # Futuramente, pode-se adicionar uma verificação de 'user.disabled' aqui
    return current_user

# --- Funções de Dependência por Perfil ---

def get_current_active_aluno(current_user: models.Usuario = Depends(get_current_active_user)) -> models.Usuario:
    """Verifica se o utilizador logado é um aluno."""
    if current_user.tipo_acesso != TipoUsuario.aluno.value:
        raise HTTPException(status_code=403, detail="Acesso restrito a alunos.")
    return current_user

def get_current_active_professor(current_user: models.Usuario = Depends(get_current_active_user)) -> models.Usuario:
    """Verifica se o utilizador logado é um professor."""
    if current_user.tipo_acesso != TipoUsuario.professor.value:
        raise HTTPException(status_code=403, detail="Acesso restrito a professores.")
    return current_user

