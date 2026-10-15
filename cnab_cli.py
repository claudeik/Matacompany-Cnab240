#!/usr/bin/env python3
"""
CLI - Conversor CNAB 240 / DDA Itaú em Excel (.xlsx) Lado a Lado
Uso:
    python3 cnab_cli.py arquivo.DET [saida.xlsx]
"""

import sys
import os
from converter import parse_cnab_dda, gerar_excel_xlsx, gerar_csv

def main():
    if len(sys.argv) < 2:
        print("Uso: python3 cnab_cli.py <arquivo_dda.DET> [arquivo_saida.xlsx]")
        print("Exemplo: python3 cnab_cli.py exemplo_itau_dda.DET resultado.xlsx")
        sys.exit(1)

    caminho_entrada = sys.argv[1]
    if not os.path.exists(caminho_entrada):
        print(f"Erro: Arquivo não encontrado: {caminho_entrada}")
        sys.exit(1)

    caminho_saida = sys.argv[2] if len(sys.argv) > 2 else os.path.splitext(caminho_entrada)[0] + "_convertido.xlsx"

    print(f"Lendo arquivo: {caminho_entrada}...")
    try:
        with open(caminho_entrada, 'r', encoding='utf-8') as f:
            conteudo = f.read()
    except UnicodeDecodeError:
        with open(caminho_entrada, 'r', encoding='latin1') as f:
            conteudo = f.read()

    registros = parse_cnab_dda(conteudo)
    total = len(registros)
    validos = sum(1 for r in registros if r['valido'])
    erros = total - validos

    print(f"Total de registros identificados: {total}")
    print(f"Boletos Válidos:                  {validos}")
    print(f"Inconsistentes / Erros:           {erros}")

    excel_bytes = gerar_excel_xlsx(registros)
    with open(caminho_saida, 'wb') as f:
        f.write(excel_bytes)

    print(f"\nPlanilha Excel gerada com sucesso:")
    print(f"  -> {caminho_saida}")
    print("Colunas de Código de Barras (44) e Linha Digitável (47) formatadas lado a lado como TEXTO para preservar os zeros à esquerda.")

if __name__ == '__main__':
    main()
