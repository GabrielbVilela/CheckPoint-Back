from sqlalchemy.orm import Session
from fastapi import HTTPException 
from . import models, schemas, utils, auth
from datetime import datetime, timezone
from app import services


# ... (suas funções de usuário, endereço e contrato existentes) ...
def get_usuario_by_email(db: Session, email: str):
    return db.query(models.Usuario).filter(models.Usuario.email == email).first()

def get_usuario_by_matricula(db: Session, matricula: str):
    return db.query(models.Usuario).filter(models.Usuario.matricula == matricula).first()

def create_usuario(db: Session, usuario: schemas.UsuarioCreate):
    hashed_password = auth.get_password_hash(usuario.senha)
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

def list_usuarios(db: Session, tipo: str = None, skip: int = 0, limit: int = 100):
    query = db.query(models.Usuario)
    if tipo:
        query = query.filter(models.Usuario.tipo_acesso == tipo)
    return query.offset(skip).limit(limit).all()

def create_endereco(db: Session, endereco: schemas.EnderecoCreate):
    address_string = f"{endereco.logradouro}, {endereco.numero}, {endereco.bairro}, {endereco.cidade}, {endereco.estado}"
    coords = services.get_coordinates_from_google(address_string)
    db_endereco = models.Endereco(
        **endereco.model_dump(),
        lat=coords["lat"] if coords else None,
        long=coords["lng"] if coords else None
    )
    db.add(db_endereco)
    db.commit()
    db.refresh(db_endereco)
    return db_endereco

def create_contrato(db: Session, contrato: schemas.ContratoCreate):
    db_aluno = db.query(models.Usuario).filter(models.Usuario.id == contrato.id_aluno).first()
    if not db_aluno or db_aluno.tipo_acesso != 'aluno':
        raise HTTPException(status_code=404, detail=f"Aluno com id {contrato.id_aluno} não encontrado ou tipo de acesso inválido.")
    
    db_professor = db.query(models.Usuario).filter(models.Usuario.id == contrato.id_professor).first()
    if not db_professor or db_professor.tipo_acesso != 'professor':
        raise HTTPException(status_code=404, detail=f"Professor com id {contrato.id_professor} não encontrado ou tipo de acesso inválido.")

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


# --- ADICIONE AS FUNÇÕES ABAIXO ---

def get_active_contract_for_student(db: Session, id_aluno: int):
    """Busca o contrato ativo para um determinado aluno."""
    return db.query(models.Contrato).filter(
        models.Contrato.id_aluno == id_aluno,
        models.Contrato.status == 'Ativo'
    ).first()

def registrar_entrada(db: Session, location_data: schemas.PontoCheckLocation):
    contrato_ativo = get_active_contract_for_student(db, location_data.id_aluno)
    if not contrato_ativo:
        raise HTTPException(status_code=404, detail="Nenhum contrato ativo encontrado para este aluno.")

    ponto_existente = db.query(models.Ponto).filter(
        models.Ponto.id_contrato == contrato_ativo.id,
        models.Ponto.ativo == True
    ).first()
    if ponto_existente:
        raise HTTPException(status_code=400, detail="Já existe um registro de ponto ativo.")

    endereco_estagio = contrato_ativo.endereco
    if not endereco_estagio.lat or not endereco_estagio.long:
        raise HTTPException(status_code=400, detail="O endereço do estágio não possui coordenadas cadastradas.")

    distancia = utils.haversine_distance(
        endereco_estagio.long, 
        endereco_estagio.lat, 
        location_data.longitude_atual, 
        location_data.latitude_atual
    )

    RAIO_PERMITIDO_METROS = 100
    if distancia > RAIO_PERMITIDO_METROS:
        raise HTTPException(
            status_code=403, 
            detail=f"Você está a {int(distancia)}m do local de estágio. A entrada só é permitida dentro de {RAIO_PERMITIDO_METROS}m."
        )

    novo_ponto = models.Ponto(id_contrato=contrato_ativo.id)
    db.add(novo_ponto)
    db.commit()
    db.refresh(novo_ponto)
    return novo_ponto

def registrar_saida(db: Session, id_aluno: int):
    ponto_ativo = db.query(models.Ponto).join(models.Contrato).filter(
        models.Contrato.id_aluno == id_aluno,
        models.Ponto.ativo == True
    ).first()
    if not ponto_ativo:
        raise HTTPException(status_code=404, detail="Nenhum ponto ativo encontrado para registrar a saída.")

    ponto_ativo.hora_saida = datetime.now(timezone.utc)
    ponto_ativo.ativo = False
    
    tempo_trabalhado = ponto_ativo.hora_saida - ponto_ativo.hora_entrada
    ponto_ativo.tempo_trabalhado_minutos = int(tempo_trabalhado.total_seconds() / 60)

    db.commit()
    db.refresh(ponto_ativo)
    return ponto_ativo

def check_location(db: Session, location_data: schemas.PontoCheckLocation):
    contrato_ativo = get_active_contract_for_student(db, location_data.id_aluno)
    if not contrato_ativo:
        raise HTTPException(status_code=404, detail="Nenhum contrato ativo encontrado para este aluno.")
    
    endereco_estagio = contrato_ativo.endereco
    if not endereco_estagio.lat or not endereco_estagio.long:
        raise HTTPException(status_code=400, detail="O endereço do estágio não possui coordenadas cadastradas.")

    distancia = utils.haversine_distance(
        endereco_estagio.long,
        endereco_estagio.lat,
        location_data.longitude_atual,
        location_data.latitude_atual
    )

    RAIO_PERMITIDO_METROS = 100
    dentro_da_area = distancia <= RAIO_PERMITIDO_METROS

    return {"dentro_da_area": dentro_da_area, "distancia_metros": round(distancia, 2)}
