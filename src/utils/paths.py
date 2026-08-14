"""
Utilitário de resolução de caminhos para compatibilidade com ambiente de desenvolvimento e PyInstaller.
"""
import os
import sys

def get_app_root() -> str:
    """Retorna o diretório raiz da aplicação."""
    if hasattr(sys, "_MEIPASS"):
        return getattr(sys, "_MEIPASS")
    # Se rodando de dentro de src/ ou da raiz
    current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.dirname(current_dir) if os.path.basename(current_dir) == "src" else current_dir

def get_asset_path(*subpaths: str) -> str:
    """Retorna o caminho absoluto para um asset dentro de assets/."""
    root = get_app_root()
    # Tenta na raiz do projeto (desenvolvimento) ou no _MEIPASS
    candidate = os.path.join(root, "assets", *subpaths)
    if os.path.exists(candidate):
        return candidate
    # Fallback se assets estiver embutido diretamente
    candidate_direct = os.path.join(root, *subpaths)
    if os.path.exists(candidate_direct):
        return candidate_direct
    return candidate

def get_resource_path(*subpaths: str) -> str:
    """Alias de compatibilidade para get_asset_path."""
    return get_asset_path(*subpaths)

def get_template_path(template_name: str = "justificativa_template.html") -> str:
    """Retorna o caminho do template HTML para geração de PDF."""
    return get_asset_path("templates", template_name)

def get_icon_path(icon_name: str = "PAGARE.ico") -> str:
    """Retorna o caminho do ícone da aplicação."""
    return get_asset_path("icons", icon_name)

def get_logo_path(logo_name: str = "logo_pagare.png") -> str:
    """Retorna o caminho da imagem do logotipo."""
    return get_asset_path("images", logo_name)
