"""
Constantes e configurações padrão do Dixi Auditor.
"""

# Identificadores de Armazenamento Seguro (Keyring)
KEYRING_SERVICE_NAME = "DixiPontoApp"

# Endpoints e URLs de Integrações
DIXI_API_BASE = "https://mobile.dixi.net.br/api"
AUTENTIQUE_GRAPHQL_URL = "https://api.autentique.com.br/v2/graphql"
OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"
DEFAULT_AI_MODEL = "nvidia/nemotron-3-ultra-550b-a55b:free"

# Parâmetros de Jornada Padrão (em segundos)
JORNADA_PADRAO_DIARIA = 8 * 3600  # 8 horas
JORNADA_SABADO_PADRAO = 0          # Fins de semana por padrão 0 horas
TOLERANCIA_PADRAO_MINUTOS = 10     # Tolerância CLT de 10 min diários
INTERVALO_ALMOCO_MINIMO_MINUTOS = 60  # Mínimo de 1 hora de almoço

# Paleta de Cores do Design System
COLOR_PRIMARY = "#16a34a"        # Verde principal
COLOR_PRIMARY_HOVER = "#15803d"  # Verde hover
COLOR_PRIMARY_DARK = "#14532d"   # Verde escuro
COLOR_PRIMARY_SOFT = "#dcfce7"   # Verde bem suave para fundos/badges
COLOR_PRIMARY_TINT = "#f0fdf4"   # Verde quase branco

COLOR_BG = "#f8fafc"             # Fundo geral (slate 50)
COLOR_SURFACE = "#ffffff"        # Superfície de cartões
COLOR_BORDER = "#e2e8f0"         # Borda sutil (slate 200)
COLOR_BORDER_FOCUS = "#16a34a"   # Borda em foco

COLOR_TEXT = "#0f172a"           # Texto principal (slate 900)
COLOR_TEXT_MUTED = "#64748b"     # Texto secundário (slate 500)
COLOR_TEXT_LIGHT = "#94a3b8"     # Texto bem suave (slate 400)

COLOR_SUCCESS = "#16a34a"        # Sucesso / Saldo positivo
COLOR_SUCCESS_BG = "#dcfce7"
COLOR_DANGER = "#dc2626"         # Erro / Saldo negativo (red 600)
COLOR_DANGER_BG = "#fee2e2"
COLOR_WARNING = "#d97706"        # Aviso / Pendência (amber 600)
COLOR_WARNING_BG = "#fef3c7"
COLOR_INFO = "#0284c7"           # Informação (sky 600)
COLOR_INFO_BG = "#e0f2fe"
COLOR_IN_PROGRESS = "#4d7c0f"    # Dia em andamento (lime/olive 700)
COLOR_IN_PROGRESS_BG = "#ecfccb"

# Tipografia
FONT_FAMILY_PRIMARY = "Segoe UI"
FONT_FAMILY_MONO = "Consolas"

# Papéis de Signatários do Autentique
ROLE_SIGN = "SIGN"
ROLE_WITNESS = "SIGN_AS_A_WITNESS"
ROLE_APPROVE = "APPROVE"

ROLES_AUTENTIQUE_DISPLAY = {
    "Assinar": ROLE_SIGN,
    "Testemunha": ROLE_WITNESS,
    "Aprovar": ROLE_APPROVE,
}

ROLES_AUTENTIQUE_REVERSE = {v: k for k, v in ROLES_AUTENTIQUE_DISPLAY.items()}
