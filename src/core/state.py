"""
Gerenciamento de estado reativo e centralizado da aplicação com ordenação cronológica garantida, persistência e histórico cumulativo.
"""
from datetime import datetime
from typing import List, Dict, Callable, Optional, Any
from src.core.models import MarcacaoDia, ResumoAuditoria, Usuario, Signatario, JustificativaItem
from src.core.ponto_engine import PontoEngine
from src.utils.formatters import normalize_date_to_iso
from src.services.storage_service import StorageService

class AppState:
    """Armazena o estado global da aplicação e notifica observadores quando modificado."""

    def __init__(self):
        self.usuario: Optional[Usuario] = None
        self.marcacoes: List[MarcacaoDia] = []
        self.ignorar_hoje: bool = True
        self.resumo: ResumoAuditoria = ResumoAuditoria()
        
        # Controle de edições sujas (ativa o botão "Recalcular Ponto")
        self.has_unsaved_edits: bool = False

        # Configurações de datas
        now = datetime.now()
        self.data_inicio: str = f"01/{now.month:02d}/{now.year}"
        self.data_fim: str = f"{now.day:02d}/{now.month:02d}/{now.year}"

        # Signatários configurados para o Autentique
        self.signatarios: List[Signatario] = []

        # Itens de Justificativa
        self.justificativa_itens: List[JustificativaItem] = []

        # Listeners / Observadores
        self._listeners: List[Callable[[str, Any], None]] = []

    def add_listener(self, listener: Callable[[str, Any], None]):
        """Registra um ouvinte para alterações de estado."""
        if listener not in self._listeners:
            self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[str, Any], None]):
        """Remove um ouvinte."""
        if listener in self._listeners:
            self._listeners.remove(listener)

    def notify(self, event_name: str, payload: Any = None):
        """Notifica todos os ouvintes sobre uma mudança de estado."""
        for listener in list(self._listeners):
            try:
                listener(event_name, payload)
            except Exception:
                pass

    def set_usuario(self, usuario: Optional[Usuario]):
        """Define o usuário autenticado."""
        self.usuario = usuario
        self.notify("user_changed", self.usuario)

    def set_datas_periodo(self, data_inicio: str, data_fim: str):
        """Atualiza as datas do período ativo."""
        self.data_inicio = data_inicio
        self.data_fim = data_fim
        self.notify("period_changed", (data_inicio, data_fim))

    def set_marcacoes(self, marcacoes: List[MarcacaoDia]):
        """Define as marcações carregadas da API ordenadas cronologicamente e reseta o estado de edição pendente."""
        self.marcacoes = sorted(marcacoes, key=lambda x: normalize_date_to_iso(x.data_id or x.data_formatada))
        self.has_unsaved_edits = False
        self.recalcular_resumo()
        self.salvar_cache_local()
        self.notify("marcacoes_loaded", self.marcacoes)

    def obter_dias_editados(self) -> List[MarcacaoDia]:
        """Retorna todos os dias que foram alterados manualmente pelo usuário ou pela IA na sessão atual."""
        return [m for m in self.marcacoes if m.editado_manualmente]

    def tem_dias_editados(self) -> bool:
        """Verifica se há dias alterados na sessão atual."""
        return any(m.editado_manualmente for m in self.marcacoes)

    def salvar_edicoes_no_historico(self) -> bool:
        """Salva as alterações do período atual no banco de histórico acumulado do usuário."""
        if self.usuario and self.usuario.username:
            editados = self.obter_dias_editados()
            if editados:
                return StorageService.salvar_edicoes_historico(self.usuario.username, editados)
        return False

    def obter_edicoes_salvas_periodo(self, start_date: str, end_date: str) -> List[MarcacaoDia]:
        """Busca no histórico persistente do usuário se existem edições salvas para o período especificado."""
        if self.usuario and self.usuario.username:
            return StorageService.obter_edicoes_periodo(self.usuario.username, start_date, end_date)
        return []

    def marcar_edicao_feita(self):
        """Sinaliza que uma batida foi editada e habilita o botão 'Recalcular Ponto'."""
        self.has_unsaved_edits = True
        self.salvar_cache_local()
        self.notify("edits_dirty", True)

    def marcar_recalculo_concluido(self):
        """Sinaliza que o recálculo foi executado e desabilita o botão 'Recalcular Ponto'."""
        self.has_unsaved_edits = False
        self.marcacoes = sorted(self.marcacoes, key=lambda x: normalize_date_to_iso(x.data_id or x.data_formatada))
        self.recalcular_resumo()
        self.salvar_cache_local()
        self.notify("edits_dirty", False)

    def set_ignorar_hoje(self, ignorar: bool):
        """Altera a preferência de ignorar o dia atual em andamento."""
        self.ignorar_hoje = ignorar
        self.recalcular_resumo()
        self.salvar_cache_local()
        self.notify("ignore_today_changed", self.ignorar_hoje)

    def recalcular_resumo(self):
        """Recalcula o resumo consolidado com base nas marcações atuais."""
        self.resumo = PontoEngine.calcular_resumo(self.marcacoes, self.ignorar_hoje)
        self.notify("resumo_updated", self.resumo)

    def set_signatarios(self, signatarios: List[Signatario]):
        """Atualiza a lista de signatários do Autentique."""
        self.signatarios = signatarios
        self.notify("signatarios_changed", self.signatarios)

    def salvar_cache_local(self):
        """Salva silenciosamente a sessão e as edições em arquivo JSON local."""
        if self.usuario and self.usuario.username and self.marcacoes:
            StorageService.salvar_sessao(
                username=self.usuario.username,
                data_inicio=self.data_inicio,
                data_fim=self.data_fim,
                marcacoes=self.marcacoes,
                ignorar_hoje=self.ignorar_hoje
            )
