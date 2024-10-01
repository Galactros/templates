import os
from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.parse
import subprocess
from main import test_connectivity_in_pod, login_to_cluster, collect_logs_from_pods

class WebInterface(BaseHTTPRequestHandler):

    # Exibe o formulário HTML para o usuário
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        html = '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>OpenShift Tool Interface</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    background-color: #f2f2f2;
                    margin: 0;
                    padding: 0;
                }
                .container {
                    width: 80%;
                    margin: auto;
                    overflow: hidden;
                    padding: 20px;
                }
                h2 {
                    color: #333;
                    border-bottom: 2px solid #333;
                    padding-bottom: 10px;
                }
                form {
                    background: #fff;
                    padding: 20px;
                    margin-bottom: 20px;
                    border-radius: 5px;
                }
                label {
                    display: block;
                    margin-top: 10px;
                    font-weight: bold;
                }
                input[type="text"],
                input[type="password"] {
                    width: 100%;
                    padding: 8px;
                    margin-top: 5px;
                    border: 1px solid #ccc;
                    border-radius: 4px;
                    box-sizing: border-box;
                }
                input[type="submit"] {
                    margin-top: 20px;
                    padding: 10px 15px;
                    background-color: #28a745;
                    color: #fff;
                    border: none;
                    border-radius: 4px;
                    cursor: pointer;
                }
                input[type="submit"]:hover {
                    background-color: #218838;
                }
                /* Estilo para mensagens de erro */
                .error {
                    color: red;
                    margin-top: 10px;
                }
            </style>
            <script>
                // Função para validar os formulários
                function validateForm(event) {
                    const form = event.target;
                    const inputs = form.querySelectorAll('input[required]');
                    let valid = true;
                    inputs.forEach(input => {
                        if (input.value.trim() === '') {
                            valid = false;
                            input.style.borderColor = 'red';
                        } else {
                            input.style.borderColor = '#ccc';
                        }
                    });
                    if (!valid) {
                        event.preventDefault();
                        alert('Por favor, preencha todos os campos obrigatórios.');
                    }
                }
                // Adicionar evento de validação aos formulários ao carregar a página
                window.onload = function() {
                    const forms = document.querySelectorAll('form');
                    forms.forEach(form => {
                        form.addEventListener('submit', validateForm);
                    });
                };
            </script>
        </head>
        <body>
            <div class="container">
                <h2>Executar OpenShift Tool</h2>
                <form method="POST" action="/execute-script">
                    <label for="clusters">Clusters (separados por vírgulas):</label>
                    <input type="text" id="clusters" name="clusters" required>
    
                    <label for="namespaces">Namespaces (separados por ponto e vírgula):</label>
                    <input type="text" id="namespaces" name="namespaces" required>
    
                    <label for="patterns">Padrões de Pods (separados por ponto e vírgula):</label>
                    <input type="text" id="patterns" name="patterns" required>
    
                    <label for="username">Username:</label>
                    <input type="text" id="username" name="username" required>
    
                    <label for="password">Password:</label>
                    <input type="password" id="password" name="password" required>
    
                    <input type="submit" value="Executar">
                </form>
    
                <h2>Testar conectividade no pod</h2>
                <form method="POST" action="/test-connectivity">
                    <label for="cluster">Cluster:</label>
                    <input type="text" id="cluster" name="cluster" required>
    
                    <label for="namespace">Namespace:</label>
                    <input type="text" id="namespace" name="namespace" required>
    
                    <label for="pod_name">Nome do Pod:</label>
                    <input type="text" id="pod_name" name="pod_name" required>
    
                    <label for="url">URL para testar:</label>
                    <input type="text" id="url" name="url" value="http://www.google.com" required>
    
                    <label for="username">Username:</label>
                    <input type="text" id="username" name="username" required>
    
                    <label for="password">Password:</label>
                    <input type="password" id="password" name="password" required>
    
                    <input type="submit" value="Testar Conectividade">
                </form>
    
                <h2>Coletar logs do workload</h2>
                <form method="POST" action="/collect-logs">
                    <label for="cluster">Cluster:</label>
                    <input type="text" id="cluster" name="cluster" required>
    
                    <label for="namespace">Namespace:</label>
                    <input type="text" id="namespace" name="namespace" required>
    
                    <label for="pattern">Padrão de Pods (Workload):</label>
                    <input type="text" id="pattern" name="pattern" required>
    
                    <label for="username">Username:</label>
                    <input type="text" id="username" name="username" required>
    
                    <label for="password">Password:</label>
                    <input type="password" id="password" name="password" required>
    
                    <input type="submit" value="Coletar Logs">
                </form>
            </div>
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
        elif self.path == '/collect-logs':
            self.collect_logs()

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

# Função para coletar logs dos pods de um workload e compactá-los
    def collect_logs(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        params = urllib.parse.parse_qs(post_data.decode('utf-8'))

        cluster = params.get('cluster', [''])[0]
        namespace = params.get('namespace', [''])[0]
        pattern = params.get('pattern', [''])[0]
        username = params.get('username', [''])[0]
        password = params.get('password', [''])[0]

        # Verifica se todos os campos foram preenchidos
        if not all([cluster, namespace, pattern, username, password]):
            self.send_response(400)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"Todos os campos sao obrigatorios!")
            return

        try:
            # Coleta e compacta os logs dos pods
            tar_file_path = collect_logs_from_pods(cluster, namespace, pattern, username, password)

            # Envia o arquivo .tar.gz para download
            self.send_response(200)
            self.send_header('Content-Type', 'application/gzip')
            self.send_header(f'Content-Disposition', f'attachment; filename="{os.path.basename(tar_file_path)}"')
            self.end_headers()

            # Lê e envia o conteúdo do arquivo tar.gz
            with open(tar_file_path, 'rb') as tar_file:
                self.wfile.write(tar_file.read())

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(bytes(f"<h2>Erro ao coletar logs:</h2><p>{str(e)}</p>", "utf8"))

def run(server_class=HTTPServer, handler_class=WebInterface, port=4545):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f'Servidor web iniciado na porta {port}...')
    httpd.serve_forever()

if __name__ == "__main__":
    run()
