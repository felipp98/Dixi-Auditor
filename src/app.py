"""
Controlador Principal da Aplicação (AppController).
Orquestra o ciclo de vida do Tkinter, navegação de telas, restauração de sessões e comunicação com os serviços.
"""
import os
import sys

# Garante que a raiz do projeto esteja no sys.path para resolução do pacote 'src'
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import logging
import tkinter as tk
from tkinter import messagebox
from typing import Optional, List

from src.config.logging_config import setup_logging
from src.core.models import Usuario, MarcacaoDia
from src.core.state import AppState
from src.core.ponto_engine import PontoEngine
from src.services.dixi_service import DixiService
from src.services.storage_service import StorageService
from src.ui.theme import enable_high_dpi, apply_theme
from src.ui.views.login_view import LoginView
from src.ui.views.main_view import MainView
from src.utils.paths import get_icon_path
from src.utils.formatters import normalize_date_to_iso
from src.utils.threading_utils import run_async_task

logger = logging.getLogger(__name__)

class App(tk.Tk):
    """Janela principal e orquestrador do Dixi Auditor."""

    def __init__(self):
        # 1. Habilita DPI Awareness antes de criar a janela
        enable_high_dpi()
        super().__init__()

        # 2. Configurações Iniciais da Janela (Tamanho compacto de Login)
        self.title("Dixi Auditor - Pagare")
        self.geometry("740x490")
        self.minsize(700, 460)

        # Centraliza a janela na tela
        self._center_window(740, 490)

        # Configura Ícone da Janela
        icon_path = get_icon_path("PAGARE.ico")
        if os.path.exists(icon_path):
            try:
                self.iconbitmap(icon_path)
            except Exception:
                pass

        # 3. Inicializa Tema, Estado e Serviços
        apply_theme(self)
        self.app_state = AppState()
        self.dixi_service = DixiService()

        # Containers de View
        self.current_view: Optional[tk.Frame] = None

        # Trata o fechamento gracioso da janela
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Exibe a tela de login inicial
        self.show_login_view()

    def _center_window(self, width: int, height: int):
        """Centraliza a janela na tela do monitor."""
        try:
            self.update_idletasks()
            screen_w = self.winfo_screenwidth()
            screen_h = self.winfo_screenheight()
            x = (screen_w - width) // 2
            y = (screen_h - height) // 2
            self.geometry(f"{width}x{height}+{x}+{y}")
        except Exception:
            pass

    def show_login_view(self):
        """Exibe a tela de login compacta."""
        if self.current_view:
            self.current_view.destroy()

        try:
            self.state("normal")
        except Exception:
            pass

        self.geometry("740x490")
        self.minsize(700, 460)
        self._center_window(740, 490)

        self.current_view = LoginView(self, on_login_submit=self.handle_login)
        self.current_view.pack(fill="both", expand=True)

    def show_main_view(self):
        """Exibe a tela principal do auditor maximizada e verifica restauração de sessão."""
        if self.current_view:
            self.current_view.destroy()

        self.minsize(980, 620)
        try:
            self.state("zoomed")  # Maximiza a janela no Windows
        except Exception:
            self.geometry("1220x760")
            self._center_window(1220, 760)

        main_v = MainView(
            self,
            app_state=self.app_state,
            on_fetch_ponto=self.handle_fetch_ponto,
            on_logout=self.handle_logout
        )
        self.current_view = main_v
        self.current_view.pack(fill="both", expand=True)

        # Verifica se existe sessão salva para o usuário logado
        if self.app_state.usuario and self.app_state.usuario.username:
            u_name = self.app_state.usuario.username
            self.after(200, lambda: self._verificar_restauracao_sessao(u_name, main_v))

    def _verificar_restauracao_sessao(self, username: str, main_view: MainView):
        """Pergunta ao usuário se deseja restaurar os dados salvos da última sessão."""
        cached_data = StorageService.carregar_sessao(username)
        if not cached_data or not cached_data.get("marcacoes"):
            return

        dt_ini = cached_data.get("data_inicio", "")
        dt_fim = cached_data.get("data_fim", "")
        tot_editados = cached_data.get("total_editados", 0)
        ign_hoje = cached_data.get("ignorar_hoje", True)
        marcacoes_salvas = cached_data.get("marcacoes", [])

        msg = (
            f"Encontramos dados salvos da sua última sessão de trabalho:\n"
            f"📅 Período: {dt_ini} até {dt_fim}\n"
        )
        if tot_editados > 0:
            msg += f"✨ Com {tot_editados} dia(s) com alterações manuais salvas.\n\n"
        else:
            msg += f"📊 Com {len(marcacoes_salvas)} dia(s) carregados.\n\n"
        msg += "Deseja restaurar as últimas alterações salvas desta sessão?"

        if messagebox.askyesno("Restaurar Sessão Salva?", msg):
            self.app_state.data_inicio = dt_ini
            self.app_state.data_fim = dt_fim
            self.app_state.ignorar_hoje = ign_hoje
            self.app_state.set_marcacoes(marcacoes_salvas)
            main_view.set_period_dates(dt_ini, dt_fim, ign_hoje)

    def handle_login(self, user: str, pwd: str):
        """Executa a autenticação assíncrona na Dixi."""
        def worker():
            return self.dixi_service.authenticate(user, pwd)

        def on_success(result):
            success, usuario, message = result
            if success and usuario:
                self.app_state.set_usuario(usuario)
                self.show_main_view()
            else:
                if isinstance(self.current_view, LoginView):
                    self.current_view.set_loading(False)
                    self.current_view.set_status(message, is_error=True)

        def on_error(err):
            if isinstance(self.current_view, LoginView):
                self.current_view.set_loading(False)
                self.current_view.set_status(f"Erro de conexão: {err}", is_error=True)

        run_async_task(worker, on_success=on_success, on_error=on_error, root_widget=self)

    def handle_fetch_ponto(self, start_date: str, end_date: str):
        """Busca os dados de ponto na Dixi, com diálogo inteligente de mesclagem para dias já editados."""
        def worker():
            raw_days = self.dixi_service.fetch_history(start_date, end_date)
            marcacoes_dixi: List[MarcacaoDia] = sorted(
                [PontoEngine.process_day(d) for d in raw_days],
                key=lambda x: normalize_date_to_iso(x.data_id or x.data_formatada)
            )
            return marcacoes_dixi

        def on_success(marcacoes_dixi):
            if not marcacoes_dixi:
                messagebox.showwarning("Aviso", "Nenhum dado de ponto encontrado para o período selecionado.")
                if isinstance(self.current_view, MainView):
                    self.current_view.finish_fetch_ponto()
                return

            # Atualiza datas no estado
            self.app_state.data_inicio = f"{start_date[6:]}/{start_date[4:6]}/{start_date[:4]}" if len(start_date) == 8 else start_date
            self.app_state.data_fim = f"{end_date[6:]}/{end_date[4:6]}/{end_date[:4]}" if len(end_date) == 8 else end_date

            # Verifica se há dias editados na memória atual ou no cache salvo
            dias_editados_candidatos = self.app_state.obter_dias_editados()
            if not dias_editados_candidatos and self.app_state.usuario and self.app_state.usuario.username:
                cached_s = StorageService.carregar_sessao(self.app_state.usuario.username)
                if cached_s:
                    dias_editados_candidatos = [m for m in cached_s.get("marcacoes", []) if m.editado_manualmente]

            if dias_editados_candidatos:
                # Checa se algum dia editado coincide com os dias retornados pela Dixi
                dias_sobrepostos = [
                    m for m in dias_editados_candidatos
                    if any(normalize_date_to_iso(m.data_id or m.data_formatada) == normalize_date_to_iso(d.data_id or d.data_formatada) for d in marcacoes_dixi)
                ]

                if dias_sobrepostos:
                    manter = messagebox.askyesno(
                        "Manter Alterações Realizadas?",
                        f"Foram encontradas alterações manuais em {len(dias_sobrepostos)} dia(s) do período selecionado.\n\n"
                        "Deseja MANTER essas alterações nos dias editados e carregar os novos dias da Dixi?\n\n"
                        "• Sim: Preserva seus horários e observações editados.\n"
                        "• Não: Descarta as edições e recarrega os dados originais da Dixi."
                    )

                    if manter:
                        marcacoes_finais, pres_count = StorageService.mesclar_marcacoes(dias_editados_candidatos, marcacoes_dixi)
                        self.app_state.set_marcacoes(marcacoes_finais)
                        messagebox.showinfo("Dados Mesclados", f"{pres_count} dia(s) com alterações manuais foram mantidos e os demais foram atualizados da Dixi.")
                    else:
                        self.app_state.set_marcacoes(marcacoes_dixi)
                else:
                    self.app_state.set_marcacoes(marcacoes_dixi)
            else:
                self.app_state.set_marcacoes(marcacoes_dixi)

            if isinstance(self.current_view, MainView):
                self.current_view.finish_fetch_ponto()

        def on_error(err):
            logger.error(f"Erro ao buscar histórico de ponto: {err}")
            messagebox.showerror("Erro de Conexão", f"Falha ao obter histórico de ponto:\n{err}")
            if isinstance(self.current_view, MainView):
                self.current_view.finish_fetch_ponto()

        run_async_task(worker, on_success=on_success, on_error=on_error, root_widget=self)

    def handle_logout(self):
        """Desconecta o usuário, salva a sessão e retorna à tela de login."""
        self.app_state.salvar_cache_local()
        self.app_state.set_usuario(None)
        self.app_state.set_marcacoes([])
        self.show_login_view()

    def on_closing(self):
        """Trata o fechamento do aplicativo salvando silenciosamente a sessão."""
        try:
            self.app_state.salvar_cache_local()
        except Exception:
            pass
        self.destroy()

def main():
    """Ponto de entrada do executável."""
    setup_logging()
    app = App()
    app.mainloop()

if __name__ == "__main__":
    main()
