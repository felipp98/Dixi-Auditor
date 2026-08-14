"""
Serviço de comunicação com a API oficial da Dixi Ponto.
"""
import logging
import requests
from typing import List, Dict, Optional, Tuple
from src.core.models import Usuario
from src.utils.security import set_secure_credential
from src.utils.colaboradores import buscar_cargo_colaborador, buscar_dados_colaborador

logger = logging.getLogger(__name__)

class DixiService:
    """Cliente HTTP da API Dixi Ponto."""

    def __init__(self, base_url: str = "https://webapiponto.dixiponto.com.br:8899"):
        self.base_url = base_url
        self.session = requests.Session()
        self.token: Optional[str] = None
        self.user_id: Optional[int] = None
        self.user_name: Optional[str] = None
        self.user_cargo: Optional[str] = None
        self.user_email: Optional[str] = None

    def authenticate(self, user: str, password: str, unidade: str = "pagare") -> Tuple[bool, Optional[Usuario], str]:
        """
        Autentica o usuário na API Dixi e armazena token de sessão.
        Retorna (sucesso, objeto_usuario, mensagem_erro).
        """
        try:
            payload = {
                "usuario": user,
                "senha": password,
                "unidade": unidade,
                "suporte": False
            }
            resp = self.session.post(f"{self.base_url}/login_", json=payload, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            if data.get("success"):
                auth_data = data.get("data", {})
                self.token = auth_data.get("token")
                user_obj = auth_data.get("usuario", {})
                func_info = user_obj.get("funcionario", {})

                self.user_id = func_info.get("idFuncionario")
                self.user_name = func_info.get("nomeFuncionario") or func_info.get("nome") or user_obj.get("nome") or user
                self.user_cargo = func_info.get("descricaoCargo") or func_info.get("cargo") or "Colaborador"
                self.user_email = func_info.get("email") or user_obj.get("email") or user

                # Busca cargo e e-mail corporativo cadastrados no Organograma / colaboradores.json
                dados_cad = buscar_dados_colaborador(self.user_name or user)
                if dados_cad:
                    if not self.user_cargo or self.user_cargo.lower() == "colaborador":
                        self.user_cargo = dados_cad.get("cargo") or self.user_cargo
                    if not self.user_email or "@" not in self.user_email:
                        self.user_email = dados_cad.get("email") or self.user_email

                self.session.headers.update({"Authorization": f"bearer {self.token}"})

                # Salva credenciais com segurança no Windows Keyring
                set_secure_credential("last_user", user)
                set_secure_credential(user, password)
                set_secure_credential("colaborador_nome", self.user_name or "")
                set_secure_credential("colaborador_cargo", self.user_cargo or "")
                set_secure_credential("colaborador_email", self.user_email or "")

                usuario = Usuario(
                    username=user,
                    nome_completo=self.user_name or "",
                    email=self.user_email or "",
                    cargo=self.user_cargo or "",
                    token_dixi=self.token or ""
                )
                return True, usuario, "Autenticado com sucesso"

            msg = data.get("message") or "Usuário ou senha incorretos."
            return False, None, msg

        except requests.exceptions.RequestException as e:
            logger.error(f"Erro de conexão com a API Dixi: {e}")
            return False, None, f"Erro de conexão: {e}"
        except Exception as e:
            logger.error(f"Erro inesperado na autenticação Dixi: {e}")
            return False, None, f"Erro inesperado: {e}"

    def fetch_history(self, start_date: str, end_date: str) -> List[Dict]:
        """
        Busca o histórico bruto de batidas do colaborador no período especificado.
        Formatos de data: 'YYYYMMDD' ou 'YYYY-MM-DD'.
        """
        if not self.token or not self.user_id:
            raise ValueError("Usuário não autenticado na API Dixi.")

        start_clean = self._sanitize_date(start_date)
        end_clean = self._sanitize_date(end_date)

        params = {
            "dataInicial": start_clean,
            "dataFinal": end_clean,
            "idRegistro": self.user_id
        }

        resp = self.session.get(f"{self.base_url}/self_/historicoPonto", params=params, timeout=25)
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", [])

    @staticmethod
    def _sanitize_date(dt_str: str) -> str:
        """Converte 'DD/MM/YYYY' para 'YYYYMMDD' se necessário."""
        dt_clean = dt_str.replace("-", "").replace("/", "")
        if len(dt_clean) == 8 and "/" in dt_str:
            parts = dt_str.split("/")
            if len(parts) == 3:
                return f"{parts[2]}{parts[1]}{parts[0]}"
        return dt_clean
