"""
Modelos de dados (Data Classes) da aplicação Dixi Auditor.
"""
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional

@dataclass
class MarcacaoDia:
    """Representa a jornada calculada de um dia específico."""
    data_id: str                              # Identificador ISO YYYYMMDD
    data_formatada: str                       # Ex: DD/MM/YYYY
    segundos_trabalhados: int                 # Tempo líquido trabalhado em segundos
    saldo_segundos: int                       # Saldo em segundos (+ ou -)
    is_pendencia: bool                        # Indica batida ímpar ou pendência
    horarios: List[str]                       # Lista de horários ['08:00', '12:00', ...]
    obs: str = ""                             # Observação ou motivo
    selecionado: bool = False                 # Controle de seleção na interface
    editado_manualmente: bool = False         # Rastreador se o dia foi ajustado pelo usuário ou IA
    horarios_originais: List[str] = field(default_factory=list) # Batidas originais da Dixi antes da edição

    def to_dict(self) -> Dict[str, Any]:
        """Serializa o objeto para dicionário JSON."""
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MarcacaoDia":
        """Reconstrói uma MarcacaoDia a partir de um dicionário."""
        return cls(
            data_id=str(d.get("data_id", "")),
            data_formatada=str(d.get("data_formatada", "")),
            segundos_trabalhados=int(d.get("segundos_trabalhados", 0)),
            saldo_segundos=int(d.get("saldo_segundos", 0)),
            is_pendencia=bool(d.get("is_pendencia", False)),
            horarios=list(d.get("horarios", [])),
            obs=str(d.get("obs", "")),
            selecionado=bool(d.get("selecionado", False)),
            editado_manualmente=bool(d.get("editado_manualmente", False)),
            horarios_originais=list(d.get("horarios_originais", []))
        )

@dataclass
class Signatario:
    """Representa uma pessoa signatária no Autentique (Colaborador, Gestor, RH ou Testemunha)."""
    nome: str
    email: str
    role: str = "SIGN"                        # SIGN, SIGN_AS_A_WITNESS, APPROVE
    positions: List[Dict[str, Any]] = field(default_factory=list)

@dataclass
class AjustePonto:
    """Representa uma sugestão ou instrução de ajuste em um dia."""
    data: str                                 # DD/MM/YYYY
    horarios: Optional[List[str]] = None
    abono: bool = False
    obs: str = ""

@dataclass
class JustificativaItem:
    """Representa um item diário para geração de formulário de justificativa."""
    data: str
    dia_semana: str
    batidas_orig: str
    batidas_prop: str
    motivo: str
    selecionado: bool = True

@dataclass
class ResumoAuditoria:
    """Sumário quantitativo do espelho de ponto auditado."""
    total_dias: int = 0
    saldo_acumulado_segundos: int = 0
    dias_pendencia: int = 0
    dias_extras: int = 0
    dias_atraso: int = 0
    dias_trabalhados: int = 0

@dataclass
class Usuario:
    """Dados da sessão do usuário autenticado."""
    username: str
    nome_completo: str = ""
    email: str = ""
    cargo: str = ""
    token_dixi: str = ""
