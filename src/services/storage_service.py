"""
Serviço de Armazenamento Local e Cache de Sessão de Ponto com Histórico Cumulativo e Mesclagem Inteligente.
"""
import os
import json
import logging
from datetime import datetime
from typing import List, Dict, Tuple, Optional, Any

from src.core.models import MarcacaoDia
from src.utils.formatters import normalize_date_to_iso

logger = logging.getLogger(__name__)

class StorageService:
    """Gerencia a persistência local em JSON e o histórico cumulativo de edições de ponto por usuário."""

    @staticmethod
    def _get_cache_dir() -> str:
        """Retorna o diretório padrão de cache local do usuário."""
        app_data = os.path.join(os.path.expanduser("~"), ".dixi_auditor")
        os.makedirs(app_data, exist_ok=True)
        return app_data

    @classmethod
    def _get_user_cache_path(cls, username: str) -> str:
        """Gera o caminho do arquivo de cache para um determinado usuário."""
        clean_user = "".join(c for c in username if c.isalnum() or c in ("_", "-")).lower()
        if not clean_user:
            clean_user = "default_user"
        return os.path.join(cls._get_cache_dir(), f"cache_{clean_user}.json")

    @classmethod
    def salvar_sessao(
        cls,
        username: str,
        data_inicio: str,
        data_fim: str,
        marcacoes: List[MarcacaoDia],
        ignorar_hoje: bool = True,
        historico_edicoes: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Salva o estado atual da sessão, marcações ativas e atualiza o histórico cumulativo de edições.
        """
        if not username:
            return False

        cache_path = cls._get_user_cache_path(username)
        try:
            # Carrega histórico existente para não perder edições de outros meses
            historico_map: Dict[str, dict] = {}
            if os.path.exists(cache_path):
                try:
                    with open(cache_path, "r", encoding="utf-8") as f:
                        old_data = json.load(f)
                        historico_map = old_data.get("historico_edicoes", {}) or {}
                except Exception:
                    historico_map = {}

            # Se foi passado um dicionário de histórico externo, mescla
            if historico_edicoes:
                for k, v in historico_edicoes.items():
                    if isinstance(v, MarcacaoDia):
                        historico_map[k] = v.to_dict()
                    elif isinstance(v, dict):
                        historico_map[k] = v

            # Adiciona/atualiza marcações editadas na sessão atual
            for m in marcacoes:
                if m.editado_manualmente:
                    iso_k = normalize_date_to_iso(m.data_id or m.data_formatada)
                    historico_map[iso_k] = m.to_dict()

            payload = {
                "username": username,
                "data_inicio": data_inicio,
                "data_fim": data_fim,
                "ignorar_hoje": ignorar_hoje,
                "timestamp_salvo": datetime.now().isoformat(),
                "total_dias": len(marcacoes),
                "total_editados": sum(1 for m in marcacoes if m.editado_manualmente),
                "marcacoes": [m.to_dict() for m in marcacoes],
                "historico_edicoes": historico_map
            }

            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)

            logger.info(f"Sessão e histórico de {username} salvos com sucesso em: {cache_path}")
            return True
        except Exception as e:
            logger.error(f"Erro ao salvar sessão local para {username}: {e}")
            return False

    @classmethod
    def carregar_sessao(cls, username: str) -> Optional[Dict[str, Any]]:
        """
        Carrega a última sessão salva do usuário e o mapa de histórico de edições acumulado.
        """
        if not username:
            return None

        cache_path = cls._get_user_cache_path(username)
        if not os.path.exists(cache_path):
            return None

        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            raw_marcacoes = data.get("marcacoes", [])
            marcacoes_obj = [MarcacaoDia.from_dict(m) for m in raw_marcacoes]
            # Garante ordenação cronológica estrita
            marcacoes_obj = sorted(marcacoes_obj, key=lambda x: normalize_date_to_iso(x.data_id or x.data_formatada))

            # Converte dicionário de histórico acumulado
            raw_hist = data.get("historico_edicoes", {}) or {}
            historico_obj_map: Dict[str, MarcacaoDia] = {}
            for k, v in raw_hist.items():
                if isinstance(v, dict):
                    historico_obj_map[k] = MarcacaoDia.from_dict(v)

            return {
                "username": data.get("username", username),
                "data_inicio": data.get("data_inicio", ""),
                "data_fim": data.get("data_fim", ""),
                "ignorar_hoje": data.get("ignorar_hoje", True),
                "timestamp_salvo": data.get("timestamp_salvo", ""),
                "total_editados": sum(1 for m in marcacoes_obj if m.editado_manualmente),
                "marcacoes": marcacoes_obj,
                "historico_edicoes": historico_obj_map
            }
        except Exception as e:
            logger.error(f"Erro ao carregar sessão local para {username}: {e}")
            return None

    @classmethod
    def salvar_edicoes_historico(cls, username: str, marcacoes_editadas: List[MarcacaoDia]) -> bool:
        """
        Salva explicitamente uma lista de dias editados no histórico cumulativo sem sobrescrever a sessão ativa.
        """
        if not username:
            return False

        cache_path = cls._get_user_cache_path(username)
        try:
            old_data = {}
            if os.path.exists(cache_path):
                try:
                    with open(cache_path, "r", encoding="utf-8") as f:
                        old_data = json.load(f)
                except Exception:
                    old_data = {}

            historico_map = old_data.get("historico_edicoes", {}) or {}
            for m in marcacoes_editadas:
                if m.editado_manualmente:
                    iso_k = normalize_date_to_iso(m.data_id or m.data_formatada)
                    historico_map[iso_k] = m.to_dict()

            old_data["username"] = username
            old_data["historico_edicoes"] = historico_map
            old_data["timestamp_salvo"] = datetime.now().isoformat()

            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(old_data, f, indent=2, ensure_ascii=False)

            logger.info(f"Histórico cumulativo de {len(marcacoes_editadas)} dia(s) salvo para {username}.")
            return True
        except Exception as e:
            logger.error(f"Erro ao salvar histórico cumulativo para {username}: {e}")
            return False

    @classmethod
    def obter_edicoes_historico(cls, username: str) -> Dict[str, MarcacaoDia]:
        """
        Retorna todo o dicionário de edições salvas no histórico do usuário {iso_date: MarcacaoDia}.
        """
        sessao = cls.carregar_sessao(username)
        if sessao and "historico_edicoes" in sessao:
            return sessao["historico_edicoes"]
        return {}

    @classmethod
    def obter_edicoes_periodo(cls, username: str, data_inicio: str, data_fim: str) -> List[MarcacaoDia]:
        """
        Retorna as edições salvas no histórico que pertencem ao intervalo cronológico [data_inicio, data_fim].
        """
        hist_map = cls.obter_edicoes_historico(username)
        if not hist_map:
            return []

        start_iso = normalize_date_to_iso(data_inicio)
        end_iso = normalize_date_to_iso(data_fim)

        edicoes_periodo = []
        for iso_k, marcacao in hist_map.items():
            if start_iso <= iso_k <= end_iso:
                edicoes_periodo.append(marcacao)

        return sorted(edicoes_periodo, key=lambda x: normalize_date_to_iso(x.data_id or x.data_formatada))

    @classmethod
    def limpar_sessao(cls, username: str) -> bool:
        """Remove o arquivo de cache salvo do usuário."""
        cache_path = cls._get_user_cache_path(username)
        if os.path.exists(cache_path):
            try:
                os.remove(cache_path)
                return True
            except Exception as e:
                logger.error(f"Erro ao limpar cache de {username}: {e}")
                return False
        return True

    @classmethod
    def mesclar_marcacoes(
        cls,
        marcacoes_anteriores: List[MarcacaoDia],
        novas_marcacoes_dixi: List[MarcacaoDia]
    ) -> Tuple[List[MarcacaoDia], int]:
        """
        Mescla inteligentemente os dados:
        - Para dias que foram editados manualmente no período anterior/histórico, mantém as edições (horários, obs, saldos).
        - Para dias não editados e dias novos, usa os dados atualizados da Dixi.
        Retorna (lista_mesclada_ordenada, total_dias_editados_preservados).
        """
        # Mapeia dias editados por ISO ID
        dias_editados_map: Dict[str, MarcacaoDia] = {
            normalize_date_to_iso(m.data_id or m.data_formatada): m
            for m in marcacoes_anteriores
            if m.editado_manualmente
        }

        mesclados_map: Dict[str, MarcacaoDia] = {}
        preservados_count = 0

        for m_dixi in novas_marcacoes_dixi:
            iso_key = normalize_date_to_iso(m_dixi.data_id or m_dixi.data_formatada)
            if iso_key in dias_editados_map:
                # Preserva a edição anterior e guarda os horários originais da Dixi como referência
                m_editado = dias_editados_map[iso_key]
                m_editado.horarios_originais = m_dixi.horarios
                mesclados_map[iso_key] = m_editado
                preservados_count += 1
            else:
                mesclados_map[iso_key] = m_dixi

        # Ordena rigorosamente pelo formato ISO YYYYMMDD
        resultado_ordenado = sorted(
            list(mesclados_map.values()),
            key=lambda x: normalize_date_to_iso(x.data_id or x.data_formatada)
        )

        return resultado_ordenado, preservados_count
