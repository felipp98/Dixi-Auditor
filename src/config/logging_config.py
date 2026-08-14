"""
Configuração de logs do aplicativo.
"""
import os
import logging

def setup_logging() -> str:
    """Configura o logger do sistema salvando erros no arquivo de log do usuário."""
    log_file = os.path.join(os.path.expanduser("~"), "dixi_auditor.log")
    try:
        logging.basicConfig(
            filename=log_file,
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] (%(name)s) %(message)s",
            encoding="utf-8"
        )
    except Exception:
        # Fallback caso falhe configuração de encoding
        logging.basicConfig(
            filename=log_file,
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] (%(name)s) %(message)s"
        )
    return log_file
