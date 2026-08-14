"""
Testes unitários para o motor de cálculos de ponto (PontoEngine).
"""
import unittest
from src.core.ponto_engine import PontoEngine
from src.core.models import MarcacaoDia

class TestPontoEngine(unittest.TestCase):

    def test_jornada_padrao_8h(self):
        """Testa uma jornada padrão exata de 8 horas (08:00 - 12:00 e 13:00 - 17:00)."""
        horarios = ["08:00", "12:00", "13:00", "17:00"]
        m = PontoEngine.process_horarios(horarios, "20260810", "10/08/2026")
        
        self.assertEqual(m.segundos_trabalhados, 8 * 3600)
        self.assertEqual(m.saldo_segundos, 0)
        self.assertFalse(m.is_pendencia)

    def test_horas_extras(self):
        """Testa jornada com 1 hora extra (08:00 - 12:00 e 13:00 - 18:00 -> 9 horas)."""
        horarios = ["08:00", "12:00", "13:00", "18:00"]
        m = PontoEngine.process_horarios(horarios, "20260811", "11/08/2026")
        
        self.assertEqual(m.segundos_trabalhados, 9 * 3600)
        self.assertEqual(m.saldo_segundos, 3600)  # +1h de saldo
        self.assertFalse(m.is_pendencia)

    def test_tolerancia_clt_debito(self):
        """
        Testa débito dentro e fora da tolerância CLT de 10 min (600s).
        - 15 min de atraso (7h45 trabalhadas = -900s diff):
          Aplica perdão de 600s -> saldo = -900 + 600 = -300s (-5 min).
        """
        horarios = ["08:15", "12:00", "13:00", "17:00"]
        m = PontoEngine.process_horarios(horarios, "20260812", "12/08/2026")
        
        self.assertEqual(m.segundos_trabalhados, 7 * 3600 + 45 * 60)
        self.assertEqual(m.saldo_segundos, -300)

    def test_regra_almoco_antecipado(self):
        """
        Se o colaborador voltou em apenas 30 minutos de almoço (ex: 12:00 - 12:30),
        a regra não deve gerar hora extra indevida e desconta os 30 min faltantes do total.
        """
        horarios = ["08:00", "12:00", "12:30", "17:00"]
        m = PontoEngine.process_horarios(horarios, "20260813", "13/08/2026")
        
        # 4h da manhã + 4.5h da tarde = 8.5h bruta.
        # Desconto de antecipação de 30 min (1800s) -> total = 8.0h (28800s)
        self.assertEqual(m.segundos_trabalhados, 8 * 3600)
        self.assertEqual(m.saldo_segundos, 0)

    def test_duas_batidas_pendencia(self):
        """Testa que 2 batidas no dia são marcadas como pendência para conferência."""
        horarios = ["08:00", "17:00"]
        m = PontoEngine.process_horarios(horarios, "20260814", "14/08/2026")
        
        self.assertEqual(m.segundos_trabalhados, 9 * 3600)
        self.assertTrue(m.is_pendencia)  # 2 batidas exigem conferência

    def test_batida_impar_pendencia(self):
        """Testa que 3 batidas geram pendência e calculam apenas o par completo."""
        horarios = ["08:00", "12:00", "13:00"]
        m = PontoEngine.process_horarios(horarios, "20260815", "15/08/2026")
        
        self.assertTrue(m.is_pendencia)
        self.assertEqual(m.segundos_trabalhados, 4 * 3600)

if __name__ == "__main__":
    unittest.main()
