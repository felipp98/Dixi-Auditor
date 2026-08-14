"""
Gerenciamento e busca de cargos/funções e e-mails dos colaboradores CLT cadastrados.
"""
import os
import json
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

def _get_json_path() -> str:
    """Localiza o arquivo colaboradores.json na raiz ou em config/."""
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    root_json = os.path.join(base_dir, "colaboradores.json")
    if os.path.exists(root_json):
        return root_json
    src_json = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "colaboradores.json")
    if os.path.exists(src_json):
        return src_json
    return root_json

def carregar_colaboradores() -> List[Dict[str, str]]:
    """Lê a lista de colaboradores CLT do arquivo JSON."""
    json_path = _get_json_path()
    if not os.path.exists(json_path):
        return []
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Erro ao carregar colaboradores.json: {e}")
        return []

def salvar_colaboradores(lista: List[Dict[str, str]]) -> bool:
    """Salva a lista atualizada de colaboradores."""
    json_path = _get_json_path()
    try:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(lista, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"Erro ao salvar colaboradores.json: {e}")
        return False

def buscar_dados_colaborador(identificador: str) -> Optional[Dict[str, str]]:
    """
    Busca o cadastro completo de um colaborador (nome, cargo, email) por nome, e-mail ou username.
    """
    if not identificador or not identificador.strip():
        return None

    ident = identificador.lower().strip()
    colabs = carregar_colaboradores()

    for c in colabs:
        nome_c = str(c.get("nome", "")).lower().strip()
        email_c = str(c.get("email", "")).lower().strip()

        if ident == nome_c or ident == email_c:
            return c

        # Checa se o primeiro nome bate (ex: "Felipp" em "Felipp Cordeiro")
        p_nome = nome_c.split()[0] if nome_c else ""
        if p_nome and (p_nome == ident or p_nome in ident):
            return c

        if nome_c and (nome_c in ident or ident in nome_c):
            return c

    return None

def buscar_cargo_colaborador(identificador: str) -> Optional[str]:
    """
    Busca o cargo/função real de um colaborador por nome, e-mail ou username.
    Exemplo: 'Felipp' -> 'RPA', 'Carla' -> 'Diretora ADM / Financeira (CFO)'.
    """
    dados = buscar_dados_colaborador(identificador)
    if dados and dados.get("cargo"):
        return dados.get("cargo")
    return None
