"""
Motor de processamento e regras de cálculo de jornada de trabalho (CLT, tolerância e almoço).
"""
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from src.core.models import MarcacaoDia, ResumoAuditoria
from src.config.constants import (
    JORNADA_PADRAO_DIARIA,
    TOLERANCIA_PADRAO_MINUTOS,
    INTERVALO_ALMOCO_MINIMO_MINUTOS
)

class PontoEngine:
    """Calcula intervalos, horas trabalhadas, almoço, saldo e pendências."""

    JORNADA_SEG: int = JORNADA_PADRAO_DIARIA
    TOLERANCIA_SEG: int = TOLERANCIA_PADRAO_MINUTOS * 60
    MIN_ALMOCO_SEG: int = INTERVALO_ALMOCO_MINIMO_MINUTOS * 60

    @classmethod
    def process_horarios(
        cls,
        raw_horarios: List[str],
        data_id: str,
        data_formatada: str,
        obs: str = ""
    ) -> MarcacaoDia:
        """
        Processa uma lista de horários de um determinado dia e retorna MarcacaoDia calculada.
        """
        raw_horarios = sorted(raw_horarios)
        qtd_batidas = len(raw_horarios)
        total_sec = 0

        # Processa pares de batidas (Entrada -> Saída)
        for i in range(0, qtd_batidas // 2 * 2, 2):
            try:
                h1 = datetime.strptime(raw_horarios[i], "%H:%M")
                h2 = datetime.strptime(raw_horarios[i+1], "%H:%M")
                diff_sec = (h2 - h1).total_seconds()

                if diff_sec < 0:
                    diff_sec += 24 * 3600  # Suporte a virada de turno noturno

                total_sec += int(diff_sec)
            except Exception:
                pass

        # Regra de Almoço: Se retornou antes de 1 hora (3600s), desconsidera a antecipação como hora extra
        if qtd_batidas >= 4:
            try:
                s1 = datetime.strptime(raw_horarios[1], "%H:%M")
                e2 = datetime.strptime(raw_horarios[2], "%H:%M")
                intervalo_almoco = (e2 - s1).total_seconds()

                if intervalo_almoco < 0:
                    intervalo_almoco += 24 * 3600

                if intervalo_almoco < cls.MIN_ALMOCO_SEG:
                    desconto_antecipacao = cls.MIN_ALMOCO_SEG - intervalo_almoco
                    total_sec -= int(desconto_antecipacao)
            except Exception:
                pass

        is_pendencia = (qtd_batidas % 2 != 0) or (qtd_batidas == 2)

        saldo = 0
        if total_sec > 0:
            diff = total_sec - cls.JORNADA_SEG
            if diff > 0:
                # Horas Extras: 100% integral
                saldo = diff
            elif diff < 0:
                # Débito/Atraso: aplica tolerância CLT se exceder 10 minutos
                if abs(diff) > cls.TOLERANCIA_SEG:
                    saldo = diff + cls.TOLERANCIA_SEG
                else:
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
        """Processa um dia bruto retornado pela API da Dixi."""
        raw_horarios = sorted([m["hora"] for m in day_data.get("marcacoes", [])])
        raw_data = str(day_data.get("data", ""))
        
        try:
            dt_obj = datetime.strptime(raw_data, "%Y%m%d")
            data_fmt = dt_obj.strftime("%d/%m/%Y")
        except Exception:
            data_fmt = raw_data

        return cls.process_horarios(raw_horarios, raw_data, data_fmt)

    @classmethod
    def calcular_resumo(
        cls,
        marcacoes: List[MarcacaoDia],
        ignorar_hoje: bool = True
    ) -> ResumoAuditoria:
        """Gera o resumo estatístico consolidado do período."""
        today_str = datetime.now().strftime("%d/%m/%Y")
        resumo = ResumoAuditoria()
        resumo.total_dias = len(marcacoes)

        for m in marcacoes:
            is_today = (m.data_formatada == today_str) and ignorar_hoje
            if is_today:
                continue

            if m.segundos_trabalhados > 0:
                resumo.dias_trabalhados += 1

            if m.is_pendencia:
                resumo.dias_pendencia += 1

            if m.saldo_segundos > 0:
                resumo.dias_extras += 1
            elif m.saldo_segundos < 0:
                resumo.dias_atraso += 1

            resumo.saldo_acumulado_segundos += m.saldo_segundos

        return resumo
