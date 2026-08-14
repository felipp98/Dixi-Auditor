"""
Tela e Gerenciador de Justificativas de Ponto para envio ao RH e Autentique com Signatários e Testemunhas.
"""
import os
import logging
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from typing import List, Dict, Any, Optional

from src.core.models import MarcacaoDia, Signatario
from src.core.state import AppState
from src.ui.components.signer_list import SignerListManager
from src.services.justificativa_service import gerar_pdf_justificativa
from src.services.autentique_service import enviar_justificativa_autentique
from src.utils.security import get_secure_credential
from src.utils.colaboradores import buscar_cargo_colaborador
from src.utils.formatters import get_dia_semana_nome, normalize_date_to_iso
from src.utils.threading_utils import run_async_task
from src.config.constants import (
    COLOR_SURFACE,
    COLOR_BORDER,
    COLOR_PRIMARY,
    COLOR_PRIMARY_DARK,
    COLOR_PRIMARY_SOFT,
    COLOR_TEXT,
    COLOR_TEXT_MUTED
)
from src.ui.theme import get_font

logger = logging.getLogger(__name__)

class JustificativaView(tk.Frame):
    """Visualização e orquestrador de Justificativas de Ponto e assinaturas digitais."""

    def __init__(self, parent, app_state: AppState):
        super().__init__(parent, bg=COLOR_SURFACE)
        self.app_state = app_state
        self._build_ui()

    def _build_ui(self):
        # 1. Cabeçalho Informativo
        hdr = tk.Frame(self, bg=COLOR_SURFACE, padx=18, pady=12, highlightbackground=COLOR_BORDER, highlightthickness=1)
        hdr.pack(fill="x", pady=(0, 10))

        tk.Label(
            hdr,
            text="📝 Central de Justificativas de Ponto para RH",
            bg=COLOR_SURFACE,
            fg=COLOR_PRIMARY_DARK,
            font=get_font(12, bold=True)
        ).pack(anchor="w")

        tk.Label(
            hdr,
            text="Selecione os dias, configure as batidas propostas, adicione signatários/testemunhas e gere o PDF ou envie ao Autentique.",
            bg=COLOR_SURFACE,
            fg=COLOR_TEXT_MUTED,
            font=get_font(9)
        ).pack(anchor="w", pady=(2, 0))

        # 2. Barra de Filtros e Controles de Seleção
        ctrl_card = tk.Frame(self, bg=COLOR_SURFACE, padx=14, pady=8, highlightbackground=COLOR_BORDER, highlightthickness=1)
        ctrl_card.pack(fill="x", pady=(0, 10))

        ttk.Button(ctrl_card, text="☑️ Marcar Todos", command=lambda: self._toggle_all(True)).pack(side="left", padx=(0, 6))
        ttk.Button(ctrl_card, text="☐ Desmarcar Todos", command=lambda: self._toggle_all(False)).pack(side="left", padx=(0, 15))

        self.lbl_count = ttk.Label(ctrl_card, text="0 dia(s) selecionado(s)", font=get_font(9, bold=True))
        self.lbl_count.pack(side="left")

        ttk.Button(ctrl_card, text="🔄 Sincronizar com Espelho de Ponto", command=self.sincronizar_dias).pack(side="right")

        # 3. Tabela de Dias a Justificar
        table_card = tk.Frame(self, bg=COLOR_SURFACE, padx=12, pady=10, highlightbackground=COLOR_BORDER, highlightthickness=1)
        table_card.pack(fill="both", expand=True, pady=(0, 10))

        cols = ("sel", "data", "dia_sem", "batidas_orig", "batidas_prop", "motivo")
        self.tree = ttk.Treeview(table_card, columns=cols, show="headings", height=6, selectmode="browse")
        self.tree.heading("sel", text="Sel")
        self.tree.heading("data", text="Data")
        self.tree.heading("dia_sem", text="Dia da Semana")
        self.tree.heading("batidas_orig", text="Batidas Registradas")
        self.tree.heading("batidas_prop", text="Ajuste Proposto (Horários)")
        self.tree.heading("motivo", text="Motivo / Justificativa")

        self.tree.column("sel", width=50, anchor="center")
        self.tree.column("data", width=95, anchor="center")
        self.tree.column("dia_sem", width=130, anchor="w")
        self.tree.column("batidas_orig", width=170, anchor="w")
        self.tree.column("batidas_prop", width=200, anchor="w")
        self.tree.column("motivo", width=250, anchor="w")

        sb = ttk.Scrollbar(table_card, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)

        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self.tree.bind("<Button-1>", self._on_click_row)
        self.tree.bind("<Double-1>", self._on_double_click_row)

        # 4. Gerenciador de Signatários & Testemunhas
        self.signer_manager = SignerListManager(self)
        self.signer_manager.pack(fill="x", pady=(0, 10))

        # 5. Justificativa Geral e Botões de Envio
        bot_card = tk.Frame(self, bg=COLOR_SURFACE, padx=14, pady=10, highlightbackground=COLOR_BORDER, highlightthickness=1)
        bot_card.pack(fill="x")

        tk.Label(
            bot_card,
            text="Observação Geral do Documento (Opcional):",
            bg=COLOR_SURFACE,
            fg=COLOR_TEXT,
            font=get_font(9, bold=True)
        ).pack(anchor="w", pady=(0, 3))

        self.txt_obs = tk.Text(bot_card, height=2, font=get_font(9))
        self.txt_obs.pack(fill="x", pady=(0, 8))

        self.lbl_status = ttk.Label(bot_card, text="", font=get_font(9, bold=True))
        self.lbl_status.pack(anchor="w", pady=(0, 6))

        btn_bar = ttk.Frame(bot_card)
        btn_bar.pack(fill="x")

        self.btn_preview = ttk.Button(
            btn_bar,
            text="👁️ Gerar e Visualizar PDF por Semana",
            command=self._gerar_pdfs_semanais
        )
        self.btn_preview.pack(side="left", padx=(0, 10))

        self.btn_send_autentique = ttk.Button(
            btn_bar,
            text="🚀 Enviar via Autentique (com Signatários e Testemunhas)",
            style="Primary.TButton",
            command=self._enviar_autentique_semanal
        )
        self.btn_send_autentique.pack(side="left")

    def sincronizar_dias(self):
        """Sincroniza os dias a partir do AppState / Tabela Principal."""
        self.tree.delete(*self.tree.get_children())
        marcacoes = sorted(self.app_state.marcacoes, key=lambda x: normalize_date_to_iso(x.data_id or x.data_formatada))

        has_checked_selection = any(m.selecionado for m in marcacoes)

        for idx, m in enumerate(marcacoes):
            punches = m.horarios
            batidas_orig = " ".join(punches) if punches else "Sem batidas"

            try:
                dt = datetime.strptime(m.data_formatada, "%d/%m/%Y")
                dia_sem = get_dia_semana_nome(dt)
            except Exception:
                dia_sem = "-"

            if has_checked_selection:
                is_sel = "[☑]" if m.selecionado else "[☐]"
            else:
                # Pré-marca dias com pendência ou saldo negativo
                is_sel = "[☑]" if (m.is_pendencia or m.saldo_segundos < 0 or m.obs) else "[☐]"

            prop_sugestao = batidas_orig if punches else "08:00 12:00 13:00 17:00"
            motivo_def = m.obs or "Ajuste de batida de ponto"

            self.tree.insert(
                "",
                "end",
                iid=f"just_{idx}",
                values=(is_sel, m.data_formatada, dia_sem, batidas_orig, prop_sugestao, motivo_def)
            )

        self._atualizar_contador()

    def _toggle_all(self, mark: bool):
        val = "[☑]" if mark else "[☐]"
        for item_id in self.tree.get_children():
            vals = list(self.tree.item(item_id, "values"))
            vals[0] = val
            self.tree.item(item_id, values=vals)
        self._atualizar_contador()

    def _atualizar_contador(self):
        cnt = sum(1 for item_id in self.tree.get_children() if self.tree.item(item_id, "values")[0] == "[☑]")
        self.lbl_count.config(text=f"{cnt} dia(s) selecionado(s)")

    def _on_click_row(self, event):
        item_id = self.tree.identify_row(event.y)
        column = self.tree.identify_column(event.x)
        if not item_id:
            return
        if column == "#1":
            vals = list(self.tree.item(item_id, "values"))
            vals[0] = "[☐]" if vals[0] == "[☑]" else "[☑]"
            self.tree.item(item_id, values=vals)
            self._atualizar_contador()

    def _on_double_click_row(self, event):
        item_id = self.tree.identify_row(event.y)
        if not item_id:
            return
        vals = list(self.tree.item(item_id, "values"))

        top = tk.Toplevel(self)
        top.title(f"Ajuste de Justificativa - {vals[1]}")
        top.geometry("480x280")
        top.transient(self)
        top.grab_set()

        ttk.Label(top, text=f"Data: {vals[1]} ({vals[2]})", font=get_font(10, bold=True)).pack(anchor="w", padx=16, pady=(14, 8))

        ttk.Label(top, text="Batidas Propostas (ex: 08:00 12:00 13:00 17:00):").pack(anchor="w", padx=16)
        ent_prop = ttk.Entry(top, width=44)
        ent_prop.insert(0, vals[4])
        ent_prop.pack(anchor="w", padx=16, pady=(3, 10))

        ttk.Label(top, text="Motivo / Justificativa detalhada:").pack(anchor="w", padx=16)
        ent_mot = ttk.Entry(top, width=44)
        ent_mot.insert(0, vals[5])
        ent_mot.pack(anchor="w", padx=16, pady=(3, 14))

        def salvar():
            vals[0] = "[☑]"
            vals[4] = ent_prop.get().strip()
            vals[5] = ent_mot.get().strip()
            self.tree.item(item_id, values=vals)
            self._atualizar_contador()
            top.destroy()

        btn_box = ttk.Frame(top)
        btn_box.pack(fill="x", padx=16, pady=4)
        ttk.Button(btn_box, text="Cancelar", command=top.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(btn_box, text="💾 Salvar Alterações", style="Primary.TButton", command=salvar).pack(side="right")

    def _obter_dias_agrupados_por_semana(self) -> Dict[tuple, List[Dict]]:
        weeks_map = {}
        for item_id in self.tree.get_children():
            vals = self.tree.item(item_id, "values")
            if vals and vals[0] == "[☑]":
                data_str = vals[1]
                dia_sem = vals[2]
                batidas_prop = vals[4]
                motivo = vals[5]

                try:
                    dt = datetime.strptime(data_str, "%d/%m/%Y")
                    iso_year, iso_week, _ = dt.isocalendar()
                    key = (iso_year, iso_week)
                    if key not in weeks_map:
                        weeks_map[key] = []

                    pts = [p for p in batidas_prop.split() if ":" in p]
                    e1 = pts[0] if len(pts) > 0 else ""
                    s1 = pts[1] if len(pts) > 1 else ""
                    e2 = pts[2] if len(pts) > 2 else ""
                    s2 = pts[3] if len(pts) > 3 else ""

                    weeks_map[key].append({
                        "data": data_str,
                        "dia_semana": dia_sem,
                        "e1": e1, "s1": s1, "e2": e2, "s2": s2,
                        "motivo": motivo
                    })
                except Exception as e:
                    logger.error(f"Erro ao agrupar dia {data_str}: {e}")

        return weeks_map

    def _gerar_pdfs_semanais(self):
        weeks_map = self._obter_dias_agrupados_por_semana()
        if not weeks_map:
            messagebox.showwarning("Aviso", "Selecione ao menos 1 dia para gerar a justificativa.")
            return

        colab_nome = get_secure_credential("colaborador_nome", "Colaborador")
        colab_cargo = get_secure_credential("colaborador_cargo", "")
        if not colab_cargo or colab_cargo.lower() == "colaborador":
            colab_cargo = buscar_cargo_colaborador(colab_nome) or colab_cargo or "CLT"
        gestor_nome = get_secure_credential("gestor_nome", "Gestor Imediato")
        rh_nome = get_secure_credential("rh_nome", "Recursos Humanos")
        obs_geral = self.txt_obs.get("1.0", "end").strip()

        output_dir = os.path.join(os.path.expanduser("~"), "Downloads")
        os.makedirs(output_dir, exist_ok=True)

        self.lbl_status.config(text="⏳ Gerando PDF(s)...", foreground="#0284c7")

        def worker():
            pdf_paths = []
            for (year, week), itens in weeks_map.items():
                pdf_name = f"Justificativa_Ponto_Semana_{week}_{year}.pdf"
                output_pdf = os.path.join(output_dir, pdf_name)
                gerar_pdf_justificativa(
                    colaborador_nome=colab_nome,
                    colaborador_funcao=colab_cargo,
                    mes_competencia_str=itens[0]["data"],
                    data_solicitacao=datetime.now().strftime("%d/%m/%Y"),
                    justificativa_geral=obs_geral,
                    gestor_nome=gestor_nome,
                    rh_nome=rh_nome,
                    itens_ponto=itens,
                    output_pdf_path=output_pdf
                )
                pdf_paths.append(output_pdf)
            return pdf_paths

        def on_success(pdf_paths):
            self.lbl_status.config(text=f"✅ {len(pdf_paths)} PDF(s) gerado(s) com sucesso em Downloads!", foreground="#16a34a")
            messagebox.showinfo("Sucesso", f"Foi(ram) gerado(s) {len(pdf_paths)} PDF(s) por semana em:\n{output_dir}")
            for p in pdf_paths:
                try:
                    os.startfile(p)
                except Exception:
                    pass

        def on_error(err):
            self.lbl_status.config(text=f"❌ Erro ao gerar PDF: {err}", foreground="#dc2626")
            messagebox.showerror("Erro", f"Falha na geração do PDF:\n{err}")

        run_async_task(worker, on_success=on_success, on_error=on_error, root_widget=self)

    def _enviar_autentique_semanal(self):
        weeks_map = self._obter_dias_agrupados_por_semana()
        if not weeks_map:
            messagebox.showwarning("Aviso", "Selecione ao menos 1 dia para enviar a justificativa.")
            return

        token = get_secure_credential("autentique_token")
        if not token:
            messagebox.showwarning("Token Ausente", "Token do Autentique não configurado. Por favor, cadastre o Token em '⚙️ Configurações'.")
            return

        signatarios = self.signer_manager.get_signatarios()
        if not signatarios:
            messagebox.showwarning("Signatários Ausentes", "Adicione ao menos um signatário na seção '👥 Signatários & Testemunhas'.")
            return

        colab_nome = get_secure_credential("colaborador_nome", "Colaborador")
        colab_cargo = get_secure_credential("colaborador_cargo", "")
        if not colab_cargo or colab_cargo.lower() == "colaborador":
            colab_cargo = buscar_cargo_colaborador(colab_nome) or colab_cargo or "CLT"
        gestor_nome = get_secure_credential("gestor_nome", "Gestor Imediato")
        rh_nome = get_secure_credential("rh_nome", "Recursos Humanos")
        obs_geral = self.txt_obs.get("1.0", "end").strip()

        self.btn_send_autentique.config(state="disabled")
        self.lbl_status.config(text="⏳ Gerando PDFs e enviando para o Autentique...", foreground="#0284c7")

        def worker():
            output_dir = os.path.join(os.path.expanduser("~"), "Downloads")
            os.makedirs(output_dir, exist_ok=True)
            resultados = []

            for (year, week), itens in weeks_map.items():
                pdf_name = f"Justificativa_Ponto_Semana_{week}_{year}.pdf"
                output_pdf = os.path.join(output_dir, pdf_name)
                gerar_pdf_justificativa(
                    colaborador_nome=colab_nome,
                    colaborador_funcao=colab_cargo,
                    mes_competencia_str=itens[0]["data"],
                    data_solicitacao=datetime.now().strftime("%d/%m/%Y"),
                    justificativa_geral=obs_geral,
                    gestor_nome=gestor_nome,
                    rh_nome=rh_nome,
                    itens_ponto=itens,
                    output_pdf_path=output_pdf
                )

                nome_doc = f"Justificativa de Ponto - {colab_nome} (Semana {week}/{year})"
                res = enviar_justificativa_autentique(token, output_pdf, nome_doc, signatarios)
                resultados.append((nome_doc, res))

            return resultados

        def on_success(resultados):
            self.btn_send_autentique.config(state="normal")
            self.lbl_status.config(text=f"✅ {len(resultados)} documento(s) enviado(s) com sucesso para o Autentique!", foreground="#16a34a")
            messagebox.showinfo("Sucesso", f"Justificativa(s) enviada(s) para assinatura de todos os signatários e testemunhas!")

        def on_error(err):
            self.btn_send_autentique.config(state="normal")
            self.lbl_status.config(text=f"❌ Erro no envio ao Autentique: {err}", foreground="#dc2626")
            messagebox.showerror("Erro Autentique", f"Erro no envio:\n{err}")

        run_async_task(worker, on_success=on_success, on_error=on_error, root_widget=self)
