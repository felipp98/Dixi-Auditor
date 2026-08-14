"""
Componente de Cards de Métricas para resumo de horas, saldo e pendências.
"""
import tkinter as tk
from tkinter import ttk
from src.config.constants import (
    COLOR_SURFACE,
    COLOR_BORDER,
    COLOR_PRIMARY_DARK,
    COLOR_DANGER,
    COLOR_SUCCESS,
    COLOR_WARNING,
    COLOR_TEXT_MUTED
)
from src.ui.theme import get_font

class MetricCard(tk.Frame):
    """Card individual de estatística resumida."""

    def __init__(
        self,
        parent,
        title: str,
        initial_value: str = "00:00",
        value_color: str = COLOR_PRIMARY_DARK,
        icon: str = "📊"
    ):
        super().__init__(
            parent,
            bg=COLOR_SURFACE,
            padx=14,
            pady=10,
            highlightbackground=COLOR_BORDER,
            highlightthickness=1
        )
        self.value_color = value_color

        # Título com Ícone
        self.lbl_title = tk.Label(
            self,
            text=f"{icon} {title}",
            bg=COLOR_SURFACE,
            fg=COLOR_TEXT_MUTED,
            font=get_font(9, bold=True)
        )
        self.lbl_title.pack(anchor="w")

        # Valor Principal
        self.lbl_value = tk.Label(
            self,
            text=initial_value,
            bg=COLOR_SURFACE,
            fg=self.value_color,
            font=get_font(15, bold=True)
        )
        self.lbl_value.pack(anchor="w", pady=(3, 0))

    def set_value(self, value: str, color: str = None):
        """Atualiza o valor exibido no card."""
        self.lbl_value.config(text=value)
        if color:
            self.lbl_value.config(fg=color)
