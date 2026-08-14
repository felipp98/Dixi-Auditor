"""
Tela de Autenticação / Login Split-Card com identidade visual Pagare e cofre Keyring.
"""
import os
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable, Optional
from PIL import Image, ImageTk

from src.config.constants import (
    COLOR_BG,
    COLOR_SURFACE,
    COLOR_BORDER,
    COLOR_PRIMARY,
    COLOR_PRIMARY_DARK,
    COLOR_PRIMARY_HOVER,
    COLOR_TEXT,
    COLOR_TEXT_MUTED
)
from src.utils.paths import get_logo_path
from src.utils.security import get_secure_credential
from src.ui.theme import get_font

class LoginView(tk.Frame):
    """Tela de login estilizada no padrão Split Card Pagare."""

    def __init__(self, parent, on_login_submit: Callable[[str, str], None]):
        super().__init__(parent, bg="#F3F4F6")
        self.on_login_submit = on_login_submit
        self.logo_img = None
        self._build_ui()

    def _build_ui(self):
        # Frame de fundo expansível
        self.pack(fill="both", expand=True)

        # Card Principal Dividido (Split Card)
        card_wrapper = tk.Frame(
            self,
            bg=COLOR_SURFACE,
            highlightbackground="#E5E7EB",
            highlightthickness=1,
            bd=0
        )
        card_wrapper.pack(expand=True, fill="both", padx=24, pady=24)

        # ==========================================
        # 1. Coluna Esquerda: Painel Hero Verde Suave
        # ==========================================
        hero_panel = tk.Frame(card_wrapper, bg="#EBF6D2", width=310, bd=0, highlightthickness=0)
        hero_panel.pack(side="left", fill="both", expand=False)
        hero_panel.pack_propagate(False)

        # Faixa de destaque verde na borda esquerda
        tk.Frame(hero_panel, bg="#5CBD28", width=6).pack(side="left", fill="y")

        hero_content = tk.Frame(hero_panel, bg="#EBF6D2", padx=20, pady=22)
        hero_content.pack(expand=True, fill="both")

        # Badge Topo
        tk.Label(
            hero_content,
            text="GESTÃO INTELIGENTE DE PONTO",
            bg="#DCEFB6",
            fg="#1E4620",
            font=get_font(8, bold=True),
            padx=10,
            pady=4
        ).pack(anchor="center", pady=(0, 6))

        # Logo
        logo_path = get_logo_path("logo_pagare.png")
        if os.path.exists(logo_path):
            try:
                pil_img = Image.open(logo_path).resize((110, 32), Image.Resampling.LANCZOS)
                self.logo_img = ImageTk.PhotoImage(pil_img)
                lbl_logo = tk.Label(hero_content, image=self.logo_img, bg="#EBF6D2")
                lbl_logo.pack(anchor="center", pady=(0, 4))
            except Exception:
                pass

        tk.Label(
            hero_content,
            text="Dixi Auditor",
            bg="#EBF6D2",
            fg="#1E4620",
            font=get_font(18, bold=True)
        ).pack(anchor="center")

        tk.Label(
            hero_content,
            text="Bem-vindo! 👋",
            bg="#EBF6D2",
            fg=COLOR_TEXT,
            font=get_font(14, bold=True)
        ).pack(anchor="center", pady=(10, 4))

        tk.Label(
            hero_content,
            text="Audite seus pontos, envie justificativas para o RH e acompanhe saldos com facilidade.",
            bg="#EBF6D2",
            fg=COLOR_TEXT_MUTED,
            font=get_font(9),
            wraplength=230,
            justify="center"
        ).pack(anchor="center", pady=(0, 12))

        # Bullets de Recursos
        features_box = tk.Frame(hero_content, bg="#EBF6D2")
        features_box.pack(anchor="center")

        for f in ["✓ Batidas em tempo real", "✓ Auditoria por IA", "✓ Assinatura Autentique"]:
            tk.Label(
                features_box,
                text=f,
                bg="#EBF6D2",
                fg="#166534",
                font=get_font(9, bold=True)
            ).pack(anchor="w", pady=1)

        # ==========================================
        # 2. Coluna Direita: Formulário de Acesso
        # ==========================================
        login_card = tk.Frame(card_wrapper, bg=COLOR_SURFACE, padx=30, pady=22)
        login_card.pack(side="right", fill="both", expand=True)

        tk.Label(
            login_card,
            text="Acessar conta",
            bg=COLOR_SURFACE,
            fg=COLOR_TEXT,
            font=get_font(15, bold=True)
        ).pack(anchor="w")

        tk.Label(
            login_card,
            text="Entre com suas credenciais da Dixi para continuar no painel.",
            bg=COLOR_SURFACE,
            fg=COLOR_TEXT_MUTED,
            font=get_font(9),
            wraplength=260,
            justify="left"
        ).pack(anchor="w", pady=(2, 14))

        # Campo Usuário
        self.ent_user = self._build_custom_input(login_card, "Usuário / E-mail")
        self.ent_pass = self._build_custom_input(login_card, "Senha", show="*")

        # Preenche com último login do Keyring
        last_user = get_secure_credential("last_user", "")
        if last_user:
            self.ent_user.insert(0, last_user)
            last_pass = get_secure_credential(last_user, "")
            if last_pass:
                self.ent_pass.insert(0, last_pass)

        # Label de Status / Erro
        self.lbl_status = tk.Label(
            login_card,
            text="",
            bg=COLOR_SURFACE,
            fg="#dc2626",
            font=get_font(9)
        )
        self.lbl_status.pack(anchor="w", pady=(2, 6))

        # Botão de Login
        self.btn_login = tk.Button(
            login_card,
            text="Entrar no painel",
            bg="#5CBD28",
            fg="white",
            activebackground="#4E9E24",
            activeforeground="white",
            font=get_font(10, bold=True),
            bd=0,
            relief="flat",
            cursor="hand2",
            padx=14,
            pady=8,
            command=self._submit
        )
        self.btn_login.pack(fill="x", pady=(2, 10))

        # Hover no Botão
        self.btn_login.bind("<Enter>", lambda e: self.btn_login.config(bg="#4E9E24") if self.btn_login["state"] != "disabled" else None)
        self.btn_login.bind("<Leave>", lambda e: self.btn_login.config(bg="#5CBD28") if self.btn_login["state"] != "disabled" else None)

        # Selo de Proteção
        tk.Label(
            login_card,
            text="🔒 Ambiente protegido",
            bg=COLOR_SURFACE,
            fg=COLOR_TEXT_MUTED,
            font=get_font(8, bold=True)
        ).pack(anchor="center", pady=(4, 0))

        # Atalhos de Teclado
        self.ent_user.bind("<Return>", lambda e: self.ent_pass.focus())
        self.ent_pass.bind("<Return>", lambda e: self._submit())
        self.ent_user.focus_set()

    def _build_custom_input(self, parent: tk.Frame, label_text: str, show: Optional[str] = None) -> tk.Entry:
        """Cria um campo de entrada com visual suave e borda dinâmica de foco."""
        group = tk.Frame(parent, bg=COLOR_SURFACE)
        group.pack(fill="x", pady=(0, 8))

        tk.Label(
            group,
            text=label_text,
            bg=COLOR_SURFACE,
            fg=COLOR_TEXT,
            font=get_font(9, bold=True)
        ).pack(anchor="w", pady=(0, 3))

        shell = tk.Frame(
            group,
            bg="#F8FBF2",
            highlightbackground="#D1D5DB",
            highlightcolor="#5CBD28",
            highlightthickness=1,
            bd=0
        )
        shell.pack(fill="x")

        entry = tk.Entry(
            shell,
            font=get_font(10),
            bg="#F8FBF2",
            fg=COLOR_TEXT,
            insertbackground=COLOR_TEXT,
            relief="flat",
            bd=0,
            highlightthickness=0,
            show=show
        )

        if show:
            entry.pack(side="left", fill="x", expand=True, padx=(10, 2), pady=7)

            btn_eye = tk.Button(
                shell,
                text="👁️",
                bg="#F8FBF2",
                fg="#64748b",
                activebackground="#FFFFFF",
                font=("Segoe UI Emoji", 10),
                bd=0,
                relief="flat",
                cursor="hand2",
                padx=6,
                pady=0
            )
            btn_eye.pack(side="right", padx=(0, 6))

            def toggle_eye():
                if entry.cget("show") == show:
                    entry.config(show="")
                    btn_eye.config(text="🙈")
                else:
                    entry.config(show=show)
                    btn_eye.config(text="👁️")

            btn_eye.config(command=toggle_eye)

            def on_focus_in(e):
                shell.configure(highlightbackground="#5CBD28", bg="#FFFFFF")
                entry.configure(bg="#FFFFFF")
                btn_eye.configure(bg="#FFFFFF")

            def on_focus_out(e):
                shell.configure(highlightbackground="#D1D5DB", bg="#F8FBF2")
                entry.configure(bg="#F8FBF2")
                btn_eye.configure(bg="#F8FBF2")
        else:
            entry.pack(fill="x", padx=10, pady=7)

            def on_focus_in(e):
                shell.configure(highlightbackground="#5CBD28", bg="#FFFFFF")
                entry.configure(bg="#FFFFFF")

            def on_focus_out(e):
                shell.configure(highlightbackground="#D1D5DB", bg="#F8FBF2")
                entry.configure(bg="#F8FBF2")

        entry.bind("<FocusIn>", on_focus_in)
        entry.bind("<FocusOut>", on_focus_out)
        return entry

    def _submit(self):
        user = self.ent_user.get().strip()
        pwd = self.ent_pass.get().strip()
        if not user or not pwd:
            self.set_status("Por favor, preencha o usuário e a senha.", is_error=True)
            return

        self.set_loading(True)
        self.on_login_submit(user, pwd)

    def set_loading(self, loading: bool):
        if loading:
            self.btn_login.config(state="disabled", text="⏳ Conectando...", bg="#94a3b8")
            self.lbl_status.config(text="")
        else:
            self.btn_login.config(state="normal", text="Entrar no painel", bg="#5CBD28")

    def set_status(self, message: str, is_error: bool = False):
        color = "#dc2626" if is_error else "#16a34a"
        self.lbl_status.config(text=message, fg=color)
