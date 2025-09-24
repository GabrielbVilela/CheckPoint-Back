from sqlalchemy.orm import Session
from fastapi import HTTPException 
from . import models, schemas, services
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_usuario_by_email(db: Session, email: str):
    return db.query(models.Usuario).filter(models.Usuario.email == email).first()

def get_usuario_by_matricula(db: Session, matricula: str):
    return db.query(models.Usuario).filter(models.Usuario.matricula == matricula).first()

def create_usuario(db: Session, usuario: schemas.UsuarioCreate):
    hashed_password = pwd_context.hash(usuario.senha)
    db_usuario = models.Usuario(
        nome=usuario.nome,
        matricula=usuario.matricula,
        senha_hash=hashed_password,
        contato=usuario.contato,
        email=usuario.email,
        turma=usuario.turma,
        tipo_acesso=usuario.tipo_acesso,
    )
    db.add(db_usuario)
    db.commit()
    db.refresh(db_usuario)
    return db_usuario

def verify_password(plain_password: str, hashed_password: str):
    return pwd_context.verify(plain_password, hashed_password)

def list_usuarios(db: Session, tipo: str = None, skip: int = 0, limit: int = 100):
    query = db.query(models.Usuario)
    if tipo:
        query = query.filter(models.Usuario.tipo_acesso == tipo)
    return query.offset(skip).limit(limit).all()

# --- FUNÇÕES PARA ENDEREÇO --- 
def create_endereco(db: Session, endereco: schemas.EnderecoCreate):
    # Formata o endereço completo para a busca
    address_string = f"{endereco.logradouro}, {endereco.numero}, {endereco.bairro}, {endereco.cidade}, {endereco.estado}"
    
    coords = services.get_coordinates_from_google(address_string)
    
    # Cria o objeto do banco de dados com ou sem coordenadas
    db_endereco = models.Endereco(
        **endereco.model_dump(),
        lat=coords["lat"] if coords else None,
        long=coords["lng"] if coords else None
    )
    
    db.add(db_endereco)
    db.commit()
    db.refresh(db_endereco)
    return db_endereco

# --- FUNÇÕES PARA CONTRATO ---
def create_contrato(db: Session, contrato: schemas.ContratoCreate):
    # Validação: Verifica se o aluno existe e tem o tipo de acesso correto
    db_aluno = db.query(models.Usuario).filter(models.Usuario.id == contrato.id_aluno).first()
    if not db_aluno or db_aluno.tipo_acesso != 'aluno':
        raise HTTPException(status_code=404, detail=f"Aluno com id {contrato.id_aluno} não encontrado ou tipo de acesso inválido.")
    
    # Validação: Verifica se o professor existe e tem o tipo de acesso correto
    db_professor = db.query(models.Usuario).filter(models.Usuario.id == contrato.id_professor).first()
    if not db_professor or db_professor.tipo_acesso != 'professor':
        raise HTTPException(status_code=404, detail=f"Professor com id {contrato.id_professor} não encontrado ou tipo de acesso inválido.")

    # Validação: Verifica se o endereço existe
    db_endereco = db.query(models.Endereco).filter(models.Endereco.id == contrato.id_endereco).first()
    if not db_endereco:
        raise HTTPException(status_code=404, detail=f"Endereço com id {contrato.id_endereco} não encontrado.")

    db_contrato = models.Contrato(**contrato.model_dump())
    db.add(db_contrato)
    db.commit()
    db.refresh(db_contrato)
    return db_contrato

def get_contratos(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Contrato).offset(skip).limit(limit).all()

def get_contrato_by_id(db: Session, contrato_id: int):
    return db.query(models.Contrato).filter(models.Contrato.id == contrato_id).first()