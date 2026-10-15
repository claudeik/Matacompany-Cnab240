"""
Suíte de Testes Automatizados para o Conversor CNAB 240 / Código de Barras
Baseado estritamente na Especificação Técnica (Seção 11 e Critérios de Aceite).
"""

import unittest
from converter import (
    converter_barras_para_linha,
    converter_linha_para_barras,
    mod10,
    mod11,
    parse_cnab_dda,
    gerar_excel_xlsx,
    gerar_csv
)

class TestConversaoBoleto(unittest.TestCase):

    def setUp(self):
        # Vetor A: valor R$ 150,00, banco 341
        self.barras_a = "34191100000000150001234567890123456789012345"
        self.linha_a = "34191234546789012345767890123457110000000015000"
        self.fmt_a = "34191.23454 67890.123457 67890.123457 1 10000000015000"

        # Vetor B: sem vencimento e valor zero, banco 001
        self.barras_b = "00193000000000000000000000000000000000000001"
        self.linha_b = "00190000090000000000000000000018300000000000000"
        self.fmt_b = "00190.00009 00000.000000 00000.000018 3 00000000000000"

        # Vetor C: zeros à esquerda e fator 9999, banco 033
        self.barras_c = "03391999900001234569876543210987654321098765"
        self.linha_c = "03399876534321098765743210987657199990000123456"
        self.fmt_c = "03399.87653 43210.987657 43210.987657 1 99990000123456"

    # --- Testes de Sucesso (Seção 11) ---

    def test_caso_a(self):
        res = converter_barras_para_linha(self.barras_a)
        self.assertTrue(res['ok'])
        self.assertEqual(res['valor'], self.linha_a)
        self.assertEqual(res['formatada'], self.fmt_a)

    def test_caso_b(self):
        res = converter_barras_para_linha(self.barras_b)
        self.assertTrue(res['ok'])
        self.assertEqual(res['valor'], self.linha_b)
        self.assertEqual(res['formatada'], self.fmt_b)

    def test_caso_c(self):
        res = converter_barras_para_linha(self.barras_c)
        self.assertTrue(res['ok'])
        self.assertEqual(res['valor'], self.linha_c)
        self.assertEqual(res['formatada'], self.fmt_c)

    # --- Teste de Sanitização ---

    def test_sanitizacao_espacos_pontos_tracos(self):
        barras_suja = " 34191.10000-000015000 1234567890123456789012345 "
        res = converter_barras_para_linha(barras_suja)
        self.assertTrue(res['ok'])
        self.assertEqual(res['valor'], self.linha_a)

    # --- Testes de Erro (Seção 11 e Tabela da Seção 8) ---

    def test_erro_e01_vazio(self):
        res = converter_barras_para_linha("")
        self.assertFalse(res['ok'])
        self.assertEqual(res['erro']['codigo'], 'E01')

        res_spaces = converter_barras_para_linha("   ")
        self.assertFalse(res_spaces['ok'])
        self.assertEqual(res_spaces['erro']['codigo'], 'E01')

    def test_erro_e02_caractere_invalido(self):
        # 44 posições com uma letra
        barras_com_letra = "3419110000000015000123456789012345678901234A"
        res = converter_barras_para_linha(barras_com_letra)
        self.assertFalse(res['ok'])
        self.assertEqual(res['erro']['codigo'], 'E02')

    def test_erro_e03_tamanho_invalido(self):
        # 43 dígitos
        res43 = converter_barras_para_linha(self.barras_a[:-1])
        self.assertFalse(res43['ok'])
        self.assertEqual(res43['erro']['codigo'], 'E03')

        # 45 dígitos
        res45 = converter_barras_para_linha(self.barras_a + "1")
        self.assertFalse(res45['ok'])
        self.assertEqual(res45['erro']['codigo'], 'E03')

    def test_erro_e04_comeca_com_8(self):
        # Boleto de arrecadação/convênio
        barras_8 = "8" + self.barras_a[1:]
        res = converter_barras_para_linha(barras_8)
        self.assertFalse(res['ok'])
        self.assertEqual(res['erro']['codigo'], 'E04')

    def test_erro_e05_dv_geral_inconsistente(self):
        # Caso A com a posição 5 trocada de 1 para 2
        barras_dv_invalido = self.barras_a[:4] + "2" + self.barras_a[5:]
        res = converter_barras_para_linha(barras_dv_invalido)
        self.assertFalse(res['ok'])
        self.assertEqual(res['erro']['codigo'], 'E05')

    def test_erro_e06_dv_campo_invalido_operacao_inversa(self):
        # Linha digitável do caso A com o DV do campo 2 alterado
        # Campo 2 do caso A é: '67890123457' (DV é o último dígito '7')
        # Trocando '7' por '8':
        linha_dv_alterado = self.linha_a[:20] + "8" + self.linha_a[21:]
        res = converter_linha_para_barras(linha_dv_alterado)
        self.assertFalse(res['ok'])
        self.assertEqual(res['erro']['codigo'], 'E06')

    # --- Teste da Operação Inversa (Seção 9 e Critérios de Aceite) ---

    def test_inversao_caso_a(self):
        inv = converter_linha_para_barras(self.linha_a)
        self.assertTrue(inv['ok'])
        self.assertEqual(inv['valor'], self.barras_a)

    def test_inversao_caso_b(self):
        inv = converter_linha_para_barras(self.linha_b)
        self.assertTrue(inv['ok'])
        self.assertEqual(inv['valor'], self.barras_b)

    def test_inversao_caso_c(self):
        inv = converter_linha_para_barras(self.linha_c)
        self.assertTrue(inv['ok'])
        self.assertEqual(inv['valor'], self.barras_c)

    def test_propriedade_inverter_converter(self):
        # Para todo código de barras válido b, inverter(converter(b)) == b
        for b in [self.barras_a, self.barras_b, self.barras_c]:
            linha = converter_barras_para_linha(b)['valor']
            b_recuperado = converter_linha_para_barras(linha)['valor']
            self.assertEqual(b_recuperado, b)

    # --- Teste de Geração de Planilha Excel e CSV ---

    def test_geracao_excel_e_csv(self):
        sample_cnab = f"""
00193000000000000000000000000000000000000001
34191100000000150001234567890123456789012345
"""
        registros = parse_cnab_dda(sample_cnab)
        self.assertEqual(len(registros), 2)
        
        # Gera Excel
        excel_bytes = gerar_excel_xlsx(registros)
        self.assertGreater(len(excel_bytes), 1000)
        self.assertTrue(excel_bytes.startswith(b'PK')) # Assinatura ZIP / OpenXML

        # Gera CSV
        csv_bytes = gerar_csv(registros)
        self.assertTrue(csv_bytes.startswith(b'\xef\xbb\xbf')) # UTF-8 BOM
        self.assertIn(b"Codigo_Barras_44;Linha_Digitavel_47", csv_bytes)

if __name__ == '__main__':
    unittest.main()
