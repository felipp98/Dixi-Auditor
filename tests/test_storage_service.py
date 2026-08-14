"""
Testes unitários para o StorageService e Mesclagem Inteligente de Ponto.
"""
import os
import unittest
from datetime import datetime
from src.core.models import MarcacaoDia
from src.services.storage_service import StorageService

class TestStorageService(unittest.TestCase):

    def setUp(self):
        self.test_user = "test_user_unit_test"
        self.dias_teste = [
            MarcacaoDia(
                data_id="20260601",
                data_formatada="01/06/2026",
                segundos_trabalhados=28800,
                saldo_segundos=0,
                is_pendencia=False,
                horarios=["08:00", "12:00", "13:00", "17:00"],
                obs="Dia Normal",
                editado_manualmente=False
            ),
            MarcacaoDia(
                data_id="20260602",
                data_formatada="02/06/2026",
                segundos_trabalhados=32400,
                saldo_segundos=3600,
                is_pendencia=False,
                horarios=["08:00", "12:00", "13:00", "18:00"],
                obs="Ajustado via IA",
                editado_manualmente=True,
                horarios_originais=["08:00", "12:00", "13:00", "17:00"]
            )
        ]

    def tearDown(self):
        StorageService.limpar_sessao(self.test_user)

    def test_salvar_e_carregar_sessao(self):
        """Testa salvar e carregar dados do cache JSON."""
        saved = StorageService.salvar_sessao(
            username=self.test_user,
            data_inicio="01/06/2026",
            data_fim="30/06/2026",
            marcacoes=self.dias_teste,
            ignorar_hoje=True
        )
        self.assertTrue(saved)

        loaded = StorageService.carregar_sessao(self.test_user)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["username"], self.test_user)
        self.assertEqual(loaded["data_inicio"], "01/06/2026")
        self.assertEqual(loaded["data_fim"], "30/06/2026")
        self.assertEqual(loaded["total_editados"], 1)

        marcacoes_loaded = loaded["marcacoes"]
        self.assertEqual(len(marcacoes_loaded), 2)
        self.assertFalse(marcacoes_loaded[0].editado_manualmente)
        self.assertTrue(marcacoes_loaded[1].editado_manualmente)
        self.assertEqual(marcacoes_loaded[1].horarios, ["08:00", "12:00", "13:00", "18:00"])
        self.assertEqual(marcacoes_loaded[1].obs, "Ajustado via IA")

    def test_mesclagem_inteligente_preserva_editados(self):
        """Testa mesclagem de dias anteriores editados com novos dias da Dixi."""
        anteriores = [
            MarcacaoDia(
                data_id="20260601",
                data_formatada="01/06/2026",
                segundos_trabalhados=28800,
                saldo_segundos=0,
                is_pendencia=False,
                horarios=["08:00", "12:00", "13:00", "17:00"],
                obs="",
                editado_manualmente=False
            ),
            MarcacaoDia(
                data_id="20260602",
                data_formatada="02/06/2026",
                segundos_trabalhados=32400,
                saldo_segundos=3600,
                is_pendencia=False,
                horarios=["08:00", "12:00", "13:00", "18:00"],
                obs="Horário corrigido manualmente",
                editado_manualmente=True
            )
        ]

        novos_dixi = [
            MarcacaoDia(
                data_id="20260601",
                data_formatada="01/06/2026",
                segundos_trabalhados=28800,
                saldo_segundos=0,
                is_pendencia=False,
                horarios=["08:00", "12:00", "13:00", "17:00"],
                obs="",
                editado_manualmente=False
            ),
            MarcacaoDia(
                data_id="20260602",
                data_formatada="02/06/2026",
                segundos_trabalhados=25200,
                saldo_segundos=-3600,
                is_pendencia=False,
                horarios=["08:00", "12:00", "13:00", "16:00"],
                obs="",
                editado_manualmente=False
            ),
            MarcacaoDia(
                data_id="20260701",
                data_formatada="01/07/2026",
                segundos_trabalhados=28800,
                saldo_segundos=0,
                is_pendencia=False,
                horarios=["08:00", "12:00", "13:00", "17:00"],
                obs="",
                editado_manualmente=False
            )
        ]

        mesclados, pres_count = StorageService.mesclar_marcacoes(anteriores, novos_dixi)

        self.assertEqual(len(mesclados), 3)
        self.assertEqual(pres_count, 1)

        # Dia 02/06 deve preservar a edição manual com saída às 18:00
        dia_02 = next(m for m in mesclados if m.data_id == "20260602")
        self.assertTrue(dia_02.editado_manualmente)
        self.assertEqual(dia_02.horarios, ["08:00", "12:00", "13:00", "18:00"])
        self.assertEqual(dia_02.obs, "Horário corrigido manualmente")
        self.assertEqual(dia_02.horarios_originais, ["08:00", "12:00", "13:00", "16:00"])

        # Dia 01/07 novo deve vir com os dados da Dixi
        dia_07 = next(m for m in mesclados if m.data_id == "20260701")
        self.assertFalse(dia_07.editado_manualmente)

if __name__ == "__main__":
    unittest.main()
