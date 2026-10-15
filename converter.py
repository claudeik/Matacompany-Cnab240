"""
Módulo de Conversão e Leitura CNAB 240 DDA Itaú
Especificação Técnica: Conversão de Código de Barras (44) em Linha Digitável (47)
Autor da especificação: @Claudio (14/10/2026)
"""

import re
import io
import zipfile
import xml.sax.saxutils as saxutils
from datetime import date, timedelta
from typing import Dict, List, Any, Optional, Tuple

# Dicionário de Bancos Brasileiros mais frequentes
BANCOS_CONHECIDOS = {
    "001": "Banco do Brasil S.A.",
    "033": "Banco Santander (Brasil) S.A.",
    "104": "Caixa Econômica Federal",
    "237": "Banco Bradesco S.A.",
    "341": "Banco Itaú Unibanco S.A.",
    "756": "Banco Cooperativo Sicoob S.A.",
    "748": "Banco Cooperativo Sicredi S.A.",
    "077": "Banco Inter S.A.",
    "260": "Nu Pagamentos S.A. (Nubank)",
    "212": "Banco Original S.A.",
    "422": "Banco Safra S.A.",
    "041": "Banco do Estado do Rio Grande do Sul (Banrisul)",
    "655": "Banco Votorantim S.A.",
    "707": "Banco Daycoval S.A.",
    "389": "Banco Mercantil do Brasil S.A.",
    "021": "BANESTES S.A. Banco do Estado do Espírito Santo",
    "070": "BRB - Banco de Brasília S.A.",
    "136": "Unicred do Brasil",
    "085": "Cooperativa Central de Crédito Urbano - CECRED (Ailos)"
}

def obter_nome_banco(codigo: str) -> str:
    """Retorna o nome do banco ou 'Banco XXX'."""
    cod = codigo.strip().zfill(3)
    return BANCOS_CONHECIDOS.get(cod, f"Banco {cod}")

def mod10(campo: str) -> str:
    """
    Cálculo do Módulo 10 para os campos 1, 2 e 3 da Linha Digitável.
    1. Percorrer os dígitos do campo da direita para a esquerda com pesos alternados 2, 1, 2, 1...
    2. Multiplicar cada dígito pelo peso. Se o produto for maior que 9, somar seus algarismos (ex: 14 vira 1 + 4 = 5).
    3. Somar todos os resultados.
    4. DV = (10 - (soma % 10)) % 10.
    """
    soma = 0
    multiplicador = 2
    for char in reversed(campo):
        prod = int(char) * multiplicador
        soma += (prod // 10) + (prod % 10)
        multiplicador = 1 if multiplicador == 2 else 2
    resto = soma % 10
    dv = (10 - resto) % 10
    return str(dv)

def mod11(bloco: str) -> str:
    """
    Cálculo do Módulo 11 para o DV geral do código de barras (posição 5).
    1. Tomar os 43 dígitos do código de barras, excluindo a posição 5.
    2. Percorrer da direita para a esquerda com pesos 2, 3, 4... até 9, reiniciando em 2 após o 9.
    3. Somar os produtos.
    4. DV = 11 - (soma % 11). Se o resultado for 0, 10 ou 11, o DV é 1.
    """
    soma = 0
    multiplicador = 2
    for char in reversed(bloco):
        soma += int(char) * multiplicador
        multiplicador = 2 if multiplicador == 9 else multiplicador + 1
    resto = soma % 11
    dv = 11 - resto
    if dv in (0, 10, 11):
        return '1'
    return str(dv)

def converter_barras_para_linha(b: str) -> Dict[str, Any]:
    """
    Converte código de barras (44 posições) em linha digitável (47 posições).
    Retorna dicionário com status, valor bruto, valor formatado e eventuais avisos/erros.
    """
    b_limpo = re.sub(r'[\s.\-]', '', str(b or ''))
    
    # E01: Entrada nula ou vazia
    if not b_limpo:
        return {'ok': False, 'erro': {'codigo': 'E01', 'mensagem': 'Código de barras não informado'}}
    
    # E02: Caractere não numérico após a sanitização
    if not b_limpo.isdigit():
        return {'ok': False, 'erro': {'codigo': 'E02', 'mensagem': 'Código de barras contém caracteres inválidos'}}
        
    # E03: Tamanho diferente de 44
    if len(b_limpo) != 44:
        return {'ok': False, 'erro': {'codigo': 'E03', 'mensagem': f'Tamanho inválido: esperado 44 dígitos, recebido {len(b_limpo)}'}}
        
    # E04: Primeiro dígito igual a 8 (arrecadação / convênio)
    if b_limpo[0] == '8':
        return {'ok': False, 'erro': {'codigo': 'E04', 'mensagem': 'Boleto de arrecadação/convênio não suportado'}}
        
    # Validação do DV geral (posição 5, índice 4)
    dv_calculado = mod11(b_limpo[0:4] + b_limpo[5:44])
    if dv_calculado != b_limpo[4]:
        return {
            'ok': False,
            'erro': {
                'codigo': 'E05',
                'mensagem': f'Dígito verificador geral inconsistente (informado: {b_limpo[4]}, esperado: {dv_calculado})'
            }
        }
        
    avisos: List[str] = []
    # Aviso W01: Moeda (posição 4, índice 3) diferente de 9
    if b_limpo[3] != '9':
        avisos.append(f'W01: Código de moeda ({b_limpo[3]}) diferente de 9 (Real)')
        
    c1 = b_limpo[0:4] + b_limpo[19:24]   # Banco (3) + Moeda (1) + Campo Livre [1..5]
    c2 = b_limpo[24:34]                  # Campo Livre [6..15]
    c3 = b_limpo[34:44]                  # Campo Livre [16..25]
    
    dv1 = mod10(c1)
    dv2 = mod10(c2)
    dv3 = mod10(c3)
    dv_geral = b_limpo[4]
    fator_valor = b_limpo[5:19]          # Fator (4) + Valor (10)
    
    bruta = f"{c1}{dv1}{c2}{dv2}{c3}{dv3}{dv_geral}{fator_valor}"
    formatada = f"{c1[:5]}.{c1[5:]}{dv1} {c2[:5]}.{c2[5:]}{dv2} {c3[:5]}.{c3[5:]}{dv3} {dv_geral} {fator_valor}"
    
    banco_cod = b_limpo[0:3]
    fator_str = b_limpo[5:9]
    valor_str = b_limpo[9:19]
    
    return {
        'ok': True,
        'valor': bruta,
        'formatada': formatada,
        'avisos': avisos,
        'banco_cod': banco_cod,
        'banco_nome': obter_nome_banco(banco_cod),
        'fator_vencimento': fator_str,
        'valor_nominal_cents': int(valor_str) if valor_str.isdigit() else 0,
        'valor_nominal_formatado': f"R$ {int(valor_str) / 100:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.') if valor_str.isdigit() else "R$ 0,00",
        'data_vencimento_calculada': calcular_data_fator(fator_str)
    }

def converter_linha_para_barras(linha: str) -> Dict[str, Any]:
    """
    Operação Inversa: Linha digitável (47 posições) para código de barras (44 posições).
    Conforme Seção 9 da especificação técnica.
    """
    l_limpo = re.sub(r'[\s.\-]', '', str(linha or ''))
    
    if not l_limpo:
        return {'ok': False, 'erro': {'codigo': 'E01', 'mensagem': 'Linha digitável não informada'}}
    if not l_limpo.isdigit():
        return {'ok': False, 'erro': {'codigo': 'E02', 'mensagem': 'Linha digitável contém caracteres inválidos'}}
    if len(l_limpo) != 47:
        return {'ok': False, 'erro': {'codigo': 'E03', 'mensagem': f'Tamanho inválido: esperado 47 dígitos, recebido {len(l_limpo)}'}}
    if l_limpo[0] == '8':
        return {'ok': False, 'erro': {'codigo': 'E04', 'mensagem': 'Boleto de arrecadação/convênio não suportado'}}
        
    c1 = l_limpo[0:10]
    c2 = l_limpo[10:21]
    c3 = l_limpo[21:32]
    dvg = l_limpo[32]
    fv = l_limpo[33:47]
    
    if mod10(c1[0:9]) != c1[9]:
        return {'ok': False, 'erro': {'codigo': 'E06', 'mensagem': f'Dígito verificador do campo 1 inconsistente (esperado: {mod10(c1[0:9])}, informado: {c1[9]})'}}
    if mod10(c2[0:10]) != c2[10]:
        return {'ok': False, 'erro': {'codigo': 'E06', 'mensagem': f'Dígito verificador do campo 2 inconsistente (esperado: {mod10(c2[0:10])}, informado: {c2[10]})'}}
    if mod10(c3[0:10]) != c3[10]:
        return {'ok': False, 'erro': {'codigo': 'E06', 'mensagem': f'Dígito verificador do campo 3 inconsistente (esperado: {mod10(c3[0:10])}, informado: {c3[10]})'}}
        
    barras = c1[0:4] + dvg + fv + c1[4:9] + c2[0:10] + c3[0:10]
    
    avisos: List[str] = []
    if barras[3] != '9':
        avisos.append(f'W01: Moeda ({barras[3]}) diferente de 9')
        
    return {
        'ok': True,
        'valor': barras,
        'avisos': avisos,
        'banco_cod': barras[0:3],
        'banco_nome': obter_nome_banco(barras[0:3])
    }

def calcular_data_fator(fator_str: str) -> str:
    """
    Calcula a data de vencimento a partir do fator de 4 dígitos.
    0000 = sem vencimento.
    Base Febraban: 07/10/1997.
    Reinício em 1000 em 22/02/2025.
    """
    if not fator_str or fator_str == '0000':
        return "Sem vencimento"
    try:
        fator = int(fator_str)
        if fator < 1000:
            return f"Fator {fator} (especial)"
        
        # Consideramos o ciclo atual pós reinício de 22/02/2025 (fator 1000):
        # Para datas a partir de 2025:
        base_reinicio = date(2025, 2, 22)
        dias = fator - 1000
        data_venc = base_reinicio + timedelta(days=dias)
        return data_venc.strftime("%d/%m/%Y")
    except Exception:
        return f"Fator {fator_str}"

def formatar_cnpj_cpf(inscricao: str, tipo: str = "") -> str:
    """Formata CPF ou CNPJ com pontuação."""
    num = re.sub(r'\D', '', str(inscricao or ''))
    if tipo == '1' or len(num) == 11:
        num = num.zfill(11)
        return f"{num[:3]}.{num[3:6]}.{num[6:9]}-{num[9:]}"
    elif tipo == '2' or len(num) == 14:
        num = num.zfill(14)
        return f"{num[:2]}.{num[2:5]}.{num[5:8]}/{num[8:12]}-{num[12:]}"
    return num

def formatar_valor_cnab(valor_centavos_str: str) -> str:
    """Formata valor em centavos do CNAB para R$ 0,00."""
    try:
        v = int(re.sub(r'\D', '', valor_centavos_str or '0'))
        return f"R$ {v / 100:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    except Exception:
        return "R$ 0,00"

def parse_cnab_dda(conteudo_texto: str) -> List[Dict[str, Any]]:
    """
    Analisa um arquivo de DDA do Itaú (.DET ou CNAB 240 / CNAB 400 ou lista de códigos).
    Varre os segmentos do arquivo, identificando:
    1. Registros Detalhe Segmento G (padrão DDA de varredura Febraban / Itaú)
    2. Registros Detalhe Segmento J (pagamento de títulos)
    3. Linhas com exatamente 44 posições numéricas
    4. Linhas que contêm sequências numéricas de 44 dígitos
    """
    linhas = conteudo_texto.splitlines()
    registros: List[Dict[str, Any]] = []
    
    # Dicionário temporário para parear Segmento H com Segmento G se houver
    ultimo_segmento_g: Optional[Dict[str, Any]] = None
    
    for idx, linha_bruta in enumerate(linhas, start=1):
        linha = linha_bruta.rstrip('\r\n')
        if not linha.strip():
            continue
            
        tamanho = len(linha)
        
        # 1. CNAB 240 Padrão (240 caracteres)
        if tamanho >= 200:
            tipo_registro = linha[7:8] if len(linha) > 7 else ''
            segmento = linha[13:14].upper() if len(linha) > 13 else ''
            
            # Segmento G: Título de Cobrança / DDA Eletrônico
            if tipo_registro == '3' and segmento == 'G':
                # Posições no Segmento G (1-based: 18 a 61 -> 0-based: [17:61] = 44 dígitos)
                codigo_barras = linha[17:61].strip()
                tipo_inscricao = linha[61:62].strip() if len(linha) >= 62 else ''
                num_inscricao = linha[62:77].strip() if len(linha) >= 77 else ''
                nome_beneficiario = linha[77:107].strip() if len(linha) >= 107 else ''
                data_venc_cnab = linha[107:115].strip() if len(linha) >= 115 else ''
                valor_cnab = linha[115:130].strip() if len(linha) >= 130 else ''
                
                # Conversão do código de barras
                conv = converter_barras_para_linha(codigo_barras)
                
                # Formatação de data DDMMAAAA se presente no CNAB
                data_venc_fmt = ""
                if len(data_venc_cnab) == 8 and data_venc_cnab.isdigit() and data_venc_cnab != '00000000':
                    data_venc_fmt = f"{data_venc_cnab[0:2]}/{data_venc_cnab[2:4]}/{data_venc_cnab[4:8]}"
                else:
                    data_venc_fmt = conv.get('data_vencimento_calculada', '')
                    
                reg = {
                    'linha_num': idx,
                    'origem': 'Segmento G (DDA)',
                    'codigo_barras': codigo_barras,
                    'tamanho_barras': len(codigo_barras),
                    'valido': conv['ok'],
                    'linha_digitavel': conv.get('valor', ''),
                    'linha_digitavel_formatada': conv.get('formatada', ''),
                    'erro': conv.get('erro'),
                    'avisos': conv.get('avisos', []),
                    'banco_cod': conv.get('banco_cod', codigo_barras[:3] if len(codigo_barras) >= 3 else ''),
                    'banco_nome': conv.get('banco_nome', obter_nome_banco(codigo_barras[:3] if len(codigo_barras) >= 3 else '')),
                    'beneficiario_nome': nome_beneficiario or 'Não informado',
                    'beneficiario_doc': formatar_cnpj_cpf(num_inscricao, tipo_inscricao),
                    'valor_formatado': formatar_valor_cnab(valor_cnab) if valor_cnab else conv.get('valor_nominal_formatado', 'R$ 0,00'),
                    'valor_centavos': int(valor_cnab) if (valor_cnab and valor_cnab.isdigit()) else conv.get('valor_nominal_cents', 0),
                    'data_vencimento': data_venc_fmt,
                    'fator_vencimento': conv.get('fator_vencimento', codigo_barras[5:9] if len(codigo_barras) >= 9 else '')
                }
                registros.append(reg)
                ultimo_segmento_g = reg
                continue
                
            # Segmento H: Complemento de valores / Sacador Avalista (enriquece o Segmento G anterior)
            elif tipo_registro == '3' and segmento == 'H':
                if ultimo_segmento_g:
                    # Pode conter juros, multa, ou dados complementares
                    pass
                continue
                
            # Segmento J: Liquidação / Pagamento de Boletos com Código de Barras
            elif tipo_registro == '3' and segmento == 'J':
                codigo_barras = linha[17:61].strip()
                valor_cnab = linha[91:106].strip() if len(linha) >= 106 else ''
                data_venc_cnab = linha[144:152].strip() if len(linha) >= 152 else ''
                nome_favorecido = linha[61:91].strip() if len(linha) >= 91 else ''
                
                conv = converter_barras_para_linha(codigo_barras)
                data_venc_fmt = ""
                if len(data_venc_cnab) == 8 and data_venc_cnab.isdigit() and data_venc_cnab != '00000000':
                    data_venc_fmt = f"{data_venc_cnab[0:2]}/{data_venc_cnab[2:4]}/{data_venc_cnab[4:8]}"
                else:
                    data_venc_fmt = conv.get('data_vencimento_calculada', '')
                    
                reg = {
                    'linha_num': idx,
                    'origem': 'Segmento J (Pagamentos)',
                    'codigo_barras': codigo_barras,
                    'tamanho_barras': len(codigo_barras),
                    'valido': conv['ok'],
                    'linha_digitavel': conv.get('valor', ''),
                    'linha_digitavel_formatada': conv.get('formatada', ''),
                    'erro': conv.get('erro'),
                    'avisos': conv.get('avisos', []),
                    'banco_cod': conv.get('banco_cod', codigo_barras[:3] if len(codigo_barras) >= 3 else ''),
                    'banco_nome': conv.get('banco_nome', obter_nome_banco(codigo_barras[:3] if len(codigo_barras) >= 3 else '')),
                    'beneficiario_nome': nome_favorecido or 'Não informado',
                    'beneficiario_doc': '',
                    'valor_formatado': formatar_valor_cnab(valor_cnab) if valor_cnab else conv.get('valor_nominal_formatado', 'R$ 0,00'),
                    'valor_centavos': int(valor_cnab) if (valor_cnab and valor_cnab.isdigit()) else conv.get('valor_nominal_cents', 0),
                    'data_vencimento': data_venc_fmt,
                    'fator_vencimento': conv.get('fator_vencimento', codigo_barras[5:9] if len(codigo_barras) >= 9 else '')
                }
                registros.append(reg)
                continue
                
            # Headers / Trailers de Lote / Arquivo: ignorar sem erro
            elif tipo_registro in ('0', '1', '5', '9'):
                continue
                
        # 2. Caso a linha seja um código direto (ex: 44 dígitos exatos)
        linha_digitos = re.sub(r'\D', '', linha)
        if len(linha_digitos) == 44:
            conv = converter_barras_para_linha(linha_digitos)
            reg = {
                'linha_num': idx,
                'origem': 'Linha Código de Barras (44)',
                'codigo_barras': linha_digitos,
                'tamanho_barras': 44,
                'valido': conv['ok'],
                'linha_digitavel': conv.get('valor', ''),
                'linha_digitavel_formatada': conv.get('formatada', ''),
                'erro': conv.get('erro'),
                'avisos': conv.get('avisos', []),
                'banco_cod': conv.get('banco_cod', linha_digitos[:3]),
                'banco_nome': conv.get('banco_nome', obter_nome_banco(linha_digitos[:3])),
                'beneficiario_nome': 'Não identificado',
                'beneficiario_doc': '',
                'valor_formatado': conv.get('valor_nominal_formatado', 'R$ 0,00'),
                'valor_centavos': conv.get('valor_nominal_cents', 0),
                'data_vencimento': conv.get('data_vencimento_calculada', ''),
                'fator_vencimento': conv.get('fator_vencimento', linha_digitos[5:9])
            }
            registros.append(reg)
            continue
            
        # 3. Caso a linha seja uma Linha Digitável direta (47 dígitos)
        if len(linha_digitos) == 47:
            inv = converter_linha_para_barras(linha_digitos)
            barras = inv.get('valor', '')
            conv = converter_barras_para_linha(barras) if inv['ok'] else {'ok': False, 'erro': inv.get('erro')}
            reg = {
                'linha_num': idx,
                'origem': 'Linha Digitável (47) Invertida',
                'codigo_barras': barras or 'Erro na inversão',
                'tamanho_barras': len(barras),
                'valido': inv['ok'],
                'linha_digitavel': linha_digitos,
                'linha_digitavel_formatada': conv.get('formatada', ''),
                'erro': inv.get('erro'),
                'avisos': inv.get('avisos', []),
                'banco_cod': inv.get('banco_cod', linha_digitos[:3]),
                'banco_nome': inv.get('banco_nome', obter_nome_banco(linha_digitos[:3])),
                'beneficiario_nome': 'Não identificado',
                'beneficiario_doc': '',
                'valor_formatado': conv.get('valor_nominal_formatado', 'R$ 0,00'),
                'valor_centavos': conv.get('valor_nominal_cents', 0),
                'data_vencimento': conv.get('data_vencimento_calculada', ''),
                'fator_vencimento': conv.get('fator_vencimento', '')
            }
            registros.append(reg)
            continue

        # 4. Procura por qualquer bloco de 44 dígitos na linha
        match_44 = re.search(r'\b\d{44}\b', linha)
        if match_44:
            codigo = match_44.group(0)
            conv = converter_barras_para_linha(codigo)
            reg = {
                'linha_num': idx,
                'origem': 'Trecho extraído (44 dígitos)',
                'codigo_barras': codigo,
                'tamanho_barras': 44,
                'valido': conv['ok'],
                'linha_digitavel': conv.get('valor', ''),
                'linha_digitavel_formatada': conv.get('formatada', ''),
                'erro': conv.get('erro'),
                'avisos': conv.get('avisos', []),
                'banco_cod': conv.get('banco_cod', codigo[:3]),
                'banco_nome': conv.get('banco_nome', obter_nome_banco(codigo[:3])),
                'beneficiario_nome': 'Não identificado',
                'beneficiario_doc': '',
                'valor_formatado': conv.get('valor_nominal_formatado', 'R$ 0,00'),
                'valor_centavos': conv.get('valor_nominal_cents', 0),
                'data_vencimento': conv.get('data_vencimento_calculada', ''),
                'fator_vencimento': conv.get('fator_vencimento', codigo[5:9])
            }
            registros.append(reg)

    return registros

def gerar_excel_xlsx(registros: List[Dict[str, Any]]) -> bytes:
    """
    Gera um arquivo Excel (.xlsx) nativo OpenXML (sem dependências externas)
    colocando o Código de Barras (44 dígitos) e a Linha Digitável (47 dígitos)
    estritamente LADO A LADO, formatados como TEXTO para preservar todos os zeros à esquerda.
    """
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>"""

    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""

    workbook_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="Matacompany - DDA Itau" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>"""

    wb_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""

    # Estilos:
    # 0: Normal
    # 1: Header Azul Marinho (#0f2a4a) com texto branco e negrito
    # 2: Texto em Fonte Monospace (#1e293b) para código de barras / linha
    # 3: Status Válido (Verde claro #ecfdf5, texto verde #065f46)
    # 4: Status Erro (Vermelho claro #fef2f2, texto vermelho #991b1b)
    # 5: Linha zebra (#f8fafc)
    styles_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="5">
    <font><name val="Segoe UI"/><sz val="10"/><color rgb="FF1E293B"/></font>
    <font><b/><name val="Segoe UI"/><sz val="11"/><color rgb="FFFFFFFF"/></font>
    <font><name val="Courier New"/><sz val="10.5"/><color rgb="FF0F172A"/></font>
    <font><b/><name val="Segoe UI"/><sz val="10"/><color rgb="FF065F46"/></font>
    <font><b/><name val="Segoe UI"/><sz val="10"/><color rgb="FF991B1B"/></font>
  </fonts>
  <fills count="6">
    <fill><patternFill fillType="none"/></fill>
    <fill><patternFill fillType="gray125"/></fill>
    <fill><patternFill fillType="solid"><fgColor rgb="FF0F2A4A"/></patternFill></fill>
    <fill><patternFill fillType="solid"><fgColor rgb="FFECFDF5"/></patternFill></fill>
    <fill><patternFill fillType="solid"><fgColor rgb="FFFEF2F2"/></patternFill></fill>
    <fill><patternFill fillType="solid"><fgColor rgb="FFF8FAFC"/></patternFill></fill>
  </fills>
  <borders count="2">
    <border><left/><right/><top/><bottom/></border>
    <border>
      <left style="thin"><color rgb="FFE2E8F0"/></left>
      <right style="thin"><color rgb="FFE2E8F0"/></right>
      <top style="thin"><color rgb="FFE2E8F0"/></top>
      <bottom style="thin"><color rgb="FFE2E8F0"/></bottom>
    </border>
  </borders>
  <cellStyleXfs count="1">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0"/>
  </cellStyleXfs>
  <cellXfs count="6">
    <!-- 0: Geral Normal -->
    <xf numFmtId="49" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyBorder="1"/>
    <!-- 1: Cabeçalho -->
    <xf numFmtId="49" fontId="1" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1">
      <alignment horizontal="center" vertical="center" wrapText="1"/>
    </xf>
    <!-- 2: Monospace Textual (para os códigos) -->
    <xf numFmtId="49" fontId="2" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyFont="1" applyBorder="1"/>
    <!-- 3: Status Válido -->
    <xf numFmtId="49" fontId="3" fillId="3" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1">
      <alignment horizontal="center" vertical="center"/>
    </xf>
    <!-- 4: Status Erro -->
    <xf numFmtId="49" fontId="4" fillId="4" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1">
      <alignment horizontal="center" vertical="center"/>
    </xf>
    <!-- 5: Linha Monospace Zebra -->
    <xf numFmtId="49" fontId="2" fillId="5" borderId="1" xfId="0" applyNumberFormat="1" applyFont="1" applyFill="1" applyBorder="1"/>
  </cellXfs>
</styleSheet>"""

    # Montagem da Sheet com colunas lado a lado
    cols_def = """  <cols>
    <col min="1" max="1" width="8" customWidth="1"/>
    <col min="2" max="2" width="48" customWidth="1"/>
    <col min="3" max="3" width="52" customWidth="1"/>
    <col min="4" max="4" width="56" customWidth="1"/>
    <col min="5" max="5" width="14" customWidth="1"/>
    <col min="6" max="6" width="30" customWidth="1"/>
    <col min="7" max="7" width="34" customWidth="1"/>
    <col min="8" max="8" width="20" customWidth="1"/>
    <col min="9" max="9" width="16" customWidth="1"/>
    <col min="10" max="10" width="14" customWidth="1"/>
    <col min="11" max="11" width="10" customWidth="1"/>
    <col min="12" max="12" width="22" customWidth="1"/>
    <col min="13" max="13" width="35" customWidth="1"/>
  </cols>"""

    headers = [
        "Item",
        "Código de Barras (44 dígitos)",
        "Linha Digitável (47 dígitos)",
        "Linha Digitável Formatada",
        "Status",
        "Banco Emissor",
        "Beneficiário / Cedente",
        "CNPJ / CPF Beneficiário",
        "Valor (R$)",
        "Vencimento",
        "Fator",
        "Origem no Arquivo",
        "Mensagem / Erro / Avisos"
    ]

    def col_to_letter(col_idx: int) -> str:
        res = ""
        while col_idx > 0:
            col_idx, remainder = divmod(col_idx - 1, 26)
            res = chr(65 + remainder) + res
        return res

    rows_xml = []
    
    # Header Row (Linha 1)
    header_cells = []
    for c_idx, h_text in enumerate(headers, start=1):
        ref = f"{col_to_letter(c_idx)}1"
        safe_t = saxutils.escape(h_text)
        header_cells.append(f'<c r="{ref}" t="inlineStr" s="1"><is><t>{safe_t}</t></is></c>')
    rows_xml.append(f'<row r="1" ht="28" customHeight="1">{"".join(header_cells)}</row>')

    # Linhas de Dados
    for r_idx, reg in enumerate(registros, start=2):
        is_zebra = (r_idx % 2 == 1)
        mono_style = "5" if is_zebra else "2"
        normal_style = "0"
        
        status_style = "3" if reg['valido'] else "4"
        status_text = "VÁLIDO" if reg['valido'] else (reg.get('erro', {}).get('codigo', 'ERRO'))
        
        msg_obs = ""
        if not reg['valido'] and reg.get('erro'):
            msg_obs = f"{reg['erro'].get('codigo', '')}: {reg['erro'].get('mensagem', '')}"
        elif reg.get('avisos'):
            msg_obs = " | ".join(reg['avisos'])
            
        cells_data = [
            (str(r_idx - 1), normal_style),
            (reg.get('codigo_barras', ''), mono_style),
            (reg.get('linha_digitavel', ''), mono_style),
            (reg.get('linha_digitavel_formatada', ''), mono_style),
            (status_text, status_style),
            (f"{reg.get('banco_cod', '')} - {reg.get('banco_nome', '')}", normal_style),
            (reg.get('beneficiario_nome', ''), normal_style),
            (reg.get('beneficiario_doc', ''), normal_style),
            (reg.get('valor_formatado', ''), normal_style),
            (reg.get('data_vencimento', ''), normal_style),
            (reg.get('fator_vencimento', ''), normal_style),
            (reg.get('origem', ''), normal_style),
            (msg_obs, normal_style)
        ]
        
        row_cells = []
        for c_idx, (val, style_id) in enumerate(cells_data, start=1):
            ref = f"{col_to_letter(c_idx)}{r_idx}"
            safe_val = saxutils.escape(str(val or ''))
            row_cells.append(f'<c r="{ref}" t="inlineStr" s="{style_id}"><is><t>{safe_val}</t></is></c>')
            
        rows_xml.append(f'<row r="{r_idx}" ht="20" customHeight="1">{"".join(row_cells)}</row>')

    sheet_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
{cols_def}
  <sheetData>
{"".join(rows_xml)}
  </sheetData>
</worksheet>"""

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', content_types)
        z.writestr('_rels/.rels', rels)
        z.writestr('xl/workbook.xml', workbook_xml)
        z.writestr('xl/_rels/workbook.xml.rels', wb_rels)
        z.writestr('xl/styles.xml', styles_xml)
        z.writestr('xl/worksheets/sheet1.xml', sheet_xml)

    return buf.getvalue()

def gerar_csv(registros: List[Dict[str, Any]]) -> bytes:
    """
    Gera CSV formatado com BOM UTF-8 e separador ';' para compatibilidade nativa com o Excel brasileiro.
    """
    output = io.StringIO()
    # UTF-8 BOM
    output.write('\ufeff')
    
    headers = [
        "Item",
        "Codigo_Barras_44",
        "Linha_Digitavel_47",
        "Linha_Digitavel_Formatada",
        "Status",
        "Banco_Codigo",
        "Banco_Nome",
        "Beneficiario_Cedente",
        "CNPJ_CPF_Beneficiario",
        "Valor",
        "Data_Vencimento",
        "Fator_Vencimento",
        "Origem_Arquivo",
        "Observacoes_Erros"
    ]
    output.write(";".join(headers) + "\n")
    
    for idx, reg in enumerate(registros, start=1):
        status_text = "VALIDO" if reg['valido'] else (reg.get('erro', {}).get('codigo', 'ERRO'))
        msg_obs = ""
        if not reg['valido'] and reg.get('erro'):
            msg_obs = f"{reg['erro'].get('codigo', '')}: {reg['erro'].get('mensagem', '')}"
        elif reg.get('avisos'):
            msg_obs = " | ".join(reg['avisos'])
            
        # Zeros à esquerda e códigos longos protegidos para o Excel como ="..."
        cb_excel = f'="{reg.get("codigo_barras", "")}"'
        ld_excel = f'="{reg.get("linha_digitavel", "")}"'
        
        linha_csv = [
            str(idx),
            cb_excel,
            ld_excel,
            f'"{reg.get("linha_digitavel_formatada", "")}"',
            status_text,
            f'"{reg.get("banco_cod", "")}"',
            f'"{reg.get("banco_nome", "")}"',
            f'"{reg.get("beneficiario_nome", "")}"',
            f'"{reg.get("beneficiario_doc", "")}"',
            f'"{reg.get("valor_formatado", "")}"',
            f'"{reg.get("data_vencimento", "")}"',
            f'"{reg.get("fator_vencimento", "")}"',
            f'"{reg.get("origem", "")}"',
            f'"{msg_obs}"'
        ]
        output.write(";".join(linha_csv) + "\n")
        
    return output.getvalue().encode('utf-8')
