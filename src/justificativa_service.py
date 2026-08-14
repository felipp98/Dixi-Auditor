import os
import sys

# Garante que a raiz do projeto esteja no sys.path
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.services.justificativa_service import (
    gerar_pdf_justificativa,
    enviar_email_smtp,
    normalizar_dia
)
from src.utils.formatters import formatar_mes_competencia, obter_mes_extenso

__all__ = [
    "gerar_pdf_justificativa",
    "enviar_email_smtp",
    "normalizar_dia",
    "formatar_mes_competencia",
    "obter_mes_extenso"
]
