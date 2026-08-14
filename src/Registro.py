"""
Dixi Auditor - Pagare
Ponto de entrada principal da aplicação (compatível com PyInstaller e execução direta).
"""
import sys
import os

# Garante que a pasta raiz e a pasta src/ estejam no sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src_dir = os.path.dirname(os.path.abspath(__file__))

for path in (root_dir, src_dir):
    if path not in sys.path:
        sys.path.insert(0, path)

from src.app import App, main
from src.core.models import MarcacaoDia, Signatario, ResumoAuditoria
from src.core.ponto_engine import PontoEngine
from src.services.dixi_service import DixiService
from src.services.excel_service import ExcelService
from src.services.ai_service import AIService
from src.services.autentique_service import (
    enviar_justificativa_autentique,
    listar_documentos_autentique,
    resgatar_documento_autentique
)
from src.services.justificativa_service import (
    gerar_pdf_justificativa,
    formatar_mes_competencia,
    obter_mes_extenso,
    enviar_email_smtp
)

# Aliases de compatibilidade histórica
IAAnalistaPonto = AIService
ExcelExporter = ExcelService

if __name__ == "__main__":
    main()
