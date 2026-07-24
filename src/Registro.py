import os
import re
import json
import logging
import threading
import keyring
import calendar
from datetime import datetime
from typing import List, Dict, Optional, Tuple
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
    obs: str = ""

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
    MIN_ALMOCO_SEG = 3600  # 1 hora de almoço (3600s)

    @classmethod
    def process_horarios(cls, raw_horarios: List[str], data_id: str, data_formatada: str, obs: str = "") -> MarcacaoDia:
        raw_horarios = sorted(raw_horarios)
        qtd_batidas = len(raw_horarios)
        total_sec = 0
        
        for i in range(0, qtd_batidas // 2 * 2, 2):
            h1 = datetime.strptime(raw_horarios[i], "%H:%M")
            h2 = datetime.strptime(raw_horarios[i+1], "%H:%M")
            diff_sec = (h2 - h1).total_seconds()
            if diff_sec < 0:
                diff_sec += 24 * 3600  # Suporte para virada de dia/turno noturno
            total_sec += int(diff_sec)

        # Regra de Almoço: Se voltou antes de 1 hora (3600s), desconsidera o tempo antecipado como hora extra
        if qtd_batidas >= 4:
            s1 = datetime.strptime(raw_horarios[1], "%H:%M")
            e2 = datetime.strptime(raw_horarios[2], "%H:%M")
            intervalo_almoco = (e2 - s1).total_seconds()
            if intervalo_almoco < 0:
                intervalo_almoco += 24 * 3600
            
            if intervalo_almoco < cls.MIN_ALMOCO_SEG:
                desconto_antecipacao = cls.MIN_ALMOCO_SEG - intervalo_almoco
                total_sec -= int(desconto_antecipacao)

        is_pendencia = (qtd_batidas % 2 != 0) or (qtd_batidas == 2)
        
        saldo = 0
        if total_sec > 0:
            diff = total_sec - cls.JORNADA_SEG
            if abs(diff) > cls.TOLERANCIA_SEG:
                saldo = diff - cls.TOLERANCIA_SEG if diff > 0 else diff + cls.TOLERANCIA_SEG

        return MarcacaoDia(
            data_id=data_id,
            data_formatada=data_formatada,
            segundos_trabalhados=total_sec,
            saldo_segundos=saldo,
            is_pendencia=is_pendencia,
            horarios=raw_horarios,
            obs=obs
        )

    @classmethod
    def process_day(cls, day_data: Dict) -> MarcacaoDia:
        raw_horarios = sorted([m["hora"] for m in day_data["marcacoes"]])
        dt_obj = datetime.strptime(str(day_data["data"]), "%Y%m%d")
        return cls.process_horarios(raw_horarios, str(day_data["data"]), dt_obj.strftime("%d/%m/%Y"))

# --- EXPORTADOR EXCEL ---
class ExcelExporter:
    @staticmethod
    def format_time(seconds: int, show_sign: bool = False) -> str:
        abs_sec = abs(seconds)
        h, m = divmod(abs_sec // 60, 60)
        sign = ("+" if seconds > 0 else "-") if show_sign and seconds != 0 else ""
        return f"{sign}{int(h):02d}:{int(m):02d}"

    def generate(self, data: List[MarcacaoDia], path: str, ignore_today: bool = True):
        rows = []
        sum_saldo = 0 
        today_str = datetime.now().strftime("%d/%m/%Y")

        max_horarios = max([len(m.horarios) for m in data]) if data else 0
        max_cols = max(6, max_horarios)
        if max_cols % 2 != 0:
            max_cols += 1

        for m in data:
            is_today = (m.data_formatada == today_str) and ignore_today
            if not is_today:
                sum_saldo += m.saldo_segundos

            punches = (m.horarios + [""] * max_cols)[:max_cols]
            saldo_str = "00:00" if is_today else self.format_time(m.saldo_segundos, True)
            obs_str = m.obs if m.obs else ("EM ANDAMENTO" if is_today else ("FALTA BATIDA" if m.is_pendencia else ""))
            
            row = [m.data_formatada] + punches + [
                self.format_time(m.segundos_trabalhados),
                saldo_str,
                obs_str
            ]
            rows.append(row)
        
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
        fill_yellow = PatternFill(start_color="FFF2CC", fill_type="solid")
        fill_olive = PatternFill(start_color="E2EFDA", fill_type="solid")
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
            elif "-" in val and val != "00:00": 
                saldo_cell.fill = fill_red
            if obs_cell.value == "FALTA BATIDA": 
                obs_cell.fill = fill_red
            elif obs_cell.value == "EM ANDAMENTO":
                obs_cell.fill = fill_olive
            elif obs_cell.value and any(k in str(obs_cell.value) for k in ["IA", "Ajust", "Abon"]):
                obs_cell.fill = fill_yellow

        wb.save(path)

# --- SERVIÇO DE ANÁLISE POR IA ---
class IAAnalistaPonto:
    @staticmethod
    def get_api_key() -> str:
        key = os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("OPENROUTER_API_KEY")
        if not key:
            key = keyring.get_password("DixiPontoApp", "openrouter_token") or ""
        return key

    @classmethod
    def analisar_ponto(cls, data: List[MarcacaoDia], api_key: Optional[str] = None, instrucoes_usuario: Optional[str] = None, ignore_today: bool = True) -> Tuple[str, List[Dict]]:
        token = api_key or cls.get_api_key()
        today_str = datetime.now().strftime("%d/%m/%Y")
        
        total_dias = len(data)
        
        if ignore_today:
            dias_pendencia = [m for m in data if m.is_pendencia and m.data_formatada != today_str]
            dias_extras = [m for m in data if m.saldo_segundos > 0 and m.data_formatada != today_str]
            dias_atraso = [m for m in data if m.saldo_segundos < 0 and m.data_formatada != today_str]
            saldo_total = sum(m.saldo_segundos for m in data if m.data_formatada != today_str)
        else:
            dias_pendencia = [m for m in data if m.is_pendencia]
            dias_extras = [m for m in data if m.saldo_segundos > 0]
            dias_atraso = [m for m in data if m.saldo_segundos < 0]
            saldo_total = sum(m.saldo_segundos for m in data)

        saldo_str = ExcelExporter.format_time(saldo_total, True)
        
        resumo_dados = f"Total de dias auditados: {total_dias}\n"
        resumo_dados += f"Saldo acumulado no período (desconsiderando dia atual em andamento): {saldo_str}\n" if ignore_today else f"Saldo acumulado no período: {saldo_str}\n"
        resumo_dados += f"Dias com batida pendente/faltante: {len(dias_pendencia)}\n"
        resumo_dados += f"Dias com saldo positivo (HE): {len(dias_extras)}\n"
        resumo_dados += f"Dias com saldo negativo (atrasos): {len(dias_atraso)}\n\n"
        resumo_dados += "Detalhamento por dia:\n"
        
        for m in data[:31]:
            is_today = (m.data_formatada == today_str) and ignore_today
            if is_today:
                resumo_dados += f"- Data: {m.data_formatada} | Batidas: {', '.join(m.horarios)} | Trabalhado: {ExcelExporter.format_time(m.segundos_trabalhados)} | (EM ANDAMENTO - IGNORADO NO SALDO)\n"
            else:
                resumo_dados += f"- Data: {m.data_formatada} | Batidas: {', '.join(m.horarios)} | Trabalhado: {ExcelExporter.format_time(m.segundos_trabalhados)} | Saldo: {ExcelExporter.format_time(m.saldo_segundos, True)} {'(PENDÊNCIA)' if m.is_pendencia else ''}\n"

        parsed_ajustes = []

        if token:
            try:
                base_url = os.environ.get("ANTHROPIC_BASE_URL", "https://openrouter.ai/api")
                endpoint = f"{base_url.rstrip('/')}/v1/chat/completions"
                model = os.environ.get("ANTHROPIC_DEFAULT_SONNET_MODEL", "meta-llama/llama-3.3-70b-instruct:free")
                
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                }
                prompt = (
                    "Você é um especialista em auditoria de RH e cartão de ponto.\n"
                    "Analise a jornada abaixo de forma clara, profissional e objetiva em português:\n"
                    "1. Faça um resumo geral do período auditado.\n"
                    "2. Destaque inconsistências graves (batidas ímpares, faltas ou atrasos recorrentes).\n"
                    "3. Dê recomendações para o gestor ou funcionário.\n\n"
                    f"DADOS DO PONTO:\n{resumo_dados}"
                )
                if instrucoes_usuario:
                    prompt += (
                        "\n\nSOLICITAÇÃO DE REAJUSTE / INSTRUÇÃO DO USUÁRIO PARA RECALCULAR:\n"
                        f"\"{instrucoes_usuario}\"\n\n"
                        "Por favor, considere as edições/ajustes solicitados acima pelo usuário nos pontos citados, recalculando a análise, saldos e considerações com base nessas instruções.\n"
                        "IMPORTANTE: Se a instrução do usuário definir horários específicos (ex: 'saída às 18:00') ou solicitar abono de faltas/pendências, inclua AO FINAL da resposta um bloco JSON estruturado exatamente assim:\n"
                        "```json\n"
                        "{\n"
                        "  \"ajustes\": [\n"
                        "    {\"data\": \"DD/MM/YYYY\", \"horarios\": [\"08:00\", \"12:00\", \"13:00\", \"18:00\"], \"obs\": \"Ajustado via IA: saída 18:00\"},\n"
                        "    {\"data\": \"DD/MM/YYYY\", \"abono\": true, \"obs\": \"Abonado via IA\"}\n"
                        "  ]\n"
                        "}\n"
                        "```\n"
                        "Ajuste apenas os dias citados na instrução do usuário. Se não houver edições diretas na tabela, não inclua o bloco JSON."
                    )
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3
                }
                resp = requests.post(endpoint, json=payload, headers=headers, timeout=20)
                if resp.status_code == 200:
                    res_json = resp.json()
                    content = res_json["choices"][0]["message"]["content"]
                    json_match = re.search(r'```json\s*(\{.*?\})\s*```', content, re.DOTALL)
                    if json_match:
                        try:
                            data_json = json.loads(json_match.group(1))
                            parsed_ajustes = data_json.get("ajustes", [])
                            content = re.sub(r'```json\s*(\{.*?\})\s*```', '', content).strip()
                        except Exception as je:
                            logging.error(f"Erro ao parsear JSON de ajustes: {je}")
                    return content, parsed_ajustes
            except Exception as e:
                logging.error(f"Erro na API de IA: {e}")

        # Fallback local de auditoria inteligente com parser local simplificado
        if instrucoes_usuario:
            for line in instrucoes_usuario.split('\n'):
                m_date = re.search(r'(\d{2}/\d{2}(?:/\d{4})?)', line)
                if m_date:
                    dt_str = m_date.group(1)
                    if len(dt_str) == 5 and data:
                        year = data[0].data_formatada.split('/')[-1]
                        dt_str = f"{dt_str}/{year}"
                    times = re.findall(r'\b\d{2}:\d{2}\b', line)
                    if times:
                        parsed_ajustes.append({"data": dt_str, "horarios": times, "obs": "Ajustado via IA (Local)"})
                    elif any(k in line.lower() for k in ["abon", "falt", "desconsider"]):
                        parsed_ajustes.append({"data": dt_str, "abono": True, "obs": "Abonado via IA (Local)"})

        fallback = "🤖 ANÁLISE AUTOMÁTICA DE AUDITORIA (Local)\n"
        fallback += "=" * 45 + "\n\n"
        fallback += f"• Período Auditado: {total_dias} dias registrados.\n"
        fallback += f"• Saldo Geral Acumulado: {saldo_str}\n\n"
        
        if instrucoes_usuario:
            fallback += f"✏️ AJUSTES E INSTRUÇÕES DIGITADAS:\n   \"{instrucoes_usuario}\"\n\n"
            if parsed_ajustes:
                fallback += f"✅ {len(parsed_ajustes)} ajuste(s) identificado(s) e aplicado(s) na tabela do aplicativo!\n\n"
        
        if dias_pendencia:
            fallback += f"⚠️ ATENÇÃO: Identificamos {len(dias_pendencia)} dia(s) com batidas pendentes/ímpares:\n"
            for d in dias_pendencia:
                fallback += f"   - Dia {d.data_formatada}: Marcações ({', '.join(d.horarios)})\n"
            fallback += "   -> Ação recomendada: Solicitar ajuste manual ou abono no sistema Dixi.\n\n"
        else:
            fallback += "✅ Nenhuma pendência de marcação ímpar detectada no período.\n\n"
            
        if len(dias_atraso) > 0:
            fallback += f"🔴 Atrasos Registrados: {len(dias_atraso)} dia(s) fecharam com saldo negativo.\n"
        if len(dias_extras) > 0:
            fallback += f"🟢 Horas Extras: {len(dias_extras)} dia(s) fecharam com saldo positivo.\n"

        if not token:
            fallback += "\n💡 Dica: Configure sua ANTHROPIC_AUTH_TOKEN ou chave do OpenRouter para que a IA recalcule com inteligência em linguagem natural."
            
        return fallback, parsed_ajustes

# --- SELETOR DE DATAS CUSTOMIZADO ---
class DateSelector(ttk.Frame):
    def __init__(self, parent, default_day="01", default_month="07", default_year="2026"):
        super().__init__(parent)
        
        self.months = {
            "Janeiro": 1, "Fevereiro": 2, "Março": 3, "Abril": 4,
            "Maio": 5, "Junho": 6, "Julho": 7, "Agosto": 8,
            "Setembro": 9, "Outubro": 10, "Novembro": 11, "Dezembro": 12
        }
        self.month_names = list(self.months.keys())
        
        self.cb_day = ttk.Combobox(self, width=3, state="readonly")
        self.cb_day.pack(side="left", padx=2)
        
        ttk.Label(self, text="/", font=("Segoe UI", 10, "bold")).pack(side="left")
        
        self.cb_month = ttk.Combobox(self, values=self.month_names, width=10, state="readonly")
        month_num = int(default_month)
        month_name = [name for name, num in self.months.items() if num == month_num][0]
        self.cb_month.set(month_name)
        self.cb_month.pack(side="left", padx=2)
        
        ttk.Label(self, text="/", font=("Segoe UI", 10, "bold")).pack(side="left")
        
        self.ent_year = ttk.Entry(self, width=5)
        self.ent_year.insert(0, default_year)
        self.ent_year.pack(side="left", padx=2)

        self.cb_month.bind("<<ComboboxSelected>>", self.update_days)
        self.ent_year.bind("<FocusOut>", self.update_days)
        self.ent_year.bind("<KeyRelease>", self.update_days)

        self.update_days(default_day=default_day)

    def update_days(self, event=None, default_day=None):
        try:
            year = int(self.ent_year.get().strip())
        except ValueError:
            year = datetime.now().year
            
        month_name = self.cb_month.get()
        month_num = self.months.get(month_name, 7)
        
        _, max_days = calendar.monthrange(year, month_num)
        
        days_list = [f"{i:02d}" for i in range(1, max_days + 1)]
        self.cb_day["values"] = days_list
        
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

# --- INTERFACE PRINCIPAL ---
class AppPonto(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Dixi Auditor - Pagare")
        self.geometry("380x520")
        self.service = DixiService()
        self.exporter = ExcelExporter()
        self.processed_data: List[MarcacaoDia] = []
        
        # Configuração de Estilo Visual
        self.style = ttk.Style()
        self.style.theme_use("clam")
        
        self.bg_color = "#F4F8F3"
        self.surface_color = "#FFFFFF"
        self.primary_color = "#5CBD28"
        self.primary_dark = "#4E9E24"
        self.primary_soft = "#EAF7E1"
        self.text_color = "#1E4620"
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
            os.path.join(base_dir, "assets", "images", "Repository Logo.png"),
            os.path.join(os.path.dirname(base_dir), "assets", "images", "Repository Logo.png"),
            os.path.join(base_dir, "assets", "images", "logo_pagare.png"),
            os.path.join(os.path.dirname(base_dir), "assets", "images", "logo_pagare.png"),
            os.path.join(os.path.dirname(base_dir), "Repository Logo.png"),
            os.path.join(base_dir, "Repository Logo.png"),
        ]
        for path in candidates:
            if os.path.exists(path):
                return path
        return None

    def _render_login_brand(self, parent: tk.Frame):
        brand_frame = tk.Frame(
            parent,
            bg=self.bg_color,
            highlightthickness=0,
            bd=0
        )
        brand_frame.pack(fill="x", pady=(10, 15))

        logo_path = self._find_logo_path()
        if logo_path and logo_path.lower().endswith((".png", ".gif")):
            try:
                self.logo_image = tk.PhotoImage(file=logo_path)
                tk.Label(brand_frame, image=self.logo_image, bg=self.bg_color).pack(pady=(10, 15))
            except Exception as exc:
                logging.error(f"Erro ao carregar logo: {exc}")

        if not self.logo_image:
            tk.Label(
                brand_frame,
                text="PAGARE",
                bg=self.bg_color,
                fg="#1E4620",
                font=("Segoe UI", 22, "bold"),
                pady=10
            ).pack()

        tk.Label(
            brand_frame,
            text="Dixi Auditor",
            bg=self.bg_color,
            fg="#1E4620",
            font=("Segoe UI", 20, "bold")
        ).pack(pady=(0, 8))

        tk.Label(
            brand_frame,
            text="Acesse com suas credenciais para consultar e exportar o espelho de ponto.",
            bg=self.bg_color,
            fg="#2E4E2E",
            font=("Segoe UI", 9),
            wraplength=290,
            justify="center"
        ).pack(padx=20, pady=(0, 10))

    def _init_login_ui(self):
        self.geometry("380x520")
        self.frame = tk.Frame(self, bg=self.bg_color, padx=25, pady=15)
        self.frame.pack(expand=True, fill="both")
        self._render_login_brand(self.frame)
        
        lbl_user = tk.Label(self.frame, text="Usuário", bg=self.bg_color, fg="#1E4620", font=("Segoe UI", 11, "bold"))
        lbl_user.pack(anchor="center", pady=(5, 4))
        
        self.ent_user = ttk.Entry(self.frame, width=32, font=("Segoe UI", 10))
        self.ent_user.pack(anchor="center", pady=(0, 14), ipady=4)
        
        lbl_pass = tk.Label(self.frame, text="Senha", bg=self.bg_color, fg="#1E4620", font=("Segoe UI", 11, "bold"))
        lbl_pass.pack(anchor="center", pady=(5, 4))
        
        self.ent_pass = ttk.Entry(self.frame, show="*", width=32, font=("Segoe UI", 10))
        self.ent_pass.pack(anchor="center", pady=(0, 20), ipady=4)

        # RECUPERA O ÚLTIMO LOGIN SALVO
        last_user = keyring.get_password("DixiPontoApp", "last_user")
        if last_user:
            self.ent_user.insert(0, last_user)
            last_pw = keyring.get_password("DixiPontoApp", last_user)
            if last_pw:
                self.ent_pass.insert(0, last_pw)

        self.btn_login = tk.Button(
            self.frame,
            text="Conectar",
            command=self._do_login,
            bg="#5CBD28",
            fg="white",
            activebackground="#4E9E24",
            activeforeground="white",
            font=("Segoe UI", 11, "bold"),
            bd=0,
            relief="flat",
            cursor="hand2",
            width=28,
            pady=8
        )
        self.btn_login.pack(anchor="center", pady=(5, 15))

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
        
        self.geometry("1100x620")
        
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
        
        filter_frame = ttk.Frame(self, padding=15)
        filter_frame.pack(fill="x", side="top")
        
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
        self.cal_f.pack(side="left", padx=(0, 15))

        # Checkbox Ignorar Dia Atual (Em Andamento)
        self.var_ignore_today = tk.BooleanVar(value=True)
        self.chk_ignore_today = ttk.Checkbutton(
            filter_frame,
            text="☑ Ignorar Dia Atual (Em Andamento)",
            variable=self.var_ignore_today,
            command=self._on_toggle_ignore_today
        )
        self.chk_ignore_today.pack(side="left", padx=(0, 15))

        # Botões de Ação
        self.btn_buscar = ttk.Button(filter_frame, text="Visualizar Ponto", command=self._fetch_and_display)
        self.btn_buscar.pack(side="left", padx=(0, 8))

        self.btn_recalc = ttk.Button(filter_frame, text="Recalcular Ponto", command=self._recalculate_tree_totals, state="disabled")
        self.btn_recalc.pack(side="left", padx=(0, 8))

        self.btn_export = ttk.Button(filter_frame, text="Exportar Excel", command=self._export_excel, state="disabled")
        self.btn_export.pack(side="left", padx=(0, 8))

        # Botão Análise por IA
        self.btn_ai = ttk.Button(filter_frame, text="🤖 Análise por IA", command=self._show_ai_analysis, state="disabled")
        self.btn_ai.pack(side="left", padx=(0, 8))

        # Botão Configuração da Chave IA
        self.btn_key = ttk.Button(filter_frame, text="🔑 Chave IA", command=self._config_ai_key)
        self.btn_key.pack(side="left")

        # Frame Principal da Tabela
        table_frame = ttk.Frame(self, padding=15)
        table_frame.pack(fill="both", expand=True, side="top")
        
        self.cols = ["Data", "E1", "S1", "E2", "S2", "E3", "S3", "Total", "Saldo", "Obs"]
        
        self.tree = ttk.Treeview(table_frame, columns=self.cols, show="headings", selectmode="browse")
        
        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        column_widths = {
            "Data": 100, "E1": 65, "S1": 65, "E2": 65, "S2": 65, "E3": 65, "S3": 65,
            "Total": 80, "Saldo": 80, "Obs": 140
        }
        for c in self.cols:
            self.tree.heading(c, text=c, anchor="center")
            self.tree.column(c, width=column_widths.get(c, 80), anchor="center")

        self.tree.tag_configure("positive", foreground=self.primary_dark, font=("Segoe UI", 10, "bold"))
        self.tree.tag_configure("negative", foreground=self.danger_color, font=("Segoe UI", 10, "bold"))
        self.tree.tag_configure("missing", background=self.warning_bg, foreground=self.danger_color)
        self.tree.tag_configure("in_progress", background="#E2EFDA", foreground="#375623")
        self.tree.tag_configure("normal", foreground=self.text_color)

        self.tree.bind("<Double-1>", self.on_double_click)

        self.lbl_status = ttk.Label(self, text="", font=("Segoe UI", 10, "italic"), padding=10)
        self.lbl_status.pack(fill="x", side="bottom")

    def _on_toggle_ignore_today(self):
        if self.processed_data:
            self._refresh_main_table()

    def on_double_click(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return
            
        column = self.tree.identify_column(event.x)
        item = self.tree.identify_row(event.y)
        
        col_idx = int(column[1:]) - 1
        col_name = self.cols[col_idx]
        
        if col_name in ["Data", "Total", "Saldo", "Obs"]:
            return
            
        x, y, width, height = self.tree.bbox(item, column)
        
        entry = ttk.Entry(self.tree)
        entry.insert(0, self.tree.set(item, column))
        entry.select_range(0, "end")
        entry.focus_set()
        entry.place(x=x, y=y, width=width, height=height)
        
        def save_edit(event=None):
            new_val = entry.get().strip()
            if new_val:
                try:
                    datetime.strptime(new_val, "%H:%M")
                except ValueError:
                    messagebox.showerror("Formato Inválido", "A hora deve estar no formato de 24h: HH:MM (ex: 08:30 ou 17:45).")
                    entry.destroy()
                    return
            
            self.tree.set(item, column, new_val)
            entry.destroy()

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
        self.btn_ai.config(state="disabled")
        
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
        max_horarios = max([len(m.horarios) for m in data]) if data else 0
        max_cols = max(6, max_horarios)
        if max_cols % 2 != 0:
            max_cols += 1

        cols = ["Data"]
        for i in range(1, (max_cols // 2) + 1):
            cols.extend([f"E{i}", f"S{i}"])
        cols.extend(["Total", "Saldo", "Obs"])
        
        self.cols = cols
        self.tree["columns"] = cols
        
        for c in cols:
            self.tree.heading(c, text=c, anchor="center")
            if c == "Data":
                self.tree.column(c, width=100, minwidth=80, anchor="center")
            elif c in ["Total", "Saldo"]:
                self.tree.column(c, width=80, minwidth=70, anchor="center")
            elif c == "Obs":
                self.tree.column(c, width=140, minwidth=100, anchor="center")
            else:
                self.tree.column(c, width=65, minwidth=50, anchor="center")

        today_str = datetime.now().strftime("%d/%m/%Y")
        ignore_today = self.var_ignore_today.get()

        for m in data:
            is_today = (m.data_formatada == today_str) and ignore_today
            punches = (m.horarios + [""] * max_cols)[:max_cols]
            total_str = self.exporter.format_time(m.segundos_trabalhados)
            
            if is_today:
                saldo_str = "00:00"
                obs_str = m.obs if m.obs else "EM ANDAMENTO"
                tag = "in_progress"
            else:
                saldo_str = self.exporter.format_time(m.saldo_segundos, True)
                obs_str = m.obs if m.obs else ("FALTA BATIDA" if m.is_pendencia else "")
                tag = "normal"
                if m.is_pendencia:
                    tag = "missing"
                elif m.saldo_segundos > 0:
                    tag = "positive"
                elif m.saldo_segundos < 0:
                    tag = "negative"
                
            row_vals = [m.data_formatada] + punches + [total_str, saldo_str, obs_str]
            self.tree.insert("", "end", values=row_vals, tags=(tag,))
            
        if data:
            self.btn_export.config(state="normal")
            self.btn_recalc.config(state="normal")
            self.btn_ai.config(state="normal")
            
            total_saldo_seg = sum([
                0 if (m.data_formatada == today_str and ignore_today) else m.saldo_segundos 
                for m in data
            ])
            total_dias = len(data)
            saldo_acumulado = self.exporter.format_time(total_saldo_seg, True)
            
            status_text = f"Dias carregados: {total_dias} | Saldo Acumulado no Período: {saldo_acumulado}"
            if ignore_today and any(m.data_formatada == today_str for m in data):
                status_text += " (Dia atual em andamento desconsiderado no saldo)"
            self.lbl_status.config(text=status_text, foreground=self.text_color)

    def _recalculate_tree_totals(self):
        total_saldo_seg = 0
        total_dias = 0
        today_str = datetime.now().strftime("%d/%m/%Y")
        ignore_today = self.var_ignore_today.get()
        
        num_punch_cols = len(self.cols) - 4
        new_processed = []
        
        for item in self.tree.get_children():
            values = list(self.tree.item(item, "values"))
            
            data_formatada = values[0]
            dt_obj = datetime.strptime(data_formatada, "%d/%m/%Y")
            data_id = dt_obj.strftime("%Y%m%d")
            
            punches = [values[i] for i in range(1, 1 + num_punch_cols) if values[i].strip()]
            
            day_data = {
                "data": data_id,
                "marcacoes": [{"hora": h} for h in punches]
            }
            
            m_dia = PontoEngine.process_day(day_data)
            new_processed.append(m_dia)
            
            is_today = (data_formatada == today_str) and ignore_today
            total_str = self.exporter.format_time(m_dia.segundos_trabalhados)
            
            if is_today:
                saldo_str = "00:00"
                obs_str = m_dia.obs if m_dia.obs else "EM ANDAMENTO"
                tag = "in_progress"
            else:
                saldo_str = self.exporter.format_time(m_dia.saldo_segundos, True)
                obs_str = m_dia.obs if m_dia.obs else ("FALTA BATIDA" if m_dia.is_pendencia else "")
                tag = "normal"
                if m_dia.is_pendencia:
                    tag = "missing"
                elif m_dia.saldo_segundos > 0:
                    tag = "positive"
                elif m_dia.saldo_segundos < 0:
                    tag = "negative"
                
            padded_punches = (punches + [""] * num_punch_cols)[:num_punch_cols]
            new_values = [data_formatada] + padded_punches + [total_str, saldo_str, obs_str]
            self.tree.item(item, values=new_values, tags=(tag,))
            
            if len(punches) > 0 and not is_today:
                total_saldo_seg += m_dia.saldo_segundos
                total_dias += 1
                
        self.processed_data = new_processed
        
        saldo_acumulado = self.exporter.format_time(total_saldo_seg, True)
        status_text = f"Dias recalculados: {total_dias} | Saldo Acumulado: {saldo_acumulado}"
        if ignore_today and any(m.data_formatada == today_str for m in new_processed):
            status_text += " (Dia atual desconsiderado)"
        self.lbl_status.config(text=status_text, foreground=self.text_color)
        
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
                self.exporter.generate(self.processed_data, path, ignore_today=self.var_ignore_today.get())
                messagebox.showinfo("Sucesso", "Planilha Excel gerada com sucesso!")
                os.startfile(path)
            except Exception as ex_save:
                messagebox.showerror("Erro ao Salvar", f"Não foi possível salvar a planilha:\n{ex_save}")

    def _config_ai_key(self):
        top = tk.Toplevel(self)
        top.title("Configurar Chave de IA (OpenRouter)")
        top.geometry("480x240")
        top.configure(bg=self.bg_color)
        top.transient(self)
        top.resizable(False, False)

        tk.Label(
            top, 
            text="🔑 Configuração da Chave da IA", 
            bg=self.bg_color, 
            fg=self.text_color, 
            font=("Segoe UI", 12, "bold")
        ).pack(pady=(15, 5))

        tk.Label(
            top, 
            text="Cole abaixo sua chave do OpenRouter (ex: sk-or-v1-...) para habilitar as análises avançadas de IA:", 
            bg=self.bg_color, 
            fg="#2E4E2E", 
            font=("Segoe UI", 9),
            wraplength=440,
            justify="center"
        ).pack(padx=15, pady=(0, 10))

        curr_key = IAAnalistaPonto.get_api_key()

        ent_key = ttk.Entry(top, width=50, show="*")
        if curr_key:
            ent_key.insert(0, curr_key)
        ent_key.pack(pady=(0, 15), ipady=3)

        lbl_info = tk.Label(top, text="", bg=self.bg_color, fg=self.primary_dark, font=("Segoe UI", 9, "italic"))
        lbl_info.pack(pady=(0, 5))

        def save():
            k = ent_key.get().strip()
            if k:
                keyring.set_password("DixiPontoApp", "openrouter_token", k)
                os.environ["ANTHROPIC_AUTH_TOKEN"] = k
                lbl_info.config(text="✅ Chave salva com segurança no Windows Keyring!", fg=self.primary_dark)
            else:
                try:
                    keyring.delete_password("DixiPontoApp", "openrouter_token")
                except Exception:
                    pass
                os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)
                lbl_info.config(text="ℹ️ Chave removida.", fg=self.danger_color)
            self.after(1500, top.destroy)

        btn_save = tk.Button(
            top,
            text="Salvar Chave",
            command=save,
            bg="#5CBD28",
            fg="white",
            font=("Segoe UI", 10, "bold"),
            bd=0,
            relief="flat",
            cursor="hand2",
            padx=15,
            pady=5
        )
        btn_save.pack()

    def _apply_ai_adjustments(self, ajustes: List[Dict]) -> int:
        count = 0
        for aj in ajustes:
            dt_target = str(aj.get("data", "")).strip()
            if not dt_target:
                continue
            
            for m in self.processed_data:
                if m.data_formatada == dt_target or m.data_formatada.startswith(dt_target):
                    if aj.get("abono"):
                        m.is_pendencia = False
                        m.obs = aj.get("obs", "Abonado via IA")
                        count += 1
                    elif aj.get("horarios"):
                        novos_horarios = sorted(aj["horarios"])
                        obs = aj.get("obs", "Ajustado via IA")
                        m_novo = PontoEngine.process_horarios(novos_horarios, m.data_id, m.data_formatada, obs=obs)
                        m.segundos_trabalhados = m_novo.segundos_trabalhados
                        m.saldo_segundos = m_novo.saldo_segundos
                        m.is_pendencia = m_novo.is_pendencia
                        m.horarios = m_novo.horarios
                        m.obs = obs
                        count += 1

        if count > 0:
            self._refresh_main_table()
        return count

    def _refresh_main_table(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._populate_table(self.processed_data)

    def _show_ai_analysis(self):
        if not self.processed_data:
            messagebox.showwarning("Aviso", "Nenhum dado carregado para análise.")
            return

        top = tk.Toplevel(self)
        top.title("Auditoria Inteligente por IA - Dixi Auditor")
        top.geometry("720x620")
        top.configure(bg=self.bg_color)
        top.transient(self)

        hdr_frame = ttk.Frame(top, padding=(15, 10))
        hdr_frame.pack(fill="x")

        tk.Label(
            hdr_frame, 
            text="🤖 Análise Inteligente de Ponto", 
            bg=self.bg_color, 
            fg=self.text_color, 
            font=("Segoe UI", 14, "bold")
        ).pack(side="left")

        btn_cfg = tk.Button(
            hdr_frame,
            text="🔑 Configurar Chave",
            command=self._config_ai_key,
            bg=self.primary_soft,
            fg=self.text_color,
            font=("Segoe UI", 9, "bold"),
            bd=1,
            relief="solid",
            cursor="hand2",
            padx=8,
            pady=3
        )
        btn_cfg.pack(side="right")

        txt_frame = ttk.Frame(top, padding=(15, 5, 15, 5))
        txt_frame.pack(fill="both", expand=True)

        txt = tk.Text(txt_frame, font=("Segoe UI", 10), wrap="word", bg="#FFFFFF", fg="#1E3014", relief="solid", bd=1)
        vsb = ttk.Scrollbar(txt_frame, orient="vertical", command=txt.yview)
        txt.configure(yscrollcommand=vsb.set)

        txt.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Container inferior para solicitar edições e recalcular
        edit_frame = tk.LabelFrame(top, text=" ✏️ Editar Pontos de Atenção & Recalcular ", bg=self.bg_color, fg=self.primary_color, font=("Segoe UI", 10, "bold"), padx=10, pady=8)
        edit_frame.pack(fill="x", padx=15, pady=(5, 15))

        lbl_instruct = tk.Label(
            edit_frame,
            text="Descreva as alterações desejadas nos pontos de atenção (ex: 'No dia 15/07 considere saída às 18:00 e abone o dia 10/07'):",
            bg=self.bg_color,
            fg=self.text_color,
            font=("Segoe UI", 9)
        )
        lbl_instruct.pack(anchor="w", pady=(0, 4))

        input_container = ttk.Frame(edit_frame)
        input_container.pack(fill="x")

        ent_instrucao = ttk.Entry(input_container, font=("Segoe UI", 10))
        ent_instrucao.pack(side="left", fill="x", expand=True, padx=(0, 8))

        btn_recalcular = tk.Button(
            input_container,
            text="🔄 Recalcular com IA",
            bg=self.primary_color,
            fg="#FFFFFF",
            font=("Segoe UI", 9, "bold"),
            bd=0,
            relief="flat",
            cursor="hand2",
            padx=12,
            pady=5
        )
        btn_recalcular.pack(side="right")

        lbl_status = tk.Label(edit_frame, text="", bg=self.bg_color, fg="#555555", font=("Segoe UI", 8, "italic"))
        lbl_status.pack(anchor="w", pady=(4, 0))

        def execute_analysis(custom_prompt=None):
            btn_recalcular.config(state="disabled")
            lbl_status.config(text="⏳ Processando análise e recalculando com a IA...")
            if custom_prompt:
                txt.config(state="normal")
                txt.insert("end", f"\n\n{'='*55}\n✏️ INSTRUÇÃO DE AJUSTE ENVIADA:\n\"{custom_prompt}\"\n{'='*55}\n\nRecalculando com IA...\n")
                txt.see("end")
                txt.config(state="disabled")
            else:
                txt.config(state="normal")
                txt.delete("1.0", "end")
                txt.insert("1.0", "Analisando dados do ponto com IA, aguarde alguns segundos...\n")
                txt.config(state="disabled")

            def run_thread():
                res_text, ajustes = IAAnalistaPonto.analisar_ponto(
                    self.processed_data, 
                    instrucoes_usuario=custom_prompt, 
                    ignore_today=self.var_ignore_today.get()
                )
                def update_ui():
                    txt.config(state="normal")
                    if custom_prompt:
                        txt.insert("end", f"\n🤖 NOVA ANÁLISE RECALCULADA:\n{res_text}\n")
                    else:
                        txt.delete("1.0", "end")
                        txt.insert("1.0", res_text)
                    txt.see("end")
                    txt.config(state="disabled")
                    btn_recalcular.config(state="normal")
                    
                    if ajustes:
                        modificados = self._apply_ai_adjustments(ajustes)
                        if modificados > 0:
                            lbl_status.config(text=f"✅ Análise recalculada e {modificados} dia(s) atualizado(s) na tabela principal do aplicativo!")
                        else:
                            lbl_status.config(text="✅ Análise recalculada com sucesso.")
                    else:
                        lbl_status.config(text="✅ Análise recalculada com sucesso.")
                        
                    ent_instrucao.delete(0, "end")
                self.after(0, update_ui)

            threading.Thread(target=run_thread, daemon=True).start()

        def on_recalculou():
            instrucao = ent_instrucao.get().strip()
            if not instrucao:
                messagebox.showwarning("Aviso", "Digite a instrução ou ajuste que deseja que a IA aplique no recálculo.", parent=top)
                return
            execute_analysis(instrucao)

        btn_recalcular.config(command=on_recalculou)
        ent_instrucao.bind("<Return>", lambda e: on_recalculou())

        # Executa análise inicial sem instrução prévia
        execute_analysis(None)

if __name__ == "__main__":
    AppPonto().mainloop()