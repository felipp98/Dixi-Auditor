"""
Tela Principal (Dashboard) do Dixi Auditor com navegação por abas, cards e controle de botões.
"""
import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
from typing import Callable, Optional, List
from PIL import Image, ImageTk

from src.core.models import Usuario, MarcacaoDia, ResumoAuditoria
from src.core.state import AppState
from src.core.ponto_engine import PontoEngine
from src.ui.theme import get_font
from src.ui.components.date_selector import DateSelector
from src.ui.components.metrics_card import MetricCard
from src.ui.components.ponto_table import PontoTable
from src.ui.components.ai_chat_widget import AIChatModal
from src.ui.views.justificativa_modal import JustificativaView
from src.ui.views.historico_view import HistoricoView
from src.ui.views.settings_modal import SettingsModal
from src.services.excel_service import ExcelService
from src.services.ai_service import AIService
from src.utils.paths import get_logo_path
from src.utils.formatters import format_time_seconds, normalize_date_to_iso
from src.utils.threading_utils import run_async_task
from src.config.constants import (
    COLOR_BG,
    COLOR_SURFACE,
    COLOR_BORDER,
    COLOR_PRIMARY,
    COLOR_PRIMARY_DARK,
    COLOR_PRIMARY_SOFT,
    COLOR_PRIMARY_HOVER,
    COLOR_TEXT,
    COLOR_TEXT_MUTED,
    COLOR_DANGER,
    COLOR_SUCCESS
)

class MainView(tk.Frame):
    """Visualização principal contendo o painel de espelho de ponto, justificativas e histórico."""

    def __init__(
        self,
        parent,
        app_state: AppState,
        on_fetch_ponto: Callable[[str, str], None],
        on_logout: Callable[[], None]
    ):
        super().__init__(parent, bg=COLOR_BG)
        self.app_state = app_state
        self.on_fetch_ponto = on_fetch_ponto
        self.on_logout = on_logout
        self.logo_img = None
        self.pending_ai_adjustments = []
        self.ai_modal: Optional[AIChatModal] = None

        self._build_ui()
        self._setup_state_listeners()

    def _build_ui(self):
        # 1. Barra Superior / Header Global
        top_bar = tk.Frame(self, bg=COLOR_SURFACE, padx=20, pady=12, highlightbackground=COLOR_BORDER, highlightthickness=1)
        top_bar.pack(fill="x")

        # Esquerda: Logo & Identificação
        left_box = tk.Frame(top_bar, bg=COLOR_SURFACE)
        left_box.pack(side="left")

        logo_path = get_logo_path("logo_pagare.png")
        if os.path.exists(logo_path):
            try:
                pil_img = Image.open(logo_path).resize((110, 30), Image.Resampling.LANCZOS)
                self.logo_img = ImageTk.PhotoImage(pil_img)
                tk.Label(left_box, image=self.logo_img, bg=COLOR_SURFACE).pack(side="left", padx=(0, 12))
            except Exception:
                pass

        title_box = tk.Frame(left_box, bg=COLOR_SURFACE)
        title_box.pack(side="left")
        tk.Label(title_box, text="Dixi Auditor", bg=COLOR_SURFACE, fg=COLOR_PRIMARY_DARK, font=get_font(14, bold=True)).pack(anchor="w")
        tk.Label(title_box, text="Visualize, recalcule e exporte o espelho de ponto", bg=COLOR_SURFACE, fg=COLOR_TEXT_MUTED, font=get_font(9)).pack(anchor="w")

        # Direita: Usuário, Configurações e Logout
        right_box = tk.Frame(top_bar, bg=COLOR_SURFACE)
        right_box.pack(side="right")

        user_box = tk.Frame(right_box, bg=COLOR_PRIMARY_SOFT, padx=12, pady=6)
        user_box.pack(side="left", padx=(0, 10))

        nome_user = self.app_state.usuario.nome_completo if self.app_state.usuario else "Colaborador"
        primeiro_nome = nome_user.split()[0] if nome_user else "Colaborador"
        cargo_user = self.app_state.usuario.cargo if self.app_state.usuario else ""

        self.lbl_user_name = tk.Label(
            user_box,
            text=f"Olá, {primeiro_nome} 👋",
            bg=COLOR_PRIMARY_SOFT,
            fg=COLOR_TEXT,
            font=get_font(9, bold=True)
        )
        self.lbl_user_name.pack(anchor="e")

        if cargo_user:
            self.lbl_user_cargo = tk.Label(
                user_box,
                text=cargo_user,
                bg=COLOR_PRIMARY_SOFT,
                fg=COLOR_PRIMARY_DARK,
                font=get_font(8)
            )
            self.lbl_user_cargo.pack(anchor="e")

        btn_settings = ttk.Button(right_box, text="⚙️ Configurações", command=self._open_settings)
        btn_settings.pack(side="left", padx=(0, 6))

        btn_logout = ttk.Button(right_box, text="🚪 Sair", command=self.on_logout)
        btn_logout.pack(side="left")

        # 2. Navegação em Abas (Tabs Cápsula)
        nav_frame = tk.Frame(self, bg=COLOR_BG, padx=20, pady=12)
        nav_frame.pack(fill="x")

        self.nav_tabs = {}
        tabs_info = [
            ("ponto", "📊 Espelho de Ponto"),
            ("justificativa", "📝 Justificativas RH"),
            ("historico", "📜 Histórico Autentique")
        ]

        for key, text in tabs_info:
            btn = tk.Button(
                nav_frame,
                text=text,
                bg=COLOR_PRIMARY_DARK if key == "ponto" else COLOR_PRIMARY_SOFT,
                fg="#ffffff" if key == "ponto" else COLOR_TEXT,
                activebackground=COLOR_PRIMARY,
                activeforeground="#ffffff",
                font=get_font(9, bold=(key == "ponto")),
                bd=0,
                relief="flat",
                cursor="hand2",
                padx=16,
                pady=6,
                command=lambda k=key: self.select_tab(k)
            )
            btn.pack(side="left", padx=(0, 6))
            self.nav_tabs[key] = btn

        # 3. Container de Conteúdo das Abas
        self.content_shell = tk.Frame(self, bg=COLOR_BG)
        self.content_shell.pack(fill="both", expand=True, padx=20, pady=(0, 16))

        # Aba 1: Espelho de Ponto
        self.frame_ponto = tk.Frame(self.content_shell, bg=COLOR_BG)
        self.frame_ponto.pack(fill="both", expand=True)
        self._build_ponto_tab_ui()

        # Aba 2: Justificativas RH
        self.view_justificativa = JustificativaView(self.content_shell, self.app_state)

        # Aba 3: Histórico Autentique
        self.view_historico = HistoricoView(self.content_shell)

    def _build_ponto_tab_ui(self):
        # Cards de Resumo e Filtro de Período
        metrics_row = tk.Frame(self.frame_ponto, bg=COLOR_BG)
        metrics_row.pack(fill="x", pady=(0, 12))

        # Card 1: Saldo Acumulado
        self.card_saldo = MetricCard(metrics_row, title="Saldo Acumulado", initial_value="+00:00", icon="⚖️")
        self.card_saldo.pack(side="left", fill="both", expand=True, padx=(0, 6))

        # Card 2: Pendências de Batidas
        self.card_pend = MetricCard(metrics_row, title="Pendências de Batidas", initial_value="0 pendências", value_color=COLOR_DANGER, icon="⚠️")
        self.card_pend.pack(side="left", fill="both", expand=True, padx=(0, 6))

        # Card 3: Período e Ignorar Hoje
        card_period = tk.Frame(metrics_row, bg=COLOR_SURFACE, padx=14, pady=10, highlightbackground=COLOR_BORDER, highlightthickness=1)
        card_period.pack(side="left", fill="both", expand=True)

        tk.Label(card_period, text="📅 Período de Análise", bg=COLOR_SURFACE, fg=COLOR_TEXT_MUTED, font=get_font(9, bold=True)).pack(anchor="w", pady=(0, 4))

        period_row = tk.Frame(card_period, bg=COLOR_SURFACE)
        period_row.pack(anchor="w")

        now = datetime.now()
        cur_year = str(now.year)
        cur_month = f"{now.month:02d}"
        cur_day = f"{now.day:02d}"

        tk.Label(period_row, text="De:", bg=COLOR_SURFACE, fg=COLOR_TEXT_MUTED, font=get_font(8)).pack(side="left", padx=(0, 2))
        self.cal_inicio = DateSelector(period_row, default_day="01", default_month=cur_month, default_year=cur_year)
        self.cal_inicio.pack(side="left", padx=(0, 8))

        tk.Label(period_row, text="Até:", bg=COLOR_SURFACE, fg=COLOR_TEXT_MUTED, font=get_font(8)).pack(side="left", padx=(0, 2))
        self.cal_fim = DateSelector(period_row, default_day=cur_day, default_month=cur_month, default_year=cur_year)
        self.cal_fim.pack(side="left", padx=(0, 8))

        self.var_ignorar_hoje = tk.BooleanVar(value=True)
        chk_ign = ttk.Checkbutton(
            period_row,
            text="Ignorar dia atual",
            variable=self.var_ignorar_hoje,
            command=self._on_toggle_ignore_today
        )
        chk_ign.pack(side="left")

        # Tabela Principal e Barra de Ações
        table_container = tk.Frame(self.frame_ponto, bg=COLOR_SURFACE, padx=16, pady=14, highlightbackground=COLOR_BORDER, highlightthickness=1)
        table_container.pack(fill="both", expand=True)

        tbl_hdr = tk.Frame(table_container, bg=COLOR_SURFACE)
        tbl_hdr.pack(fill="x", pady=(0, 10))

        lbl_tbl_title = tk.Frame(tbl_hdr, bg=COLOR_SURFACE)
        lbl_tbl_title.pack(side="left")
        tk.Label(lbl_tbl_title, text="Espelho de Ponto", bg=COLOR_SURFACE, fg=COLOR_TEXT, font=get_font(12, bold=True)).pack(anchor="w")
        tk.Label(lbl_tbl_title, text="Duplo clique em uma linha para editar horários. Ajustes ativam o botão de recálculo.", bg=COLOR_SURFACE, fg=COLOR_TEXT_MUTED, font=get_font(9)).pack(anchor="w")

        # Ações da Tabela
        tbl_actions = tk.Frame(tbl_hdr, bg=COLOR_SURFACE)
        tbl_actions.pack(side="right")

        self.btn_buscar = ttk.Button(tbl_actions, text="🔍 Visualizar Ponto", command=self._trigger_fetch_ponto)
        self.btn_buscar.pack(side="left", padx=(0, 6))

        # BOTÃO RECALCULAR PONTO: Inicialmente DESATIVADO conforme solicitação
        self.btn_recalc = ttk.Button(
            tbl_actions,
            text="🔄 Recalcular Ponto",
            state="disabled",
            command=self._recalcular_ponto
        )
        self.btn_recalc.pack(side="left", padx=(0, 6))

        # ÚNICO BOTÃO DO ASSISTENTE IA: Ao lado do Recalcular Ponto
        self.btn_open_ai = ttk.Button(
            tbl_actions,
            text="🤖 Assistente IA",
            command=self.open_ai_modal
        )
        self.btn_open_ai.pack(side="left", padx=(0, 6))

        self.btn_export = ttk.Button(tbl_actions, text="📊 Exportar Excel", state="disabled", command=self._export_excel)
        self.btn_export.pack(side="left")

        # Tabela
        self.table = PontoTable(
            table_container,
            on_edit_callback=self._on_table_edit,
            on_selection_change=self._on_table_selection_change
        )
        self.table.pack(fill="both", expand=True)

    def open_ai_modal(self):
        """Abre ou traz para frente a janela do Assistente IA."""
        if self.ai_modal is not None and self.ai_modal.winfo_exists():
            self.ai_modal.deiconify()
            self.ai_modal.lift()
            self.ai_modal.focus_set()
        else:
            self.ai_modal = AIChatModal(
                self,
                on_send_message=self._on_ai_send_message,
                on_quick_audit=self._on_ai_quick_audit,
                on_apply_adjustments=self._on_ai_apply_adjustments
            )

    def _setup_state_listeners(self):
        self.app_state.add_listener(self._on_state_event)

    def _on_state_event(self, event_name: str, payload: any):
        if event_name == "user_changed":
            if self.app_state.usuario:
                nome = self.app_state.usuario.nome_completo or self.app_state.usuario.username
                p_nome = nome.split()[0] if nome else "Colaborador"
                self.lbl_user_name.config(text=f"Olá, {p_nome} 👋")
                if hasattr(self, "lbl_user_cargo"):
                    self.lbl_user_cargo.config(text=self.app_state.usuario.cargo or "")
        elif event_name == "marcacoes_loaded":
            self.table.populate_data(self.app_state.marcacoes, self.app_state.ignorar_hoje)
            self.btn_export.config(state="normal")
            # Recalcular ponto começa desativado após busca limpa
            self.btn_recalc.config(state="disabled")
        elif event_name == "edits_dirty":
            state_val = "normal" if payload else "disabled"
            self.btn_recalc.config(state=state_val)
        elif event_name == "resumo_updated":
            resumo: ResumoAuditoria = payload
            saldo_str = format_time_seconds(resumo.saldo_acumulado_segundos, show_sign=True)
            cor_saldo = COLOR_SUCCESS if resumo.saldo_acumulado_segundos >= 0 else COLOR_DANGER
            self.card_saldo.set_value(saldo_str, cor_saldo)
            self.card_pend.set_value(f"{resumo.dias_pendencia} pendência(s)")

    def _on_table_edit(self):
        """Chamado quando uma batida é alterada na tabela: Habilita 'Recalcular Ponto'."""
        self.app_state.marcar_edicao_feita()

    def _on_table_selection_change(self, count: int):
        pass

    def _on_toggle_ignore_today(self):
        self.app_state.set_ignorar_hoje(self.var_ignorar_hoje.get())

    def _trigger_fetch_ponto(self):
        start_iso = self.cal_inicio.get_date_str_iso()
        end_iso = self.cal_fim.get_date_str_iso()
        self.btn_buscar.config(state="disabled", text="⏳ Buscando...")
        self.on_fetch_ponto(start_iso, end_iso)

    def finish_fetch_ponto(self):
        self.btn_buscar.config(state="normal", text="🔍 Visualizar Ponto")

    def _recalcular_ponto(self):
        """Lê os horários editados da tabela e recalcula todos os saldos e pendências."""
        novas_marcacoes = self.table.get_all_rows_as_marcacoes()
        self.app_state.set_marcacoes(novas_marcacoes)
        self.app_state.marcar_recalculo_concluido()
        messagebox.showinfo("Recalculado", "Ponto recalculado com sucesso!")

    def _export_excel(self):
        if not self.app_state.marcacoes:
            messagebox.showwarning("Aviso", "Não há dados para exportar.")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Planilhas Excel", "*.xlsx")],
            initialfile=f"Espelho_Ponto_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        )
        if not file_path:
            return

        try:
            ExcelService.generate(self.app_state.marcacoes, file_path, self.app_state.ignorar_hoje)
            messagebox.showinfo("Sucesso", f"Planilha exportada com sucesso em:\n{file_path}")
            try:
                os.startfile(file_path)
            except Exception:
                pass
        except Exception as e:
            messagebox.showerror("Erro na Exportação", f"Falha ao gerar Excel:\n{e}")

    def select_tab(self, key: str):
        """Alterna a aba ativa da interface."""
        for t_key, btn in self.nav_tabs.items():
            if t_key == key:
                btn.config(bg=COLOR_PRIMARY_DARK, fg="#ffffff", font=get_font(9, bold=True))
            else:
                btn.config(bg=COLOR_PRIMARY_SOFT, fg=COLOR_TEXT, font=get_font(9))

        self.frame_ponto.pack_forget()
        self.view_justificativa.pack_forget()
        self.view_historico.pack_forget()

        if key == "ponto":
            self.frame_ponto.pack(fill="both", expand=True)
        elif key == "justificativa":
            self.view_justificativa.pack(fill="both", expand=True)
            self.view_justificativa.sincronizar_dias()
        elif key == "historico":
            self.view_historico.pack(fill="both", expand=True)
            self.view_historico.carregar_historico()

    def _open_settings(self):
        SettingsModal(self)

    # --- Métodos do Assistente IA ---
    def _on_ai_quick_audit(self):
        if not self.app_state.marcacoes:
            if self.ai_modal:
                self.ai_modal.append_message("Assistente IA", "Por favor, busque primeiro os dados de ponto clicando em '🔍 Visualizar Ponto'.")
            return

        if self.ai_modal:
            self.ai_modal.set_status("⏳ Analisando com IA...")
            self.ai_modal.append_message("Assistente IA", "⏳ Executando auditoria do espelho de ponto com Nemotron 550B...")

        def worker():
            return AIService.analisar_ponto(self.app_state.marcacoes, ignore_today=self.app_state.ignorar_hoje)

        def on_success(res):
            content, parsed_ajustes, auto_enviar = res
            self.pending_ai_adjustments = parsed_ajustes
            if self.ai_modal:
                self.ai_modal.set_status("")
                self.ai_modal.append_message("Assistente IA", content)

                if parsed_ajustes:
                    self.ai_modal.enable_apply_button(len(parsed_ajustes))
                else:
                    self.ai_modal.disable_apply_button()

            if auto_enviar:
                self.select_tab("justificativa")

        def on_error(err):
            if self.ai_modal:
                self.ai_modal.set_status("❌ Erro na análise")
                self.ai_modal.append_message("Assistente IA", f"Erro na análise: {err}")

        run_async_task(worker, on_success=on_success, on_error=on_error, root_widget=self)

    def _on_ai_send_message(self, user_msg: str):
        if not self.app_state.marcacoes:
            if self.ai_modal:
                self.ai_modal.append_message("Assistente IA", "Busque primeiro o período no Espelho de Ponto para que eu possa analisar.")
            return

        if self.ai_modal:
            self.ai_modal.set_status("⏳ Processando instrução...")

        def worker():
            return AIService.analisar_ponto(
                self.app_state.marcacoes,
                instrucoes_usuario=user_msg,
                ignore_today=self.app_state.ignorar_hoje
            )

        def on_success(res):
            content, parsed_ajustes, auto_enviar = res
            self.pending_ai_adjustments = parsed_ajustes
            if self.ai_modal:
                self.ai_modal.set_status("")
                self.ai_modal.append_message("Assistente IA", content)

                if parsed_ajustes:
                    self.ai_modal.enable_apply_button(len(parsed_ajustes))
                else:
                    self.ai_modal.disable_apply_button()

            if auto_enviar:
                self.select_tab("justificativa")

        def on_error(err):
            if self.ai_modal:
                self.ai_modal.set_status("❌ Erro")
                self.ai_modal.append_message("Assistente IA", f"Erro ao processar mensagem: {err}")

        run_async_task(worker, on_success=on_success, on_error=on_error, root_widget=self)

    def _on_ai_apply_adjustments(self):
        """Aplica os ajustes sugeridos pela IA diretamente na tabela de ponto."""
        if not self.pending_ai_adjustments:
            messagebox.showinfo("Aviso", "Nenhuma sugestão de ajuste pendente para aplicar.")
            return

        count_applied = 0
        marcacoes = self.app_state.marcacoes

        for aj in self.pending_ai_adjustments:
            dt_target = str(aj.get("data", "")).strip()
            if not dt_target:
                continue

            for m in marcacoes:
                if m.data_formatada == dt_target or m.data_formatada.startswith(dt_target):
                    if not m.horarios_originais:
                        m.horarios_originais = list(m.horarios)
                    m.editado_manualmente = True

                    if aj.get("abono"):
                        m.is_pendencia = False
                        m.obs = aj.get("obs", "Abonado via IA")
                        count_applied += 1
                    elif aj.get("horarios"):
                        novos_horarios = sorted(aj["horarios"])
                        obs = aj.get("obs", "Ajustado via IA")
                        m_novo = PontoEngine.process_horarios(novos_horarios, m.data_id, m.data_formatada, obs=obs)
                        m.segundos_trabalhados = m_novo.segundos_trabalhados
                        m.saldo_segundos = m_novo.saldo_segundos
                        m.is_pendencia = m_novo.is_pendencia
                        m.horarios = m_novo.horarios
                        m.obs = obs
                        count_applied += 1

        if count_applied > 0:
            self.table.populate_data(self.app_state.marcacoes, self.app_state.ignorar_hoje)
            self.app_state.marcar_edicao_feita()
            if self.ai_modal:
                self.ai_modal.disable_apply_button()
                self.ai_modal.append_message("Assistente IA", f"✅ {count_applied} ajuste(s) aplicado(s) na tabela! O botão '🔄 Recalcular Ponto' foi habilitado para atualizar o saldo.")
            messagebox.showinfo("Ajustes Aplicados", f"{count_applied} ajuste(s) da IA foram aplicados com sucesso na tabela!")
        else:
            if self.ai_modal:
                self.ai_modal.append_message("Assistente IA", "Nenhum dia correspondente encontrado para aplicar os ajustes.")

    def set_period_dates(self, data_inicio: str, data_fim: str, ignorar_hoje: bool = True):
        """Atualiza visualmente os seletores de data e o checkbox de ignorar dia atual."""
        self.cal_inicio.set_date(data_inicio)
        self.cal_fim.set_date(data_fim)
        self.var_ignorar_hoje.set(ignorar_hoje)
