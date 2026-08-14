"""
Tela de Consulta e Acompanhamento do Histórico de Documentos no Autentique.
"""
import os
import webbrowser
import logging
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional

from src.services.autentique_service import listar_documentos_autentique
from src.utils.security import get_secure_credential
from src.utils.threading_utils import run_async_task
from src.config.constants import (
    COLOR_SURFACE,
    COLOR_BORDER,
    COLOR_PRIMARY_DARK,
    COLOR_TEXT_MUTED
)
from src.ui.theme import get_font

logger = logging.getLogger(__name__)

class HistoricoView(tk.Frame):
    """Visualização do histórico de documentos enviados para o Autentique."""

    def __init__(self, parent):
        super().__init__(parent, bg=COLOR_SURFACE)
        self.doc_cache = []
        self._build_ui()

    def _build_ui(self):
        # Cabeçalho
        hdr = tk.Frame(self, bg=COLOR_SURFACE, padx=18, pady=12, highlightbackground=COLOR_BORDER, highlightthickness=1)
        hdr.pack(fill="x", pady=(0, 10))

        tk.Label(
            hdr,
            text="📜 Histórico de Documentos e Assinaturas (Autentique)",
            bg=COLOR_SURFACE,
            fg=COLOR_PRIMARY_DARK,
            font=get_font(12, bold=True)
        ).pack(anchor="w")

        tk.Label(
            hdr,
            text="Acompanhe em tempo real quem já assinou, visualizou ou recusou as justificativas de ponto.",
            bg=COLOR_SURFACE,
            fg=COLOR_TEXT_MUTED,
            font=get_font(9)
        ).pack(anchor="w", pady=(2, 0))

        # Controles
        ctrl = tk.Frame(self, bg=COLOR_SURFACE, padx=14, pady=8, highlightbackground=COLOR_BORDER, highlightthickness=1)
        ctrl.pack(fill="x", pady=(0, 10))

        ttk.Button(ctrl, text="🔄 Atualizar Lista", command=self.carregar_historico).pack(side="left")
        self.lbl_status = ttk.Label(ctrl, text="", font=get_font(9, bold=True))
        self.lbl_status.pack(side="left", padx=(15, 0))

        # Tabela de Histórico
        table_card = tk.Frame(self, bg=COLOR_SURFACE, padx=12, pady=10, highlightbackground=COLOR_BORDER, highlightthickness=1)
        table_card.pack(fill="both", expand=True, pady=(0, 10))

        cols = ("id", "nome", "data", "status_assinaturas")
        self.tree = ttk.Treeview(table_card, columns=cols, show="headings", selectmode="browse")
        self.tree.heading("id", text="ID")
        self.tree.heading("nome", text="Nome do Documento")
        self.tree.heading("data", text="Criado em")
        self.tree.heading("status_assinaturas", text="Signatários & Status")

        self.tree.column("id", width=120, anchor="center")
        self.tree.column("nome", width=260, anchor="w")
        self.tree.column("data", width=140, anchor="center")
        self.tree.column("status_assinaturas", width=380, anchor="w")

        sb = ttk.Scrollbar(table_card, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)

        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        # Botão de Ação
        bot_bar = tk.Frame(self, bg=COLOR_SURFACE, padx=14, pady=8)
        bot_bar.pack(fill="x")

        ttk.Button(bot_bar, text="🌐 Abrir no Navegador", command=self._abrir_no_navegador).pack(side="left")

    def carregar_historico(self):
        token = get_secure_credential("autentique_token")
        if not token:
            self.lbl_status.config(text="⚠️ Configure o Token do Autentique em 'Configurações'.", foreground="#d97706")
            return

        self.lbl_status.config(text="⏳ Buscando documentos no Autentique...", foreground="#0284c7")

        def worker():
            return listar_documentos_autentique(token, page=1, limit=50)

        def on_success(data):
            self.tree.delete(*self.tree.get_children())
            docs = data.get("data", [])
            self.doc_cache = docs

            for d in docs:
                doc_id = d.get("id", "")
                name = d.get("name", "")
                created = d.get("created_at", "")[:19].replace("T", " ")
                sigs = d.get("signatures", [])

                sig_summary = []
                for s in sigs:
                    s_name = s.get("name") or s.get("email") or "Signatário"
                    if s.get("signed"):
                        st = "✔ Assinado"
                    elif s.get("rejected"):
                        st = "❌ Recusado"
                    elif s.get("viewed"):
                        st = "👁️ Visualizado"
                    else:
                        st = "⏳ Pendente"
                    sig_summary.append(f"{s_name} ({st})")

                summary_str = " | ".join(sig_summary) if sig_summary else "Sem signatários"
                self.tree.insert("", "end", iid=doc_id, values=(doc_id, name, created, summary_str))

            self.lbl_status.config(text=f"✅ {len(docs)} documento(s) listado(s).", foreground="#16a34a")

        def on_error(err):
            self.lbl_status.config(text=f"❌ Erro ao listar documentos: {err}", foreground="#dc2626")

        run_async_task(worker, on_success=on_success, on_error=on_error, root_widget=self)

    def _abrir_no_navegador(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Aviso", "Selecione um documento da lista.")
            return
        doc_id = sel[0]
        # Procura o link do documento
        for d in self.doc_cache:
            if d.get("id") == doc_id:
                sigs = d.get("signatures", [])
                for s in sigs:
                    link = s.get("link", {}).get("short_link")
                    if link:
                        webbrowser.open(link)
                        return
        webbrowser.open("https://app.autentique.com.br")
