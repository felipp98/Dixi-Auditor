import os
import sys

# Garante que a raiz do projeto esteja no sys.path
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

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
