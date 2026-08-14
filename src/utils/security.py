"""
Gerenciamento seguro de credenciais via Windows Credential Manager / Keyring.
"""
import logging
from typing import Optional
import keyring
from src.config.constants import KEYRING_SERVICE_NAME

logger = logging.getLogger(__name__)

def get_secure_credential(key: str, default: str = "") -> str:
    """Recupera uma credencial de forma segura do cofre do sistema."""
    try:
        val = keyring.get_password(KEYRING_SERVICE_NAME, key)
        return val if val is not None else default
    except Exception as e:
        logger.warning(f"Erro ao recuperar credencial '{key}' do keyring: {e}")
        return default

def set_secure_credential(key: str, value: str) -> bool:
    """Salva uma credencial de forma segura no cofre do sistema."""
    try:
        keyring.set_password(KEYRING_SERVICE_NAME, key, value)
        return True
    except Exception as e:
        logger.error(f"Erro ao salvar credencial '{key}' no keyring: {e}")
        return False

def delete_secure_credential(key: str) -> bool:
    """Remove uma credencial do cofre do sistema."""
    try:
        keyring.delete_password(KEYRING_SERVICE_NAME, key)
        return True
    except Exception as e:
        logger.warning(f"Erro ao deletar credencial '{key}' do keyring: {e}")
        return False
