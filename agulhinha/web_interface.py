import os
from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.parse
import subprocess
from main import test_connectivity_in_pod, login_to_cluster

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
            <form method="POST" action="/execute-script">
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

            <h2>Testar conectividade no pod</h2>
            <form method="POST" action="/test-connectivity">
                <label for="cluster">Cluster:</label><br>
                <input type="text" id="cluster" name="cluster"><br><br>
                <label for="namespace">Namespace:</label><br>
                <input type="text" id="namespace" name="namespace"><br><br>
                <label for="pod_name">Nome do Pod:</label><br>
                <input type="text" id="pod_name" name="pod_name"><br><br>
                <label for="url">URL para testar:</label><br>
                <input type="text" id="url" name="url" value="http://www.google.com"><br><br>
                <input type="hidden" name="username" value=""><!-- Será preenchido com JavaScript -->
                <input type="hidden" name="password" value=""><!-- Será preenchido com JavaScript -->
                <input type="submit" value="Testar Conectividade">
            </form>

            <script>
                // Preenche os campos de username e password no formulário de teste de conectividade
                document.querySelector('form[action="/test-connectivity"] input[name="username"]').value =
                    document.querySelector('form[action="/execute-script"] input[name="username"]').value;
                document.querySelector('form[action="/test-connectivity"] input[name="password"]').value =
                    document.querySelector('form[action="/execute-script"] input[name="password"]').value;
            </script>
        </body>
        </html>
        '''
        self.wfile.write(bytes(html, "utf8"))
        return

    # Redireciona as requisições POST de acordo com o que foi enviado no formulário
    def do_POST(self):
        if self.path == '/execute-script':
            self.execute_script()
        elif self.path == '/test-connectivity':
            self.test_connectivity()

    # Função para executar o script principal
    def execute_script(self):
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
            result = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = result.communicate()

            # Verifica se houve erro
            if result.returncode != 0:
                self.send_response(500)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(bytes(f"<h2>Erro ao executar o script:</h2><pre>{stderr.decode('utf-8')}</pre>", "utf8"))
                return

            # Nome do arquivo CSV gerado
            csv_file = "pods_status.csv"

            # Verifica se o arquivo foi gerado
            if os.path.exists(csv_file):
                # Envia o arquivo CSV para download
                self.send_response(200)
                self.send_header('Content-Type', 'text/csv')
                self.send_header('Content-Disposition', 'attachment; filename="pods_status.csv"')
                self.end_headers()

                # Lê e envia o conteúdo do arquivo CSV
                with open(csv_file, 'rb') as file:
                    self.wfile.write(file.read())

            else:
                # Caso o arquivo CSV não tenha sido gerado
                self.send_response(500)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(b"<h2>Erro: Arquivo CSV nao foi gerado.</h2>")

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(bytes(f"<h2>Erro ao executar o script:</h2><p>{str(e)}</p>", "utf8"))

    # Função para testar conectividade em um pod
    def test_connectivity(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        params = urllib.parse.parse_qs(post_data.decode('utf-8'))

        cluster = params.get('cluster', [''])[0]
        namespace = params.get('namespace', [''])[0]
        pod_name = params.get('pod_name', [''])[0]
        url = params.get('url', [''])[0]
        username = params.get('username', [''])[0]
        password = params.get('password', [''])[0]

        # Verifica se todos os campos foram preenchidos
        if not all([cluster, namespace, pod_name, url, username, password]):
            self.send_response(400)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"Todos os campos sao obrigatorios!")
            return

        # Conecta ao cluster antes de realizar o teste
        login_to_cluster(cluster, username, password)

        # Executa o teste de conectividade no pod
        result = test_connectivity_in_pod(cluster, namespace, pod_name, url)

        # Exibe o resultado na página
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"<h2>Resultado do Teste de Conectividade:</h2>")
        self.wfile.write(bytes(f"<pre>{result}</pre>", "utf8"))


def run(server_class=HTTPServer, handler_class=WebInterface, port=4545):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f'Servidor web iniciado na porta {port}...')
    httpd.serve_forever()

if __name__ == "__main__":
    run()
