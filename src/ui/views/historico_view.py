"""
Tela de Consulta e Acompanhamento do Histórico de Documentos no Autentique com Filtros por Status.
"""
import os
import webbrowser
import logging
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, List, Dict, Any

from src.services.autentique_service import listar_documentos_autentique
from src.utils.security import get_secure_credential
from src.utils.threading_utils import run_async_task
from src.config.constants import (
    COLOR_SURFACE,
    COLOR_BG,
    COLOR_BORDER,
    COLOR_PRIMARY,
    COLOR_PRIMARY_DARK,
    COLOR_PRIMARY_SOFT,
    COLOR_TEXT,
    COLOR_TEXT_MUTED,
    COLOR_SUCCESS_BG,
    COLOR_DANGER_BG,
    COLOR_WARNING_BG
)
from src.ui.theme import get_font

logger = logging.getLogger(__name__)

class HistoricoView(tk.Frame):
    """Visualização do histórico de documentos enviados para o Autentique com filtros em cápsula."""

    def __init__(self, parent):
        super().__init__(parent, bg=COLOR_BG)
        self.all_docs: List[Dict[str, Any]] = []
        self.filtro_ativo: str = "todos"  # 'todos', 'pendentes', 'concluidos', 'cancelados'
        self.filter_buttons = {}
        self._build_ui()

    def _build_ui(self):
        # 1. Cabeçalho
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

        # 2. Barra de Filtros em Cápsula e Atualização
        ctrl = tk.Frame(self, bg=COLOR_SURFACE, padx=14, pady=10, highlightbackground=COLOR_BORDER, highlightthickness=1)
        ctrl.pack(fill="x", pady=(0, 10))

        # Filtros em Cápsula
        pills_frame = tk.Frame(ctrl, bg=COLOR_SURFACE)
        pills_frame.pack(side="left")

        filtros_def = [
            ("todos", "📋 Todos (0)"),
            ("pendentes", "⏳ Pendentes (0)"),
            ("concluidos", "✅ Concluídos (0)"),
            ("cancelados", "❌ Cancelados (0)")
        ]

        for key, text in filtros_def:
            btn = tk.Button(
                pills_frame,
                text=text,
                bg=COLOR_PRIMARY_DARK if key == "todos" else COLOR_PRIMARY_SOFT,
                fg="#ffffff" if key == "todos" else COLOR_TEXT,
                activebackground=COLOR_PRIMARY,
                activeforeground="#ffffff",
                font=get_font(9, bold=(key == "todos")),
                bd=0,
                relief="flat",
                cursor="hand2",
                padx=12,
                pady=5,
                command=lambda k=key: self._set_filtro(k)
            )
            btn.pack(side="left", padx=(0, 6))
            self.filter_buttons[key] = btn

        # Botão de Atualizar à Direita
        btn_refresh = ttk.Button(ctrl, text="🔄 Atualizar Lista", command=self.carregar_historico)
        btn_refresh.pack(side="right")

        self.lbl_status = ttk.Label(ctrl, text="", font=get_font(9, bold=True))
        self.lbl_status.pack(side="right", padx=(0, 12))

        # 3. Tabela de Histórico
        table_card = tk.Frame(self, bg=COLOR_SURFACE, padx=12, pady=10, highlightbackground=COLOR_BORDER, highlightthickness=1)
        table_card.pack(fill="both", expand=True, pady=(0, 10))

        cols = ("status_icon", "nome", "data", "status_assinaturas", "id")
        self.tree = ttk.Treeview(table_card, columns=cols, show="headings", selectmode="browse")
        self.tree.heading("status_icon", text="Status", anchor="center")
        self.tree.heading("nome", text="Nome do Documento", anchor="w")
        self.tree.heading("data", text="Criado em", anchor="center")
        self.tree.heading("status_assinaturas", text="Signatários & Assinaturas", anchor="w")
        self.tree.heading("id", text="ID Autentique", anchor="center")

        self.tree.column("status_icon", width=110, anchor="center")
        self.tree.column("nome", width=280, anchor="w")
        self.tree.column("data", width=140, anchor="center")
        self.tree.column("status_assinaturas", width=380, anchor="w")
        self.tree.column("id", width=180, anchor="center")

        # Tags visuais de status
        self.tree.tag_configure("concluido", background=COLOR_SUCCESS_BG, foreground="#14532d")
        self.tree.tag_configure("pendente", background=COLOR_WARNING_BG, foreground="#78350f")
        self.tree.tag_configure("cancelado", background=COLOR_DANGER_BG, foreground="#7f1d1d")
        self.tree.tag_configure("normal", background=COLOR_SURFACE, foreground=COLOR_TEXT)

        sb = ttk.Scrollbar(table_card, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)

        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self.tree.bind("<Double-1>", lambda e: self._abrir_no_navegador())

        # 4. Barra de Ações Inferior
        bot_bar = tk.Frame(self, bg=COLOR_SURFACE, padx=14, pady=10, highlightbackground=COLOR_BORDER, highlightthickness=1)
        bot_bar.pack(fill="x")

        ttk.Button(bot_bar, text="🌐 Abrir Documento no Autentique", style="Primary.TButton", command=self._abrir_no_navegador).pack(side="left", padx=(0, 10))
        tk.Label(
            bot_bar,
            text="Dica: Você também pode dar um duplo clique em qualquer linha para abrir o documento diretamente.",
            bg=COLOR_SURFACE,
            fg=COLOR_TEXT_MUTED,
            font=get_font(8)
        ).pack(side="left")

    def _classificar_documento(self, doc: Dict[str, Any]) -> str:
        """Classifica o status global do documento em 'concluidos', 'cancelados' ou 'pendentes'."""
        sigs = doc.get("signatures", [])
        if not sigs:
            return "pendentes"

        # Se alguém recusou ou foi rejeitado
        if any(s.get("rejected") for s in sigs):
            return "cancelados"

        # Se todos assinaram
        if all(s.get("signed") for s in sigs):
            return "concluidos"

        return "pendentes"

    def _set_filtro(self, key: str):
        """Altera a cápsula ativa e filtra os dados da tabela."""
        self.filtro_ativo = key
        for k, btn in self.filter_buttons.items():
            if k == key:
                btn.config(bg=COLOR_PRIMARY_DARK, fg="#ffffff", font=get_font(9, bold=True))
            else:
                btn.config(bg=COLOR_PRIMARY_SOFT, fg=COLOR_TEXT, font=get_font(9))

        self._render_tabela()

    def _render_tabela(self):
        """Renderiza os documentos aplicando o filtro ativo e as tags de cores."""
        self.tree.delete(*self.tree.get_children())

        docs_filtrados = []
        for doc in self.all_docs:
            status_cat = self._classificar_documento(doc)
            if self.filtro_ativo == "todos" or self.filtro_ativo == status_cat:
                docs_filtrados.append((doc, status_cat))

        for doc, status_cat in docs_filtrados:
            doc_id = doc.get("id", "")
            name = doc.get("name", "")
            created = str(doc.get("created_at", ""))[:19].replace("T", " ")
            sigs = doc.get("signatures", [])

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

            if status_cat == "concluidos":
                status_label = "✅ CONCLUÍDO"
                tag = "concluido"
            elif status_cat == "cancelados":
                status_label = "❌ RECUSADO"
                tag = "cancelado"
            else:
                status_label = "⏳ PENDENTE"
                tag = "pendente"

            self.tree.insert(
                "",
                "end",
                iid=doc_id,
                values=(status_label, name, created, summary_str, doc_id),
                tags=(tag,)
            )

    def _atualizar_contadores(self):
        """Atualiza a contagem exibida nos botões cápsula de filtro."""
        total = len(self.all_docs)
        pendentes = sum(1 for d in self.all_docs if self._classificar_documento(d) == "pendentes")
        concluidos = sum(1 for d in self.all_docs if self._classificar_documento(d) == "concluidos")
        cancelados = sum(1 for d in self.all_docs if self._classificar_documento(d) == "cancelados")

        if "todos" in self.filter_buttons:
            self.filter_buttons["todos"].config(text=f"📋 Todos ({total})")
        if "pendentes" in self.filter_buttons:
            self.filter_buttons["pendentes"].config(text=f"⏳ Pendentes ({pendentes})")
        if "concluidos" in self.filter_buttons:
            self.filter_buttons["concluidos"].config(text=f"✅ Concluídos ({concluidos})")
        if "cancelados" in self.filter_buttons:
            self.filter_buttons["cancelados"].config(text=f"❌ Cancelados ({cancelados})")

    def carregar_historico(self):
        """Busca a lista de documentos atualizada no Autentique."""
        token = get_secure_credential("autentique_token")
        if not token:
            self.lbl_status.config(text="⚠️ Configure o Token do Autentique em 'Configurações'.", foreground="#d97706")
            return

        self.lbl_status.config(text="⏳ Buscando documentos...", foreground="#0284c7")

        def worker():
            return listar_documentos_autentique(token, page=1, limit=60)

        def on_success(data):
            docs = data.get("data", [])
            self.all_docs = docs
            self._atualizar_contadores()
            self._render_tabela()
            self.lbl_status.config(text=f"✅ {len(docs)} documento(s) carregados.", foreground="#16a34a")

        def on_error(err):
            self.lbl_status.config(text=f"❌ Erro ao listar: {err}", foreground="#dc2626")

        run_async_task(worker, on_success=on_success, on_error=on_error, root_widget=self)

    def _abrir_no_navegador(self):
        """Abre o documento selecionado no portal web do Autentique."""
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Aviso", "Selecione um documento da lista.")
            return

        doc_id = sel[0]
        # Tenta pegar a URL de assinatura ou link direto do documento
        for d in self.all_docs:
            if d.get("id") == doc_id:
                link = None
                # Verifica links diretos
                if d.get("link"):
                    link = d.get("link", {}).get("short_link")
                if not link and d.get("signatures"):
                    for s in d.get("signatures", []):
                        if s.get("link", {}).get("short_link"):
                            link = s.get("link", {}).get("short_link")
                            break

                if not link:
                    link = f"https://painel.autentique.com.br/documentos/{doc_id}"

                try:
                    webbrowser.open(link)
                except Exception as e:
                    messagebox.showerror("Erro ao Abrir", f"Falha ao abrir navegador:\n{e}")
                return

        webbrowser.open(f"https://painel.autentique.com.br/documentos/{doc_id}")
