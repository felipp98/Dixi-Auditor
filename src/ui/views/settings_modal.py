"""
Modal de Configurações do Sistema (Credenciais, Chaves de API e Parâmetros).
"""
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional

from src.utils.security import get_secure_credential, set_secure_credential
from src.utils.colaboradores import buscar_cargo_colaborador
from src.config.constants import DEFAULT_AI_MODEL
from src.ui.components.password_entry import PasswordEntry
from src.ui.theme import get_font

class SettingsModal(tk.Toplevel):
    """Janela modal para configurações do usuário, gestores e chaves de API."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("⚙️ Configurações do Sistema")
        self.geometry("720x620")
        self.minsize(650, 520)
        self.transient(parent)
        self.grab_set()
        self._build_ui()

    def _build_ui(self):
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=12, pady=12)

        # Aba 1: Dados do Colaborador & Gestão
        tab_colab = ttk.Frame(notebook, padding=15)
        notebook.add(tab_colab, text="👤 Dados do Colaborador & RH")

        sec_c = ttk.LabelFrame(tab_colab, text=" Dados Pessoais do Colaborador ", padding=12)
        sec_c.pack(fill="x", pady=(0, 10))
        sec_c.columnconfigure(1, weight=1)

        colab_nome = get_secure_credential("colaborador_nome", "Colaborador")
        colab_cargo = get_secure_credential("colaborador_cargo", "")
        if not colab_cargo or colab_cargo.lower() == "colaborador":
            cargo_sug = buscar_cargo_colaborador(colab_nome)
            if cargo_sug:
                colab_cargo = cargo_sug

        ttk.Label(sec_c, text="Nome Completo:").grid(row=0, column=0, sticky="w", pady=4)
        self.ent_colab_nome = ttk.Entry(sec_c)
        self.ent_colab_nome.insert(0, colab_nome)
        self.ent_colab_nome.grid(row=0, column=1, sticky="ew", pady=4, padx=(8, 0))

        ttk.Label(sec_c, text="Cargo / Função:").grid(row=1, column=0, sticky="w", pady=4)
        self.ent_colab_cargo = ttk.Entry(sec_c)
        self.ent_colab_cargo.insert(0, colab_cargo)
        self.ent_colab_cargo.grid(row=1, column=1, sticky="ew", pady=4, padx=(8, 0))

        ttk.Label(sec_c, text="E-mail do Colaborador:").grid(row=2, column=0, sticky="w", pady=4)
        self.ent_colab_email = ttk.Entry(sec_c)
        self.ent_colab_email.insert(0, get_secure_credential("colaborador_email", ""))
        self.ent_colab_email.grid(row=2, column=1, sticky="ew", pady=4, padx=(8, 0))

        sec_ap = ttk.LabelFrame(tab_colab, text=" Aprovadores e Destinatários (Gestão / RH) ", padding=12)
        sec_ap.pack(fill="x", pady=(0, 10))
        sec_ap.columnconfigure(1, weight=1)

        ttk.Label(sec_ap, text="Nome do Gestor:").grid(row=0, column=0, sticky="w", pady=4)
        self.ent_gestor_nome = ttk.Entry(sec_ap)
        self.ent_gestor_nome.insert(0, get_secure_credential("gestor_nome", "Gestor Imediato"))
        self.ent_gestor_nome.grid(row=0, column=1, sticky="ew", pady=4, padx=(8, 0))

        ttk.Label(sec_ap, text="E-mail do Gestor:").grid(row=1, column=0, sticky="w", pady=4)
        self.ent_gestor_email = ttk.Entry(sec_ap)
        self.ent_gestor_email.insert(0, get_secure_credential("gestor_email", ""))
        self.ent_gestor_email.grid(row=1, column=1, sticky="ew", pady=4, padx=(8, 0))

        ttk.Label(sec_ap, text="Nome do RH:").grid(row=2, column=0, sticky="w", pady=4)
        self.ent_rh_nome = ttk.Entry(sec_ap)
        self.ent_rh_nome.insert(0, get_secure_credential("rh_nome", "Recursos Humanos"))
        self.ent_rh_nome.grid(row=2, column=1, sticky="ew", pady=4, padx=(8, 0))

        ttk.Label(sec_ap, text="E-mail do RH:").grid(row=3, column=0, sticky="w", pady=4)
        self.ent_rh_email = ttk.Entry(sec_ap)
        self.ent_rh_email.insert(0, get_secure_credential("rh_email", ""))
        self.ent_rh_email.grid(row=3, column=1, sticky="ew", pady=4, padx=(8, 0))

        self.lbl_colab_msg = ttk.Label(tab_colab, text="", font=get_font(9, bold=True))
        self.lbl_colab_msg.pack(anchor="w", pady=(0, 8))

        btn_save_colab = ttk.Button(tab_colab, text="💾 Salvar Dados de Pessoas", style="Primary.TButton", command=self._salvar_dados_colab)
        btn_save_colab.pack(anchor="e")

        # Aba 2: Chaves de API e Assinaturas
        tab_api = ttk.Frame(notebook, padding=15)
        notebook.add(tab_api, text="🔑 Integrações & Autentique")

        sec_keys = ttk.LabelFrame(tab_api, text=" Chaves de API e Tokens ", padding=12)
        sec_keys.pack(fill="x", pady=(0, 10))
        sec_keys.columnconfigure(1, weight=1)

        ttk.Label(sec_keys, text="Token Autentique:").grid(row=0, column=0, sticky="w", pady=4)
        self.ent_autentique_tok = PasswordEntry(sec_keys, show_char="•")
        self.ent_autentique_tok.insert(0, get_secure_credential("autentique_token", ""))
        self.ent_autentique_tok.grid(row=0, column=1, sticky="ew", pady=4, padx=(8, 0))

        ttk.Label(sec_keys, text="API Key OpenRouter / IA:").grid(row=1, column=0, sticky="w", pady=4)
        self.ent_ai_tok = PasswordEntry(sec_keys, show_char="•")
        self.ent_ai_tok.insert(0, get_secure_credential("openrouter_token", ""))
        self.ent_ai_tok.grid(row=1, column=1, sticky="ew", pady=4, padx=(8, 0))

        saved_model = get_secure_credential("openrouter_model", DEFAULT_AI_MODEL)
        ttk.Label(sec_keys, text="Modelo OpenRouter:").grid(row=2, column=0, sticky="w", pady=4)
        self.combo_ai_model = ttk.Combobox(
            sec_keys,
            values=[
                "nvidia/nemotron-3-ultra-550b-a55b:free",
                "meta-llama/llama-3.3-70b-instruct:free",
                "deepseek/deepseek-r1:free",
                "google/gemini-2.0-flash-lite-preview-02-05:free"
            ]
        )
        self.combo_ai_model.set(saved_model)
        self.combo_ai_model.grid(row=2, column=1, sticky="ew", pady=4, padx=(8, 0))

        sec_pos = ttk.LabelFrame(tab_api, text=" Posição das Assinaturas no PDF ", padding=12)
        sec_pos.pack(fill="x", pady=(0, 10))
        sec_pos.columnconfigure(1, weight=1)

        saved_preset = get_secure_credential("autentique_pos_preset", "Sobre a Linha Verde (Y: 68%)")
        ttk.Label(sec_pos, text="Preset de Posição:").grid(row=0, column=0, sticky="w", pady=4)
        self.combo_preset = ttk.Combobox(
            sec_pos,
            values=["Sobre a Linha Verde (Y: 68%)", "Rodapé (Y: 85%)", "Personalizado"],
            state="readonly"
        )
        self.combo_preset.set(saved_preset)
        self.combo_preset.grid(row=0, column=1, sticky="ew", pady=4, padx=(8, 0))

        self.lbl_api_msg = ttk.Label(tab_api, text="", font=get_font(9, bold=True))
        self.lbl_api_msg.pack(anchor="w", pady=(0, 8))

        btn_save_api = ttk.Button(tab_api, text="💾 Salvar Configurações de API", style="Primary.TButton", command=self._salvar_chaves_api)
        btn_save_api.pack(anchor="e")

    def _salvar_dados_colab(self):
        try:
            set_secure_credential("colaborador_nome", self.ent_colab_nome.get().strip())
            set_secure_credential("colaborador_cargo", self.ent_colab_cargo.get().strip())
            set_secure_credential("colaborador_email", self.ent_colab_email.get().strip())
            set_secure_credential("gestor_nome", self.ent_gestor_nome.get().strip())
            set_secure_credential("gestor_email", self.ent_gestor_email.get().strip())
            set_secure_credential("rh_nome", self.ent_rh_nome.get().strip())
            set_secure_credential("rh_email", self.ent_rh_email.get().strip())
            self.lbl_colab_msg.config(text="✅ Dados salvos com sucesso!", foreground="#16a34a")
        except Exception as e:
            self.lbl_colab_msg.config(text=f"❌ Erro ao salvar: {e}", foreground="#dc2626")

    def _salvar_chaves_api(self):
        try:
            tok_aut = self.ent_autentique_tok.get().strip()
            if tok_aut:
                set_secure_credential("autentique_token", tok_aut)

            tok_ai = self.ent_ai_tok.get().strip()
            if tok_ai:
                set_secure_credential("openrouter_token", tok_ai)

            mod_ai = self.combo_ai_model.get().strip()
            if mod_ai:
                set_secure_credential("openrouter_model", mod_ai)

            set_secure_credential("autentique_pos_preset", self.combo_preset.get())
            self.lbl_api_msg.config(text="✅ Chaves salvas com sucesso!", foreground="#16a34a")
        except Exception as e:
            self.lbl_api_msg.config(text=f"❌ Erro ao salvar: {e}", foreground="#dc2626")
