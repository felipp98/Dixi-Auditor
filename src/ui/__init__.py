"""
Camada de Interface com o Usuário (UI): Tema, Componentes e Telas/Views.
"""
from src.ui.theme import apply_theme, enable_high_dpi, get_font
from src.ui.components import DateSelector, MetricCard, PontoTable, SignerListManager, AIChatModal, AIChatWidget, PasswordEntry
from src.ui.views import LoginView, MainView, JustificativaView, SettingsModal, HistoricoView
