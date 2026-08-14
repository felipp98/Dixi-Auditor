"""
Utilitários de formatação de horários, datas e strings.
"""
from datetime import datetime
from typing import Optional

MESES_EXTENSO = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
    5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
}

DIAS_SEMANA_EXTENSO = {
    0: "SEGUNDA FEIRA",
    1: "TERÇA FEIRA",
    2: "QUARTA FEIRA",
    3: "QUINTA FEIRA",
    4: "SEXTA FEIRA",
    5: "SÁBADO",
    6: "DOMINGO"
}

def format_time_seconds(seconds: int, show_sign: bool = False) -> str:
    """
    Formata uma quantidade de segundos em formato HH:MM (ex: '+01:30', '-00:45', '08:00').
    """
    is_neg = seconds < 0
    s_abs = abs(seconds)
    hours = s_abs // 3600
    minutes = (s_abs % 3600) // 60
    
    if show_sign:
        sign = "-" if is_neg else "+"
        return f"{sign}{hours:02d}:{minutes:02d}"
    return f"{hours:02d}:{minutes:02d}"

def obter_mes_extenso(mes: int) -> str:
    """Retorna o nome do mês por extenso em português."""
    return MESES_EXTENSO.get(mes, "Julho")

def formatar_mes_competencia(mes_input: str) -> str:
    """
    Formata o mês de competência para garantir o nome por extenso.
    Exemplos: '7' -> 'Julho', '07' -> 'Julho', '07/2026' -> 'Julho / 2026', 'julho' -> 'Julho'
    """
    if not mes_input:
        return MESES_EXTENSO.get(datetime.now().month, "Janeiro")
    
    mes_str = str(mes_input).strip()
    
    if mes_str.isdigit():
        num = int(mes_str)
        if 1 <= num <= 12:
            return MESES_EXTENSO[num]
            
    if "/" in mes_str:
        partes = mes_str.split("/")
        p1 = partes[0].strip()
        if p1.isdigit():
            num = int(p1)
            if 1 <= num <= 12:
                ano = partes[1].strip() if len(partes) > 1 else ""
                return f"{MESES_EXTENSO[num]} / {ano}" if ano else MESES_EXTENSO[num]
                
    return mes_str.capitalize()

def get_dia_semana_nome(dt: datetime) -> str:
    """Retorna o dia da semana em português maiúsculo."""
    return DIAS_SEMANA_EXTENSO.get(dt.weekday(), "")

def normalize_date_to_iso(date_str: str) -> str:
    """
    Converte qualquer formato de data (DD/MM/YYYY, YYYY-MM-DD, YYYYMMDD) para YYYYMMDD para ordenação cronológica precisa.
    """
    if not date_str:
        return "00000000"
    s = str(date_str).strip()
    if "/" in s:
        parts = s.split("/")
        if len(parts) == 3:
            day, month, year = parts
            return f"{year.zfill(4)}{month.zfill(2)}{day.zfill(2)}"
    elif "-" in s:
        parts = s.split("-")
        if len(parts) == 3:
            if len(parts[0]) == 4:  # YYYY-MM-DD
                year, month, day = parts
            else:  # DD-MM-YYYY
                day, month, year = parts
            return f"{year.zfill(4)}{month.zfill(2)}{day.zfill(2)}"
    elif len(s) == 8 and s.isdigit():
        return s
    return s
