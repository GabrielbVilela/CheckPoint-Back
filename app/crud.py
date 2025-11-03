from typing import Optional, List
from datetime import date, datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from models import Usuario, Endereco, Contrato, Ponto
from schemas import UsuarioCreate, EnderecoCreate, ContratoCreate, PontoCheckLocation
from utils import ensure_aware

# --------------------------------------------------------------------------
# CRUD: Usuários
# --------------------------------------------------------------------------
def get_usuario_by_email(db: Session, email: str) -> Optional[Usuario]:
    return db.query(Usuario).filter(Usuario.email == email).first()

def get_usuario_by_matricula(db: Session, matricula: str) -> Optional[Usuario]:
    return db.query(Usuario).filter(Usuario.matricula == matricula).first()

def get_usuario_by_contato(db: Session, contato: str) -> Optional[Usuario]:
    return db.query(Usuario).filter(Usuario.contato == contato).first()

def list_usuarios(db: Session, tipo: Optional[str] = None) -> List[Usuario]:
    if tipo:
        return db.query(Usuario).filter(Usuario.tipo_acesso == tipo).all()
    return db.query(Usuario).all()

def create_usuario(db: Session, usuario: UsuarioCreate) -> Usuario:
    novo = Usuario(
        nome=usuario.nome,
        matricula=usuario.matricula,
        senha_hash=usuario.senha,  # ajuste conforme seu hash real
        contato=usuario.contato,
        email=usuario.email,
        turma=usuario.turma,
        tipo_acesso=usuario.tipo_acesso,
    )
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return novo

# --------------------------------------------------------------------------
# CRUD: Endereços
# --------------------------------------------------------------------------
def create_endereco(db: Session, data: EnderecoCreate) -> Endereco:
    novo = Endereco(
        cep=data.cep,
        logradouro=data.logradouro,
        cidade=data.cidade,
        estado=data.estado,
        numero=data.numero,
        bairro=data.bairro,
    )
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return novo

def list_enderecos(db: Session) -> List[Endereco]:
    return db.query(Endereco).all()

# --------------------------------------------------------------------------
# CRUD: Contratos
# --------------------------------------------------------------------------
def get_user_by_id(db: Session, uid: int) -> Optional[Usuario]:
    return db.query(Usuario).filter(Usuario.id == uid).first()

def get_endereco_by_id(db: Session, eid: int) -> Optional[Endereco]:
    return db.query(Endereco).filter(Endereco.id == eid).first()

def get_contrato_ativo_do_aluno(db: Session, id_aluno: int) -> Optional[Contrato]:
    # Compat: boolean OR strings legadas
    return (
        db.query(Contrato)
        .filter(
            and_(
                Contrato.id_aluno == id_aluno,
                or_(
                    Contrato.status.is_(True),               # booleano certo
                    getattr(Contrato, "status") == "Ativo",  # legados
                    getattr(Contrato, "status") == "TRUE",
                    getattr(Contrato, "status") == "True",
                    getattr(Contrato, "status") == "true",
                    getattr(Contrato, "status") == "1",
                ),
            )
        )
        .first()
    )

def create_contrato(db: Session, data: ContratoCreate) -> Contrato:
    aluno = get_user_by_id(db, data.id_aluno)
    prof = get_user_by_id(db, data.id_professor)
    end = get_endereco_by_id(db, data.id_endereco)
    if not aluno or not prof or not end:
        raise ValueError("Aluno, Professor ou Endereço inválido(s).")

    novo = Contrato(
        id_aluno=data.id_aluno,
        id_professor=data.id_professor,
        id_endereco=data.id_endereco,
        data_inicio=data.data_inicio,
        data_final=data.data_final,
        status=True if data.status is None else bool(data.status),
    )
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return novo

def get_contratos(db: Session) -> List[Contrato]:
    return db.query(Contrato).all()

# --------------------------------------------------------------------------
# CRUD: Ponto Eletrônico
# --------------------------------------------------------------------------
def ponto_entrada(db: Session, matricula: str, payload: PontoCheckLocation) -> Ponto:
    user = get_usuario_by_matricula(db, matricula)
    if not user:
        raise ValueError("Usuário não encontrado.")

    contrato = get_contrato_ativo_do_aluno(db, payload.id_aluno)
    if not contrato:
        raise ValueError("Nenhum contrato ativo para este aluno.")

    # Impede ponto duplicado aberto para o contrato
    ponto_aberto = (
        db.query(Ponto)
        .filter(and_(Ponto.id_contrato == contrato.id, Ponto.ativo.is_(True)))
        .first()
    )
    if ponto_aberto:
        raise ValueError("Já existe um ponto em aberto para este aluno.")

    agora = datetime.utcnow()
    p = Ponto(
        id_contrato=contrato.id,
        data=date.today(),
        hora_entrada=agora,
        ativo=True,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p

def ponto_saida(db: Session, matricula: str) -> Ponto:
    user = get_usuario_by_matricula(db, matricula)
    if not user:
        raise ValueError("Usuário não encontrado.")

    # Busca ponto em aberto (ativo) pelo contrato do aluno
    p = (
        db.query(Ponto)
        .join(Contrato, Contrato.id == Ponto.id_contrato)
        .filter(and_(Contrato.id_aluno == user.id, Ponto.ativo.is_(True)))
        .first()
    )
    if not p:
        raise ValueError("Nenhum ponto em aberto encontrado para este aluno.")

    p.hora_saida = datetime.utcnow()
    # Garante timezone-aware para cálculo seguro
    he = ensure_aware(p.hora_entrada)
    hs = ensure_aware(p.hora_saida)
    if he and hs:
        delta = hs - he
        p.tempo_trabalhado_minutos = int(delta.total_seconds() // 60)
    p.ativo = False

    db.commit()
    db.refresh(p)
    return p


def get_ponto_aberto(db: Session, id_aluno: int) -> Optional[Ponto]:
    """Retorna o ponto em aberto (ativo) do aluno, se existir."""
    return (
        db.query(Ponto)
        .join(Contrato, Contrato.id == Ponto.id_contrato)
        .filter(and_(Contrato.id_aluno == id_aluno, Ponto.ativo.is_(True)))
        .first()
    )
