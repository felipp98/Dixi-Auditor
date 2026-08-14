"""
Componente de Gestão Dinâmica de Signatários e Testemunhas para o Autentique.
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
    ROLE_SIGN,
    ROLE_WITNESS,
    ROLE_APPROVE,
    ROLES_AUTENTIQUE_DISPLAY,
    ROLES_AUTENTIQUE_REVERSE
)
from src.utils.security import get_secure_credential
from src.utils.colaboradores import buscar_dados_colaborador
from src.ui.theme import get_font

class SignerListManager(tk.Frame):
    """Widget para gerenciar pessoas signatárias e testemunhas antes do envio ao Autentique."""

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
        self.signers: List[Signatario] = []
        self._build_ui()
        self.load_defaults_from_settings()

    def _build_ui(self):
        # Cabeçalho da seção
        hdr_frame = tk.Frame(self, bg=COLOR_SURFACE)
        hdr_frame.pack(fill="x", pady=(0, 8))

        lbl_title = tk.Label(
            hdr_frame,
            text="👥 Signatários & Testemunhas (Autentique)",
            bg=COLOR_SURFACE,
            fg=COLOR_PRIMARY_DARK,
            font=get_font(10, bold=True)
        )
        lbl_title.pack(side="left")

        btn_add = ttk.Button(
            hdr_frame,
            text="➕ Adicionar Signatário / Testemunha",
            command=self._open_add_signer_dialog
        )
        btn_add.pack(side="right")

        # Tabela de Signatários
        cols = ("nome", "email", "role")
        self.tree_signers = ttk.Treeview(self, columns=cols, show="headings", height=4, selectmode="browse")
        self.tree_signers.heading("nome", text="Nome Completo")
        self.tree_signers.heading("email", text="E-mail")
        self.tree_signers.heading("role", text="Papel / Função")

        self.tree_signers.column("nome", width=180, anchor="w")
        self.tree_signers.column("email", width=220, anchor="w")
        self.tree_signers.column("role", width=120, anchor="center")

        self.tree_signers.pack(fill="x", expand=True, pady=(0, 8))

        # Botões de Ação na Lista
        btn_bar = tk.Frame(self, bg=COLOR_SURFACE)
        btn_bar.pack(fill="x")

        ttk.Button(btn_bar, text="✏️ Editar Selecionado", command=self._edit_selected_signer).pack(side="left", padx=(0, 6))
        ttk.Button(btn_bar, text="🗑️ Remover Selecionado", command=self._remove_selected_signer).pack(side="left", padx=(0, 6))
        ttk.Button(btn_bar, text="🔄 Restaurar Padrões das Configurações", command=self.load_defaults_from_settings).pack(side="right")

    def load_defaults_from_settings(self):
        """Carrega os signatários padrão configurados no cofre (Colaborador, Gestor e RH)."""
        self.signers.clear()

        colab_nome = get_secure_credential("colaborador_nome", "Colaborador")
        colab_email = get_secure_credential("colaborador_email", "")
        if not colab_email or "@" not in colab_email:
            cad_c = buscar_dados_colaborador(colab_nome)
            if cad_c and cad_c.get("email"):
                colab_email = cad_c.get("email")

        gestor_nome = get_secure_credential("gestor_nome", "Gestor Imediato")
        gestor_email = get_secure_credential("gestor_email", "")
        if not gestor_email or "@" not in gestor_email:
            cad_g = buscar_dados_colaborador(gestor_nome)
            if cad_g and cad_g.get("email"):
                gestor_email = cad_g.get("email")

        rh_nome = get_secure_credential("rh_nome", "Recursos Humanos")
        rh_email = get_secure_credential("rh_email", "")
        if not rh_email or "@" not in rh_email:
            cad_rh = buscar_dados_colaborador(rh_nome)
            if cad_rh and cad_rh.get("email"):
                rh_email = cad_rh.get("email")

        # Posições padrão para o layout oficial
        pos_preset = get_secure_credential("autentique_pos_preset", "Sobre a Linha Verde (Y: 68%)")
        y_pos = 68.0 if "68%" in pos_preset else 85.0

        if colab_email:
            self.signers.append(Signatario(
                nome=colab_nome,
                email=colab_email,
                role=ROLE_SIGN,
                positions=[{"x": 15.0, "y": y_pos, "z": 1, "element": "SIGNATURE", "scale": 0.85}]
            ))

        if gestor_email:
            self.signers.append(Signatario(
                nome=gestor_nome,
                email=gestor_email,
                role=ROLE_SIGN,
                positions=[{"x": 50.0, "y": y_pos, "z": 1, "element": "SIGNATURE", "scale": 0.85}]
            ))

        if rh_email:
            self.signers.append(Signatario(
                nome=rh_nome,
                email=rh_email,
                role=ROLE_APPROVE,
                positions=[{"x": 80.0, "y": y_pos, "z": 1, "element": "SIGNATURE", "scale": 0.85}]
            ))

        self._refresh_tree()

    def _refresh_tree(self):
        self.tree_signers.delete(*self.tree_signers.get_children())
        for idx, sig in enumerate(self.signers):
            display_role = ROLES_AUTENTIQUE_REVERSE.get(sig.role, "Assinar")
            self.tree_signers.insert("", "end", iid=f"sig_{idx}", values=(sig.nome, sig.email, display_role))
        if self.on_change_callback:
            self.on_change_callback()

    def _open_add_signer_dialog(self):
        self._open_signer_editor_dialog(None)

    def _edit_selected_signer(self):
        sel = self.tree_signers.selection()
        if not sel:
            messagebox.showinfo("Aviso", "Selecione um signatário da lista para editar.")
            return
        idx = int(sel[0].replace("sig_", ""))
        self._open_signer_editor_dialog(idx)

    def _open_signer_editor_dialog(self, edit_idx: Optional[int] = None):
        is_editing = (edit_idx is not None and 0 <= edit_idx < len(self.signers))
        target_sig = self.signers[edit_idx] if is_editing else None

        top = tk.Toplevel(self)
        top.title("Editar Signatário" if is_editing else "Adicionar Signatário / Testemunha")
        top.geometry("450x260")
        top.minsize(400, 240)
        top.transient(self)
        top.grab_set()

        ttk.Label(top, text="Nome Completo:").pack(anchor="w", padx=16, pady=(12, 2))
        ent_nome = ttk.Entry(top, width=44)
        ent_nome.insert(0, target_sig.nome if target_sig else "")
        ent_nome.pack(anchor="w", padx=16, pady=(0, 8))

        ttk.Label(top, text="E-mail:").pack(anchor="w", padx=16, pady=(0, 2))
        ent_email = ttk.Entry(top, width=44)
        ent_email.insert(0, target_sig.email if target_sig else "")
        ent_email.pack(anchor="w", padx=16, pady=(0, 8))

        ttk.Label(top, text="Papel no Documento:").pack(anchor="w", padx=16, pady=(0, 2))
        cb_role = ttk.Combobox(top, width=20, values=["Assinar", "Testemunha", "Aprovar"], state="readonly")
        if target_sig:
            cb_role.set(ROLES_AUTENTIQUE_REVERSE.get(target_sig.role, "Assinar"))
        else:
            cb_role.set("Testemunha")
        cb_role.pack(anchor="w", padx=16, pady=(0, 14))

        def salvar():
            nome = ent_nome.get().strip()
            email = ent_email.get().strip()
            role_choice = cb_role.get()
            role_code = ROLES_AUTENTIQUE_DISPLAY.get(role_choice, ROLE_SIGN)

            if not nome or not email or "@" not in email:
                messagebox.showwarning("Campos Obrigatórios", "Por favor preencha um nome e um e-mail válido.")
                return

            if is_editing:
                self.signers[edit_idx].nome = nome
                self.signers[edit_idx].email = email
                self.signers[edit_idx].role = role_code
            else:
                self.signers.append(Signatario(
                    nome=nome,
                    email=email,
                    role=role_code
                ))

            self._refresh_tree()
            top.destroy()

        btn_box = ttk.Frame(top)
        btn_box.pack(fill="x", padx=16, pady=4)
        ttk.Button(btn_box, text="Cancelar", command=top.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(btn_box, text="💾 Salvar", style="Primary.TButton", command=salvar).pack(side="right")

    def _remove_selected_signer(self):
        sel = self.tree_signers.selection()
        if not sel:
            messagebox.showinfo("Aviso", "Selecione um signatário para remover.")
            return
        idx = int(sel[0].replace("sig_", ""))
        del self.signers[idx]
        self._refresh_tree()

    def get_signatarios(self) -> List[Signatario]:
        """Retorna a lista atual de signatários configurados."""
        return list(self.signers)
