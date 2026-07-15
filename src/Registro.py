import os
import logging
import threading
import keyring
import calendar
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass

import pandas as pd
import requests
from openpyxl import load_workbook
from openpyxl.styles import PatternFill, Font
import tkinter as tk
from tkinter import messagebox, ttk, filedialog

# Configura o Logging para salvar erros em arquivo local
log_file = os.path.join(os.path.expanduser("~"), "dixi_auditor.log")
logging.basicConfig(
    filename=log_file,
    level=logging.ERROR,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# --- MODELOS DE DADOS ---
@dataclass
class MarcacaoDia:
    data_id: str  
    data_formatada: str
    segundos_trabalhados: int
    saldo_segundos: int
    is_pendencia: bool
    horarios: List[str]

# --- SERVIÇO DE API ---
class DixiService:
    def __init__(self):
        self.base_url = "https://webapiponto.dixiponto.com.br:8899"
        self.session = requests.Session()
        self.token: Optional[str] = None
        self.user_id: Optional[int] = None

    def authenticate(self, user: str, password: str) -> bool:
        try:
            resp = self.session.post(f"{self.base_url}/login_", json={
                "usuario": user, "senha": password, "unidade": "pagare", "suporte": False
            }, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if data.get("success"):
                self.token = data["data"]["token"]
                self.user_id = data["data"]["usuario"]["funcionario"]["idFuncionario"]
                self.session.headers.update({"Authorization": f"bearer {self.token}"})
                # Guarda as credenciais com segurança no Windows
                keyring.set_password("DixiPontoApp", "last_user", user)
                keyring.set_password("DixiPontoApp", user, password)
                return True
            return False
        except Exception as e:
            logging.error(f"Erro na autenticação: {e}")
            return False

    def fetch_history(self, start: str, end: str) -> List[Dict]:
        params = {"dataInicial": start, "dataFinal": end, "idRegistro": self.user_id}
        resp = self.session.get(f"{self.base_url}/self_/historicoPonto", params=params, timeout=20)
        resp.raise_for_status()
        return resp.json().get("data", [])

# --- MECANISMO DE CÁLCULO ---
class PontoEngine:
    JORNADA_SEG = 8 * 3600
    TOLERANCIA_SEG = 600

    @classmethod
    def process_day(cls, day_data: Dict) -> MarcacaoDia:
        raw_horarios = sorted([m["hora"] for m in day_data["marcacoes"]])
        qtd_batidas = len(raw_horarios)
        total_sec = 0
        
        for i in range(0, qtd_batidas // 2 * 2, 2):
            h1 = datetime.strptime(raw_horarios[i], "%H:%M")
            h2 = datetime.strptime(raw_horarios[i+1], "%H:%M")
            diff_sec = (h2 - h1).total_seconds()
            if diff_sec < 0:
                diff_sec += 24 * 3600  # Suporte para virada de dia/turno noturno
            total_sec += int(diff_sec)

        dt_obj = datetime.strptime(str(day_data["data"]), "%Y%m%d")
        is_pendencia = (qtd_batidas % 2 != 0) or (qtd_batidas == 2)
        
        saldo = 0
        if total_sec > 0:
            diff = total_sec - cls.JORNADA_SEG
            if abs(diff) > cls.TOLERANCIA_SEG:
                saldo = diff - cls.TOLERANCIA_SEG if diff > 0 else diff + cls.TOLERANCIA_SEG

        return MarcacaoDia(
            data_id=str(day_data["data"]),
            data_formatada=dt_obj.strftime("%d/%m/%Y"),
            segundos_trabalhados=total_sec,
            saldo_segundos=saldo,
            is_pendencia=is_pendencia,
            horarios=raw_horarios
        )

# --- EXPORTADOR EXCEL ---
class ExcelExporter:
    @staticmethod
    def format_time(seconds: int, show_sign: bool = False) -> str:
        abs_sec = abs(seconds)
        h, m = divmod(abs_sec // 60, 60)
        sign = ("+" if seconds > 0 else "-") if show_sign and seconds != 0 else ""
        return f"{sign}{int(h):02d}:{int(m):02d}"

    def generate(self, data: List[MarcacaoDia], path: str):
        rows = []
        sum_saldo = 0 

        # Encontra o número máximo de marcações no período para definir as colunas dinamicamente
        max_horarios = max([len(m.horarios) for m in data]) if data else 0
        # Garante pelo menos 6 colunas (E1, S1, E2, S2, E3, S3)
        max_cols = max(6, max_horarios)
        if max_cols % 2 != 0:
            max_cols += 1

        for m in data:
            sum_saldo += m.saldo_segundos
            # Preenche os horários excedentes com vazio
            punches = (m.horarios + [""] * max_cols)[:max_cols]
            row = [m.data_formatada] + punches + [
                self.format_time(m.segundos_trabalhados),
                self.format_time(m.saldo_segundos, True),
                "FALTA BATIDA" if m.is_pendencia else ""
            ]
            rows.append(row)
        
        # Cabeçalhos dinâmicos
        headers = ["Data"]
        for i in range(1, (max_cols // 2) + 1):
            headers.extend([f"E{i}", f"S{i}"])
        headers.extend(["Total", "Saldo", "Obs"])
        
        df = pd.DataFrame(rows, columns=headers)
        df.to_excel(path, index=False)
        self._finalize_excel(path, sum_saldo, max_cols)

    def _finalize_excel(self, path, total_s, max_cols):
        wb = load_workbook(path)
        ws = wb.active
        last_row = ws.max_row + 1
        
        from openpyxl.utils import get_column_letter
        col_saldo_letter = get_column_letter(3 + max_cols)
        col_obs_letter = get_column_letter(4 + max_cols)
        
        ws[f"A{last_row}"] = "SALDO ACUMULADO"
        ws[f"{col_saldo_letter}{last_row}"] = self.format_time(total_s, True)
        
        fill_total = PatternFill(start_color="DDEBF7", fill_type="solid")
        fill_red = PatternFill(start_color="FFC7CE", fill_type="solid")
        fill_green = PatternFill(start_color="C6EFCE", fill_type="solid")
        bold_font = Font(bold=True)

        for cell in ws[last_row]:
            cell.fill = fill_total
            cell.font = bold_font

        for row in range(2, ws.max_row):
            saldo_cell = ws[f"{col_saldo_letter}{row}"]
            obs_cell = ws[f"{col_obs_letter}{row}"]
            val = str(saldo_cell.value)
            if "+" in val: 
                saldo_cell.fill = fill_green
            elif "-" in val: 
                saldo_cell.fill = fill_red
            if obs_cell.value == "FALTA BATIDA": 
                obs_cell.fill = fill_red

        wb.save(path)

# --- SELETOR DE DATAS CUSTOMIZADO (Lista de Meses + Limite de Dias Dinâmico + Ano Digitável) ---
class DateSelector(ttk.Frame):
    def __init__(self, parent, default_day="01", default_month="07", default_year="2026"):
        super().__init__(parent)
        
        self.months = {
            "Janeiro": 1, "Fevereiro": 2, "Março": 3, "Abril": 4,
            "Maio": 5, "Junho": 6, "Julho": 7, "Agosto": 8,
            "Setembro": 9, "Outubro": 10, "Novembro": 11, "Dezembro": 12
        }
        self.month_names = list(self.months.keys())
        
        # Combo Dia (Lista Suspensa)
        self.cb_day = ttk.Combobox(self, width=3, state="readonly")
        self.cb_day.pack(side="left", padx=2)
        
        ttk.Label(self, text="/", font=("Segoe UI", 10, "bold")).pack(side="left")
        
        # Combo Mês (Lista Suspensa)
        self.cb_month = ttk.Combobox(self, values=self.month_names, width=10, state="readonly")
        month_num = int(default_month)
        month_name = [name for name, num in self.months.items() if num == month_num][0]
        self.cb_month.set(month_name)
        self.cb_month.pack(side="left", padx=2)
        
        ttk.Label(self, text="/", font=("Segoe UI", 10, "bold")).pack(side="left")
        
        # Entry Ano (Permite digitar diretamente)
        self.ent_year = ttk.Entry(self, width=5)
        self.ent_year.insert(0, default_year)
        self.ent_year.pack(side="left", padx=2)

        # Binds para atualizar quantidade de dias dinamicamente
        self.cb_month.bind("<<ComboboxSelected>>", self.update_days)
        self.ent_year.bind("<FocusOut>", self.update_days)
        self.ent_year.bind("<KeyRelease>", self.update_days)

        # Popula os dias pela primeira vez
        self.update_days(default_day=default_day)

    def update_days(self, event=None, default_day=None):
        try:
            year = int(self.ent_year.get().strip())
        except ValueError:
            year = datetime.now().year # Fallback se estiver vazio ou inválido
            
        month_name = self.cb_month.get()
        month_num = self.months.get(month_name, 7)
        
        # Calcula quantos dias tem o mês/ano selecionados
        _, max_days = calendar.monthrange(year, month_num)
        
        days_list = [f"{i:02d}" for i in range(1, max_days + 1)]
        self.cb_day["values"] = days_list
        
        # Valida se o dia atualmente selecionado é maior que o máximo permitido
        curr_day = default_day if default_day else self.cb_day.get()
        if not curr_day:
            curr_day = "01"
            
        try:
            if int(curr_day) > max_days:
                curr_day = f"{max_days:02d}"
        except ValueError:
            curr_day = "01"
            
        self.cb_day.set(curr_day)

    def get_date(self) -> datetime:
        day = self.cb_day.get()
        month_num = self.months[self.cb_month.get()]
        year = self.ent_year.get().strip()
        
        try:
            return datetime.strptime(f"{day}/{month_num:02d}/{year}", "%d/%m/%Y")
        except ValueError:
            raise ValueError(f"Data inválida: {day}/{month_num:02d}/{year}")

# --- INTERFACE ---
class AppPonto(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Dixi Auditor - Pagare")
        self.geometry("380x480")
        self.service = DixiService()
        self.exporter = ExcelExporter()
        self.processed_data: List[MarcacaoDia] = []
        
        # Configuração de Estilo Visual Moderno
        self.style = ttk.Style()
        self.style.theme_use("clam")
        
        self.bg_color = "#F6FBF2"
        self.surface_color = "#FFFFFF"
        self.primary_color = "#6ACC32"
        self.primary_dark = "#4E9E24"
        self.primary_soft = "#EAF7E1"
        self.text_color = "#234018"
        self.danger_color = "#C0392B"
        self.warning_bg = "#FFF1CC"
        self.logo_image = None
        
        self.configure(bg=self.bg_color)
        self.style.configure("TFrame", background=self.bg_color)
        self.style.configure("TLabel", background=self.bg_color, foreground=self.text_color, font=("Segoe UI", 10))
        self.style.configure("TButton",
                             background=self.primary_color,
                             foreground="white",
                             font=("Segoe UI", 10, "bold"),
                             padding=6,
                             bordercolor=self.primary_color,
                             lightcolor=self.primary_color,
                             darkcolor=self.primary_color,
                             relief="flat")
        self.style.map("TButton",
                       background=[("active", self.primary_dark), ("disabled", "#BDC3C7")],
                       bordercolor=[("active", self.primary_dark), ("disabled", "#BDC3C7")],
                       lightcolor=[("active", self.primary_dark), ("disabled", "#BDC3C7")],
                       darkcolor=[("active", self.primary_dark), ("disabled", "#BDC3C7")])
        self.style.configure("TEntry",
                             fieldbackground=self.surface_color,
                             bordercolor="#BDC3C7",
                             lightcolor="#BDC3C7",
                             darkcolor="#BDC3C7")
        self.style.configure("TCombobox", fieldbackground=self.surface_color)
        
        self._init_login_ui()

    def _find_logo_path(self) -> Optional[str]:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        candidates = [
            # Prioritize logo_pagare.png
            os.path.join(base_dir, "assets", "images", "logo_pagare.png"),
            os.path.join(os.path.dirname(base_dir), "assets", "images", "logo_pagare.png"),
            # Fallbacks
            os.path.join(base_dir, "assets", "images", "PAGARE.png"),
            os.path.join(os.path.dirname(base_dir), "assets", "images", "PAGARE.png"),
            os.path.join(base_dir, "logo_pagare.png"),
            os.path.join(base_dir, "PAGARE.png"),
        ]
        for path in candidates:
            if os.path.exists(path):
                return path
        return None

    def _render_login_brand(self, parent: ttk.Frame):
        brand_frame = tk.Frame(
            parent,
            bg=self.bg_color,
            highlightthickness=0,
            bd=0
        )
        brand_frame.pack(fill="x", pady=(0, 22))

        logo_path = self._find_logo_path()
        if logo_path and logo_path.lower().endswith((".png", ".gif")):
            try:
                self.logo_image = tk.PhotoImage(file=logo_path)
                tk.Label(brand_frame, image=self.logo_image, bg=self.bg_color).pack(pady=(18, 8))
            except Exception as exc:
                logging.error(f"Erro ao carregar logo_pagare: {exc}")

        if not self.logo_image:
            tk.Label(
                brand_frame,
                text="PAGARE",
                bg=self.bg_color,
                fg=self.primary_dark,
                font=("Segoe UI", 22, "bold"),
                pady=18
            ).pack()

        tk.Label(
            brand_frame,
            text="Dixi Auditor",
            bg=self.bg_color,
            fg=self.text_color,
            font=("Segoe UI", 16, "bold")
        ).pack()

        tk.Label(
            brand_frame,
            text="Acesse com suas credenciais para consultar e exportar o espelho de ponto.",
            bg=self.bg_color,
            fg=self.text_color,
            font=("Segoe UI", 9),
            wraplength=280,
            justify="center",
            pady=10
        ).pack(padx=18, pady=(0, 14))

    def _init_login_ui(self):
        self.frame = ttk.Frame(self, padding=20)
        self.frame.pack(expand=True, fill="both")
        self._render_login_brand(self.frame)
        
        ttk.Label(self.frame, text="Usuário", font=("Segoe UI", 11, "bold")).pack(anchor="center", pady=(0, 5))
        self.ent_user = ttk.Entry(self.frame, width=34)
        self.ent_user.pack(anchor="center", pady=(0, 15), ipady=3)
        
        ttk.Label(self.frame, text="Senha", font=("Segoe UI", 11, "bold")).pack(anchor="center", pady=(0, 5))
        self.ent_pass = ttk.Entry(self.frame, show="*", width=34)
        self.ent_pass.pack(anchor="center", pady=(0, 15), ipady=3)

        # RECUPERA O ÚLTIMO LOGIN SALVO
        last_user = keyring.get_password("DixiPontoApp", "last_user")
        if last_user:
            self.ent_user.insert(0, last_user)
            last_pw = keyring.get_password("DixiPontoApp", last_user)
            if last_pw:
                self.ent_pass.insert(0, last_pw)

        self.btn_login = ttk.Button(self.frame, text="Conectar", command=self._do_login, width=34)
        self.btn_login.pack(anchor="center", pady=20)

    def _do_login(self):
        u, p = self.ent_user.get(), self.ent_pass.get()
        self.btn_login.config(state="disabled")
        
        def run():
            if self.service.authenticate(u, p):
                self.after(0, self._init_main_ui)
            else:
                self.after(0, lambda: messagebox.showerror("Erro", "Falha no Login"))
                self.after(0, lambda: self.btn_login.config(state="normal"))
        
        threading.Thread(target=run, daemon=True).start()

    def _init_main_ui(self):
        for w in self.winfo_children(): w.destroy()
        
        # Redimensiona a janela para acomodar a visualização em tabela e layout horizontal
        self.geometry("980x600")
        
        # Configuração de cores e temas específicos para a tabela
        self.style.configure("Treeview", 
                             background="#FFFFFF", 
                             foreground=self.text_color, 
                             fieldbackground="#FFFFFF",
                             rowheight=25,
                             font=("Segoe UI", 10))
        self.style.configure("Treeview.Heading", 
                             background=self.primary_soft, 
                             foreground=self.text_color, 
                             font=("Segoe UI", 10, "bold"))
        
        # Painel de Filtros Horizontal (Igual ao layout de busca do DIXI)
        filter_frame = ttk.Frame(self, padding=15)
        filter_frame.pack(fill="x", side="top")
        
        # Recupera data atual para pré-selecionar os filtros
        now = datetime.now()
        current_year = str(now.year)
        current_month = f"{now.month:02d}"
        current_day = f"{now.day:02d}"

        # Data Início
        lbl_i = ttk.Label(filter_frame, text="Data Início:", font=("Segoe UI", 10, "bold"))
        lbl_i.pack(side="left", padx=(0, 5))
        self.cal_i = DateSelector(filter_frame, default_day="01", default_month=current_month, default_year=current_year)
        self.cal_i.pack(side="left", padx=(0, 15))

        # Data Fim
        lbl_f = ttk.Label(filter_frame, text="Data Fim:", font=("Segoe UI", 10, "bold"))
        lbl_f.pack(side="left", padx=(0, 5))
        self.cal_f = DateSelector(filter_frame, default_day=current_day, default_month=current_month, default_year=current_year)
        self.cal_f.pack(side="left", padx=(0, 20))

        # Botão Buscar/Visualizar
        self.btn_buscar = ttk.Button(filter_frame, text="Visualizar Ponto", command=self._fetch_and_display)
        self.btn_buscar.pack(side="left", padx=(0, 10))

        # Botão Recalcular Ponto (Permite simular após edições)
        self.btn_recalc = ttk.Button(filter_frame, text="Recalcular Ponto", command=self._recalculate_tree_totals, state="disabled")
        self.btn_recalc.pack(side="left", padx=(0, 10))

        # Botão Exportar Excel (inicialmente desativado)
        self.btn_export = ttk.Button(filter_frame, text="Exportar Excel", command=self._export_excel, state="disabled")
        self.btn_export.pack(side="left")

        # Frame Principal da Tabela
        table_frame = ttk.Frame(self, padding=15)
        table_frame.pack(fill="both", expand=True, side="top")
        
        # Cabeçalhos padrão iniciais
        self.cols = ["Data", "E1", "S1", "E2", "S2", "E3", "S3", "Total", "Saldo", "Obs"]
        
        # Widget de Tabela
        self.tree = ttk.Treeview(table_frame, columns=self.cols, show="headings", selectmode="browse")
        
        # Barras de rolagem
        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        # Posicionamento em Grid para visualização adequada
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # Configura as larguras padrões
        column_widths = {
            "Data": 100, "E1": 65, "S1": 65, "E2": 65, "S2": 65, "E3": 65, "S3": 65,
            "Total": 80, "Saldo": 80, "Obs": 120
        }
        for c in self.cols:
            self.tree.heading(c, text=c, anchor="center")
            self.tree.column(c, width=column_widths.get(c, 80), anchor="center")

        # Configuração de tags de coloração para linhas da tabela
        self.tree.tag_configure("positive", foreground=self.primary_dark, font=("Segoe UI", 10, "bold"))
        self.tree.tag_configure("negative", foreground=self.danger_color, font=("Segoe UI", 10, "bold"))
        self.tree.tag_configure("missing", background=self.warning_bg, foreground=self.danger_color)
        self.tree.tag_configure("normal", foreground=self.text_color)

        # Vincula duplo clique para edição de células
        self.tree.bind("<Double-1>", self.on_double_click)

        # Label de Status / Resumo no rodapé
        self.lbl_status = ttk.Label(self, text="", font=("Segoe UI", 10, "italic"), padding=10)
        self.lbl_status.pack(fill="x", side="bottom")

    def on_double_click(self, event):
        # Identifica em qual célula o usuário deu dois cliques
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return
            
        column = self.tree.identify_column(event.x) # Ex: '#1', '#2'
        item = self.tree.identify_row(event.y)
        
        col_idx = int(column[1:]) - 1
        col_name = self.cols[col_idx]
        
        # Não permite editar as colunas de Data, Total, Saldo ou Obs
        if col_name in ["Data", "Total", "Saldo", "Obs"]:
            return
            
        # Pega a posição geométrica exata da célula clicada
        x, y, width, height = self.tree.bbox(item, column)
        
        # Cria uma caixa de digitação (Entry) exatamente em cima da célula
        entry = ttk.Entry(self.tree)
        entry.insert(0, self.tree.set(item, column))
        entry.select_range(0, "end")
        entry.focus_set()
        entry.place(x=x, y=y, width=width, height=height)
        
        def save_edit(event=None):
            new_val = entry.get().strip()
            # Se digitou algo, valida se é um formato de hora HH:MM válido
            if new_val:
                try:
                    datetime.strptime(new_val, "%H:%M")
                except ValueError:
                    messagebox.showerror("Formato Inválido", "A hora deve estar no formato de 24h: HH:MM (ex: 08:30 ou 17:45).")
                    entry.destroy()
                    return
            
            self.tree.set(item, column, new_val)
            entry.destroy()
            # IMPORTANTE: Apenas salva o valor digitado no Grid. Não dispara o recálculo nem exibe pop-up na hora.

        def cancel_edit(event=None):
            entry.destroy()

        entry.bind("<Return>", save_edit)
        entry.bind("<FocusOut>", save_edit)
        entry.bind("<Escape>", cancel_edit)

    def _fetch_and_display(self):
        try:
            s = self.cal_i.get_date().strftime("%Y%m%d")
            e = self.cal_f.get_date().strftime("%Y%m%d")
        except ValueError as val_ex:
            messagebox.showerror("Erro de Data", str(val_ex))
            return
        
        self.btn_buscar.config(state="disabled")
        self.btn_export.config(state="disabled")
        self.btn_recalc.config(state="disabled")
        
        # Limpa registros antigos da visualização
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        self.lbl_status.config(text="Obtendo dados do espelho de ponto na Dixi...", foreground=self.primary_dark)
        
        def run():
            try:
                raw = self.service.fetch_history(s, e)
                if not raw:
                    self.after(0, lambda: messagebox.showwarning("Aviso", "Nenhum dado de ponto encontrado para o período selecionado."))
                    return
                
                processed = sorted(
                    [PontoEngine.process_day(d) for d in raw], 
                    key=lambda x: x.data_id
                )
                
                self.processed_data = processed
                self.after(0, lambda: self._populate_table(processed))
                
            except Exception as ex:
                self.after(0, lambda: messagebox.showerror("Erro", f"Erro ao buscar histórico:\n{ex}"))
            finally:
                self.after(0, lambda: self.btn_buscar.config(state="normal"))
        
        threading.Thread(target=run, daemon=True).start()

    def _populate_table(self, data: List[MarcacaoDia]):
        # Identifica dinamicamente a quantidade máxima de colunas necessárias
        max_horarios = max([len(m.horarios) for m in data]) if data else 0
        max_cols = max(6, max_horarios)
        if max_cols % 2 != 0:
            max_cols += 1

        # Reconstrói os cabeçalhos das colunas
        cols = ["Data"]
        for i in range(1, (max_cols // 2) + 1):
            cols.extend([f"E{i}", f"S{i}"])
        cols.extend(["Total", "Saldo", "Obs"])
        
        self.cols = cols
        self.tree["columns"] = cols
        
        # Configura novos cabeçalhos
        for c in cols:
            self.tree.heading(c, text=c, anchor="center")
            if c == "Data":
                self.tree.column(c, width=100, minwidth=80, anchor="center")
            elif c in ["Total", "Saldo"]:
                self.tree.column(c, width=80, minwidth=70, anchor="center")
            elif c == "Obs":
                self.tree.column(c, width=120, minwidth=100, anchor="center")
            else:
                self.tree.column(c, width=65, minwidth=50, anchor="center")

        # Popula os dados
        for m in data:
            punches = (m.horarios + [""] * max_cols)[:max_cols]
            total_str = self.exporter.format_time(m.segundos_trabalhados)
            saldo_str = self.exporter.format_time(m.saldo_segundos, True)
            obs_str = "FALTA BATIDA" if m.is_pendencia else ""
            
            row_vals = [m.data_formatada] + punches + [total_str, saldo_str, obs_str]
            
            tag = "normal"
            if m.is_pendencia:
                tag = "missing"
            elif m.saldo_segundos > 0:
                tag = "positive"
            elif m.saldo_segundos < 0:
                tag = "negative"
                
            self.tree.insert("", "end", values=row_vals, tags=(tag,))
            
        # Ativa botões de ação e calcula saldo total
        if data:
            self.btn_export.config(state="normal")
            self.btn_recalc.config(state="normal")
            
            total_saldo_seg = sum([m.saldo_segundos for m in data])
            total_dias = len(data)
            saldo_acumulado = self.exporter.format_time(total_saldo_seg, True)
            
            status_text = f"Dias carregados: {total_dias} | Saldo Acumulado no Período: {saldo_acumulado}"
            self.lbl_status.config(text=status_text, foreground=self.text_color)

    def _recalculate_tree_totals(self):
        # Lê os dados editados diretamente do Grid e recalcula todos os horários e saldos
        total_saldo_seg = 0
        total_dias = 0
        
        # Identifica quantidade de colunas de marcação no Treeview
        num_punch_cols = len(self.cols) - 4
        
        new_processed = []
        
        for item in self.tree.get_children():
            values = list(self.tree.item(item, "values"))
            
            data_formatada = values[0]
            dt_obj = datetime.strptime(data_formatada, "%d/%m/%Y")
            data_id = dt_obj.strftime("%Y%m%d")
            
            # Filtra apenas os horários preenchidos (ignora os vazios)
            punches = [values[i] for i in range(1, 1 + num_punch_cols) if values[i].strip()]
            
            day_data = {
                "data": data_id,
                "marcacoes": [{"hora": h} for h in punches]
            }
            
            # Recalcula usando a engine
            m_dia = PontoEngine.process_day(day_data)
            new_processed.append(m_dia)
            
            # Formata os novos resultados
            total_str = self.exporter.format_time(m_dia.segundos_trabalhados)
            saldo_str = self.exporter.format_time(m_dia.saldo_segundos, True)
            obs_str = "FALTA BATIDA" if m_dia.is_pendencia else ""
            
            padded_punches = (punches + [""] * num_punch_cols)[:num_punch_cols]
            new_values = [data_formatada] + padded_punches + [total_str, saldo_str, obs_str]
            
            tag = "normal"
            if m_dia.is_pendencia:
                tag = "missing"
            elif m_dia.saldo_segundos > 0:
                tag = "positive"
            elif m_dia.saldo_segundos < 0:
                tag = "negative"
                
            self.tree.item(item, values=new_values, tags=(tag,))
            
            # Conta no saldo acumulado apenas se o dia tem batidas
            if len(punches) > 0:
                total_saldo_seg += m_dia.saldo_segundos
                total_dias += 1
                
        # Atualiza a lista interna para exportação para Excel
        self.processed_data = new_processed
        
        # Atualiza o status do rodapé
        saldo_acumulado = self.exporter.format_time(total_saldo_seg, True)
        status_text = f"Dias recalculados: {total_dias} | Saldo Acumulado: {saldo_acumulado}"
        self.lbl_status.config(text=status_text, foreground=self.text_color)
        
        # Exibe o popup informativo de recálculo apenas neste botão, não a cada edição de célula
        messagebox.showinfo("Recalculado", "Os cálculos diários e o saldo acumulado foram atualizados com sucesso!")

    def _export_excel(self):
        if not self.processed_data:
            messagebox.showwarning("Aviso", "Nenhum dado carregado para exportação.")
            return
            
        try:
            s = self.cal_i.get_date().strftime("%Y%m%d")
            e = self.cal_f.get_date().strftime("%Y%m%d")
        except ValueError as val_ex:
            messagebox.showerror("Erro de Data", str(val_ex))
            return
        
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Planilha Excel", "*.xlsx")],
            initialfile=f"Ponto_{s}_a_{e}.xlsx",
            title="Salvar Relatório de Ponto"
        )
        if path:
            try:
                self.exporter.generate(self.processed_data, path)
                messagebox.showinfo("Sucesso", "Planilha Excel gerada com sucesso!")
                os.startfile(path)
            except Exception as ex_save:
                messagebox.showerror("Erro ao Salvar", f"Não foi possível salvar a planilha:\n{ex_save}")

if __name__ == "__main__":
    AppPonto().mainloop()