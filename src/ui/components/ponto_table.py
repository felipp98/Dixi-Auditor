"""
Componente Tabela (Treeview) de Espelho de Ponto com suporte a seleção [☑], edição inline e tags de status.
"""
import re
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from typing import List, Dict, Optional, Callable

from src.core.models import MarcacaoDia
from src.core.ponto_engine import PontoEngine
from src.utils.formatters import format_time_seconds, normalize_date_to_iso
from src.config.constants import (
    COLOR_SURFACE,
    COLOR_BORDER,
    COLOR_SUCCESS_BG,
    COLOR_DANGER_BG,
    COLOR_WARNING_BG,
    COLOR_IN_PROGRESS_BG,
    COLOR_PRIMARY
)

class PontoTable(ttk.Frame):
    """Tabela rica para visualização e edição interativa do espelho de ponto."""

    def __init__(
        self,
        parent,
        on_edit_callback: Optional[Callable[[], None]] = None,
        on_selection_change: Optional[Callable[[int], None]] = None
    ):
        super().__init__(parent)
        self.on_edit_callback = on_edit_callback
        self.on_selection_change = on_selection_change
        self._data_map: Dict[str, MarcacaoDia] = {}

        self._build_tree()

    def _build_tree(self):
        columns = (
            "sel", "data", "e1", "s1", "e2", "s2", "e3", "s3",
            "trabalhado", "saldo", "obs"
        )

        self.tree = ttk.Treeview(
            self,
            columns=columns,
            show="headings",
            selectmode="browse",
            height=14
        )

        # Configuração de Cabeçalhos e Larguras
        headers = [
            ("sel", "Sel", 40, "center"),
            ("data", "Data", 90, "center"),
            ("e1", "Entrada 1", 75, "center"),
            ("s1", "Saída 1", 75, "center"),
            ("e2", "Entrada 2", 75, "center"),
            ("s2", "Saída 2", 75, "center"),
            ("e3", "Entrada 3", 75, "center"),
            ("s3", "Saída 3", 75, "center"),
            ("trabalhado", "Total Trab.", 85, "center"),
            ("saldo", "Saldo Dia", 85, "center"),
            ("obs", "Observação / Motivo", 260, "w")
        ]

        for col_id, text, width, anchor in headers:
            self.tree.heading(col_id, text=text, command=lambda c=col_id: self._on_header_click(c))
            self.tree.column(col_id, width=width, minwidth=width, anchor=anchor)

        # Scrollbars
        v_scroll = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        h_scroll = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Configuração de Cores / Tags
        self.tree.tag_configure("saldo_positivo", background=COLOR_SUCCESS_BG, foreground="#14532d")
        self.tree.tag_configure("saldo_negativo", background=COLOR_DANGER_BG, foreground="#7f1d1d")
        self.tree.tag_configure("pendencia", background=COLOR_WARNING_BG, foreground="#78350f")
        self.tree.tag_configure("em_andamento", background=COLOR_IN_PROGRESS_BG, foreground="#365314")
        self.tree.tag_configure("normal", background=COLOR_SURFACE, foreground="#0f172a")
        self.tree.tag_configure("editado", background="#fef9c3", foreground="#854d0e")

        # Eventos do Mouse
        self.tree.bind("<Button-1>", self._on_click)
        self.tree.bind("<Double-1>", self._on_double_click)

    def _on_header_click(self, col_id: str):
        """Ao clicar no cabeçalho 'Sel', marca ou desmarca todos."""
        if col_id == "sel":
            all_selected = all(self.tree.item(item, "values")[0] == "[☑]" for item in self.tree.get_children())
            new_val = "[☐]" if all_selected else "[☑]"
            for item in self.tree.get_children():
                vals = list(self.tree.item(item, "values"))
                vals[0] = new_val
                self.tree.item(item, values=vals)

            if self.on_selection_change:
                self.on_selection_change(self.count_selected())

    def _on_click(self, event):
        """Alterna a caixa de seleção [☑] / [☐] na coluna 'sel'."""
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return

        column = self.tree.identify_column(event.x)
        item_id = self.tree.identify_row(event.y)
        if not item_id:
            return

        if column == "#1":  # Coluna 'sel'
            vals = list(self.tree.item(item_id, "values"))
            vals[0] = "[☐]" if vals[0] == "[☑]" else "[☑]"
            self.tree.item(item_id, values=vals)

            iso_id = normalize_date_to_iso(vals[1])
            if iso_id in self._data_map:
                self._data_map[iso_id].selecionado = (vals[0] == "[☑]")

            if self.on_selection_change:
                self.on_selection_change(self.count_selected())

    def _on_double_click(self, event):
        """Abre a janela modal para edição inline dos horários e da observação."""
        item_id = self.tree.identify_row(event.y)
        if not item_id:
            return

        vals = self.tree.item(item_id, "values")
        if not vals:
            return

        data_str = vals[1]
        iso_id = normalize_date_to_iso(data_str)
        existing_m = self._data_map.get(iso_id)
        current_punches = [v for v in vals[2:8] if v and v != "--:--"]
        current_obs = vals[10]

        top = tk.Toplevel(self)
        top.title(f"Ajustar Ponto - {data_str}")
        top.geometry("440x260")
        top.minsize(400, 240)
        top.transient(self)
        top.grab_set()

        lbl_info = ttk.Label(top, text=f"Data: {data_str}\nDigite os horários válidos separados por espaço (ex: 08:00 12:00 13:00 17:00):")
        lbl_info.pack(anchor="w", padx=16, pady=(14, 8))

        ent_horarios = ttk.Entry(top, font=("Segoe UI", 10))
        ent_horarios.insert(0, " ".join(current_punches))
        ent_horarios.pack(anchor="w", padx=16, pady=(4, 10), fill="x")

        ttk.Label(top, text="Observação / Motivo do Ajuste:").pack(anchor="w", padx=16)
        ent_obs = ttk.Entry(top, font=("Segoe UI", 10))
        ent_obs.insert(0, current_obs if current_obs != "EM ANDAMENTO" and current_obs != "PENDÊNCIA DE BATIDA" else "")
        ent_obs.pack(anchor="w", padx=16, pady=(4, 14), fill="x")

        def salvar():
            raw_text = ent_horarios.get().strip()
            obs_text = ent_obs.get().strip()

            novos_horarios = []
            if raw_text:
                for token in raw_text.split():
                    if re.match(r"^\d{1,2}:\d{2}$", token):
                        partes = token.split(":")
                        novos_horarios.append(f"{int(partes[0]):02d}:{partes[1]}")
                    else:
                        messagebox.showerror("Horário Inválido", f"'{token}' não é um horário válido no formato HH:MM.", parent=top)
                        return

            novos_horarios = sorted(novos_horarios)
            m = PontoEngine.process_horarios(novos_horarios, iso_id, data_str, obs=obs_text)
            m.selecionado = (vals[0] == "[☑]")
            m.editado_manualmente = True

            if existing_m and existing_m.horarios_originais:
                m.horarios_originais = existing_m.horarios_originais
            elif existing_m:
                m.horarios_originais = existing_m.horarios

            self._data_map[iso_id] = m

            punches_pad = (m.horarios + ["--:--"] * 6)[:6]
            new_vals = [
                vals[0],
                data_str,
                punches_pad[0], punches_pad[1],
                punches_pad[2], punches_pad[3],
                punches_pad[4], punches_pad[5],
                format_time_seconds(m.segundos_trabalhados),
                format_time_seconds(m.saldo_segundos, show_sign=True),
                m.obs
            ]

            tag = "editado"
            if m.saldo_segundos > 0:
                tag = "saldo_positivo"
            elif m.saldo_segundos < 0:
                tag = "saldo_negativo"
            if m.is_pendencia:
                tag = "pendencia"

            self.tree.item(item_id, values=new_vals, tags=(tag,))
            top.destroy()

            # Notifica que houve edição (HABILITA BOTÃO RECALCULAR PONTO E PERSISTE)
            if self.on_edit_callback:
                self.on_edit_callback()

        btn_box = ttk.Frame(top)
        btn_box.pack(fill="x", padx=16, pady=6)
        ttk.Button(btn_box, text="Cancelar", command=top.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(btn_box, text="💾 Salvar Ajuste", style="Primary.TButton", command=salvar).pack(side="right")

    def populate_data(self, data: List[MarcacaoDia], ignore_today: bool = True):
        """Limpa e preenche a tabela com a lista de marcações calculadas."""
        self.tree.delete(*self.tree.get_children())
        self._data_map.clear()
        today_str = datetime.now().strftime("%d/%m/%Y")

        for idx, m in enumerate(data):
            iso_id = normalize_date_to_iso(m.data_id or m.data_formatada)
            self._data_map[iso_id] = m

            is_today = (m.data_formatada == today_str) and ignore_today
            punches = (m.horarios + ["--:--"] * 6)[:6]

            saldo_str = "00:00" if is_today else format_time_seconds(m.saldo_segundos, show_sign=True)
            obs_str = m.obs
            if not obs_str:
                if is_today:
                    obs_str = "EM ANDAMENTO"
                elif m.is_pendencia:
                    obs_str = "PENDÊNCIA DE BATIDA"

            tag = "normal"
            if m.editado_manualmente:
                tag = "editado"
            elif is_today:
                tag = "em_andamento"
            elif m.is_pendencia:
                tag = "pendencia"
            elif m.saldo_segundos > 0:
                tag = "saldo_positivo"
            elif m.saldo_segundos < 0:
                tag = "saldo_negativo"

            row_id = f"row_{idx}_{iso_id}"
            sel_val = "[☑]" if m.selecionado else "[☐]"
            self.tree.insert(
                "",
                "end",
                iid=row_id,
                values=(
                    sel_val,
                    m.data_formatada,
                    punches[0], punches[1],
                    punches[2], punches[3],
                    punches[4], punches[5],
                    format_time_seconds(m.segundos_trabalhados),
                    saldo_str,
                    obs_str
                ),
                tags=(tag,)
            )

        if self.on_selection_change:
            self.on_selection_change(self.count_selected())

    def count_selected(self) -> int:
        """Conta quantos dias estão com checkbox marcado."""
        return sum(1 for item_id in self.tree.get_children() if self.tree.item(item_id, "values")[0] == "[☑]")

    def get_selected_days_formatted(self) -> List[Dict]:
        """Retorna os dados dos dias selecionados para uso na Justificativa."""
        selected = []
        for item_id in self.tree.get_children():
            vals = self.tree.item(item_id, "values")
            if vals and vals[0] == "[☑]":
                data_str = vals[1]
                punches = [v for v in vals[2:8] if v and v != "--:--"]
                obs = vals[10] if len(vals) > 10 else ""
                selected.append({
                    "data": data_str,
                    "punches": punches,
                    "obs": obs,
                    "saldo": vals[9]
                })
        return selected

    def get_all_rows_as_marcacoes(self) -> List[MarcacaoDia]:
        """Lê todas as linhas atuais da tabela e retorna objetos MarcacaoDia preservando flags de edição."""
        marcacoes = []
        for item_id in self.tree.get_children():
            vals = self.tree.item(item_id, "values")
            if not vals:
                continue
            data_str = vals[1]
            iso_id = normalize_date_to_iso(data_str)
            punches = [v for v in vals[2:8] if v and v != "--:--"]
            obs = vals[10] if len(vals) > 10 else ""

            existing_m = self._data_map.get(iso_id)
            m = PontoEngine.process_horarios(punches, iso_id, data_str, obs)
            m.selecionado = (vals[0] == "[☑]")
            if existing_m:
                m.editado_manualmente = existing_m.editado_manualmente
                m.horarios_originais = existing_m.horarios_originais
            marcacoes.append(m)

        return marcacoes
