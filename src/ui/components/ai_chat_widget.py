"""
Janela e Widget do Assistente IA de Ponto com suporte a auditoria, diálogo e aplicação direta de ajustes.
"""
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable, Optional, List, Dict, Any

from src.config.constants import (
    COLOR_PRIMARY,
    COLOR_PRIMARY_DARK,
    COLOR_PRIMARY_SOFT,
    COLOR_PRIMARY_HOVER,
    COLOR_SURFACE,
    COLOR_BG,
    COLOR_BORDER,
    COLOR_TEXT,
    COLOR_TEXT_MUTED
)
from src.ui.theme import get_font

class AIChatModal(tk.Toplevel):
    """Janela flutuante não-intrusiva do Assistente IA de Ponto."""

    def __init__(
        self,
        parent,
        on_send_message: Callable[[str], None],
        on_quick_audit: Callable[[], None],
        on_apply_adjustments: Callable[[], None]
    ):
        super().__init__(parent)
        self.title("🤖 Assistente IA de Ponto (Nemotron 550B Reasoning)")
        self.geometry("680x560")
        self.minsize(580, 480)
        self.configure(bg=COLOR_BG)
        self.transient(parent)

        self.on_send_message = on_send_message
        self.on_quick_audit = on_quick_audit
        self.on_apply_adjustments = on_apply_adjustments

        self._build_ui()

    def _build_ui(self):
        # 1. Cabeçalho
        hdr = tk.Frame(self, bg=COLOR_PRIMARY_DARK, padx=16, pady=12)
        hdr.pack(fill="x")

        hdr_left = tk.Frame(hdr, bg=COLOR_PRIMARY_DARK)
        hdr_left.pack(side="left")

        tk.Label(
            hdr_left,
            text="🤖 Assistente IA de Auditoria",
            bg=COLOR_PRIMARY_DARK,
            fg="#ffffff",
            font=get_font(12, bold=True)
        ).pack(anchor="w")

        tk.Label(
            hdr_left,
            text="Análise de batidas, detecção de pendências e ajustes inteligentes",
            bg=COLOR_PRIMARY_DARK,
            fg="#dcfce7",
            font=get_font(8)
        ).pack(anchor="w")

        # 2. Barra de Ações Rápidas
        quick_bar = tk.Frame(self, bg=COLOR_PRIMARY_SOFT, padx=14, pady=8, highlightbackground=COLOR_BORDER, highlightthickness=1)
        quick_bar.pack(fill="x")

        btn_quick = ttk.Button(
            quick_bar,
            text="⚡ Auditoria Rápida",
            command=self.on_quick_audit
        )
        btn_quick.pack(side="left", padx=(0, 8))

        self.btn_apply = ttk.Button(
            quick_bar,
            text="✨ Aplicar Ajustes na Tabela",
            style="Primary.TButton",
            state="disabled",
            command=self.on_apply_adjustments
        )
        self.btn_apply.pack(side="left")

        self.lbl_status = tk.Label(
            quick_bar,
            text="",
            bg=COLOR_PRIMARY_SOFT,
            fg=COLOR_PRIMARY_DARK,
            font=get_font(9, bold=True)
        )
        self.lbl_status.pack(side="right", padx=(8, 0))

        # 3. Área de Mensagens / Análise
        msg_container = tk.Frame(self, bg=COLOR_BG, padx=14, pady=10)
        msg_container.pack(fill="both", expand=True)

        self.txt_chat = tk.Text(
            msg_container,
            wrap="word",
            bg=COLOR_SURFACE,
            fg=COLOR_TEXT,
            font=get_font(9),
            bd=1,
            highlightbackground=COLOR_BORDER,
            highlightthickness=1,
            padx=12,
            pady=10
        )
        scroll = ttk.Scrollbar(msg_container, orient="vertical", command=self.txt_chat.yview)
        self.txt_chat.configure(yscrollcommand=scroll.set)

        self.txt_chat.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        # Mensagem inicial
        self.append_message(
            "Assistente IA",
            "Olá! Sou seu assistente de auditoria de ponto. Clique em '⚡ Auditoria Rápida' para analisar o período ou digite uma instrução abaixo (ex: 'considere saída às 18:00 no dia 10' ou 'abone a falta de sexta-feira')."
        )

        # 4. Barra de Entrada / Diálogo
        inp_bar = tk.Frame(self, bg=COLOR_SURFACE, padx=14, pady=10, highlightbackground=COLOR_BORDER, highlightthickness=1)
        inp_bar.pack(fill="x")

        self.ent_msg = ttk.Entry(inp_bar, font=get_font(10))
        self.ent_msg.pack(side="left", fill="x", expand=True, padx=(0, 8), ipady=4)
        self.ent_msg.bind("<Return>", lambda e: self._send())

        self.btn_send = ttk.Button(inp_bar, text="💬 Enviar / Recalcular", style="Primary.TButton", command=self._send)
        self.btn_send.pack(side="right")

    def append_message(self, sender: str, text: str):
        """Adiciona mensagem formatada na caixa de texto."""
        self.txt_chat.config(state="normal")
        tag_prefix = "user" if sender == "Você" else "bot"

        header_str = f"\n[{sender}]:\n"
        self.txt_chat.insert("end", header_str, f"{tag_prefix}_hdr")
        self.txt_chat.insert("end", f"{text}\n")

        self.txt_chat.tag_configure("user_hdr", font=get_font(9, bold=True), foreground=COLOR_PRIMARY_DARK)
        self.txt_chat.tag_configure("bot_hdr", font=get_font(9, bold=True), foreground="#0284c7")

        self.txt_chat.see("end")
        self.txt_chat.config(state="disabled")

    def enable_apply_button(self, count: int = 1):
        """Habilita o botão para aplicar ajustes."""
        self.btn_apply.config(state="normal", text=f"✨ Aplicar {count} Ajuste(s)")

    def disable_apply_button(self):
        """Desabilita o botão de aplicar ajustes."""
        self.btn_apply.config(state="disabled", text="✨ Aplicar Ajustes na Tabela")

    def set_status(self, text: str):
        self.lbl_status.config(text=text)

    def _send(self):
        msg = self.ent_msg.get().strip()
        if not msg:
            return
        self.ent_msg.delete(0, tk.END)
        self.append_message("Você", msg)
        self.on_send_message(msg)

# Alias de compatibilidade
AIChatWidget = AIChatModal
