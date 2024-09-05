import subprocess
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs

# Defina uma porta para o servidor
PORT = 8080

# Handler para responder às solicitações HTTP
class MyHandler(BaseHTTPRequestHandler):

    # Função que será chamada quando houver uma solicitação GET (carregar a página HTML)
    def do_GET(self):
        # Resposta com código 200 (OK)
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

        # Conteúdo HTML da página com um formulário
        html_content = '''
        <html>
            <head><title>Gerar Relatório de Pods</title></head>
            <body>
                <h1>Gerar Relatório de Pods</h1>
                <form method="POST" action="/generate_report">
                    <label>Clusters:</label>
                    <input type="text" name="clusters" value="cluster1,cluster2"><br><br>
                    <label>Namespaces:</label>
                    <input type="text" name="namespaces" value="namespace1;namespace2"><br><br>
                    <label>Padrões de Pods:</label>
                    <input type="text" name="patterns" value="pattern1,pattern2"><br><br>
                    <input type="submit" value="Gerar Relatório">
                </form>
            </body>
        </html>
        '''
        # Envia o conteúdo HTML como resposta
        self.wfile.write(html_content.encode('utf-8'))

    # Função que será chamada quando houver uma solicitação POST (enviar os dados do formulário)
    def do_POST(self):
        if self.path == '/generate_report':
            # Lê o tamanho dos dados enviados no corpo da solicitação POST
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length).decode('utf-8')

            # Processa os dados do formulário
            form_data = parse_qs(post_data)
            clusters = form_data.get('clusters', [''])[0]
            namespaces = form_data.get('namespaces', [''])[0]
            patterns = form_data.get('patterns', [''])[0]

            # Executa o script Python que gera o relatório
            subprocess.run(['python', 'seu_script.py', '-c', clusters, '-n', namespaces, '-p', patterns])

            # Caminho para o arquivo gerado
            file_path = 'pods_status.xlsx'

            # Verifica se o arquivo foi gerado e envia como resposta
            if os.path.exists(file_path):
                # Cabeçalhos para download de arquivo
                self.send_response(200)
                self.send_header('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                self.send_header('Content-Disposition', 'attachment; filename="pods_status.xlsx"')
                self.end_headers()

                # Lê o arquivo e envia o conteúdo como resposta
                with open(file_path, 'rb') as file:
                    self.wfile.write(file.read())
            else:
                # Se o arquivo não foi encontrado, retorna uma mensagem de erro
                self.send_response(404)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(b"Erro: Arquivo nao encontrado.")

# Função para iniciar o servidor
def run(server_class=HTTPServer, handler_class=MyHandler, port=PORT):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f"Servidor rodando na porta {port}...")
    httpd.serve_forever()

# Iniciar o servidor
if __name__ == '__main__':
    run()
