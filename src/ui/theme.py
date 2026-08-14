"""
Design System, DPI Awareness e Configuração de Estilos TTK para o Dixi Auditor.
"""
import sys
import ctypes
import tkinter as tk
from tkinter import ttk

from src.config.constants import (
    COLOR_PRIMARY,
    COLOR_PRIMARY_HOVER,
    COLOR_PRIMARY_DARK,
    COLOR_PRIMARY_SOFT,
    COLOR_PRIMARY_TINT,
    COLOR_BG,
    COLOR_SURFACE,
    COLOR_BORDER,
    COLOR_TEXT,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_LIGHT,
    COLOR_SUCCESS,
    COLOR_SUCCESS_BG,
    COLOR_DANGER,
    COLOR_DANGER_BG,
    COLOR_WARNING,
    COLOR_WARNING_BG,
    COLOR_INFO,
    COLOR_INFO_BG,
    FONT_FAMILY_PRIMARY,
    FONT_FAMILY_MONO
)

def enable_high_dpi():
    """Habilita DPI Awareness no Windows para telas Full HD e 4K."""
    if sys.platform.startswith("win"):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass

def get_font(size: int = 10, bold: bool = False, mono: bool = False) -> tuple:
    """Retorna tupla de fonte padronizada."""
    family = FONT_FAMILY_MONO if mono else FONT_FAMILY_PRIMARY
    weight = "bold" if bold else "normal"
    return (family, size, weight)

def apply_theme(root: tk.Tk):
    """Configura o tema e estilos TTK do aplicativo."""
    root.configure(bg=COLOR_BG)

    style = ttk.Style()
    try:
        style.theme_use("clam")
    except Exception:
        pass

    # Frame padrão
    style.configure("TFrame", background=COLOR_BG)
    style.configure("Surface.TFrame", background=COLOR_SURFACE)

    # Labels
    style.configure("TLabel", background=COLOR_BG, foreground=COLOR_TEXT, font=get_font(10))
    style.configure("Surface.TLabel", background=COLOR_SURFACE, foreground=COLOR_TEXT, font=get_font(10))
    style.configure("Muted.TLabel", background=COLOR_SURFACE, foreground=COLOR_TEXT_MUTED, font=get_font(9))
    style.configure("Header.TLabel", background=COLOR_SURFACE, foreground=COLOR_TEXT, font=get_font(13, bold=True))
    style.configure("MetricTitle.TLabel", background=COLOR_SURFACE, foreground=COLOR_TEXT_MUTED, font=get_font(9, bold=True))

    # Botões Padrão
    style.configure(
        "TButton",
        background=COLOR_SURFACE,
        foreground=COLOR_TEXT,
        bordercolor=COLOR_BORDER,
        font=get_font(9),
        padding=(10, 6)
    )
    style.map(
        "TButton",
        background=[("active", COLOR_BG), ("disabled", COLOR_BG)],
        foreground=[("disabled", COLOR_TEXT_LIGHT)]
    )

    # Botão Primário
    style.configure(
        "Primary.TButton",
        background=COLOR_PRIMARY,
        foreground="#ffffff",
        bordercolor=COLOR_PRIMARY_DARK,
        font=get_font(9, bold=True),
        padding=(12, 6)
    )
    style.map(
        "Primary.TButton",
        background=[("active", COLOR_PRIMARY_HOVER), ("disabled", COLOR_BORDER)],
        foreground=[("disabled", COLOR_TEXT_LIGHT)]
    )

    # Botão Danger (Ação crítica)
    style.configure(
        "Danger.TButton",
        background=COLOR_DANGER,
        foreground="#ffffff",
        font=get_font(9, bold=True),
        padding=(10, 6)
    )
    style.map(
        "Danger.TButton",
        background=[("active", "#b91c1c"), ("disabled", COLOR_BORDER)],
        foreground=[("disabled", COLOR_TEXT_LIGHT)]
    )

    # Entry & Combobox
    style.configure(
        "TEntry",
        fieldbackground=COLOR_SURFACE,
        foreground=COLOR_TEXT,
        bordercolor=COLOR_BORDER,
        padding=6
    )
    style.configure(
        "TCombobox",
        fieldbackground=COLOR_SURFACE,
        foreground=COLOR_TEXT,
        bordercolor=COLOR_BORDER,
        padding=4
    )

    # Checkbutton
    style.configure(
        "TCheckbutton",
        background=COLOR_SURFACE,
        foreground=COLOR_TEXT,
        font=get_font(9)
    )

    # Notebook & Tabs
    style.configure(
        "TNotebook",
        background=COLOR_BG,
        tabmargins=[2, 5, 2, 0]
    )
    style.configure(
        "TNotebook.Tab",
        background=COLOR_PRIMARY_SOFT,
        foreground=COLOR_TEXT,
        padding=[14, 6],
        font=get_font(9, bold=True)
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", COLOR_PRIMARY_DARK)],
        foreground=[("selected", "#ffffff")]
    )

    # Treeview (Tabela de Ponto)
    style.configure(
        "Treeview",
        background=COLOR_SURFACE,
        foreground=COLOR_TEXT,
        fieldbackground=COLOR_SURFACE,
        rowheight=26,
        font=get_font(9),
        bordercolor=COLOR_BORDER
    )
    style.configure(
        "Treeview.Heading",
        background=COLOR_PRIMARY_SOFT,
        foreground=COLOR_PRIMARY_DARK,
        font=get_font(9, bold=True),
        padding=6
    )
    style.map(
        "Treeview",
        background=[("selected", COLOR_PRIMARY_TINT)],
        foreground=[("selected", COLOR_PRIMARY_DARK)]
    )
