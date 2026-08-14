"""
Testes unitários para os formatadores de data e hora.
"""
import unittest
from src.utils.formatters import (
    format_time_seconds,
    obter_mes_extenso,
    formatar_mes_competencia,
    normalize_date_to_iso
)

class TestFormatters(unittest.TestCase):

    def test_format_time_seconds(self):
        self.assertEqual(format_time_seconds(3600), "01:00")
        self.assertEqual(format_time_seconds(3660), "01:01")
        self.assertEqual(format_time_seconds(3600, show_sign=True), "+01:00")
        self.assertEqual(format_time_seconds(-1800, show_sign=True), "-00:30")
        self.assertEqual(format_time_seconds(0, show_sign=True), "+00:00")

    def test_obter_mes_extenso(self):
        self.assertEqual(obter_mes_extenso(1), "Janeiro")
        self.assertEqual(obter_mes_extenso(7), "Julho")
        self.assertEqual(obter_mes_extenso(12), "Dezembro")

    def test_formatar_mes_competencia(self):
        self.assertEqual(formatar_mes_competencia("7"), "Julho")
        self.assertEqual(formatar_mes_competencia("08"), "Agosto")
        self.assertEqual(formatar_mes_competencia("08/2026"), "Agosto / 2026")
        self.assertEqual(formatar_mes_competencia("julho"), "Julho")

    def test_normalize_date_to_iso_and_sorting(self):
        """Testa que as datas são ordenadas corretamente mesmo quando ultrapassam viradas de mês."""
        dates_br = ["24/07/2026", "13/08/2026", "14/07/2026", "01/07/2026"]
        sorted_dates = sorted(dates_br, key=normalize_date_to_iso)
        
        expected_order = ["01/07/2026", "14/07/2026", "24/07/2026", "13/08/2026"]
        self.assertEqual(sorted_dates, expected_order)

if __name__ == "__main__":
    unittest.main()
