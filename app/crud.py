import logging
import math
import re
import json
from typing import Optional, List, Tuple
from datetime import date, datetime, timedelta
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, func, cast, String, or_

from . import services, schemas, models
from .models import (
    Usuario,
    Endereco,
    Contrato,
    Ponto,
    Curso,
    Turma,
    Empresa,
    SupervisorExterno,
    Convenio,
    Justificativa,
    JustificativaLog,
    DiarioAtividade,
    Documento,
    AvaliacaoRubrica,
    Avaliacao,
)
from .schemas import (
    UsuarioCreate,
    EnderecoCreate,
    ContratoCreate,
    PontoCheckLocation,
    AlunoCadastroIn,
    PontoLocalizacaoIn,
    CursoCreate,
    TurmaCreate,
    EmpresaCreate,
    SupervisorExternoCreate,
    ConvenioCreate,
    JustificativaCreate,
    JustificativaStatus,
    TipoUsuario,
    DiarioAtividadeCreate,
    DiarioStatus,
    DocumentoCreate,
    DocumentoUpdate,
    AvaliacaoRubricaCreate,
    AvaliacaoCreate,
    AvaliacaoStatus,
)
from .utils import ensure_aware, haversine_distance
from .security import get_password_hash
from .config import (
    PONTO_RAIO_PADRAO_METROS,
    PONTO_TOLERANCIA_PADRAO_MINUTOS,
    PONTO_ARREDONDAMENTO_MINUTOS,
    JUSTIFICATIVA_SLA_HORAS,
)

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# CRUD: Usuários
# --------------------------------------------------------------------------
def get_usuario_by_email(db: Session, email: str) -> Optional[Usuario]:
    return db.query(Usuario).filter(Usuario.email == email).first()

def get_usuario_by_matricula(db: Session, matricula: str) -> Optional[Usuario]:
    return db.query(Usuario).filter(Usuario.matricula == matricula).first()

def get_usuario_by_contato(db: Session, contato: str) -> Optional[Usuario]:
    return db.query(Usuario).filter(Usuario.contato == contato).first()

def list_usuarios(
    db: Session,
    tipo: Optional[str] = None,
    search: Optional[str] = None,
    limit: Optional[int] = None,
) -> List[Usuario]:
    query = db.query(Usuario)
    if tipo:
        query = query.filter(Usuario.tipo_acesso == tipo)
    if search:
        termo = f"%{search.strip().lower()}%"
        query = query.filter(
            or_(
                func.lower(Usuario.nome).like(termo),
                func.lower(Usuario.matricula).like(termo),
                func.lower(Usuario.email).like(termo),
                func.lower(Usuario.turma).like(termo),
            )
        )
    query = query.order_by(Usuario.nome.asc())
    if limit:
        query = query.limit(limit)
    return query.all()

def create_usuario(db: Session, usuario: UsuarioCreate) -> Usuario:
    novo = Usuario(
        nome=usuario.nome,
        matricula=usuario.matricula,
        senha_hash=get_password_hash(usuario.senha),
        contato=usuario.contato,
        email=usuario.email,
        turma=usuario.turma,
        periodo=usuario.periodo,
        tipo_acesso=usuario.tipo_acesso,
    )
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return novo

# --------------------------------------------------------------------------
# CRUD: Cursos
# --------------------------------------------------------------------------
def create_curso(db: Session, data: CursoCreate) -> Curso:
    curso = Curso(
        nome=data.nome.strip(),
        carga_horaria_total=data.carga_horaria_total,
        competencias=data.competencias,
    )
    db.add(curso)
    db.commit()
    db.refresh(curso)
    return curso


def list_cursos(db: Session) -> List[Curso]:
    return db.query(Curso).order_by(Curso.nome.asc()).all()


def get_curso_by_id(db: Session, curso_id: int) -> Optional[Curso]:
    return db.query(Curso).filter(Curso.id == curso_id).first()


# --------------------------------------------------------------------------
# CRUD: Turmas
# --------------------------------------------------------------------------
def create_turma(db: Session, data: TurmaCreate) -> Turma:
    curso = get_curso_by_id(db, data.id_curso)
    if not curso:
        raise ValueError("Curso informado não existe.")

    turma = Turma(
        nome=data.nome.strip(),
        ano=data.ano,
        semestre=data.semestre,
        turno=data.turno,
        id_curso=data.id_curso,
    )
    db.add(turma)
    db.commit()
    db.refresh(turma)
    return turma


def list_turmas(db: Session) -> List[Turma]:
    return db.query(Turma).order_by(Turma.nome.asc()).all()


def get_turma_by_id(db: Session, turma_id: int) -> Optional[Turma]:
    return db.query(Turma).filter(Turma.id == turma_id).first()


# --------------------------------------------------------------------------
# CRUD: Empresas e Supervisores
# --------------------------------------------------------------------------
def create_empresa(db: Session, data: EmpresaCreate) -> Empresa:
    empresa = Empresa(
        razao_social=data.razao_social.strip(),
        nome_fantasia=(data.nome_fantasia.strip() if data.nome_fantasia else None),
        cnpj=(data.cnpj.strip() if data.cnpj else None),
        telefone=(data.telefone.strip() if data.telefone else None),
        email=(data.email.strip() if data.email else None),
    )
    db.add(empresa)
    db.commit()
    db.refresh(empresa)
    return empresa


def list_empresas(db: Session) -> List[Empresa]:
    return db.query(Empresa).order_by(Empresa.razao_social.asc()).all()


def update_empresa(db: Session, empresa_id: int, data: schemas.EmpresaUpdate) -> Empresa:
    empresa = db.query(Empresa).filter(Empresa.id == empresa_id).first()
    if not empresa:
        raise ValueError("Empresa não encontrada.")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(empresa, field, value)
    db.commit()
    db.refresh(empresa)
    return empresa


def delete_empresa(db: Session, empresa_id: int) -> None:
    empresa = db.query(Empresa).filter(Empresa.id == empresa_id).first()
    if not empresa:
        raise ValueError("Empresa não encontrada.")
    db.delete(empresa)
    db.commit()


def get_empresa_by_id(db: Session, empresa_id: int) -> Optional[Empresa]:
    return db.query(Empresa).filter(Empresa.id == empresa_id).first()


def create_supervisor_externo(db: Session, data: SupervisorExternoCreate) -> SupervisorExterno:
    empresa = get_empresa_by_id(db, data.id_empresa)
    if not empresa:
        raise ValueError("Empresa informada n�o existe.")

    supervisor = SupervisorExterno(
        nome=data.nome.strip(),
        email=(data.email.strip() if data.email else None),
        telefone=(data.telefone.strip() if data.telefone else None),
        cargo=(data.cargo.strip() if data.cargo else None),
        id_empresa=data.id_empresa,
    )
    db.add(supervisor)
    db.commit()
    db.refresh(supervisor)
    return supervisor


def list_supervisores_externos(db: Session) -> List[SupervisorExterno]:
    return db.query(SupervisorExterno).order_by(SupervisorExterno.nome.asc()).all()


def get_supervisor_externo_by_id(db: Session, supervisor_id: int) -> Optional[SupervisorExterno]:
    return db.query(SupervisorExterno).filter(SupervisorExterno.id == supervisor_id).first()


def update_supervisor_externo(
    db: Session,
    supervisor_id: int,
    data: schemas.SupervisorExternoUpdate,
) -> SupervisorExterno:
    supervisor = get_supervisor_externo_by_id(db, supervisor_id)
    if not supervisor:
        raise ValueError("Supervisor n?o encontrado.")

    payload = data.model_dump(exclude_unset=True)
    if "id_empresa" in payload and payload["id_empresa"] is not None:
        empresa = get_empresa_by_id(db, payload["id_empresa"])
        if not empresa:
            raise ValueError("Empresa informada n?o existe.")
    for field, value in payload.items():
        setattr(supervisor, field, value)
    db.commit()
    db.refresh(supervisor)
    return supervisor


def delete_supervisor_externo(db: Session, supervisor_id: int) -> None:
    supervisor = get_supervisor_externo_by_id(db, supervisor_id)
    if not supervisor:
        raise ValueError("Supervisor n?o encontrado.")
    db.delete(supervisor)
    db.commit()


# --------------------------------------------------------------------------
# CRUD: Conv�nios
# --------------------------------------------------------------------------
def create_convenio(db: Session, data: ConvenioCreate) -> Convenio:
    empresa = get_empresa_by_id(db, data.id_empresa)
    if not empresa:
        raise ValueError("Empresa informada n�o existe.")
    curso = get_curso_by_id(db, data.id_curso)
    if not curso:
        raise ValueError("Curso informado n�o existe.")

    convenio = Convenio(
        id_empresa=data.id_empresa,
        id_curso=data.id_curso,
        data_inicio=data.data_inicio,
        data_fim=data.data_fim,
        status=True if data.status is None else bool(data.status),
        descricao=data.descricao,
    )
    db.add(convenio)
    db.commit()
    db.refresh(convenio)
    return convenio


def list_convenios(db: Session) -> List[Convenio]:
    return (
        db.query(Convenio)
        .options(joinedload(Convenio.empresa), joinedload(Convenio.curso))
        .order_by(Convenio.id.desc())
        .all()
    )


def get_convenio_by_id(db: Session, convenio_id: int) -> Optional[Convenio]:
    return db.query(Convenio).filter(Convenio.id == convenio_id).first()


def update_convenio(db: Session, convenio_id: int, data: schemas.ConvenioUpdate) -> Convenio:
    convenio = get_convenio_by_id(db, convenio_id)
    if not convenio:
        raise ValueError("Convênio não encontrado.")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(convenio, field, value)
    db.commit()
    db.refresh(convenio)
    return convenio


def delete_convenio(db: Session, convenio_id: int) -> None:
    convenio = get_convenio_by_id(db, convenio_id)
    if not convenio:
        raise ValueError("Convênio não encontrado.")
    db.delete(convenio)
    db.commit()


def create_documento(db: Session, data: DocumentoCreate) -> Documento:
    contrato = get_contrato_by_id(db, data.id_contrato)
    if not contrato:
        raise ValueError("Contrato informado não existe.")
    documento = Documento(
        id_contrato=data.id_contrato,
        tipo=data.tipo.value if hasattr(data.tipo, "value") else data.tipo,
        arquivo_url=data.arquivo_url,
        status="pendente",
        observacoes=data.observacoes,
    )
    db.add(documento)
    db.commit()
    db.refresh(documento)
    return documento


def list_documentos(db: Session, contrato_id: Optional[int] = None) -> List[Documento]:
    query = db.query(Documento).options(joinedload(Documento.contrato))
    if contrato_id:
        query = query.filter(Documento.id_contrato == contrato_id)
    return query.order_by(Documento.criado_em.desc()).all()


def get_documento_by_id(db: Session, documento_id: int) -> Optional[Documento]:
    return db.query(Documento).filter(Documento.id == documento_id).first()


def update_documento(db: Session, documento_id: int, data: DocumentoUpdate) -> Documento:
    documento = get_documento_by_id(db, documento_id)
    if not documento:
        raise ValueError("Documento não encontrado.")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(documento, field, value)
    db.commit()
    db.refresh(documento)
    return documento


def delete_documento(db: Session, documento_id: int) -> None:
    documento = get_documento_by_id(db, documento_id)
    if not documento:
        raise ValueError("Documento não encontrado.")
    db.delete(documento)
    db.commit()


def get_contrato_by_id(db: Session, contrato_id: int) -> Optional[Contrato]:
    return db.query(Contrato).filter(Contrato.id == contrato_id).first()

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
    # Converte status para string comparável, aceitando legados e booleanos
    status_norm = func.lower(cast(Contrato.status, String))
    return (
        db.query(Contrato)
        .options(joinedload(Contrato.endereco))
        .filter(Contrato.id_aluno == id_aluno)
        .filter(status_norm.in_(["true", "1", "ativo"]))
        .first()
    )

def create_contrato(db: Session, data: ContratoCreate) -> Contrato:
    aluno = get_user_by_id(db, data.id_aluno)
    prof = get_user_by_id(db, data.id_professor)
    end = get_endereco_by_id(db, data.id_endereco)
    if not aluno or not prof or not end:
        raise ValueError("Aluno, Professor ou Endere�o inv�lido(s).")

    turma = None
    if data.id_turma is not None:
        turma = get_turma_by_id(db, data.id_turma)
        if not turma:
            raise ValueError("Turma informada n�o existe.")

    convenio = None
    if data.id_convenio is not None:
        convenio = get_convenio_by_id(db, data.id_convenio)
        if not convenio:
            raise ValueError("Conv�nio informado n�o existe.")

    supervisor_ext = None
    if data.id_supervisor_externo is not None:
        supervisor_ext = get_supervisor_externo_by_id(db, data.id_supervisor_externo)
        if not supervisor_ext:
            raise ValueError("Supervisor externo informado n�o existe.")

    novo = Contrato(
        id_aluno=data.id_aluno,
        id_professor=data.id_professor,
        id_endereco=data.id_endereco,
        data_inicio=data.data_inicio,
        data_final=data.data_final,
        status=True if data.status is None else bool(data.status),
        hora_inicio_prevista=data.hora_inicio_prevista,
        hora_fim_prevista=data.hora_fim_prevista,
        tolerancia_minutos=data.tolerancia_minutos,
        raio_permitido_metros=data.raio_permitido_metros,
        id_turma=data.id_turma if turma else None,
        id_convenio=data.id_convenio if convenio else None,
        id_supervisor_externo=data.id_supervisor_externo if supervisor_ext else None,
    )
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return novo


def get_contratos(db: Session) -> List[Contrato]:
    return db.query(Contrato).all()


def list_contratos_ativos_do_aluno(db: Session, aluno_id: int) -> List[Contrato]:
    hoje = date.today()
    return (
        db.query(Contrato)
        .options(
            joinedload(Contrato.professor),
            joinedload(Contrato.turma).joinedload(Turma.curso),
            joinedload(Contrato.convenio).joinedload(Convenio.empresa),
        )
        .filter(Contrato.id_aluno == aluno_id)
        .filter(Contrato.status.is_(True))
        .filter(or_(Contrato.data_inicio.is_(None), Contrato.data_inicio <= hoje))
        .filter(or_(Contrato.data_final.is_(None), Contrato.data_final >= hoje))
        .order_by(Contrato.data_inicio.desc().nullslast(), Contrato.id.desc())
        .all()
    )


def _only_digits(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    digits = re.sub(r"\D+", "", value)
    return digits or None


def _format_address_for_geocode(data: AlunoCadastroIn) -> str:
    parts = [
        data.logradouro,
        data.numero or "",
        data.bairro or "",
        data.cidade,
        data.estado or "",
        data.cep or "",
    ]
    return ", ".join(filter(None, (part.strip() for part in parts if part)))


def _round_datetime(dt: datetime, base_minutes: int) -> datetime:
    if base_minutes <= 0:
        return dt
    base_seconds = base_minutes * 60
    epoch = datetime(1970, 1, 1, tzinfo=dt.tzinfo)
    elapsed = (dt - epoch).total_seconds()
    rounded_seconds = math.floor((elapsed + base_seconds / 2) / base_seconds) * base_seconds
    return epoch + timedelta(seconds=rounded_seconds)


def _avaliar_geofencing(contrato: Contrato, latitude: float, longitude: float) -> dict:
    raio = contrato.raio_permitido_metros or PONTO_RAIO_PADRAO_METROS
    endereco = contrato.endereco
    if not endereco or endereco.lat is None or endereco.long is None:
        return {
            "dentro": True,
            "mensagem": "Endereço sem coordenadas geográficas. Validação manual necessária.",
            "distancia": None,
            "raio": raio,
            "alerta": "endereco_sem_coordenadas",
            "validado": False,
        }

    distancia = haversine_distance(endereco.long, endereco.lat, longitude, latitude)
    if distancia <= raio:
        return {
            "dentro": True,
            "mensagem": "Localização validada dentro do raio permitido.",
            "distancia": distancia,
            "raio": raio,
            "alerta": None,
            "validado": True,
        }

    return {
        "dentro": False,
        "mensagem": f"Localização fora da área permitida ({distancia:.1f}m > {raio}m).",
        "distancia": distancia,
        "raio": raio,
        "alerta": "fora_da_area",
        "validado": False,
    }


def _avaliar_janela(contrato: Contrato, referencia: datetime) -> dict:
    hora_prevista = contrato.hora_inicio_prevista
    if hora_prevista is None:
        return {"dentro": True, "mensagem": "Sem janela configurada.", "alerta": None}

    tolerancia = contrato.tolerancia_minutos or PONTO_TOLERANCIA_PADRAO_MINUTOS
    janela_inicio = datetime.combine(referencia.date(), hora_prevista) - timedelta(minutes=tolerancia)
    janela_fim = datetime.combine(referencia.date(), hora_prevista) + timedelta(minutes=tolerancia)

    if janela_inicio <= referencia <= janela_fim:
        return {"dentro": True, "mensagem": "Dentro da janela de tolerância.", "alerta": None}

    status = "antes" if referencia < janela_inicio else "depois"
    mensagem = f"Registro realizado fora da janela ({status})."
    return {"dentro": False, "mensagem": mensagem, "alerta": f"fora_da_janela:{status}"}


def verificar_localizacao_para_aluno(
    db: Session, aluno_id: int, payload: PontoLocalizacaoIn
) -> dict:
    contrato = get_contrato_ativo_do_aluno(db, aluno_id)
    if not contrato:
        raise ValueError("Nenhum contrato ativo para este aluno.")

    resultado = _avaliar_geofencing(
        contrato, payload.latitude_atual, payload.longitude_atual
    )
    return {
        "dentro_area": resultado["dentro"],
        "distancia_m": resultado["distancia"],
        "raio_permitido_m": resultado["raio"],
        "mensagem": resultado["mensagem"],
        "alerta": resultado.get("alerta"),
    }


def _calcular_prazo_justificativa() -> datetime:
    return datetime.utcnow() + timedelta(hours=JUSTIFICATIVA_SLA_HORAS)


def _registrar_log_justificativa(
    db: Session,
    justificativa: Justificativa,
    mensagem: str,
) -> JustificativaLog:
    log = JustificativaLog(
        justificativa_id=justificativa.id,
        status=justificativa.status,
        mensagem=mensagem,
    )
    db.add(log)
    db.flush()
    return log


def expirar_justificativas_atrasadas(db: Session) -> int:
    agora = datetime.utcnow()
    pendentes = (
        db.query(Justificativa)
        .filter(Justificativa.status == JustificativaStatus.pendente.value)
        .filter(Justificativa.prazo_resposta.isnot(None))
        .filter(Justificativa.prazo_resposta < agora)
        .all()
    )
    alteradas = 0
    for justificativa in pendentes:
        justificativa.status = JustificativaStatus.expirado.value
        justificativa.resolvido_em = agora
        justificativa.atualizado_em = agora
        _registrar_log_justificativa(db, justificativa, "Justificativa expirada por SLA.")
        alteradas += 1
    if alteradas:
        db.commit()
    return alteradas


def create_justificativa(
    db: Session,
    *,
    aluno_id: int,
    data: JustificativaCreate,
    criado_automaticamente: bool = False,
) -> Justificativa:
    contrato = get_contrato_by_id(db, data.id_contrato)
    if not contrato:
        raise ValueError("Contrato informado não existe.")
    if contrato.id_aluno != aluno_id:
        raise ValueError("Contrato não pertence ao aluno autenticado.")

    if data.id_ponto:
        ponto = db.query(Ponto).filter(Ponto.id == data.id_ponto).first()
        if not ponto:
            raise ValueError("Ponto informado não existe.")
    prazo = _calcular_prazo_justificativa()

    justificativa = Justificativa(
        id_aluno=aluno_id,
        id_contrato=data.id_contrato,
        id_ponto=data.id_ponto,
        tipo=data.tipo.strip(),
        motivo=data.motivo.strip(),
        status=JustificativaStatus.pendente.value,
        evidencia_url=data.evidencia_url,
        data_referencia=data.data_referencia,
        prazo_resposta=prazo,
        criado_automaticamente=criado_automaticamente,
    )
    db.add(justificativa)
    db.flush()
    mensagem = (
        "Justificativa criada automaticamente devido à falha no geofencing."
        if criado_automaticamente
        else "Justificativa criada pelo aluno."
    )
    _registrar_log_justificativa(db, justificativa, mensagem)
    db.commit()
    db.refresh(justificativa)
    return justificativa


def get_justificativa_by_id(db: Session, justificativa_id: int) -> Optional[Justificativa]:
    return db.query(Justificativa).filter(Justificativa.id == justificativa_id).first()


def list_justificativas(
    db: Session,
    current_user: models.Usuario,
    status: Optional[str] = None,
) -> List[Justificativa]:
    expirar_justificativas_atrasadas(db)
    query = db.query(Justificativa)
    if status:
        query = query.filter(Justificativa.status == status)

    if current_user.tipo_acesso == TipoUsuario.aluno.value:
        query = query.filter(Justificativa.id_aluno == current_user.id)
    elif current_user.tipo_acesso == TipoUsuario.professor.value:
        query = query.join(Contrato, Contrato.id == Justificativa.id_contrato).filter(
            Contrato.id_professor == current_user.id
        )
    elif current_user.tipo_acesso == TipoUsuario.supervisor.value:
        query = query.join(Contrato, Contrato.id == Justificativa.id_contrato).filter(
            Contrato.id_supervisor_externo == current_user.id
        )

    return query.order_by(Justificativa.criado_em.desc()).all()


def update_justificativa_status(
    db: Session,
    justificativa_id: int,
    status: JustificativaStatus,
    comentario: Optional[str],
) -> Justificativa:
    justificativa = get_justificativa_by_id(db, justificativa_id)
    if not justificativa:
        raise ValueError("Justificativa não encontrada.")

    if justificativa.status != JustificativaStatus.pendente.value:
        raise ValueError("Justificativa já foi processada.")

    status_value = status.value if isinstance(status, JustificativaStatus) else status
    justificativa.status = status_value
    justificativa.comentario_resolucao = comentario
    justificativa.resolvido_em = datetime.utcnow()
    justificativa.atualizado_em = datetime.utcnow()
    _registrar_log_justificativa(
        db,
        justificativa,
        f"Status atualizado para {status_value}. Comentário: {comentario or '—'}",
    )
    db.commit()
    db.refresh(justificativa)
    return justificativa


def get_justificativas_por_data(db: Session, aluno_id: int, dia: date) -> List[Justificativa]:
    return (
        db.query(Justificativa)
        .filter(Justificativa.id_aluno == aluno_id)
        .filter(Justificativa.data_referencia == dia)
        .order_by(Justificativa.criado_em.desc())
        .all()
    )


def criar_justificativa_automatica_localizacao(
    db: Session,
    contrato: Contrato,
    mensagem: str,
) -> Justificativa:
    payload = JustificativaCreate(
        tipo="ajuste_localizacao",
        motivo=mensagem,
        id_contrato=contrato.id,
        data_referencia=date.today(),
    )
    return create_justificativa(
        db,
        aluno_id=contrato.id_aluno,
        data=payload,
        criado_automaticamente=True,
    )


def create_diario(
    db: Session,
    *,
    aluno_id: int,
    data: DiarioAtividadeCreate,
) -> DiarioAtividade:
    contrato = get_contrato_by_id(db, data.id_contrato)
    if not contrato:
        raise ValueError("Contrato informado não existe.")
    if contrato.id_aluno != aluno_id:
        raise ValueError("Contrato não pertence ao aluno autenticado.")

    diario = DiarioAtividade(
        id_aluno=aluno_id,
        id_contrato=data.id_contrato,
        data_referencia=data.data_referencia,
        resumo=data.resumo.strip(),
        detalhes=(data.detalhes.strip() if data.detalhes else None),
        anexo_url=data.anexo_url,
        status=DiarioStatus.pendente.value,
    )
    db.add(diario)
    db.commit()
    db.refresh(diario)
    return diario


def list_diarios(
    db: Session,
    current_user: models.Usuario,
    status: Optional[str] = None,
    data_referencia: Optional[date] = None,
) -> List[DiarioAtividade]:
    query = db.query(DiarioAtividade)
    if status:
        query = query.filter(DiarioAtividade.status == status)
    if data_referencia:
        query = query.filter(DiarioAtividade.data_referencia == data_referencia)

    if current_user.tipo_acesso == TipoUsuario.aluno.value:
        query = query.filter(DiarioAtividade.id_aluno == current_user.id)
    elif current_user.tipo_acesso == TipoUsuario.professor.value:
        query = query.join(Contrato, Contrato.id == DiarioAtividade.id_contrato).filter(
            Contrato.id_professor == current_user.id
        )
    elif current_user.tipo_acesso == TipoUsuario.supervisor.value:
        query = query.join(Contrato, Contrato.id == DiarioAtividade.id_contrato).filter(
            Contrato.id_supervisor_externo == current_user.id
        )

    return query.order_by(DiarioAtividade.data_referencia.desc(), DiarioAtividade.criado_em.desc()).all()


def get_diario_by_id(db: Session, diario_id: int) -> Optional[DiarioAtividade]:
    return db.query(DiarioAtividade).filter(DiarioAtividade.id == diario_id).first()


def update_diario_status(
    db: Session,
    diario_id: int,
    status: DiarioStatus,
    comentario: Optional[str],
) -> DiarioAtividade:
    diario = get_diario_by_id(db, diario_id)
    if not diario:
        raise ValueError("Diário de atividades não encontrado.")
    if diario.status != DiarioStatus.pendente.value:
        raise ValueError("Diário já foi avaliado.")

    status_value = status.value if isinstance(status, DiarioStatus) else status
    diario.status = status_value
    diario.comentario_avaliador = comentario
    diario.atualizado_em = datetime.utcnow()
    db.commit()
    db.refresh(diario)
    return diario


def get_diarios_por_data(db: Session, aluno_id: int, dia: date) -> List[DiarioAtividade]:
    return (
        db.query(DiarioAtividade)
        .filter(DiarioAtividade.id_aluno == aluno_id)
        .filter(DiarioAtividade.data_referencia == dia)
        .order_by(DiarioAtividade.criado_em.asc())
        .all()
    )


# --------------------------------------------------------------------------
# Avaliações e Rubricas
# --------------------------------------------------------------------------
def create_rubrica(db: Session, data: AvaliacaoRubricaCreate) -> AvaliacaoRubrica:
    rubrica = AvaliacaoRubrica(
        nome=data.nome.strip(),
        descricao=(data.descricao.strip() if data.descricao else None),
        criterios=data.criterios,
        ativo=True,
    )
    db.add(rubrica)
    db.commit()
    db.refresh(rubrica)
    return rubrica


def list_rubricas(db: Session, somente_ativas: bool = False) -> List[AvaliacaoRubrica]:
    query = db.query(AvaliacaoRubrica)
    if somente_ativas:
        query = query.filter(AvaliacaoRubrica.ativo.is_(True))
    return query.order_by(AvaliacaoRubrica.nome.asc()).all()


def get_rubrica_by_id(db: Session, rubrica_id: int) -> Optional[AvaliacaoRubrica]:
    return db.query(AvaliacaoRubrica).filter(AvaliacaoRubrica.id == rubrica_id).first()


def create_avaliacao(
    db: Session,
    *,
    contrato_id: int,
    rubrica_id: int,
    avaliador_id: int,
    payload: AvaliacaoCreate,
    AvaliacaoStatus,
) -> Avaliacao:
    contrato = get_contrato_by_id(db, contrato_id)
    if not contrato:
        raise ValueError("Contrato informado não existe.")
    rubrica = get_rubrica_by_id(db, rubrica_id)
    if not rubrica or not rubrica.ativo:
        raise ValueError("Rubrica inválida ou inativa.")

    notas_json = json.dumps(payload.notas or {})
    avaliacao = Avaliacao(
        id_contrato=contrato_id,
        id_rubrica=rubrica_id,
        id_avaliador=avaliador_id,
        periodo=payload.periodo,
        notas=notas_json,
        feedback=payload.feedback,
        plano_acao=payload.plano_acao,
        status=AvaliacaoStatus.concluida.value,
        exportado=False,
    )
    db.add(avaliacao)
    db.commit()
    db.refresh(avaliacao)
    return avaliacao


def list_avaliacoes(
    db: Session,
    current_user: models.Usuario,
    contrato_id: Optional[int] = None,
) -> List[Avaliacao]:
    query = (
        db.query(Avaliacao)
        .options(joinedload(Avaliacao.rubrica))
    )
    if contrato_id:
        query = query.filter(Avaliacao.id_contrato == contrato_id)

    if current_user.tipo_acesso == TipoUsuario.aluno.value:
        query = query.join(Contrato, Contrato.id == Avaliacao.id_contrato).filter(
            Contrato.id_aluno == current_user.id
        )
    elif current_user.tipo_acesso == TipoUsuario.professor.value:
        query = query.join(Contrato, Contrato.id == Avaliacao.id_contrato).filter(
            Contrato.id_professor == current_user.id
        )
    elif current_user.tipo_acesso == TipoUsuario.supervisor.value:
        query = query.join(Contrato, Contrato.id == Avaliacao.id_contrato).filter(
            Contrato.id_supervisor_externo.isnot(None)
        )

    return query.order_by(Avaliacao.criado_em.desc()).all()


def mark_avaliacoes_exportadas(db: Session, avaliacoes: List[Avaliacao]) -> None:
    for avaliacao in avaliacoes:
        avaliacao.exportado = True
    db.commit()


def export_avaliacoes_csv(avaliacoes: List[Avaliacao]) -> str:
    import csv
    from io import StringIO

    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "ID",
            "Contrato",
            "Aluno",
            "Rubrica",
            "Periodo",
            "Notas",
            "Feedback",
            "PlanoAcao",
            "Avaliador",
            "Status",
            "CriadoEm",
        ]
    )
    for avaliacao in avaliacoes:
        notas = avaliacao.notas or "{}"
        contrato = avaliacao.contrato
        writer.writerow(
            [
                avaliacao.id,
                contrato.id if contrato else "",
                contrato.id_aluno if contrato else "",
                avaliacao.rubrica.nome if avaliacao.rubrica else "",
                avaliacao.periodo or "",
                notas,
                avaliacao.feedback or "",
                avaliacao.plano_acao or "",
                avaliacao.id_avaliador,
                avaliacao.status,
                avaliacao.criado_em.isoformat(),
            ]
        )
    return buffer.getvalue()


def get_avaliacoes_por_data(db: Session, aluno_id: int, dia: date) -> List[Avaliacao]:
    return (
        db.query(Avaliacao)
        .join(Contrato, Contrato.id == Avaliacao.id_contrato)
        .filter(Contrato.id_aluno == aluno_id)
        .filter(Avaliacao.periodo == dia.isoformat())
        .all()
    )


def create_aluno_completo(db: Session, data: AlunoCadastroIn, id_professor: int) -> Tuple[Usuario, Endereco, Contrato]:
    if get_usuario_by_matricula(db, data.matricula):
        raise ValueError("Matrícula já cadastrada.")
    if get_usuario_by_email(db, data.email):
        raise ValueError("E-mail já cadastrado.")

    contato_normalizado = _only_digits(data.celular) or data.celular
    if contato_normalizado and get_usuario_by_contato(db, contato_normalizado):
        raise ValueError("Número de contato já cadastrado.")

    professor = get_user_by_id(db, id_professor)
    if not professor:
        raise ValueError("Professor de referência inválido.")

    senha_plana = data.senha or data.matricula
    if not senha_plana:
        raise ValueError("Senha ou matrícula devem ser fornecidas.")

    aluno = Usuario(
        nome=data.nome.strip(),
        matricula=data.matricula.strip(),
        senha_hash=get_password_hash(senha_plana),
        contato=contato_normalizado,
        email=data.email.strip(),
        turma=data.turma.strip(),
        periodo=(data.periodo.strip() if data.periodo else None),
        tipo_acesso="aluno",
    )

    endereco = Endereco(
        cep=_only_digits(data.cep),
        logradouro=data.logradouro.strip(),
        cidade=data.cidade.strip(),
        estado=(data.estado or "").strip(),
        numero=(data.numero.strip() if data.numero else None),
        bairro=(data.bairro.strip() if data.bairro else None),
    )

    # Geocodificação opcional (melhor esforço)
    try:
        coords = services.get_coordinates_from_google(_format_address_for_geocode(data))
        if coords:
            endereco.lat = coords.get("lat")
            endereco.long = coords.get("lng")
    except Exception as exc:
        logger.warning("Falha ao geocodificar endereço do aluno %s: %s", data.matricula, exc)

    tolerancia_minutos = (
        data.tolerancia_minutos
        if data.tolerancia_minutos is not None
        else PONTO_TOLERANCIA_PADRAO_MINUTOS
    )
    raio_permitido = (
        data.raio_permitido_metros
        if data.raio_permitido_metros is not None
        else PONTO_RAIO_PADRAO_METROS
    )

    turma = None
    if data.id_turma is not None:
        turma = get_turma_by_id(db, data.id_turma)
        if not turma:
            raise ValueError("Turma informada não existe.")

    convenio = None
    if data.id_convenio is not None:
        convenio = get_convenio_by_id(db, data.id_convenio)
        if not convenio:
            raise ValueError("Convênio informado não existe.")

    supervisor_ext = None
    if data.id_supervisor_externo is not None:
        supervisor_ext = get_supervisor_externo_by_id(db, data.id_supervisor_externo)
        if not supervisor_ext:
            raise ValueError("Supervisor externo informado não existe.")

    contrato = Contrato(
        data_inicio=data.data_inicio,
        data_final=data.data_final,
        status=True,
        id_professor=id_professor,
        hora_inicio_prevista=data.hora_inicio_prevista,
        hora_fim_prevista=data.hora_fim_prevista,
        tolerancia_minutos=tolerancia_minutos,
        raio_permitido_metros=raio_permitido,
        id_turma=data.id_turma if turma else None,
        id_convenio=data.id_convenio if convenio else None,
        id_supervisor_externo=data.id_supervisor_externo if supervisor_ext else None,
    )

    try:
        db.add(aluno)
        db.add(endereco)
        db.flush()  # garante IDs para relacionamento

        contrato.id_aluno = aluno.id
        contrato.id_endereco = endereco.id

        db.add(contrato)
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(aluno)
    db.refresh(endereco)
    db.refresh(contrato)
    return aluno, endereco, contrato

# --------------------------------------------------------------------------
# CRUD: Ponto Eletrônico
# --------------------------------------------------------------------------
def _finalizar_ponto(db: Session, ponto: Ponto) -> Ponto:
    """
    Finaliza um ponto aberto calculando o tempo trabalhado e desativando-o.
    """
    ponto.hora_saida = datetime.utcnow()
    he = ensure_aware(ponto.hora_entrada)
    hs = ensure_aware(ponto.hora_saida)
    if he and hs:
        base = PONTO_ARREDONDAMENTO_MINUTOS
        he_round = _round_datetime(he, base)
        hs_round = _round_datetime(hs, base)
        delta = hs_round - he_round
        if delta.total_seconds() < 0:
            delta = timedelta(0)
        ponto.tempo_trabalhado_minutos = int(delta.total_seconds() // 60)
    ponto.ativo = False

    db.commit()
    db.refresh(ponto)
    return ponto


def ponto_entrada(db: Session, matricula: str, payload: PontoCheckLocation) -> Tuple[Ponto, bool]:
    user = get_usuario_by_matricula(db, matricula)
    if not user:
        raise ValueError("Usuário não encontrado.")

    ponto_aberto = get_ponto_aberto(db, user.id)
    if ponto_aberto:
        return _finalizar_ponto(db, ponto_aberto), True

    contrato = get_contrato_ativo_do_aluno(db, user.id)
    if not contrato:
        raise ValueError("Nenhum contrato ativo para este aluno.")

    agora = datetime.utcnow()
    avaliacao_local = _avaliar_geofencing(contrato, payload.latitude_atual, payload.longitude_atual)
    if not avaliacao_local["dentro"]:
        justificativa = criar_justificativa_automatica_localizacao(
            db=db,
            contrato=contrato,
            mensagem=avaliacao_local["mensagem"],
        )
        raise ValueError(
            f"{avaliacao_local['mensagem']} Uma justificativa automática (ID {justificativa.id}) foi aberta para análise."
        )

    janela = _avaliar_janela(contrato, agora)
    alertas: List[str] = []
    if avaliacao_local.get("alerta"):
        alertas.append(avaliacao_local["mensagem"])
    if not janela["dentro"]:
        alertas.append(janela["mensagem"])

    ponto = Ponto(
        id_contrato=contrato.id,
        data=date.today(),
        hora_entrada=agora,
        ativo=True,
        entrada_latitude=payload.latitude_atual,
        entrada_longitude=payload.longitude_atual,
        validado_localizacao=avaliacao_local.get("validado", False),
        alerta="; ".join(alertas) if alertas else None,
    )
    db.add(ponto)
    db.commit()
    db.refresh(ponto)
    return ponto, False


def ponto_saida(db: Session, matricula: str) -> Ponto:
    user = get_usuario_by_matricula(db, matricula)
    if not user:
        raise ValueError("Usuário não encontrado.")

    ponto_aberto = get_ponto_aberto(db, user.id)
    if not ponto_aberto:
        raise ValueError("Nenhum ponto em aberto encontrado para este aluno.")

    return _finalizar_ponto(db, ponto_aberto)


def get_ponto_aberto(db: Session, id_aluno: int) -> Optional[Ponto]:
    """Retorna o ponto em aberto (ativo) do aluno, se existir."""
    return (
        db.query(Ponto)
        .join(Contrato, Contrato.id == Ponto.id_contrato)
        .filter(and_(Contrato.id_aluno == id_aluno, Ponto.ativo.is_(True)))
        .first()
    )


def _calcular_carga_prevista_minutos(contrato: Optional[Contrato]) -> Optional[int]:
    if (
        not contrato
        or contrato.hora_inicio_prevista is None
        or contrato.hora_fim_prevista is None
    ):
        return None
    inicio = datetime.combine(date.today(), contrato.hora_inicio_prevista)
    fim = datetime.combine(date.today(), contrato.hora_fim_prevista)
    delta = fim - inicio
    if delta.total_seconds() <= 0:
        return None
    return int(delta.total_seconds() // 60)


def _calcular_minutos_trabalhados(ponto: Ponto) -> int:
    if ponto.tempo_trabalhado_minutos is not None:
        return ponto.tempo_trabalhado_minutos
    he = ensure_aware(ponto.hora_entrada)
    hs = ensure_aware(ponto.hora_saida or datetime.utcnow())
    if not he or not hs:
        return 0
    delta = hs - he
    if delta.total_seconds() <= 0:
        return 0
    return int(delta.total_seconds() // 60)


def obter_timeline_do_dia(
    db: Session, aluno_id: int, dia: date
) -> Tuple[List[Ponto], List[Justificativa], List[DiarioAtividade], int, Optional[int], Optional[int]]:
    pontos = (
        db.query(Ponto)
        .join(Contrato, Contrato.id == Ponto.id_contrato)
        .options(joinedload(Ponto.contrato))
        .filter(and_(Contrato.id_aluno == aluno_id, Ponto.data == dia))
        .order_by(Ponto.hora_entrada.asc())
        .all()
    )

    contrato_referencia: Optional[Contrato] = pontos[0].contrato if pontos else get_contrato_ativo_do_aluno(db, aluno_id)
    esperado = _calcular_carga_prevista_minutos(contrato_referencia)
    total = sum(_calcular_minutos_trabalhados(p) for p in pontos)
    saldo = total - esperado if esperado is not None else None
    justificativas = get_justificativas_por_data(db, aluno_id, dia)
    diarios = get_diarios_por_data(db, aluno_id, dia)
    avaliacoes = get_avaliacoes_por_data(db, aluno_id, dia)
    return pontos, justificativas, diarios, avaliacoes, total, esperado, saldo


