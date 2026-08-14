"""
Proxy de compatibilidade para o pacote src.services.autentique_service.
"""
from src.services.autentique_service import (
    enviar_justificativa_autentique,
    listar_documentos_autentique,
    resgatar_documento_autentique
)

__all__ = [
    "enviar_justificativa_autentique",
    "listar_documentos_autentique",
    "resgatar_documento_autentique"
]
