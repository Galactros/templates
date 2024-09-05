import os
from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.parse
import subprocess

class WebInterface(BaseHTTPRequestHandler):

    # Exibe o formulário HTML para o usuário
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        html = '''
        <html>
        <body>
            <h2>Executar OpenShift Tool</h2>
            <form method="POST">
                <label for="clusters">Clusters (separados por vírgulas):</label><br>
                <input type="text" id="clusters" name="clusters"><br><br>
                <label for="namespaces">Namespaces (separados por ponto e vírgula):</label><br>
                <input type="text" id="namespaces" name="namespaces"><br><br>
                <label for="patterns">Padrões de Pods (separados por ponto e vírgula):</label><br>
                <input type="text" id="patterns" name="patterns"><br><br>
                <label for="username">Username:</label><br>
                <input type="text" id="username" name="username"><br><br>
                <label for="password">Password:</label><br>
                <input type="password" id="password" name="password"><br><br>
                <input type="submit" value="Executar">
            </form>
        </body>
        </html>
        '''
        self.wfile.write(bytes(html, "utf8"))
        return

    # Processa os dados enviados pelo formulário e chama o main.py com os parâmetros
    def do_POST(self):
        # Extrai os dados do formulário
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        params = urllib.parse.parse_qs(post_data.decode('utf-8'))

        clusters = params.get('clusters', [''])[0]
        namespaces = params.get('namespaces', [''])[0]
        patterns = params.get('patterns', [''])[0]
        username = params.get('username', [''])[0]
        password = params.get('password', [''])[0]

        # Verifica se todos os campos foram preenchidos
        if not all([clusters, namespaces, patterns, username, password]):
            self.send_response(400)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"Todos os campos sao obrigatorios!")
            return

        # Monta o comando para chamar o main.py com os parâmetros
        command = [
            'python3', 'main.py',
            '--clusters', clusters,
            '--namespaces', namespaces,
            '--patterns', patterns,
            '--username', username,
            '--password', password
        ]

        try:
            # Executa o comando chamando o main.py
            result = subprocess.run(command, capture_output=True, text=True)

            # Exibe o resultado da execução na página
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"<h2>Resultado da Execucao:</h2>")
            self.wfile.write(bytes("<pre>" + result.stdout + "</pre>", "utf8"))
            if result.stderr:
                self.wfile.write(bytes("<pre style='color:red'>" + result.stderr + "</pre>", "utf8"))

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(bytes(f"<h2>Erro ao executar o script:</h2><p>{str(e)}</p>", "utf8"))

def run(server_class=HTTPServer, handler_class=WebInterface, port=8080):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f'Servidor web iniciado na porta {port}...')
    httpd.serve_forever()

if __name__ == "__main__":
    run()
