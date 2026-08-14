"""
Serviço de Auditoria e Assistente IA com suporte a modelos OpenRouter (Nemotron, Llama, DeepSeek) e reasoning.
"""
import os
import re
import json
import logging
import requests
from datetime import datetime
from typing import List, Dict, Tuple, Optional, Any

from src.core.models import MarcacaoDia
from src.utils.security import get_secure_credential
from src.utils.formatters import format_time_seconds
from src.config.constants import (
    OPENROUTER_API_BASE,
    DEFAULT_AI_MODEL
)

logger = logging.getLogger(__name__)

class AIService:
    """Serviço de análise inteligente de jornadas de trabalho via OpenRouter e heurísticas offline."""

    @classmethod
    def get_api_key(cls) -> Optional[str]:
        """Recupera a chave de API do OpenRouter salva com segurança."""
        key = get_secure_credential("openrouter_token")
        if not key:
            key = os.environ.get("OPENROUTER_API_KEY")
        return key

    @classmethod
    def get_model_name(cls) -> str:
        """Recupera o modelo configurado ou usa o Nemotron Ultra padrão."""
        saved_model = get_secure_credential("openrouter_model", "")
        if saved_model and saved_model.strip():
            return saved_model.strip()
        return os.environ.get("OPENROUTER_MODEL", DEFAULT_AI_MODEL)

    @staticmethod
    def encontrar_sugestoes_duplicadas(data: List[MarcacaoDia]) -> Tuple[List[Dict[str, Any]], str]:
        """
        Analisa offline as marcações procurando batidas duplicadas ou com intervalo <= 2 minutos.
        """
        sugestoes_ajustes = []
        texto_sugestoes = ""

        for m in data:
            if not m.horarios or len(m.horarios) < 2:
                continue

            # Caso 1: Batida exatamente idêntica
            if len(m.horarios) != len(set(m.horarios)):
                h_unicos = sorted(list(dict.fromkeys(m.horarios)))
                sugestoes_ajustes.append({
                    "data": m.data_formatada,
                    "horarios": h_unicos,
                    "obs": "Corrigido via IA: duplicação de batida removida"
                })
                texto_sugestoes += f"  • Dia {m.data_formatada}: Batida duplicada ({', '.join(m.horarios)}) -> Sugestão: remover duplicidade ({', '.join(h_unicos)})\n"
            else:
                # Caso 2: Batidas muito próximas (intervalo <= 2 min)
                cleaned = [m.horarios[0]]
                has_near_dup = False
                for h in m.horarios[1:]:
                    try:
                        t_prev = datetime.strptime(cleaned[-1], "%H:%M")
                        t_curr = datetime.strptime(h, "%H:%M")
                        diff_min = abs((t_curr - t_prev).total_seconds()) / 60
                        if diff_min <= 2:
                            has_near_dup = True
                        else:
                            cleaned.append(h)
                    except Exception:
                        cleaned.append(h)

                if has_near_dup:
                    sugestoes_ajustes.append({
                        "data": m.data_formatada,
                        "horarios": cleaned,
                        "obs": "Corrigido via IA: batidas de curto intervalo unificadas"
                    })
                    texto_sugestoes += f"  • Dia {m.data_formatada}: Batidas muito próximas ({', '.join(m.horarios)}) -> Sugestão: unificar ({', '.join(cleaned)})\n"

        return sugestoes_ajustes, texto_sugestoes

    @classmethod
    def analisar_ponto(
        cls,
        data: List[MarcacaoDia],
        api_key: Optional[str] = None,
        instrucoes_usuario: Optional[str] = None,
        ignore_today: bool = True
    ) -> Tuple[str, List[Dict[str, Any]], bool]:
        """
        Executa a análise inteligente do espelho de ponto.
        Retorna (texto_resposta, lista_ajustes, auto_enviar_justificativa).
        """
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

        saldo_str = format_time_seconds(saldo_total, show_sign=True)

        resumo_dados = f"Total de dias auditados: {total_dias}\n"
        resumo_dados += f"Saldo acumulado no período: {saldo_str}\n"
        resumo_dados += f"Dias com batida pendente/faltante: {len(dias_pendencia)}\n"
        resumo_dados += f"Dias com saldo positivo (HE): {len(dias_extras)}\n"
        resumo_dados += f"Dias com saldo negativo (atrasos): {len(dias_atraso)}\n\n"
        resumo_dados += "Detalhamento por dia:\n"

        for m in data[:31]:
            is_today = (m.data_formatada == today_str) and ignore_today
            if is_today:
                resumo_dados += f"- Data: {m.data_formatada} | Batidas: {', '.join(m.horarios)} | Trabalhado: {format_time_seconds(m.segundos_trabalhados)} | (EM ANDAMENTO - IGNORADO NO SALDO)\n"
            else:
                pend_tag = " (PENDÊNCIA)" if m.is_pendencia else ""
                resumo_dados += f"- Data: {m.data_formatada} | Batidas: {', '.join(m.horarios)} | Trabalhado: {format_time_seconds(m.segundos_trabalhados)} | Saldo: {format_time_seconds(m.saldo_segundos, True)}{pend_tag}\n"

        parsed_ajustes: List[Dict[str, Any]] = []

        if token:
            try:
                base_url = os.environ.get("OPENROUTER_BASE_URL", OPENROUTER_API_BASE)
                endpoint = f"{base_url.rstrip('/')}/chat/completions"
                model = cls.get_model_name()

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
                    )

                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "reasoning": {"enabled": True}
                }

                resp = requests.post(endpoint, json=payload, headers=headers, timeout=40)
                auto_enviar = False

                if resp.status_code == 200:
                    res_json = resp.json()
                    msg_obj = res_json["choices"][0]["message"]
                    content = msg_obj.get("content") or ""
                    
                    json_match = re.search(r'```json\s*(\{.*?\})\s*```', content, re.DOTALL)
                    if json_match:
                        try:
                            data_json = json.loads(json_match.group(1))
                            parsed_ajustes = data_json.get("ajustes", [])
                            auto_enviar = bool(data_json.get("enviar_justificativa", False))
                            content = re.sub(r'```json\s*(\{.*?\})\s*```', '', content).strip()
                        except Exception as je:
                            logger.error(f"Erro ao parsear JSON de ajustes: {je}")

                    if instrucoes_usuario and any(k in instrucoes_usuario.lower() for k in ["enviar", "envie", "gerar", "justificativa", "rh", "autentique"]):
                        auto_enviar = True

                    return content, parsed_ajustes, auto_enviar
                else:
                    logger.warning(f"OpenRouter retornou status {resp.status_code}: {resp.text}")
            except Exception as e:
                logger.error(f"Erro na API de IA: {e}")

        # Fallback offline heurístico
        sugestoes_ajustes, texto_sugestoes = cls.encontrar_sugestoes_duplicadas(data)
        analise_texto = "🔍 **Resumo da Auditoria Heurística Offline:**\n\n"
        analise_texto += f"• Total de dias no período: {total_dias}\n"
        analise_texto += f"• Saldo Total Acumulado: {saldo_str}\n"
        analise_texto += f"• Dias com Pendência de Batida: {len(dias_pendencia)}\n"
        analise_texto += f"• Dias com Horas Extras: {len(dias_extras)}\n"
        analise_texto += f"• Dias com Débito/Atraso: {len(dias_atraso)}\n\n"

        if texto_sugestoes:
            analise_texto += f"💡 **Sugestões Heurísticas de Correção:**\n{texto_sugestoes}\n"
        else:
            analise_texto += "✅ Nenhuma duplicação óbvia ou intervalo muito curto detectado.\n"

        if not token:
            analise_texto += "\n*(Configure sua chave de API nas Configurações para habilitar a IA Generativa completa.)*"

        return analise_texto, sugestoes_ajustes, False
