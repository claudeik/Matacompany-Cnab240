"""
Servidor Web do Portal DDA Itaú - Conversor CNAB 240
Executa servidor HTTP nativo em Python sem necessidade de dependências externas.
"""

import sys
import os
import json
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any

from converter import (
    parse_cnab_dda,
    converter_barras_para_linha,
    converter_linha_para_barras,
    gerar_excel_xlsx,
    gerar_csv
)

PORT = 8000
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class PortalHandler(BaseHTTPRequestHandler):

    def send_json(self, status_code: int, data: Any):
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

        # 1. Página Principal
        if path in ('/', '/index.html'):
            file_path = os.path.join(BASE_DIR, 'index.html')
            if os.path.exists(file_path):
                with open(file_path, 'rb') as f:
                    content = f.read()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return
            else:
                self.send_error(404, "Arquivo index.html não encontrado")
                return

        # 2. Arquivo de Exemplo .DET
        elif path in ('/exemplo_itau_dda.DET', '/api/sample-file'):
            file_path = os.path.join(BASE_DIR, 'exemplo_itau_dda.DET')
            if os.path.exists(file_path):
                with open(file_path, 'rb') as f:
                    content = f.read()
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain; charset=utf-8')
                self.send_header('Content-Disposition', 'attachment; filename="exemplo_itau_dda.DET"')
                self.send_header('Content-Length', str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return
            else:
                self.send_error(404, "Arquivo de exemplo não encontrado")
                return

        # 3. API para obter conteúdo do arquivo de exemplo
        elif path == '/api/sample':
            file_path = os.path.join(BASE_DIR, 'exemplo_itau_dda.DET')
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    text_content = f.read()
                self.send_json(200, {
                    'ok': True,
                    'filename': 'exemplo_itau_dda.DET',
                    'content': text_content
                })
                return
            else:
                self.send_json(404, {'ok': False, 'mensagem': 'Arquivo de exemplo não encontrado'})
                return

        else:
            self.send_error(404, "Rota não encontrada")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        content_length = int(self.headers.get('Content-Length', 0))
        raw_body = self.rfile.read(content_length)

        # 1. Processamento / Upload de Arquivo ou Texto
        if path == '/api/parse':
            try:
                content_type = self.headers.get('Content-Type', '')
                texto = ""

                # Se for JSON
                if 'application/json' in content_type:
                    data = json.loads(raw_body.decode('utf-8'))
                    texto = data.get('conteudo', '')
                # Se for Multipart Form Data (upload de arquivo direto)
                elif 'multipart/form-data' in content_type:
                    # Parse simplificado de multipart sem depender de cgi deprecado no Python 3.13
                    boundary = content_type.split("boundary=")[-1].encode()
                    parts = raw_body.split(boundary)
                    for part in parts:
                        if b'filename="' in part:
                            header_body_split = part.split(b'\r\n\r\n', 1)
                            if len(header_body_split) == 2:
                                file_bytes = header_body_split[1].rstrip(b'\r\n--')
                                try:
                                    texto = file_bytes.decode('utf-8')
                                except UnicodeDecodeError:
                                    try:
                                        texto = file_bytes.decode('latin1')
                                    except Exception:
                                        texto = file_bytes.decode('utf-8', errors='replace')
                                break
                else:
                    # Texto bruto
                    try:
                        texto = raw_body.decode('utf-8')
                    except UnicodeDecodeError:
                        texto = raw_body.decode('latin1')

                registros = parse_cnab_dda(texto)
                
                # Métricas
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

        # 2. Exportação para Excel (.xlsx) Lado a Lado
        elif path == '/api/export-excel':
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

        # 3. Exportação para CSV (Padrão Excel Brasileiro)
        elif path == '/api/export-csv':
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

        # 4. Conversor Unitário
        elif path == '/api/convert-single':
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
            self.send_error(404, "Rota não encontrada")

def run_server(port=PORT):
    server_address = ('', port)
    try:
        httpd = HTTPServer(server_address, PortalHandler)
        print(f"============================================================")
        print(f" Portal DDA Itaú - Conversor CNAB 240 Iniciado com Sucesso! ")
        print(f" Acesse no seu navegador: http://localhost:{port}           ")
        print(f"============================================================")
        httpd.serve_forever()
    except OSError as e:
        if port < 8020:
            print(f"Porta {port} em uso, tentando porta {port + 1}...")
            run_server(port + 1)
        else:
            raise e

if __name__ == '__main__':
    run_server()
