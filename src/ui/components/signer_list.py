"""
Componente de Gestão Dinâmica e Expandida de Signatários e Testemunhas para o Autentique.
"""
import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Dict, Any, Optional

from src.core.models import Signatario
from src.config.constants import (
    COLOR_SURFACE,
    COLOR_BORDER,
    COLOR_PRIMARY,
    COLOR_PRIMARY_SOFT,
    COLOR_PRIMARY_DARK,
    COLOR_TEXT,
    COLOR_TEXT_MUTED,
    ROLE_SIGN,
    ROLE_WITNESS,
    ROLE_APPROVE,
    ROLES_AUTENTIQUE_DISPLAY,
    ROLES_AUTENTIQUE_REVERSE
)
from src.utils.security import get_secure_credential, set_secure_credential
from src.utils.colaboradores import carregar_colaboradores, buscar_dados_colaborador
from src.ui.theme import get_font

class SignerListManager(tk.Frame):
    """Painel expandido para visualização, edição e controle de signatários e testemunhas do Autentique."""

    def __init__(self, parent, on_change_callback: Optional[callable] = None):
        super().__init__(
            parent,
            bg=COLOR_SURFACE,
            padx=14,
            pady=12,
            highlightbackground=COLOR_BORDER,
            highlightthickness=1
        )
        self.on_change_callback = on_change_callback
        self.testemunhas_extras: List[Signatario] = []
        self._build_ui()
        self.load_defaults_from_settings()

    def _build_ui(self):
        # 1. Cabeçalho
        hdr_frame = tk.Frame(self, bg=COLOR_SURFACE)
        hdr_frame.pack(fill="x", pady=(0, 10))

        lbl_title = tk.Label(
            hdr_frame,
            text="👥 Signatários & Testemunhas da Justificativa",
            bg=COLOR_SURFACE,
            fg=COLOR_PRIMARY_DARK,
            font=get_font(10, bold=True)
        )
        lbl_title.pack(side="left")

        btn_rst = ttk.Button(
            hdr_frame,
            text="🔄 Recarregar Padrões",
            command=self.load_defaults_from_settings
        )
        btn_rst.pack(side="right")

        # 2. Cards de Colaborador e Gestor (Lado a Lado)
        cards_row = tk.Frame(self, bg=COLOR_SURFACE)
        cards_row.pack(fill="x", pady=(0, 10))

        # Card do Colaborador (Você)
        card_colab = tk.LabelFrame(
            cards_row,
            text=" 👤 Colaborador (Assinante Principal) ",
            bg=COLOR_SURFACE,
            fg=COLOR_PRIMARY_DARK,
            font=get_font(9, bold=True),
            padx=10,
            pady=8
        )
        card_colab.pack(side="left", fill="both", expand=True, padx=(0, 6))

        tk.Label(card_colab, text="Nome Completo:", bg=COLOR_SURFACE, fg=COLOR_TEXT_MUTED, font=get_font(8)).pack(anchor="w")
        self.ent_colab_nome = ttk.Entry(card_colab, font=get_font(9))
        self.ent_colab_nome.pack(fill="x", pady=(1, 4))

        tk.Label(card_colab, text="E-mail Corporativo:", bg=COLOR_SURFACE, fg=COLOR_TEXT_MUTED, font=get_font(8)).pack(anchor="w")
        self.ent_colab_email = ttk.Entry(card_colab, font=get_font(9))
        self.ent_colab_email.pack(fill="x", pady=(1, 2))

        # Card do Gestor Imediato
        card_gestor = tk.LabelFrame(
            cards_row,
            text=" 👔 Gestor Imediato (Aprovador / Assinante) ",
            bg=COLOR_SURFACE,
            fg=COLOR_PRIMARY_DARK,
            font=get_font(9, bold=True),
            padx=10,
            pady=8
        )
        card_gestor.pack(side="left", fill="both", expand=True, padx=(6, 0))

        tk.Label(card_gestor, text="Nome do Gestor:", bg=COLOR_SURFACE, fg=COLOR_TEXT_MUTED, font=get_font(8)).pack(anchor="w")
        
        # Obter lista de colaboradores cadastrados para autocomplete
        colabs = carregar_colaboradores()
        nomes_colabs = [c.get("nome", "") for c in colabs if c.get("nome")]

        self.cb_gestor_nome = ttk.Combobox(card_gestor, values=nomes_colabs, font=get_font(9))
        self.cb_gestor_nome.pack(fill="x", pady=(1, 4))
        self.cb_gestor_nome.bind("<<ComboboxSelected>>", self._on_gestor_selected)

        tk.Label(card_gestor, text="E-mail do Gestor:", bg=COLOR_SURFACE, fg=COLOR_TEXT_MUTED, font=get_font(8)).pack(anchor="w")
        self.ent_gestor_email = ttk.Entry(card_gestor, font=get_font(9))
        self.ent_gestor_email.pack(fill="x", pady=(1, 2))

        # 3. Seção de Testemunhas e Outros Signatários
        sec_test = tk.LabelFrame(
            self,
            text=" 📋 Testemunhas & Signatários Adicionais ",
            bg=COLOR_SURFACE,
            fg=COLOR_PRIMARY_DARK,
            font=get_font(9, bold=True),
            padx=10,
            pady=8
        )
        sec_test.pack(fill="both", expand=True)

        tbl_bar = tk.Frame(sec_test, bg=COLOR_SURFACE)
        tbl_bar.pack(fill="x", pady=(0, 6))

        tk.Label(
            tbl_bar,
            text="Pessoas que assinarão como testemunha ou receberão cópia do documento:",
            bg=COLOR_SURFACE,
            fg=COLOR_TEXT_MUTED,
            font=get_font(8)
        ).pack(side="left")

        btn_add = ttk.Button(
            tbl_bar,
            text="➕ Adicionar Testemunha",
            command=self._open_add_signer_dialog
        )
        btn_add.pack(side="right")

        cols = ("nome", "email", "role")
        self.tree_extras = ttk.Treeview(sec_test, columns=cols, show="headings", height=3, selectmode="browse")
        self.tree_extras.heading("nome", text="Nome Completo")
        self.tree_extras.heading("email", text="E-mail")
        self.tree_extras.heading("role", text="Papel no Autentique")

        self.tree_extras.column("nome", width=180, anchor="w")
        self.tree_extras.column("email", width=220, anchor="w")
        self.tree_extras.column("role", width=130, anchor="center")
        self.tree_extras.pack(fill="x", expand=True, pady=(0, 6))

        btn_actions = tk.Frame(sec_test, bg=COLOR_SURFACE)
        btn_actions.pack(fill="x")

        ttk.Button(btn_actions, text="✏️ Editar Testemunha", command=self._edit_selected_extra).pack(side="left", padx=(0, 6))
        ttk.Button(btn_actions, text="🗑️ Remover Testemunha", command=self._remove_selected_extra).pack(side="left")

    def _on_gestor_selected(self, event=None):
        """Ao escolher um gestor da lista, auto-completa o e-mail correspondente."""
        nome_selecionado = self.cb_gestor_nome.get().strip()
        dados = buscar_dados_colaborador(nome_selecionado)
        if dados and dados.get("email"):
            self.ent_gestor_email.delete(0, tk.END)
            self.ent_gestor_email.insert(0, dados.get("email"))

    def load_defaults_from_settings(self):
        """Carrega os dados padrão de signatários a partir do cofre e do cadastro de colaboradores."""
        colab_nome = get_secure_credential("colaborador_nome", "")
        colab_email = get_secure_credential("colaborador_email", "")

        if not colab_email or "@" not in colab_email:
            cad_c = buscar_dados_colaborador(colab_nome)
            if cad_c and cad_c.get("email"):
                colab_email = cad_c.get("email")

        self.ent_colab_nome.delete(0, tk.END)
        self.ent_colab_nome.insert(0, colab_nome)
        self.ent_colab_email.delete(0, tk.END)
        self.ent_colab_email.insert(0, colab_email)

        gestor_nome = get_secure_credential("gestor_nome", "")
        gestor_email = get_secure_credential("gestor_email", "")

        if not gestor_email or "@" not in gestor_email:
            cad_g = buscar_dados_colaborador(gestor_nome)
            if cad_g and cad_g.get("email"):
                gestor_email = cad_g.get("email")

        self.cb_gestor_nome.set(gestor_nome)
        self.ent_gestor_email.delete(0, tk.END)
        self.ent_gestor_email.insert(0, gestor_email)

        # Se houver RH configurado, adiciona como testemunha padrão se não houver extras
        rh_nome = get_secure_credential("rh_nome", "")
        rh_email = get_secure_credential("rh_email", "")
        if not rh_email or "@" not in rh_email:
            cad_rh = buscar_dados_colaborador(rh_nome)
            if cad_rh and cad_rh.get("email"):
                rh_email = cad_rh.get("email")

        self.testemunhas_extras.clear()
        if rh_email and rh_nome:
            self.testemunhas_extras.append(Signatario(
                nome=rh_nome,
                email=rh_email,
                role=ROLE_WITNESS,
                positions=[{"x": 80.0, "y": 68.0, "z": 1, "element": "SIGNATURE", "scale": 0.85}]
            ))
        self._refresh_extras_table()

    def _refresh_extras_table(self):
        """Atualiza visualmente a tabela de testemunhas e extras."""
        self.tree_extras.delete(*self.tree_extras.get_children())
        for idx, sig in enumerate(self.testemunhas_extras):
            role_disp = ROLES_AUTENTIQUE_REVERSE.get(sig.role, sig.role)
            self.tree_extras.insert("", "end", iid=f"extra_{idx}", values=(sig.nome, sig.email, role_disp))

    def _open_add_signer_dialog(self):
        """Abre diálogo para adicionar testemunha ou outro signatário."""
        top = tk.Toplevel(self)
        top.title("Adicionar Signatário / Testemunha")
        top.geometry("440x260")
        top.minsize(400, 240)
        top.transient(self)
        top.grab_set()

        tk.Label(top, text="Nome Completo:", font=get_font(9)).pack(anchor="w", padx=16, pady=(12, 2))
        colabs = carregar_colaboradores()
        nomes_colabs = [c.get("nome", "") for c in colabs if c.get("nome")]

        cb_nome = ttk.Combobox(top, values=nomes_colabs, font=get_font(9))
        cb_nome.pack(fill="x", padx=16, pady=(0, 6))

        tk.Label(top, text="E-mail:", font=get_font(9)).pack(anchor="w", padx=16, pady=(2, 2))
        ent_email = ttk.Entry(top, font=get_font(9))
        ent_email.pack(fill="x", padx=16, pady=(0, 6))

        def on_name_select(e=None):
            dados = buscar_dados_colaborador(cb_nome.get().strip())
            if dados and dados.get("email"):
                ent_email.delete(0, tk.END)
                ent_email.insert(0, dados.get("email"))

        cb_nome.bind("<<ComboboxSelected>>", on_name_select)

        tk.Label(top, text="Papel no Documento:", font=get_font(9)).pack(anchor="w", padx=16, pady=(2, 2))
        combo_role = ttk.Combobox(
            top,
            values=list(ROLES_AUTENTIQUE_DISPLAY.keys()),
            state="readonly",
            font=get_font(9)
        )
        combo_role.set("Testemunha")
        combo_role.pack(fill="x", padx=16, pady=(0, 12))

        def salvar():
            nome = cb_nome.get().strip()
            email = ent_email.get().strip()
            role_sel = combo_role.get()
            role_api = ROLES_AUTENTIQUE_DISPLAY.get(role_sel, ROLE_WITNESS)

            if not nome or not email or "@" not in email:
                messagebox.showerror("Campos Obrigatórios", "Informe um nome válido e um e-mail válido com @.", parent=top)
                return

            self.testemunhas_extras.append(Signatario(
                nome=nome,
                email=email,
                role=role_api,
                positions=[{"x": 80.0, "y": 68.0, "z": 1, "element": "SIGNATURE", "scale": 0.85}]
            ))
            self._refresh_extras_table()
            top.destroy()

        btn_frame = ttk.Frame(top)
        btn_frame.pack(fill="x", padx=16, pady=6)
        ttk.Button(btn_frame, text="Cancelar", command=top.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(btn_frame, text="➕ Adicionar", style="Primary.TButton", command=salvar).pack(side="right")

    def _edit_selected_extra(self):
        sel = self.tree_extras.selection()
        if not sel:
            messagebox.showinfo("Aviso", "Selecione uma testemunha para editar.")
            return

        idx = int(sel[0].replace("extra_", ""))
        sig = self.testemunhas_extras[idx]

        top = tk.Toplevel(self)
        top.title("Editar Testemunha / Signatário")
        top.geometry("440x240")
        top.transient(self)
        top.grab_set()

        tk.Label(top, text="Nome Completo:", font=get_font(9)).pack(anchor="w", padx=16, pady=(12, 2))
        ent_nome = ttk.Entry(top, font=get_font(9))
        ent_nome.insert(0, sig.nome)
        ent_nome.pack(fill="x", padx=16, pady=(0, 6))

        tk.Label(top, text="E-mail:", font=get_font(9)).pack(anchor="w", padx=16, pady=(2, 2))
        ent_email = ttk.Entry(top, font=get_font(9))
        ent_email.insert(0, sig.email)
        ent_email.pack(fill="x", padx=16, pady=(0, 6))

        tk.Label(top, text="Papel no Documento:", font=get_font(9)).pack(anchor="w", padx=16, pady=(2, 2))
        combo_role = ttk.Combobox(top, values=list(ROLES_AUTENTIQUE_DISPLAY.keys()), state="readonly", font=get_font(9))
        combo_role.set(ROLES_AUTENTIQUE_REVERSE.get(sig.role, "Testemunha"))
        combo_role.pack(fill="x", padx=16, pady=(0, 12))

        def salvar_edicao():
            sig.nome = ent_nome.get().strip()
            sig.email = ent_email.get().strip()
            sig.role = ROLES_AUTENTIQUE_DISPLAY.get(combo_role.get(), ROLE_WITNESS)
            self._refresh_extras_table()
            top.destroy()

        btn_frame = ttk.Frame(top)
        btn_frame.pack(fill="x", padx=16, pady=6)
        ttk.Button(btn_frame, text="Cancelar", command=top.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(btn_frame, text="💾 Salvar", style="Primary.TButton", command=salvar_edicao).pack(side="right")

    def _remove_selected_extra(self):
        sel = self.tree_extras.selection()
        if not sel:
            messagebox.showinfo("Aviso", "Selecione uma testemunha para remover.")
            return

        idx = int(sel[0].replace("extra_", ""))
        del self.testemunhas_extras[idx]
        self._refresh_extras_table()

    def get_signers(self) -> List[Signatario]:
        """
        Coleta a lista completa de signatários e testemunhas validados para envio ao Autentique.
        """
        all_signers: List[Signatario] = []

        pos_preset = get_secure_credential("autentique_pos_preset", "Sobre a Linha Verde (Y: 68%)")
        y_pos = 68.0 if "68%" in pos_preset else 85.0

        # 1. Colaborador
        c_nome = self.ent_colab_nome.get().strip() or "Colaborador"
        c_email = self.ent_colab_email.get().strip()
        if c_email and "@" in c_email:
            all_signers.append(Signatario(
                nome=c_nome,
                email=c_email,
                role=ROLE_SIGN,
                positions=[{"x": 15.0, "y": y_pos, "z": 1, "element": "SIGNATURE", "scale": 0.85}]
            ))

        # 2. Gestor
        g_nome = self.cb_gestor_nome.get().strip() or "Gestor Imediato"
        g_email = self.ent_gestor_email.get().strip()
        if g_email and "@" in g_email:
            all_signers.append(Signatario(
                nome=g_nome,
                email=g_email,
                role=ROLE_SIGN,
                positions=[{"x": 50.0, "y": y_pos, "z": 1, "element": "SIGNATURE", "scale": 0.85}]
            ))

        # 3. Testemunhas e Extras
        for idx, t in enumerate(self.testemunhas_extras):
            if t.email and "@" in t.email:
                x_val = 80.0 if idx == 0 else 80.0 + (idx * 5.0)
                t.positions = [{"x": x_val, "y": y_pos, "z": 1, "element": "SIGNATURE", "scale": 0.85}]
                all_signers.append(t)

        return all_signers
