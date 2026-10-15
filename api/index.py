import sys
import os
import json
import urllib.parse
from http.server import BaseHTTPRequestHandler

# Adiciona diretório raiz ao path para importar converter.py
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from converter import (
    parse_cnab_dda,
    converter_barras_para_linha,
    converter_linha_para_barras,
    gerar_excel_xlsx,
    gerar_csv
)

class handler(BaseHTTPRequestHandler):

    def send_json(self, status_code: int, data: dict):
        payload = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        self.wfile.write(payload)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path in ('/api/sample', '/api/sample/'):
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            file_path = os.path.join(base_dir, 'exemplo_itau_dda.DET')
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    text_content = f.read()
                self.send_json(200, {
                    'ok': True,
                    'filename': 'exemplo_itau_dda.DET',
                    'content': text_content
                })
            else:
                self.send_json(404, {'ok': False, 'mensagem': 'Arquivo de exemplo não encontrado'})
        else:
            self.send_json(200, {'ok': True, 'servico': 'API DDA Itau CNAB 240', 'status': 'online'})

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        content_length = int(self.headers.get('Content-Length', 0))
        raw_body = self.rfile.read(content_length)

        if path.endswith('/parse'):
            try:
                content_type = self.headers.get('Content-Type', '')
                texto = ""

                if 'application/json' in content_type:
                    data = json.loads(raw_body.decode('utf-8'))
                    texto = data.get('conteudo', '')
                else:
                    try:
                        texto = raw_body.decode('utf-8')
                    except UnicodeDecodeError:
                        texto = raw_body.decode('latin1')

                registros = parse_cnab_dda(texto)
                total = len(registros)
                validos = sum(1 for r in registros if r['valido'])
                erros = total - validos
                soma_centavos = sum(r['valor_centavos'] for r in registros if r['valido'])
                soma_formatada = f"R$ {soma_centavos / 100:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

                self.send_json(200, {
                    'ok': True,
                    'total': total,
                    'validos': validos,
                    'erros': erros,
                    'soma_total': soma_formatada,
                    'registros': registros
                })
            except Exception as e:
                self.send_json(500, {'ok': False, 'mensagem': f'Erro ao processar: {str(e)}'})

        elif path.endswith('/export-excel'):
            try:
                data = json.loads(raw_body.decode('utf-8'))
                registros = data.get('registros', [])
                if not registros and 'conteudo' in data:
                    registros = parse_cnab_dda(data['conteudo'])

                xlsx_bytes = gerar_excel_xlsx(registros)
                self.send_response(200)
                self.send_header('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                self.send_header('Content-Disposition', 'attachment; filename="DDA_Itau_Barras_e_Linhas.xlsx"')
                self.send_header('Content-Length', str(len(xlsx_bytes)))
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(xlsx_bytes)
            except Exception as e:
                self.send_json(500, {'ok': False, 'mensagem': f'Erro ao gerar Excel: {str(e)}'})

        elif path.endswith('/export-csv'):
            try:
                data = json.loads(raw_body.decode('utf-8'))
                registros = data.get('registros', [])
                if not registros and 'conteudo' in data:
                    registros = parse_cnab_dda(data['conteudo'])

                csv_bytes = gerar_csv(registros)
                self.send_response(200)
                self.send_header('Content-Type', 'text/csv; charset=utf-8')
                self.send_header('Content-Disposition', 'attachment; filename="DDA_Itau_Barras_e_Linhas.csv"')
                self.send_header('Content-Length', str(len(csv_bytes)))
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(csv_bytes)
            except Exception as e:
                self.send_json(500, {'ok': False, 'mensagem': f'Erro ao gerar CSV: {str(e)}'})

        elif path.endswith('/convert-single'):
            try:
                data = json.loads(raw_body.decode('utf-8'))
                valor = data.get('valor', '')
                direcao = data.get('direcao', 'barras_para_linha')

                if direcao == 'barras_para_linha':
                    res = converter_barras_para_linha(valor)
                else:
                    res = converter_linha_para_barras(valor)
                self.send_json(200, res)
            except Exception as e:
                self.send_json(500, {'ok': False, 'mensagem': f'Erro na conversão: {str(e)}'})

        else:
            self.send_json(404, {'ok': False, 'mensagem': 'Endpoint não encontrado'})
