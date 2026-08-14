"""
Testes unitários para as regras heurísticas de auditoria offline do AIService.
"""
import unittest
from src.core.models import MarcacaoDia
from src.services.ai_service import AIService

class TestAIHeuristics(unittest.TestCase):

    def test_deteccao_batidas_duplicadas(self):
        """Testa detecção de batidas exatamente duplicadas no mesmo dia."""
        m = MarcacaoDia(
            data_id="20260810",
            data_formatada="10/08/2026",
            segundos_trabalhados=8 * 3600,
            saldo_segundos=0,
            is_pendencia=False,
            horarios=["08:00", "08:00", "12:00", "13:00", "17:00"]
        )
        sugestoes, texto = AIService.encontrar_sugestoes_duplicadas([m])
        
        self.assertEqual(len(sugestoes), 1)
        self.assertEqual(sugestoes[0]["horarios"], ["08:00", "12:00", "13:00", "17:00"])
        self.assertIn("Batida duplicada", texto)

    def test_deteccao_batidas_muito_proximas(self):
        """Testa detecção de batidas com intervalo menor que 2 minutos (ex: 08:00 e 08:01)."""
        m = MarcacaoDia(
            data_id="20260811",
            data_formatada="11/08/2026",
            segundos_trabalhados=8 * 3600,
            saldo_segundos=0,
            is_pendencia=False,
            horarios=["08:00", "08:01", "12:00", "13:00", "17:00"]
        )
        sugestoes, texto = AIService.encontrar_sugestoes_duplicadas([m])
        
        self.assertEqual(len(sugestoes), 1)
        self.assertEqual(sugestoes[0]["horarios"], ["08:00", "12:00", "13:00", "17:00"])
        self.assertIn("Batidas muito próximas", texto)

if __name__ == "__main__":
    unittest.main()
