import os

import re

import json

import io

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

from PIL import Image, ImageTk

from playwright.sync_api import sync_playwright



from justificativa_service import gerar_pdf_justificativa, formatar_mes_competencia, obter_mes_extenso, enviar_email_smtp

from autentique_service import enviar_justificativa_autentique



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

        self.user_name: Optional[str] = None

        self.user_cargo: Optional[str] = None



    def authenticate(self, user: str, password: str) -> bool:

        try:

            resp = self.session.post(f"{self.base_url}/login_", json={

                "usuario": user, "senha": password, "unidade": "pagare", "suporte": False

            }, timeout=15)

            resp.raise_for_status()

            data = resp.json()

            if data.get("success"):

                self.token = data["data"]["token"]

                user_obj = data["data"].get("usuario", {})

                func_info = user_obj.get("funcionario", {})

                self.user_id = func_info.get("idFuncionario")

                self.user_name = func_info.get("nomeFuncionario") or func_info.get("nome") or user_obj.get("nome") or user

                self.user_cargo = func_info.get("descricaoCargo") or func_info.get("cargo") or "Colaborador"

                self.user_email = func_info.get("email") or user_obj.get("email") or user

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
                saldo = diff



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

                        "  ],\n"

                        "  \"enviar_justificativa\": true\n"

                        "}\n"

                        "```\n"

                        "Nota: Inclua \"enviar_justificativa\": true apenas se o usuário solicitar enviar, gerar ou encaminhar a justificativa/folha para o RH/Autentique."

                    )

                payload = {

                    "model": model,

                    "messages": [{"role": "user", "content": prompt}],

                    "temperature": 0.3

                }

                resp = requests.post(endpoint, json=payload, headers=headers, timeout=20)

                auto_enviar = False

                if resp.status_code == 200:

                    res_json = resp.json()

                    content = res_json["choices"][0]["message"]["content"]

                    json_match = re.search(r'```json\s*(\{.*?\})\s*```', content, re.DOTALL)

                    if json_match:

                        try:

                            data_json = json.loads(json_match.group(1))

                            parsed_ajustes = data_json.get("ajustes", [])

                            auto_enviar = bool(data_json.get("enviar_justificativa", False))

                            content = re.sub(r'```json\s*(\{.*?\})\s*```', '', content).strip()

                        except Exception as je:

                            logging.error(f"Erro ao parsear JSON de ajustes: {je}")

                    

                    # Checagem por palavra-chave se o usuário pediu envio

                    if instrucoes_usuario and any(k in instrucoes_usuario.lower() for k in ["enviar", "envie", "gerar", "justificativa", "rh", "autentique"]):

                        auto_enviar = True



                    return content, parsed_ajustes, auto_enviar

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



        auto_enviar = False

        if instrucoes_usuario and any(k in instrucoes_usuario.lower() for k in ["enviar", "envie", "gerar", "justificativa", "rh", "autentique"]):

            auto_enviar = True



        return fallback, parsed_ajustes, auto_enviar



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

        self.geometry("460x640")

        self.service = DixiService()

        self.exporter = ExcelExporter()

        self.processed_data: List[MarcacaoDia] = []

        

        # Configuração de Estilo Visual

        self.style = ttk.Style()

        self.style.theme_use("clam")

        

        self.bg_color = "#F6F9F1"

        self.surface_color = "#FFFFFF"

        self.primary_color = "#ACC320"

        self.primary_dark = "#8A9D18"

        self.primary_soft = "#EFF7D9"

        self.text_color = "#16311A"

        self.muted_text_color = "#5D7058"

        self.border_color = "#DDE7CF"

        self.danger_color = "#C0392B"

        self.warning_bg = "#FFF1CC"

        self.logo_image = None

        self.logo_title_image = None

        self.logo_brand_image = None

        

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



        self._load_brand_assets()

        

        self._init_login_ui()



    def _find_logo_path(self) -> Optional[str]:

        base_dir = os.path.dirname(os.path.abspath(__file__))

        candidates = [

            os.path.join(base_dir, "assets", "icons", "logo.svg"),

            os.path.join(os.path.dirname(base_dir), "assets", "icons", "logo.svg"),

            os.path.join(base_dir, "assets", "icons", "logo-pagare.svg"),

            os.path.join(os.path.dirname(base_dir), "assets", "icons", "logo-pagare.svg"),

            os.path.join(base_dir, "assets", "icons", "logo_pagare.svg"),

            os.path.join(os.path.dirname(base_dir), "assets", "icons", "logo_pagare.svg"),

        ]

        for path in candidates:

            if os.path.exists(path):

                return path

        return None



    def _load_brand_assets(self):

        logo_path = self._find_logo_path()

        if not logo_path:

            return



        try:

            with open(logo_path, "r", encoding="utf-8") as svg_file:

                svg_markup = svg_file.read()



            with sync_playwright() as p:

                browser = p.chromium.launch(headless=True)

                page = browser.new_page(viewport={"width": 1920, "height": 1080, "device_scale_factor": 2})

                page.set_content(

                    f"""

                    <html>

                        <body style="margin:0; background:transparent; display:flex; align-items:center; justify-content:center;">

                            {svg_markup}

                        </body>

                    </html>

                    """

                )

                svg_bytes = page.locator("svg").screenshot(omit_background=True)

                browser.close()



            logo = Image.open(io.BytesIO(svg_bytes)).convert("RGBA")

            symbol_logo = logo.crop((0, 280, 520, 860))

            self.logo_title_image = ImageTk.PhotoImage(symbol_logo.resize((28, 28), Image.LANCZOS))

            self.logo_brand_image = ImageTk.PhotoImage(logo.resize((100, 60), Image.LANCZOS))

            self.logo_image = self.logo_brand_image

            self.iconphoto(True, self.logo_title_image)

        except Exception as exc:

            logging.error(f"Erro ao carregar logo: {exc}")



    def _set_entry_focus_state(self, shell: tk.Frame, focused: bool):

        shell.configure(

            highlightbackground=self.primary_color if focused else self.border_color,

            highlightcolor=self.primary_color if focused else self.border_color,

            bg="#FFFFFF" if focused else "#F8FBF2"

        )



    def _build_login_input(self, parent: tk.Frame, label_text: str, show: Optional[str] = None) -> tk.Entry:

        field_group = tk.Frame(parent, bg=self.surface_color)

        field_group.pack(fill="x", pady=(0, 10))



        tk.Label(

            field_group,

            text=label_text,

            bg=self.surface_color,

            fg=self.text_color,

            font=("Segoe UI", 9, "bold")

        ).pack(anchor="w", pady=(0, 4))



        field_shell = tk.Frame(

            field_group,

            bg="#F8FBF2",

            highlightbackground=self.border_color,

            highlightcolor=self.primary_color,

            highlightthickness=1,

            bd=0

        )

        field_shell.pack(fill="x")



        entry = tk.Entry(

            field_shell,

            font=("Segoe UI", 11),

            bg="#F8FBF2",

            fg=self.text_color,

            insertbackground=self.text_color,

            relief="flat",

            bd=0,

            highlightthickness=0,

            show=show

        )

        entry.pack(fill="x", padx=12, pady=9)

        entry.bind("<FocusIn>", lambda _e: self._set_entry_focus_state(field_shell, True))

        entry.bind("<FocusOut>", lambda _e: self._set_entry_focus_state(field_shell, False))

        return entry



    def _bind_button_hover(self, button: tk.Button):

        button.bind("<Enter>", lambda _e: button.config(bg=self.primary_dark))

        button.bind("<Leave>", lambda _e: button.config(bg=self.primary_color))



    def _set_login_button_state(self, loading: bool):

        if not hasattr(self, "btn_login"):

            return



        self.btn_login.config(

            state="disabled" if loading else "normal",

            text="Conectando..." if loading else "Entrar no painel"

        )



    def _render_login_brand(self, parent: tk.Frame):

        brand_frame = tk.Frame(parent, bg=self.primary_soft, highlightthickness=0, bd=0)

        brand_frame.pack(fill="x")



        tk.Label(

            brand_frame,

            text="GESTÃO INTELIGENTE DE PONTO",

            bg="#DCEFB6",

            fg=self.primary_dark,

            font=("Segoe UI", 8, "bold"),

            padx=12,

            pady=6

        ).pack(anchor="center", pady=(0, 2))



        if self.logo_brand_image:

            tk.Label(

                brand_frame,

                image=self.logo_brand_image,

                bg=self.primary_soft

            ).pack(anchor="center", pady=(0, 2))



        tk.Label(

            brand_frame,

            text="Dixi Auditor",

            bg=self.primary_soft,

            fg=self.text_color,

            font=("Segoe UI", 20, "bold")

        ).pack(anchor="center")



        tk.Label(

            brand_frame,

            text="Consulta, revisão e exportação do espelho de ponto em uma experiência mais clara, rápida e confiável.",

            bg=self.primary_soft,

            fg=self.muted_text_color,

            font=("Segoe UI", 8),

            wraplength=260,

            justify="center"

        ).pack(anchor="center", pady=(6, 0))



    def _init_login_ui(self):

        self.geometry("360x620")

        self.frame = tk.Frame(self, bg=self.bg_color)

        self.frame.pack(expand=True, fill="both")



        backdrop = tk.Canvas(self.frame, bg=self.bg_color, highlightthickness=0, bd=0)

        backdrop.place(relx=0, rely=0, relwidth=1, relheight=1)

        backdrop.create_oval(-60, -40, 180, 130, fill="#E6F3C8", outline="")

        backdrop.create_oval(220, -20, 420, 120, fill="#EDF7D8", outline="")

        backdrop.create_oval(210, 290, 430, 510, fill="#E0F0BA", outline="")



        content = tk.Frame(self.frame, bg=self.bg_color, padx=16, pady=12)

        content.pack(expand=True, fill="both")



        hero_panel = tk.Frame(content, bg=self.primary_soft, bd=0, highlightthickness=0)

        hero_panel.pack(fill="x", pady=(0, 8))



        tk.Frame(hero_panel, bg=self.primary_color, height=4).pack(fill="x")



        hero_body = tk.Frame(hero_panel, bg=self.primary_soft, padx=14, pady=12)

        hero_body.pack(fill="x")

        self._render_login_brand(hero_body)



        login_card = tk.Frame(

            content,

            bg=self.surface_color,

            padx=16,

            pady=14,

            highlightbackground=self.border_color,

            highlightthickness=1,

            bd=0

        )

        login_card.pack(fill="x")



        tk.Label(

            login_card,

            text="Acessar conta",

            bg=self.surface_color,

            fg=self.text_color,

            font=("Segoe UI", 15, "bold")

        ).pack(anchor="center")



        tk.Label(

            login_card,

            text="Entre com suas credenciais da Dixi para continuar no painel.",

            bg=self.surface_color,

            fg=self.muted_text_color,

            font=("Segoe UI", 8),

            wraplength=250,

            justify="center"

        ).pack(anchor="center", pady=(3, 10))



        self.ent_user = self._build_login_input(login_card, "Usuário")

        self.ent_pass = self._build_login_input(login_card, "Senha", show="*")



        last_user = keyring.get_password("DixiPontoApp", "last_user")

        if last_user:

            self.ent_user.insert(0, last_user)

            last_pw = keyring.get_password("DixiPontoApp", last_user)

            if last_pw:

                self.ent_pass.insert(0, last_pw)



        self.btn_login = tk.Button(

            login_card,

            text="Entrar no painel",

            command=self._do_login,

            bg=self.primary_color,

            fg="white",

            activebackground=self.primary_dark,

            activeforeground="white",

            font=("Segoe UI", 10, "bold"),

            bd=0,

            relief="flat",

            cursor="hand2",

            padx=14,

            pady=8

        )

        self.btn_login.pack(fill="x", pady=(2, 8))

        self._bind_button_hover(self.btn_login)



        footer = tk.Frame(login_card, bg=self.surface_color)

        footer.pack(fill="x", pady=(0, 0))



        tk.Label(

            footer,

            text="Ambiente protegido",

            bg=self.surface_color,

            fg=self.text_color,

            font=("Segoe UI", 8, "bold")

        ).pack(anchor="center")



        tk.Label(

            footer,

            text="Consulta de ponto, justificativas e exportações com acesso autenticado.",

            bg=self.surface_color,

            fg=self.muted_text_color,

            font=("Segoe UI", 7),

            wraplength=250,

            justify="center"

        ).pack(anchor="center", pady=(2, 0))



        self.ent_user.focus_set()

        return



        hero_panel = tk.Frame(self.frame, bg=self.primary_soft, bd=0, highlightthickness=0)

        hero_panel.pack(fill="x", pady=(0, 18))



        tk.Frame(hero_panel, bg=self.primary_color, height=4).pack(fill="x")



        hero_body = tk.Frame(hero_panel, bg=self.primary_soft, padx=22, pady=22)

        hero_body.pack(fill="x")

        self._render_login_brand(hero_body)



        login_card = tk.Frame(

            self.frame,

            bg=self.surface_color,

            padx=24,

            pady=24,

            highlightbackground=self.border_color,

            highlightthickness=1,

            bd=0

        )

        login_card.pack(fill="x")



        tk.Label(

            login_card,

            text="Entrar",

            bg=self.surface_color,

            fg=self.text_color,

            font=("Segoe UI", 18, "bold")

        ).pack(anchor="w")



        tk.Label(

            login_card,

            text="Use o mesmo acesso da Dixi para continuar.",

            bg=self.surface_color,

            fg=self.muted_text_color,

            font=("Segoe UI", 10)

        ).pack(anchor="w", pady=(4, 18))



        self.ent_user = self._build_login_input(login_card, "Usuário")

        self.ent_pass = self._build_login_input(login_card, "Senha", show="*")



        last_user = keyring.get_password("DixiPontoApp", "last_user")

        if last_user:

            self.ent_user.insert(0, last_user)

            last_pw = keyring.get_password("DixiPontoApp", last_user)

            if last_pw:

                self.ent_pass.insert(0, last_pw)



        self.btn_login = tk.Button(

            login_card,

            text="Conectar",

            command=self._do_login,

            bg=self.primary_color,

            fg="white",

            activebackground=self.primary_dark,

            activeforeground="white",

            font=("Segoe UI", 11, "bold"),

            bd=0,

            relief="flat",

            cursor="hand2",

            padx=18,

            pady=12

        )

        self.btn_login.pack(fill="x", pady=(6, 12))

        self._bind_button_hover(self.btn_login)



        tk.Label(

            login_card,

            text="Ambiente protegido para consulta de ponto, justificativas e exportações.",

            bg=self.surface_color,

            fg=self.muted_text_color,

            font=("Segoe UI", 9),

            wraplength=340,

            justify="center"

        ).pack(pady=(2, 0))

        return

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

        self._set_login_button_state(True)

        

        def run():

            if self.service.authenticate(u, p):

                self.after(0, self._init_main_ui)

            else:

                self.after(0, lambda: messagebox.showerror("Erro", "Falha no Login"))

                self.after(0, lambda: self._set_login_button_state(False))

        

        threading.Thread(target=run, daemon=True).start()



    def _init_main_ui(self):

        return self._init_main_ui_modern()



    def _init_main_ui_modern(self):

        for w in self.winfo_children():

            w.destroy()



        self.geometry("1220x760")

        self.configure(bg=self.bg_color)



        self.style.configure(

            "Treeview",

            background="#FFFFFF",

            foreground=self.text_color,

            fieldbackground="#FFFFFF",

            rowheight=28,

            font=("Segoe UI", 10)

        )

        self.style.configure(

            "Treeview.Heading",

            background=self.primary_soft,

            foreground=self.text_color,

            font=("Segoe UI", 10, "bold")

        )



        shell = tk.Frame(self, bg=self.bg_color, padx=18, pady=18)

        shell.pack(fill="both", expand=True)



        header_card = tk.Frame(

            shell,

            bg=self.surface_color,

            padx=22,

            pady=18,

            highlightbackground=self.border_color,

            highlightthickness=1,

            bd=0

        )

        header_card.pack(fill="x", pady=(0, 14))



        header_top = tk.Frame(header_card, bg=self.surface_color)

        header_top.pack(fill="x")



        header_left = tk.Frame(header_top, bg=self.surface_color)

        header_left.pack(side="left", fill="x", expand=True)



        tk.Label(

            header_left,

            text="Dixi Auditor",

            bg=self.surface_color,

            fg=self.text_color,

            font=("Segoe UI", 20, "bold")

        ).pack(anchor="w")



        tk.Label(

            header_left,

            text="Visualize, recalcule e exporte o espelho de ponto em um fluxo mais claro.",

            bg=self.surface_color,

            fg=self.muted_text_color,

            font=("Segoe UI", 10)

        ).pack(anchor="w", pady=(4, 0))



        user_name = self.service.user_name or "Colaborador"

        user_role = self.service.user_cargo or "Acesso autenticado"



        badge = tk.Frame(header_top, bg=self.primary_soft, padx=14, pady=10)

        badge.pack(side="right")



        tk.Label(

            badge,

            text=user_name,

            bg=self.primary_soft,

            fg=self.text_color,

            font=("Segoe UI", 10, "bold")

        ).pack(anchor="e")



        tk.Label(

            badge,

            text=user_role,

            bg=self.primary_soft,

            fg=self.primary_dark,

            font=("Segoe UI", 9)

        ).pack(anchor="e", pady=(2, 0))



        controls_card = tk.Frame(

            shell,

            bg=self.surface_color,

            padx=20,

            pady=18,

            highlightbackground=self.border_color,

            highlightthickness=1,

            bd=0

        )

        controls_card.pack(fill="x", pady=(0, 14))



        filters_row = tk.Frame(controls_card, bg=self.surface_color)

        filters_row.pack(fill="x", pady=(0, 14))



        actions_row = tk.Frame(controls_card, bg=self.surface_color)

        actions_row.pack(fill="x")



        now = datetime.now()

        current_year = str(now.year)

        current_month = f"{now.month:02d}"

        current_day = f"{now.day:02d}"



        period_card = tk.Frame(filters_row, bg="#F8FBF2", padx=14, pady=12)

        period_card.pack(side="left", fill="x", expand=True)



        tk.Label(

            period_card,

            text="Período de análise",

            bg="#F8FBF2",

            fg=self.text_color,

            font=("Segoe UI", 10, "bold")

        ).pack(anchor="w", pady=(0, 8))



        period_inputs = tk.Frame(period_card, bg="#F8FBF2")

        period_inputs.pack(anchor="w")



        start_group = tk.Frame(period_inputs, bg="#F8FBF2")

        start_group.pack(side="left", padx=(0, 18))



        tk.Label(start_group, text="Data Início", bg="#F8FBF2", fg=self.muted_text_color, font=("Segoe UI", 9)).pack(anchor="w")

        self.cal_i = DateSelector(start_group, default_day="01", default_month=current_month, default_year=current_year)

        self.cal_i.pack(anchor="w", pady=(3, 0))



        end_group = tk.Frame(period_inputs, bg="#F8FBF2")

        end_group.pack(side="left")



        tk.Label(end_group, text="Data Fim", bg="#F8FBF2", fg=self.muted_text_color, font=("Segoe UI", 9)).pack(anchor="w")

        self.cal_f = DateSelector(end_group, default_day=current_day, default_month=current_month, default_year=current_year)

        self.cal_f.pack(anchor="w", pady=(3, 0))



        prefs_card = tk.Frame(filters_row, bg=self.primary_soft, padx=14, pady=12)

        prefs_card.pack(side="left", padx=(12, 0))



        tk.Label(

            prefs_card,

            text="Preferências",

            bg=self.primary_soft,

            fg=self.text_color,

            font=("Segoe UI", 10, "bold")

        ).pack(anchor="w", pady=(0, 8))



        self.var_ignore_today = tk.BooleanVar(value=True)

        self.chk_ignore_today = ttk.Checkbutton(

            prefs_card,

            text="Ignorar dia atual (em andamento)",

            variable=self.var_ignore_today,

            command=self._on_toggle_ignore_today

        )

        self.chk_ignore_today.pack(anchor="w")



        tk.Label(

            actions_row,

            text="Ações",

            bg=self.surface_color,

            fg=self.text_color,

            font=("Segoe UI", 10, "bold")

        ).pack(anchor="w", pady=(0, 8))



        action_buttons = tk.Frame(actions_row, bg=self.surface_color)

        action_buttons.pack(fill="x")



        self.btn_buscar = ttk.Button(action_buttons, text="Visualizar Ponto", command=self._fetch_and_display)

        self.btn_buscar.pack(side="left", padx=(0, 8))



        self.btn_recalc = ttk.Button(action_buttons, text="Recalcular Ponto", command=self._recalculate_tree_totals, state="disabled")

        self.btn_recalc.pack(side="left", padx=(0, 8))



        self.btn_export = ttk.Button(action_buttons, text="Exportar Excel", command=self._export_excel, state="disabled")

        self.btn_export.pack(side="left", padx=(0, 8))



        self.btn_ai = ttk.Button(action_buttons, text="Análise por IA", command=self._show_ai_analysis, state="disabled")

        self.btn_ai.pack(side="left", padx=(0, 8))



        self.btn_key = ttk.Button(action_buttons, text="Chave IA", command=self._config_ai_key)

        self.btn_key.pack(side="left", padx=(0, 8))



        self.btn_justificativa = ttk.Button(action_buttons, text="Enviar Justificativa RH", command=self._abrir_modal_justificativa, state="disabled")

        self.btn_justificativa.pack(side="left")



        table_card = tk.Frame(

            shell,

            bg=self.surface_color,

            padx=16,

            pady=16,

            highlightbackground=self.border_color,

            highlightthickness=1,

            bd=0

        )

        table_card.pack(fill="both", expand=True)



        table_header = tk.Frame(table_card, bg=self.surface_color)

        table_header.pack(fill="x", pady=(0, 10))



        tk.Label(

            table_header,

            text="Espelho de ponto",

            bg=self.surface_color,

            fg=self.text_color,

            font=("Segoe UI", 12, "bold")

        ).pack(anchor="w")



        tk.Label(

            table_header,

            text="Edite batidas com duplo clique, selecione dias e acompanhe os saldos em tempo real.",

            bg=self.surface_color,

            fg=self.muted_text_color,

            font=("Segoe UI", 9)

        ).pack(anchor="w", pady=(3, 0))



        table_frame = ttk.Frame(table_card)

        table_frame.pack(fill="both", expand=True)



        self.cols = ["Sel", "Data", "E1", "S1", "E2", "S2", "E3", "S3", "Total", "Saldo", "Obs"]

        self.tree = ttk.Treeview(table_frame, columns=self.cols, show="headings", selectmode="extended")



        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)

        hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)

        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)



        self.tree.grid(row=0, column=0, sticky="nsew")

        vsb.grid(row=0, column=1, sticky="ns")

        hsb.grid(row=1, column=0, sticky="ew")



        table_frame.grid_rowconfigure(0, weight=1)

        table_frame.grid_columnconfigure(0, weight=1)



        column_widths = {

            "Sel": 45, "Data": 105, "E1": 70, "S1": 70, "E2": 70, "S2": 70, "E3": 70, "S3": 70,

            "Total": 85, "Saldo": 85, "Obs": 180

        }

        self.var_main_sel_all = True



        def _toggle_sel_all_main():

            self.var_main_sel_all = not self.var_main_sel_all

            mark = "[☑]" if self.var_main_sel_all else "[☐]"

            self.tree.heading("Sel", text=f"Sel {mark}")

            for child in self.tree.get_children():

                vals = list(self.tree.item(child, "values"))

                if vals:

                    vals[0] = mark

                    self.tree.item(child, values=vals)



        for c in self.cols:

            if c == "Sel":

                self.tree.heading(c, text="Sel [☑]", command=_toggle_sel_all_main, anchor="center")

            else:

                self.tree.heading(c, text=c, anchor="center")

            self.tree.column(c, width=column_widths.get(c, 80), minwidth=40 if c == "Sel" else 50, stretch=False, anchor="center")



        def _on_tree_click(event):

            region = self.tree.identify_region(event.x, event.y)

            if region == "cell":

                col = self.tree.identify_column(event.x)

                if col == "#1":

                    item = self.tree.identify_row(event.y)

                    if item:

                        vals = list(self.tree.item(item, "values"))

                        if vals:

                            vals[0] = "[☐]" if vals[0] == "[☑]" else "[☑]"

                            self.tree.item(item, values=vals)



        self.tree.bind("<Button-1>", _on_tree_click)



        def _on_tree_hscroll(event):

            if self.tree.winfo_exists():

                self.tree.xview_scroll(int(-1 * (event.delta / 120)), "units")



        self.tree.bind("<Shift-MouseWheel>", _on_tree_hscroll)

        self.tree.bind("<Double-1>", self.on_double_click)



        self.tree.tag_configure("positive", foreground=self.primary_dark, font=("Segoe UI", 10, "bold"))

        self.tree.tag_configure("negative", foreground=self.danger_color, font=("Segoe UI", 10, "bold"))

        self.tree.tag_configure("missing", background=self.warning_bg, foreground=self.danger_color)

        self.tree.tag_configure("in_progress", background="#E2EFDA", foreground="#375623")

        self.tree.tag_configure("normal", foreground=self.text_color)



        self.lbl_status = tk.Label(

            table_frame,

            text="Dias carregados: 0 | Saldo Acumulado no Período: +00:00",

            bg=self.surface_color,

            fg=self.muted_text_color,

            font=("Segoe UI", 10, "italic"),

            anchor="w"

        )

        self.lbl_status.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))



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

        

        if col_name in ["Sel", "Data", "Total", "Saldo", "Obs"]:

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



        cols = ["Sel", "Data"]

        for i in range(1, (max_cols // 2) + 1):

            cols.extend([f"E{i}", f"S{i}"])

        cols.extend(["Total", "Saldo", "Obs"])

        

        self.var_main_sel_all = True



        def _toggle_sel_all_main():

            self.var_main_sel_all = not getattr(self, "var_main_sel_all", True)

            mark = "[☑]" if self.var_main_sel_all else "[☐]"

            self.tree.heading("Sel", text=f"Sel {mark}")

            for child in self.tree.get_children():

                vals = list(self.tree.item(child, "values"))

                if vals:

                    vals[0] = mark

                    self.tree.item(child, values=vals)



        for c in cols:

            if c == "Sel":

                self.tree.heading(c, text="Sel [☑]", command=_toggle_sel_all_main, anchor="center")

                self.tree.column(c, width=45, minwidth=40, stretch=False, anchor="center")

            elif c == "Data":

                self.tree.column(c, width=105, minwidth=80, stretch=False, anchor="center")

            elif c in ["Total", "Saldo"]:

                self.tree.column(c, width=85, minwidth=70, stretch=False, anchor="center")

            elif c == "Obs":

                self.tree.column(c, width=180, minwidth=100, stretch=False, anchor="center")

            else:

                self.tree.column(c, width=70, minwidth=50, stretch=False, anchor="center")



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

                

            tem_ajuste = bool(obs_str or any([p for p in punches if p]))

            sel_str = "[☑]" if tem_ajuste else "[☐]"

            row_vals = [sel_str, m.data_formatada] + punches + [total_str, saldo_str, obs_str]

            self.tree.insert("", "end", values=row_vals, tags=(tag,))

            

        if data:

            self.btn_export.config(state="normal")

            self.btn_recalc.config(state="normal")

            self.btn_ai.config(state="normal")

            self.btn_justificativa.config(state="normal")

            

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

        try:

            total_saldo_seg = 0

            total_dias = 0

            today_str = datetime.now().strftime("%d/%m/%Y")

            ignore_today = self.var_ignore_today.get()

            

            has_sel = ("Sel" in self.cols)

            offset = 1 if has_sel else 0

            num_punch_cols = len(self.cols) - (5 if has_sel else 4)

            new_processed = []

            

            for item in self.tree.get_children():

                values = list(self.tree.item(item, "values"))

                if not values:

                    continue

                

                sel_val = values[0] if has_sel else "[☑]"

                data_formatada = str(values[offset])

                try:

                    dt_obj = datetime.strptime(data_formatada, "%d/%m/%Y")

                    data_id = dt_obj.strftime("%Y%m%d")

                except Exception:

                    continue

                

                punches = [str(values[i]).strip() for i in range(1 + offset, 1 + offset + num_punch_cols) if i < len(values) and str(values[i]).strip()]

                

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

                new_values = ([sel_val] if has_sel else []) + [data_formatada] + padded_punches + [total_str, saldo_str, obs_str]

                self.tree.item(item, values=new_values, tags=(tag,))

                

                if len(punches) > 0 and not is_today:

                    total_saldo_seg += m_dia.saldo_segundos

                    total_dias += 1

                    

            self.processed_data = new_processed

            

            saldo_acumulado = self.exporter.format_time(total_saldo_seg, True)

            status_text = f"🔄 Ponto Recalculado! Dias: {total_dias} | Saldo Acumulado: {saldo_acumulado}"

            if ignore_today and any(m.data_formatada == today_str for m in new_processed):

                status_text += " (Dia atual desconsiderado)"

            self.lbl_status.config(text=status_text, foreground=self.primary_dark)

            messagebox.showinfo("Recálculo Concluído", f"Ponto recalculado com sucesso para {total_dias} dias!\n\nSaldo Acumulado no Período: {saldo_acumulado}", parent=self)

        except Exception as ex:

            logging.error(f"Erro ao recalcular ponto: {ex}")

            messagebox.showerror("Erro de Recálculo", f"Falha ao recalcular o ponto:\n{ex}", parent=self)



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

                res_text, ajustes, auto_enviar = IAAnalistaPonto.analisar_ponto(

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



                    if auto_enviar:

                        lbl_status.config(text="🚀 IA abrindo formulário de Justificativa para o RH...")

                        self.after(600, self._abrir_modal_justificativa)

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



    def _abrir_modal_justificativa(self):

        top = tk.Toplevel(self)

        top.title("✍️ Enviar Justificativa de Ponto (Autentique / E-mail)")

        top.geometry("720x800")

        top.minsize(680, 600)

        top.transient(self)

        top.grab_set()



        try:

            def safe_keyring_get(key, default=""):

                try:

                    return keyring.get_password("DixiPontoApp", key) or default

                except Exception as ex_k:

                    logging.error(f"Erro no keyring get {key}: {ex_k}")

                    return default



            saved_token = safe_keyring_get("autentique_token")

            saved_gestor_email = safe_keyring_get("gestor_email")

            saved_rh_email = safe_keyring_get("rh_email")

            saved_colab_email = safe_keyring_get("colaborador_email")

            saved_gestor_nome = safe_keyring_get("gestor_nome", "Gestor Imediato")
            saved_rh_nome = safe_keyring_get("rh_nome", "Recursos Humanos")
            saved_auto_sign = safe_keyring_get("auto_assinar_colab", "1") != "0"
            saved_sig_img = safe_keyring_get("colab_signature_img_path", "")

            saved_pos_visivel = safe_keyring_get("autentique_pos_visivel", "1") != "0"
            saved_pos_preset = safe_keyring_get("autentique_pos_preset", "Sobre a Linha Verde (Y: 68%)")
            saved_colab_x = safe_keyring_get("autentique_colab_x", "10")
            saved_colab_y = safe_keyring_get("autentique_colab_y", "68")
            saved_colab_z = safe_keyring_get("autentique_colab_z", "1")
            saved_gestor_x = safe_keyring_get("autentique_gestor_x", "42")
            saved_gestor_y = safe_keyring_get("autentique_gestor_y", "68")
            saved_gestor_z = safe_keyring_get("autentique_gestor_z", "1")
            saved_rh_x = safe_keyring_get("autentique_rh_x", "73")
            saved_rh_y = safe_keyring_get("autentique_rh_y", "68")
            saved_rh_z = safe_keyring_get("autentique_rh_z", "1")



            dixi_srv = getattr(self, "service", None) or getattr(self, "dixi", None)

            dixi_user_email = getattr(dixi_srv, "user_email", "") if dixi_srv else ""

            colab_email_default = dixi_user_email or saved_colab_email



            colab_nome_default = getattr(dixi_srv, "user_name", "") if dixi_srv else ""

            colab_nome_default = colab_nome_default or "Colaborador"



            colab_cargo_default = ""



            try:

                dt_ini = self.cal_i.get_date()

                mes_comp_default = obter_mes_extenso(dt_ini.month)

            except Exception:

                mes_comp_default = obter_mes_extenso(datetime.now().month)



            data_solic_default = datetime.now().strftime("%d/%m/%Y")



            # Rodapé Fixo (Botões de Ação)

            bottom_bar = ttk.Frame(top, padding=(15, 10))

            bottom_bar.pack(side="bottom", fill="x")



            lbl_status = ttk.Label(bottom_bar, text="", font=("Segoe UI", 9, "bold"))

            lbl_status.pack(anchor="w", pady=(0, 4))



            btn_frame = ttk.Frame(bottom_bar)

            btn_frame.pack(fill="x")



            # Container Principal Rolável (Formulário)

            main_container = ttk.Frame(top)

            main_container.pack(side="top", fill="both", expand=True)



            canvas_modal = tk.Canvas(main_container, highlightthickness=0)

            vsb_modal = ttk.Scrollbar(main_container, orient="vertical", command=canvas_modal.yview)

            frame = ttk.Frame(canvas_modal, padding=15)



            canvas_modal_win = canvas_modal.create_window((0, 0), window=frame, anchor="nw")

            canvas_modal.configure(yscrollcommand=vsb_modal.set)



            canvas_modal.bind("<Configure>", lambda e: canvas_modal.itemconfig(canvas_modal_win, width=e.width))

            frame.bind("<Configure>", lambda e: canvas_modal.configure(scrollregion=canvas_modal.bbox("all")))



            canvas_modal.pack(side="left", fill="both", expand=True)

            vsb_modal.pack(side="right", fill="y")



            lbl_top = ttk.Label(frame, text="Formulário de Justificativa de Ponto para o RH", font=("Segoe UI", 11, "bold"))

            lbl_top.pack(anchor="w", pady=(0, 10))



            # Seção 1: Dados do Colaborador

            sec_colab = ttk.LabelFrame(frame, text=" 👤 Dados do Colaborador ", padding=10)

            sec_colab.pack(fill="x", pady=(0, 8))

            sec_colab.columnconfigure(1, weight=1)

            sec_colab.columnconfigure(3, weight=1)



            ttk.Label(sec_colab, text="Colaborador:").grid(row=0, column=0, sticky="w", pady=3)

            ent_colab = ttk.Entry(sec_colab, width=28)

            ent_colab.insert(0, colab_nome_default)

            ent_colab.grid(row=0, column=1, sticky="ew", pady=3, padx=(5, 15))



            ttk.Label(sec_colab, text="Função / Cargo:").grid(row=0, column=2, sticky="w", pady=3)

            ent_cargo = ttk.Entry(sec_colab, width=24)

            ent_cargo.insert(0, colab_cargo_default)

            ent_cargo.grid(row=0, column=3, sticky="ew", pady=3, padx=(5, 0))



            ttk.Label(sec_colab, text="Mês Competência:").grid(row=1, column=0, sticky="w", pady=3)

            ent_mes = ttk.Entry(sec_colab, width=28)

            ent_mes.insert(0, mes_comp_default)

            ent_mes.grid(row=1, column=1, sticky="ew", pady=3, padx=(5, 15))



            ttk.Label(sec_colab, text="Data Solicitação:").grid(row=1, column=2, sticky="w", pady=3)

            ent_data_solic = ttk.Entry(sec_colab, width=24)

            ent_data_solic.insert(0, data_solic_default)

            ent_data_solic.grid(row=1, column=3, sticky="ew", pady=3, padx=(5, 0))



            ttk.Label(sec_colab, text="E-mail Colaborador:").grid(row=2, column=0, sticky="w", pady=3)

            ent_colab_email = ttk.Entry(sec_colab, width=28)

            ent_colab_email.insert(0, colab_email_default)

            ent_colab_email.grid(row=2, column=1, sticky="ew", pady=3, padx=(5, 15))



            ttk.Label(sec_colab, text="Papel no Documento:").grid(row=2, column=2, sticky="w", pady=3)

            combo_colab_role = ttk.Combobox(sec_colab, values=["Assinar", "Testemunha", "Aprovar"], state="readonly", width=18)

            combo_colab_role.set("Assinar")

            combo_colab_role.grid(row=2, column=3, sticky="ew", pady=3, padx=(5, 0))



            # Seção 2: Aprovadores e Destinatários

            sec_aprov = ttk.LabelFrame(frame, text=" 👔 Aprovadores (Gestão / RH) ", padding=10)

            sec_aprov.pack(fill="x", pady=(0, 8))

            sec_aprov.columnconfigure(1, weight=1)

            sec_aprov.columnconfigure(3, weight=1)



            ttk.Label(sec_aprov, text="Nome do Gestor:").grid(row=0, column=0, sticky="w", pady=3)

            ent_gestor_nome = ttk.Entry(sec_aprov, width=28)

            ent_gestor_nome.insert(0, saved_gestor_nome)

            ent_gestor_nome.grid(row=0, column=1, sticky="ew", pady=3, padx=(5, 15))



            ttk.Label(sec_aprov, text="E-mail do Gestor:").grid(row=0, column=2, sticky="w", pady=3)

            ent_gestor_email = ttk.Entry(sec_aprov, width=24)

            ent_gestor_email.insert(0, saved_gestor_email)

            ent_gestor_email.grid(row=0, column=3, sticky="ew", pady=3, padx=(5, 0))



            ttk.Label(sec_aprov, text="Papel do Gestor:").grid(row=1, column=0, sticky="w", pady=3)

            combo_gestor_role = ttk.Combobox(sec_aprov, values=["Assinar", "Testemunha", "Aprovar"], state="readonly", width=18)

            combo_gestor_role.set("Assinar")

            combo_gestor_role.grid(row=1, column=1, sticky="ew", pady=3, padx=(5, 15))



            ttk.Label(sec_aprov, text="Nome do RH:").grid(row=2, column=0, sticky="w", pady=3)

            ent_rh_nome = ttk.Entry(sec_aprov, width=28)

            ent_rh_nome.insert(0, saved_rh_nome)

            ent_rh_nome.grid(row=2, column=1, sticky="ew", pady=3, padx=(5, 15))



            ttk.Label(sec_aprov, text="E-mail do RH:").grid(row=2, column=2, sticky="w", pady=3)

            ent_rh_email = ttk.Entry(sec_aprov, width=24)

            ent_rh_email.insert(0, saved_rh_email)

            ent_rh_email.grid(row=2, column=3, sticky="ew", pady=3, padx=(5, 0))



            ttk.Label(sec_aprov, text="Papel do RH:").grid(row=3, column=0, sticky="w", pady=3)

            combo_rh_role = ttk.Combobox(sec_aprov, values=["Assinar", "Testemunha", "Aprovar"], state="readonly", width=18)

            combo_rh_role.set("Assinar")

            combo_rh_role.grid(row=3, column=1, sticky="ew", pady=3, padx=(5, 15))



            ttk.Label(sec_aprov, text="Token Autentique:").grid(row=3, column=2, sticky="w", pady=3)

            ent_token = ttk.Entry(sec_aprov, width=24, show="*")

            ent_token.insert(0, saved_token)

            ent_token.grid(row=3, column=3, sticky="ew", pady=3, padx=(5, 0))



            # Seção 2.5: Signatários Adicionais / Testemunhas Extras

            sec_extras = ttk.LabelFrame(frame, text=" 👥 Signatários Adicionais / Testemunhas Extras ", padding=8)

            sec_extras.pack(fill="x", pady=(0, 8))



            extras_container = ttk.Frame(sec_extras)

            extras_container.pack(fill="x", expand=True)



            lista_widgets_extras = []



            def adicionar_signatario_extra(nome="", email="", papel="Assinar"):

                row_ex = ttk.Frame(extras_container)

                row_ex.pack(fill="x", pady=2)



                ttk.Label(row_ex, text="Nome:").pack(side="left", padx=(0, 2))

                ent_ex_nome = ttk.Entry(row_ex, width=18)

                ent_ex_nome.insert(0, nome)

                ent_ex_nome.pack(side="left", padx=(0, 8))



                ttk.Label(row_ex, text="E-mail:").pack(side="left", padx=(0, 2))

                ent_ex_email = ttk.Entry(row_ex, width=22)

                ent_ex_email.insert(0, email)

                ent_ex_email.pack(side="left", padx=(0, 8))



                ttk.Label(row_ex, text="Papel:").pack(side="left", padx=(0, 2))

                cb_ex_papel = ttk.Combobox(row_ex, values=["Assinar", "Testemunha", "Aprovar"], state="readonly", width=12)

                cb_ex_papel.set(papel)

                cb_ex_papel.pack(side="left", padx=(0, 8))



                item_dict = {"frame": row_ex, "nome": ent_ex_nome, "email": ent_ex_email, "papel": cb_ex_papel}



                def remover():

                    row_ex.destroy()

                    if item_dict in lista_widgets_extras:

                        lista_widgets_extras.remove(item_dict)



                btn_del = ttk.Button(row_ex, text="❌", width=3, command=remover)

                btn_del.pack(side="left")



                lista_widgets_extras.append(item_dict)



            btn_add_extra = ttk.Button(sec_extras, text="➕ Adicionar Signatário Extra", command=lambda: adicionar_signatario_extra())
            btn_add_extra.pack(anchor="w", pady=(2, 0))



            # Seletor com checkboxes dos dias para o RH

            sel_hdr_frame = ttk.Frame(frame)

            sel_hdr_frame.pack(fill="x", pady=(6, 4))



            ttk.Label(sel_hdr_frame, text="📅 Selecione os dias com ajuste para a Justificativa:", font=("Segoe UI", 9, "bold")).pack(side="left")

            lbl_count = ttk.Label(sel_hdr_frame, text="(0 dias)", font=("Segoe UI", 9, "bold"), foreground="#15803d")

            lbl_count.pack(side="left", padx=(6, 0))



            var_master_select = tk.BooleanVar(value=False)



            def atualizar_contador():

                qtd = sum(1 for d in lista_dias_vars if d["var"].get())

                lbl_count.config(text=f"({qtd} {'dia selecionado' if qtd == 1 else 'dias selecionados'})")



            def toggle_master_select():

                val = var_master_select.get()

                for d in lista_dias_vars:

                    d["var"].set(val)

                atualizar_contador()



            chk_master = ttk.Checkbutton(sel_hdr_frame, text="Selecionar / Desmarcar Todos", variable=var_master_select, command=toggle_master_select)

            chk_master.pack(side="right")



            chk_container = ttk.Frame(frame)

            chk_container.pack(fill="both", expand=True, pady=(0, 8))



            canvas_chk = tk.Canvas(chk_container, height=160, bg="#ffffff", highlightthickness=1, highlightbackground="#a5d6a7")

            vsb_chk = ttk.Scrollbar(chk_container, orient="vertical", command=canvas_chk.yview)

            scroll_frame = ttk.Frame(canvas_chk)



            canvas_window = canvas_chk.create_window((0, 0), window=scroll_frame, anchor="nw")



            scroll_frame.bind(

                "<Configure>",

                lambda e: canvas_chk.configure(scrollregion=canvas_chk.bbox("all"))

            )

            canvas_chk.bind(

                "<Configure>",

                lambda e: canvas_chk.itemconfig(canvas_window, width=e.width)

            )



            canvas_chk.configure(yscrollcommand=vsb_chk.set)



            # Scroll da roda do mouse (MouseWheel)

            def _on_mousewheel(event):

                if canvas_chk.winfo_exists():

                    canvas_chk.yview_scroll(int(-1 * (event.delta / 120)), "units")



            def _bind_mw(e):

                canvas_chk.bind_all("<MouseWheel>", _on_mousewheel)



            def _unbind_mw(e):

                canvas_chk.unbind_all("<MouseWheel>")



            canvas_chk.bind("<Enter>", _bind_mw)

            canvas_chk.bind("<Leave>", _unbind_mw)



            def _on_modal_close():

                try:

                    canvas_chk.unbind_all("<MouseWheel>")

                except Exception:

                    pass

                top.destroy()



            top.protocol("WM_DELETE_WINDOW", _on_modal_close)



            canvas_chk.pack(side="left", fill="both", expand=True)

            vsb_chk.pack(side="right", fill="y")



            dias_semana_map = ["SEGUNDA-FEIRA", "TERÇA-FEIRA", "QUARTA-FEIRA", "QUINTA-FEIRA", "SEXTA-FEIRA", "SÁBADO / DOMINGO"]

            lista_dias_vars = []



            checked_items = [c for c in self.tree.get_children() if self.tree.item(c)["values"] and str(self.tree.item(c)["values"][0]) == "[☑]"]

            selected_items = list(set(self.tree.selection()))

            target_items = checked_items if checked_items else selected_items

            has_user_filter = len(target_items) > 0



            for child in self.tree.get_children():

                if has_user_filter and child not in target_items:

                    continue



                vals = self.tree.item(child)["values"]

                if not vals:

                    continue



                if str(vals[0]) in ["[☑]", "[☐]"]:

                    dt = str(vals[1])

                    punches = vals[2:-3] if len(vals) >= 5 else []

                    obs = str(vals[-1]) if len(vals) > 0 else ""

                else:

                    dt = str(vals[0])

                    punches = vals[1:-3] if len(vals) >= 4 else []

                    obs = str(vals[-1]) if len(vals) > 0 else ""



                try:

                    dt_obj = datetime.strptime(dt, "%d/%m/%Y")

                    w = dt_obj.weekday()

                    dia_sem = dias_semana_map[w] if w < 5 else "SÁBADO / DOMINGO"

                except Exception:

                    dia_sem = "DIA DE TRABALHO"



                e1 = punches[0] if len(punches) > 0 else ""

                s1 = punches[1] if len(punches) > 1 else ""

                e2 = punches[2] if len(punches) > 2 else ""

                s2 = punches[3] if len(punches) > 3 else ""

                e3 = punches[4] if len(punches) > 4 else ""

                s3 = punches[5] if len(punches) > 5 else ""



                tem_ajuste = bool(obs or any([e1, s1, e2, s2, e3, s3]))



                v_chk = tk.BooleanVar(value=tem_ajuste)



                row_item = ttk.Frame(scroll_frame)

                row_item.pack(fill="x", expand=True, padx=6, pady=4)



                txt_lbl = f"{dt} ({dia_sem})"

                chk_btn = ttk.Checkbutton(row_item, text=txt_lbl, variable=v_chk, command=atualizar_contador)

                chk_btn.pack(side="left", anchor="w")



                lbl_motivo = ttk.Label(row_item, text="Motivo:")

                lbl_motivo.pack(side="left", padx=(12, 4))



                var_motivo = tk.StringVar(value=obs or "Ajuste de horário")

                ent_motivo = ttk.Entry(row_item, textvariable=var_motivo, width=35)

                ent_motivo.pack(side="left", fill="x", expand=True, padx=(0, 6))



                lista_dias_vars.append({

                    "var": v_chk,

                    "dia_semana": dia_sem,

                    "data": dt,

                    "e1": e1, "s1": s1, "e2": e2, "s2": s2, "e3": e3, "s3": s3,

                    "var_motivo": var_motivo

                })



            atualizar_contador()



            # Seção 3: Justificativa Geral
            sec_just = ttk.LabelFrame(frame, text=" 📝 Justificativa Geral / Observações adicionais para o RH (Opcional) ", padding=8)
            sec_just.pack(fill="x", pady=(0, 6))

            txt_justificativa_geral = tk.Text(sec_just, height=3, font=("Segoe UI", 9), wrap="word")
            txt_justificativa_geral.pack(fill="x", pady=2)

            lbl_status = ttk.Label(frame, text="", font=("Segoe UI", 9, "bold"))
            lbl_status.pack(anchor="w", pady=2)

            def extrair_itens_tabela():
                resultado = []
                for d in lista_dias_vars:
                    if d["var"].get():
                        resultado.append({
                            "dia_semana": d["dia_semana"],
                            "data": d["data"],
                            "e1": d["e1"], "s1": d["s1"], "e2": d["e2"], "s2": d["s2"], "e3": d["e3"], "s3": d["s3"],
                            "motivo": d["var_motivo"].get().strip() or "Ajuste de horário"
                        })
                # Se nada foi marcado individualmente, envia todos os dias carregados para não bloquear
                if not resultado and lista_dias_vars:
                    for d in lista_dias_vars:
                        resultado.append({
                            "dia_semana": d["dia_semana"],
                            "data": d["data"],
                            "e1": d["e1"], "s1": d["s1"], "e2": d["e2"], "s2": d["s2"], "e3": d["e3"], "s3": d["s3"],
                            "motivo": d["var_motivo"].get().strip() or "Ajuste de horário"
                        })
                return resultado



            def visualizar_pdf_teste():

                colab_nome = ent_colab.get().strip() or "Colaborador"

                cargo = ent_cargo.get().strip()

                if not cargo:

                    messagebox.showerror("Campo Obrigatório", "Por favor, informe a Função / Cargo do Colaborador.", parent=top)

                    return

                mes_comp = formatar_mes_competencia(ent_mes.get().strip())

                dt_solic = ent_data_solic.get().strip()

                gestor_nome = ent_gestor_nome.get().strip() or "Gestor"

                rh_nome = ent_rh_nome.get().strip() or "RH"

                just_geral_texto = txt_justificativa_geral.get("1.0", "end-1c").strip()



                lbl_status.config(text="⏳ Gerando visualização do PDF de teste...", foreground="#0284c7")



                def run_preview():

                    try:

                        itens = extrair_itens_tabela()

                        if not itens:

                            def warn_no_items():

                                messagebox.showwarning("Aviso", "Selecione pelo menos um dia na lista para gerar a justificativa.", parent=top)

                                lbl_status.config(text="")

                            self.after(0, warn_no_items)

                            return



                        pdf_file = os.path.join(os.path.expanduser("~"), f"Justificativa_Ponto_TESTE_{mes_comp}.pdf")

                        gerar_pdf_justificativa(
                            colaborador_nome=colab_nome,
                            colaborador_funcao=cargo,
                            mes_competencia_str=mes_comp,
                            data_solicitacao=dt_solic,
                            justificativa_geral=just_geral_texto,
                            gestor_nome=gestor_nome,
                            rh_nome=rh_nome,
                            itens_ponto=itens,
                            output_pdf_path=pdf_file,
                            auto_assinar_colaborador=False
                        )

                        

                        def open_file():

                            lbl_status.config(text="✅ PDF de Teste gerado e aberto!", foreground="#16a34a")

                            try:

                                os.startfile(pdf_file)

                            except Exception:

                                messagebox.showinfo("PDF Gerado", f"PDF de teste salvo com sucesso em:\n{pdf_file}", parent=top)



                        self.after(0, open_file)

                    except Exception as ex:

                        err = str(ex)

                        def update_err():

                            lbl_status.config(text=f"❌ Erro ao gerar PDF: {err}", foreground="#dc2626")

                        self.after(0, update_err)



                threading.Thread(target=run_preview, daemon=True).start()



            def disparar_teste_email():

                colab_email = ent_colab_email.get().strip()

                if not colab_email:

                    messagebox.showerror("Erro", "Informe o seu e-mail no campo 'E-mail Colaborador'.", parent=top)

                    return



                itens = extrair_itens_tabela()

                if not itens:

                    messagebox.showwarning("Aviso", "Selecione pelo menos um dia na lista para enviar a justificativa.", parent=top)

                    return

                

                colab_nome = ent_colab.get().strip() or "Colaborador"

                cargo = ent_cargo.get().strip() or "Cargo"

                mes_comp = formatar_mes_competencia(ent_mes.get().strip())

                dt_solic = ent_data_solic.get().strip()

                gestor_nome = ent_gestor_nome.get().strip() or "Gestor"

                rh_nome = ent_rh_nome.get().strip() or "RH"

                just_geral_texto = txt_justificativa_geral.get("1.0", "end-1c").strip()



                dlg_email = tk.Toplevel(top)

                dlg_email.title("📧 Teste de Envio por E-mail (SMTP)")

                dlg_email.geometry("450x380")

                dlg_email.transient(top)

                dlg_email.grab_set()



                p_frame = ttk.Frame(dlg_email, padding=15)

                p_frame.pack(fill="both", expand=True)



                saved_host = safe_keyring_get("smtp_host", "smtp.office365.com")



                ttk.Label(p_frame, text="Configuração de Envio por E-mail", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 8))



                preset_frame = ttk.Frame(p_frame)

                preset_frame.pack(fill="x", pady=(0, 8))

                ttk.Label(preset_frame, text="Provedor:").pack(side="left", padx=(0, 5))



                def aplicar_preset(host, port):

                    ent_smtp_host.delete(0, "end")

                    ent_smtp_host.insert(0, host)

                    ent_smtp_port.delete(0, "end")

                    ent_smtp_port.insert(0, port)



                ttk.Button(preset_frame, text="Outlook / Hotmail", command=lambda: aplicar_preset("smtp.office365.com", "587")).pack(side="left", padx=(0, 5))

                ttk.Button(preset_frame, text="Gmail", command=lambda: aplicar_preset("smtp.gmail.com", "587")).pack(side="left")



                g_frame = ttk.Frame(p_frame)

                g_frame.pack(fill="x", pady=5)



                ttk.Label(g_frame, text="Servidor SMTP:").grid(row=0, column=0, sticky="w", pady=3)

                ent_smtp_host = ttk.Entry(g_frame, width=28)

                ent_smtp_host.insert(0, saved_host)

                ent_smtp_host.grid(row=0, column=1, sticky="w", pady=3, padx=5)



                ttk.Label(g_frame, text="Porta SMTP:").grid(row=1, column=0, sticky="w", pady=3)

                ent_smtp_port = ttk.Entry(g_frame, width=10)

                ent_smtp_port.insert(0, safe_keyring_get("smtp_port", "587"))

                ent_smtp_port.grid(row=1, column=1, sticky="w", pady=3, padx=5)



                ttk.Label(g_frame, text="E-mail Remetente:").grid(row=2, column=0, sticky="w", pady=3)

                ent_smtp_user = ttk.Entry(g_frame, width=28)

                ent_smtp_user.insert(0, safe_keyring_get("smtp_user", colab_email))

                ent_smtp_user.grid(row=2, column=1, sticky="w", pady=3, padx=5)



                ttk.Label(g_frame, text="Senha de App:").grid(row=3, column=0, sticky="w", pady=3)

                ent_smtp_pass = ttk.Entry(g_frame, width=28, show="*")

                ent_smtp_pass.insert(0, safe_keyring_get("smtp_pass", ""))

                ent_smtp_pass.grid(row=3, column=1, sticky="w", pady=3, padx=5)



                lbl_email_status = ttk.Label(p_frame, text="", font=("Segoe UI", 9, "bold"))

                lbl_email_status.pack(anchor="w", pady=5)



                def enviar_smtp_confirm():

                    h = ent_smtp_host.get().strip()

                    p_str = ent_smtp_port.get().strip() or "587"

                    u = ent_smtp_user.get().strip()

                    pwd = ent_smtp_pass.get().strip()



                    if not h or not u or not pwd:

                        messagebox.showerror("Erro", "Preencha o servidor, e-mail e senha de SMTP.", parent=dlg_email)

                        return



                    try:

                        keyring.set_password("DixiPontoApp", "smtp_host", h)

                        keyring.set_password("DixiPontoApp", "smtp_port", p_str)

                        keyring.set_password("DixiPontoApp", "smtp_user", u)

                        keyring.set_password("DixiPontoApp", "smtp_pass", pwd)

                    except Exception:

                        pass



                    lbl_email_status.config(text="⏳ Gerando PDF e enviando e-mail...", foreground="#0284c7")



                    def run_smtp_async():

                        try:

                            pdf_file = os.path.join(os.path.expanduser("~"), f"Justificativa_Ponto_TESTE_{mes_comp}.pdf")

                            gerar_pdf_justificativa(
                                colaborador_nome=colab_nome,
                                colaborador_funcao=cargo,
                                mes_competencia_str=mes_comp,
                                data_solicitacao=dt_solic,
                                justificativa_geral=just_geral_texto,
                                gestor_nome=gestor_nome,
                                rh_nome=rh_nome,
                                itens_ponto=itens,
                                output_pdf_path=pdf_file,
                                auto_assinar_colaborador=False
                            )



                            enviar_email_smtp(

                                smtp_server=h,

                                smtp_port=int(p_str),

                                remetente_email=u,

                                remetente_senha=pwd,

                                destinatario_email=colab_email,

                                assunto=f"[TESTE] Justificativa de Ponto - {colab_nome} ({mes_comp})",

                                corpo_texto=f"Olá {colab_nome},\n\nSegue em anexo a Justificativa de Ponto em formato PDF referente ao mês de {mes_comp}.\n\nAtenciosamente,\nDixi Auditor",

                                caminho_pdf=pdf_file

                            )



                            def update_smtp_success():

                                lbl_email_status.config(text="✅ E-mail enviado com sucesso!", foreground="#16a34a")

                                messagebox.showinfo("Sucesso", f"E-mail de teste com o PDF em anexo enviado para:\n{colab_email}", parent=dlg_email)

                                dlg_email.destroy()



                            self.after(0, update_smtp_success)

                        except Exception as ex_smtp:

                            err_s = str(ex_smtp)

                            def update_smtp_err():

                                lbl_email_status.config(text=f"❌ Erro ao enviar: {err_s}", foreground="#dc2626")

                            self.after(0, update_smtp_err)



                    threading.Thread(target=run_smtp_async, daemon=True).start()



                ttk.Button(p_frame, text="📧 Confirmar e Enviar E-mail", command=enviar_smtp_confirm).pack(fill="x", pady=10)



            def disparar_envio_autentique():

                token = ent_token.get().strip()

                colab_nome = ent_colab.get().strip()

                colab_email = ent_colab_email.get().strip()

                cargo = ent_cargo.get().strip()

                if not cargo:

                    messagebox.showerror("Campo Obrigatório", "Por favor, informe a Função / Cargo do Colaborador.", parent=top)

                    return

                if not token:

                    messagebox.showerror("Erro", "Por favor, preencha o Token da API do Autentique.", parent=top)

                    return

                mes_comp = formatar_mes_competencia(ent_mes.get().strip())

                dt_solic = ent_data_solic.get().strip()

                gestor_nome = ent_gestor_nome.get().strip()

                gestor_email = ent_gestor_email.get().strip()

                rh_nome = ent_rh_nome.get().strip()

                rh_email = ent_rh_email.get().strip()

                just_geral_texto = txt_justificativa_geral.get("1.0", "end-1c").strip()



                if not colab_email or not gestor_email or not rh_email:

                    messagebox.showerror("Erro", "Por favor, informe os e-mails do Colaborador, Gestor e RH.", parent=top)

                    return



                itens = extrair_itens_tabela()

                if not itens:

                    messagebox.showwarning("Aviso", "Selecione pelo menos um dia na lista para enviar a justificativa.", parent=top)

                    return



                try:
                    keyring.set_password("DixiPontoApp", "autentique_token", token)
                    keyring.set_password("DixiPontoApp", "colaborador_email", colab_email)
                    keyring.set_password("DixiPontoApp", "gestor_email", gestor_email)
                    keyring.set_password("DixiPontoApp", "rh_email", rh_email)
                    keyring.set_password("DixiPontoApp", "gestor_nome", gestor_nome)
                    keyring.set_password("DixiPontoApp", "rh_nome", rh_nome)
                except Exception:
                    pass

                btn_autentique.config(state="disabled")
                lbl_status.config(text="⏳ Gerando documento PDF e enviando para o Autentique...", foreground="#0284c7")

                def run_async():
                    try:
                        pdf_file = os.path.join(os.path.expanduser("~"), f"Justificativa_Ponto_{mes_comp}.pdf")

                        gerar_pdf_justificativa(
                            colaborador_nome=colab_nome,
                            colaborador_funcao=cargo,
                            mes_competencia_str=mes_comp,
                            data_solicitacao=dt_solic,
                            justificativa_geral=just_geral_texto,
                            gestor_nome=gestor_nome,
                            rh_nome=rh_nome,
                            itens_ponto=itens,
                            output_pdf_path=pdf_file,
                            auto_assinar_colaborador=False
                        )

                        action_map = {
                            "Assinar": "SIGN",
                            "Testemunha": "SIGN_AS_A_WITNESS",
                            "Aprovar": "APPROVE"
                        }

                        sig_colab = {
                            "email": colab_email,
                            "action": action_map.get(combo_colab_role.get(), "SIGN"),
                            "positions": [{"x": 10.0, "y": 78.0, "z": 1, "element": "SIGNATURE", "scale": 0.85}]
                        }

                        sig_gestor = {
                            "email": gestor_email,
                            "action": action_map.get(combo_gestor_role.get(), "SIGN"),
                            "positions": [{"x": 42.0, "y": 78.0, "z": 1, "element": "SIGNATURE", "scale": 0.85}]
                        }

                        sig_rh = {
                            "email": rh_email,
                            "action": action_map.get(combo_rh_role.get(), "SIGN"),
                            "positions": [{"x": 73.0, "y": 78.0, "z": 1, "element": "SIGNATURE", "scale": 0.85}]
                        }

                        lista_signatarios = [sig_colab, sig_gestor, sig_rh]



                        for w_ex in lista_widgets_extras:

                            ex_e = w_ex["email"].get().strip()

                            ex_p = action_map.get(w_ex["papel"].get(), "SIGN")

                            if ex_e:

                                lista_signatarios.append({

                                    "email": ex_e,

                                    "action": ex_p

                                })



                        res = enviar_justificativa_autentique(

                            token=token,

                            caminho_pdf=pdf_file,

                            nome_documento=f"Justificativa de Ponto - {colab_nome} ({mes_comp})",

                            lista_signatarios=lista_signatarios

                        )



                        def update_success():

                            lbl_status.config(text="✅ Documento enviado com sucesso ao Autentique!", foreground="#16a34a")

                            messagebox.showinfo("Sucesso", f"Justificativa enviada com sucesso para assinatura de {colab_email}, {gestor_email} e {rh_email}!", parent=top)

                            top.destroy()



                        self.after(0, update_success)



                    except Exception as ex:

                        err_msg = str(ex)

                        def update_error():

                            lbl_status.config(text=f"❌ Erro ao enviar: {err_msg}", foreground="#dc2626")

                            btn_autentique.config(state="normal")

                        self.after(0, update_error)



                threading.Thread(target=run_async, daemon=True).start()



            btn_frame = ttk.Frame(bottom_bar)

            btn_frame.pack(fill="x")



            btn_preview = ttk.Button(btn_frame, text="👁️ Gerar e Visualizar PDF", command=visualizar_pdf_teste)

            btn_preview.pack(side="left", fill="x", expand=True, padx=(0, 10))



            btn_autentique = ttk.Button(btn_frame, text="🚀 Enviar via Autentique", command=disparar_envio_autentique)

            btn_autentique.pack(side="left", fill="x", expand=True)



        except Exception as top_err:

            logging.error(f"Erro ao inicializar janela de justificativa: {top_err}")

            top.destroy()

if __name__ == "__main__":

    AppPonto().mainloop()



