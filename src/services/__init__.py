"""
Camada de serviços externos, integrações (Dixi, Autentique, IA, PDF, Excel) e armazenamento.
"""
from src.services.dixi_service import DixiService
from src.services.autentique_service import (
    enviar_justificativa_autentique,
    listar_documentos_autentique,
    resgatar_documento_autentique
)
from src.services.justificativa_service import gerar_pdf_justificativa
from src.services.ai_service import AIService
from src.services.excel_service import ExcelService
from src.services.storage_service import StorageService
