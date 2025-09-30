import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from . import crud, models, schemas
from .database import get_db

load_dotenv()

# --- Configurações de Segurança ---
SECRET_KEY = os.getenv("SECRET_KEY", "6573b3f4e4f8c9d6e7f8a9b0c1d2e3f4g5h6i7j8k9l0m1n2o3p4q5r6s7t8u9v0")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


# --- Funções de Utilitário ---

def verify_password(plain_password: str, hashed_password: str):
    """Verifica se a senha fornecida corresponde ao hash armazenado."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str):
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


# --- Dependência de Autenticação ---

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """
    Decodifica o token, valida as credenciais e retorna o usuário.
    Esta função será usada como uma dependência para proteger os endpoints.
    """
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

# Dependência para verificar se o usuário é um professor
async def get_current_professor(current_user: models.Usuario = Depends(get_current_user)):
    if current_user.tipo_acesso != "professor":
        raise HTTPException(status_code=403, detail="Acesso negado: Requer perfil de professor.")
    return current_user