"""
Componente reutilizável de campo de senha/token com botão de alternância de visibilidade (Olho 👁️ / 🙈).
"""
import tkinter as tk
from tkinter import ttk
from typing import Optional, Callable
from src.ui.theme import get_font

class PasswordEntry(ttk.Frame):
    """Entry com botão integrado para exibir/ocultar senha ou tokens."""

    def __init__(
        self,
        parent,
        show_char: str = "•",
        font_size: int = 10,
        placeholder: str = "",
        width: Optional[int] = None,
        **kwargs
    ):
        super().__init__(parent)
        self.show_char = show_char
        self.is_visible = False

        self.columnconfigure(0, weight=1)

        self.entry = ttk.Entry(
            self,
            show=self.show_char,
            font=get_font(font_size),
            width=width,
            **kwargs
        )
        self.entry.grid(row=0, column=0, sticky="ew")

        self.btn_toggle = tk.Button(
            self,
            text="👁️",
            command=self.toggle_visibility,
            bg="#f1f5f9",
            fg="#475569",
            activebackground="#e2e8f0",
            activeforeground="#0f172a",
            font=("Segoe UI Emoji", 10),
            bd=0,
            relief="flat",
            cursor="hand2",
            padx=6,
            pady=2
        )
        self.btn_toggle.grid(row=0, column=1, padx=(4, 0), sticky="e")

    def toggle_visibility(self):
        """Alterna a visibilidade do texto."""
        self.is_visible = not self.is_visible
        if self.is_visible:
            self.entry.config(show="")
            self.btn_toggle.config(text="🙈", bg="#e2e8f0")
        else:
            self.entry.config(show=self.show_char)
            self.btn_toggle.config(text="👁️", bg="#f1f5f9")

    def get(self) -> str:
        return self.entry.get()

    def insert(self, index, string: str):
        self.entry.insert(index, string)

    def delete(self, first, last=None):
        self.entry.delete(first, last)

    def focus_set(self):
        self.entry.focus_set()

    def bind(self, sequence=None, func=None, add=None):
        return self.entry.bind(sequence, func, add)
