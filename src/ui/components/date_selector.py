"""
Componente Seletor de Datas customizado com suporte a anos bissextos e nomes em português.
"""
import calendar
import tkinter as tk
from tkinter import ttk
from datetime import datetime
from typing import Optional

MESES_NOMES = [
    ("01", "Janeiro"),
    ("02", "Fevereiro"),
    ("03", "Março"),
    ("04", "Abril"),
    ("05", "Maio"),
    ("06", "Junho"),
    ("07", "Julho"),
    ("08", "Agosto"),
    ("09", "Setembro"),
    ("10", "Outubro"),
    ("11", "Novembro"),
    ("12", "Dezembro")
]

class DateSelector(ttk.Frame):
    """Componente horizontal de seleção de dia, mês e ano."""

    def __init__(self, parent, default_day: str = "01", default_month: str = "01", default_year: str = "2026"):
        super().__init__(parent)

        self.meses_map = {num: nome for num, nome in MESES_NOMES}
        self.meses_map_rev = {nome: num for num, nome in MESES_NOMES}

        # Dropdown de Dia
        self.cb_dia = ttk.Combobox(self, width=3, state="readonly")
        self.cb_dia.pack(side="left", padx=(0, 2))

        # Dropdown de Mês
        self.cb_mes = ttk.Combobox(
            self,
            width=10,
            values=[nome for _, nome in MESES_NOMES],
            state="readonly"
        )
        mes_nome_padrao = self.meses_map.get(str(default_month).zfill(2), "Janeiro")
        self.cb_mes.set(mes_nome_padrao)
        self.cb_mes.pack(side="left", padx=(0, 2))

        # Campo de Ano
        self.ent_ano = ttk.Entry(self, width=5)
        self.ent_ano.insert(0, str(default_year))
        self.ent_ano.pack(side="left")

        # Atualiza a lista de dias disponíveis
        self.update_days(default_day=default_day)

        # Eventos de alteração de mês ou ano
        self.cb_mes.bind("<<ComboboxSelected>>", self.update_days)
        self.ent_ano.bind("<FocusOut>", self.update_days)
        self.ent_ano.bind("<Return>", self.update_days)

    def update_days(self, event=None, default_day: Optional[str] = None):
        """Ajusta o total de dias conforme o mês e ano selecionados (ex: 28, 29, 30 ou 31 dias)."""
        mes_nome = self.cb_mes.get()
        mes_num = int(self.meses_map_rev.get(mes_nome, "01"))

        try:
            ano = int(self.ent_ano.get().strip())
        except ValueError:
            ano = datetime.now().year
            self.ent_ano.delete(0, tk.END)
            self.ent_ano.insert(0, str(ano))

        _, max_dias = calendar.monthrange(ano, mes_num)
        dias_valores = [f"{d:02d}" for d in range(1, max_dias + 1)]
        self.cb_dia["values"] = dias_valores

        dia_atual = default_day or self.cb_dia.get()
        if dia_atual in dias_valores:
            self.cb_dia.set(dia_atual)
        else:
            self.cb_dia.set(f"{min(int(dia_atual or 1), max_dias):02d}")

    def set_date(self, dt_str: str):
        """Define a data a partir de uma string 'DD/MM/YYYY', 'YYYY-MM-DD' ou 'YYYYMMDD'."""
        if not dt_str:
            return
        clean = dt_str.strip()
        try:
            if "/" in clean:
                parts = clean.split("/")
                d, m, y = parts[0].zfill(2), parts[1].zfill(2), parts[2]
            elif "-" in clean:
                parts = clean.split("-")
                if len(parts[0]) == 4:
                    y, m, d = parts[0], parts[1].zfill(2), parts[2].zfill(2)
                else:
                    d, m, y = parts[0].zfill(2), parts[1].zfill(2), parts[2]
            elif len(clean) == 8 and clean.isdigit():
                y, m, d = clean[:4], clean[4:6], clean[6:]
            else:
                return

            self.ent_ano.delete(0, tk.END)
            self.ent_ano.insert(0, str(y))
            mes_nome = self.meses_map.get(m, "Janeiro")
            self.cb_mes.set(mes_nome)
            self.update_days(default_day=d)
        except Exception:
            pass

    def get_date(self) -> datetime:
        """Retorna a data selecionada como objeto datetime."""
        dia = int(self.cb_dia.get())
        mes_nome = self.cb_mes.get()
        mes = int(self.meses_map_rev.get(mes_nome, "01"))
        ano = int(self.ent_ano.get().strip())
        return datetime(ano, mes, dia)

    def get_date_str_iso(self) -> str:
        """Retorna no formato 'YYYYMMDD' para consumo de APIs."""
        return self.get_date().strftime("%Y%m%d")

    def get_date_str_br(self) -> str:
        """Retorna no formato 'DD/MM/YYYY'."""
        return self.get_date().strftime("%d/%m/%Y")
