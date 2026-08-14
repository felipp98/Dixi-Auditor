"""
Proxy de compatibilidade para o pacote src.services.justificativa_service.
"""
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
