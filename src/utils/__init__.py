"""
Funções e utilitários auxiliares (segurança, caminhos, formatações, threads, colaboradores).
"""
from src.utils.paths import get_resource_path, get_asset_path, get_logo_path, get_icon_path
from src.utils.security import get_secure_credential, set_secure_credential
from src.utils.formatters import (
    format_time_seconds,
    obter_mes_extenso,
    formatar_mes_competencia,
    get_dia_semana_nome,
    normalize_date_to_iso
)
from src.utils.threading_utils import run_async_task
from src.utils.colaboradores import carregar_colaboradores, salvar_colaboradores, buscar_cargo_colaborador
