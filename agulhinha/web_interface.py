import os
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.parse
import subprocess
from main import test_connectivity_in_pod, login_to_cluster, collect_logs_from_pods, generate_pods_report

sessions = {}

class WebInterface(BaseHTTPRequestHandler):

    def do_GET(self):
        session = self.get_session()
        if self.path == '/':
            if session is None:
                self.show_login_page()
            else:
                self.show_main_page(session)
        elif self.path == '/logout':
            self.handle_logout()
        else:
            # Se a rota não for reconhecida, redireciona para a página principal
            self.send_response(302)
            self.send_header('Location', '/')
            self.end_headers()

    def do_POST(self):
        if self.path == '/login':
            self.handle_login()
        else:
            session = self.get_session()
            if session is None:
                # Redireciona para a página de login
                self.send_response(302)
                self.send_header('Location', '/')
                self.end_headers()
            else:
                if self.path == '/execute-script':
                    self.execute_script(session)
                elif self.path == '/test-connectivity':
                    self.test_connectivity(session)
                elif self.path == '/collect-logs':
                    self.collect_logs(session)
                else:
                    # Se a rota não for reconhecida, redireciona para a página principal
                    self.send_response(302)
                    self.send_header('Location', '/')
                    self.end_headers()

    # Função para exibir a página de login
    def show_login_page(self, error_message=None):
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')  # Inclui o charset no cabeçalho
        self.end_headers()
        html = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Login - OpenShift Tool Interface</title>
            <style>
                body {{ font-family: Arial, sans-serif; background-color: #f2f2f2; }}
                .login-container {{ width: 300px; margin: 100px auto; padding: 20px; background: #fff; border-radius: 5px; }}
                .error-message {{ color: red; }}
                input[type="text"], input[type="password"] {{
                    width: 100%;
                    padding: 8px;
                    margin-top: 5px;
                    border: 1px solid #ccc;
                    border-radius: 4px;
                    box-sizing: border-box;
                }}
                input[type="submit"] {{
                    margin-top: 20px;
                    padding: 10px 15px;
                    background-color: #28a745;
                    color: #fff;
                    border: none;
                    border-radius: 4px;
                    cursor: pointer;
                }}
                input[type="submit"]:hover {{
                    background-color: #218838;
                }}
            </style>
        </head>
        <body>
            <div class="login-container">
                <h2>Login</h2>
                {f"<p class='error-message'>{error_message}</p>" if error_message else ""}
                <form method="POST" action="/login">
                    <label for="username">Username:</label><br>
                    <input type="text" id="username" name="username" required><br><br>
                    <label for="password">Senha:</label><br>
                    <input type="password" id="password" name="password" required><br><br>
                    <input type="submit" value="Entrar">
                </form>
            </div>
        </body>
        </html>
        '''
        self.wfile.write(html.encode('utf-8'))  # Codifica o HTML em UTF-8 antes de enviar

    # Função para processar o login
    def handle_login(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        params = urllib.parse.parse_qs(post_data.decode('utf-8'))

        username = params.get('username', [''])[0]
        password = params.get('password', [''])[0]

        if username and password:
            # Cria um ID de sessão único
            session_id = str(uuid.uuid4())
            # Armazena as credenciais na sessão
            sessions[session_id] = {'username': username, 'password': password}

            # Envia um cookie com o ID de sessão
            self.send_response(302)
            self.send_header('Location', '/')
            self.send_header('Set-Cookie', f'session_id={session_id}; HttpOnly')
            self.end_headers()
        else:
            # Credenciais inválidas, mostra a página de login novamente com uma mensagem de erro
            self.show_login_page(error_message="Username ou senha inválidos.")

    # Função para obter a sessão atual a partir do cookie
    def get_session(self):
        if 'Cookie' in self.headers:
            cookies = self.headers.get('Cookie')
            cookies = cookies.split(';')
            for cookie in cookies:
                if 'session_id' in cookie:
                    session_id = cookie.split('=')[1].strip()
                    session = sessions.get(session_id)
                    if session:
                        return session
        return None

    # Função para exibir a página principal
    def show_main_page(self, session):
        username = session['username']
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')  # Inclui o charset no cabeçalho
        self.end_headers()
        html = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>OpenShift Tool Interface</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    background-color: #f2f2f2;
                    margin: 0;
                    padding: 0;
                }}
                .container {{
                    width: 80%;
                    margin: auto;
                    overflow: hidden;
                    padding: 20px;
                }}
                h2 {{
                    color: #333;
                    border-bottom: 2px solid #333;
                    padding-bottom: 10px;
                }}
                form {{
                    background: #fff;
                    padding: 20px;
                    margin-bottom: 20px;
                    border-radius: 5px;
                }}
                label {{
                    display: block;
                    margin-top: 10px;
                    font-weight: bold;
                }}
                input[type="text"],
                input[type="password"] {{
                    width: 100%;
                    padding: 8px;
                    margin-top: 5px;
                    border: 1px solid #ccc;
                    border-radius: 4px;
                    box-sizing: border-box;
                }}
                input[type="submit"] {{
                    margin-top: 20px;
                    padding: 10px 15px;
                    background-color: #28a745;
                    color: #fff;
                    border: none;
                    border-radius: 4px;
                    cursor: pointer;
                }}
                input[type="submit"]:hover {{
                    background-color: #218838;
                }}
                /* Estilo para mensagens de erro */
                .error {{
                    color: red;
                    margin-top: 10px;
                }}
                .logout {{
                    float: right;
                    margin-top: -60px;
                }}
                .logout a {{
                    text-decoration: none;
                    color: #fff;
                    background-color: #dc3545;
                    padding: 10px 15px;
                    border-radius: 4px;
                }}
                .logout a:hover {{
                    background-color: #c82333;
                }}
            </style>
            <script>
                // Função para validar os formulários
                function validateForm(event) {{
                    const form = event.target;
                    const inputs = form.querySelectorAll('input[required]');
                    let valid = true;
                    inputs.forEach(input => {{
                        if (input.value.trim() === '') {{
                            valid = false;
                            input.style.borderColor = 'red';
                        }} else {{
                            input.style.borderColor = '#ccc';
                        }}
                    }});
                    if (!valid) {{
                        event.preventDefault();
                        alert('Por favor, preencha todos os campos obrigatórios.');
                    }}
                }}
                // Adicionar evento de validação aos formulários ao carregar a página
                window.onload = function() {{
                    const forms = document.querySelectorAll('form');
                    forms.forEach(form => {{
                        form.addEventListener('submit', validateForm);
                    }});
                }};
            </script>
        </head>
        <body>
            <div class="container">
                <div class="logout">
                    <a href="/logout">Logout</a>
                </div>
                <h2>Bem-vindo, {username}</h2>
                
                <form method="POST" action="/execute-script">
                    <h3>Executar OpenShift Tool</h3>
                    <label for="clusters">Clusters (separados por vírgulas):</label>
                    <input type="text" id="clusters" name="clusters" required>

                    <label for="namespaces">Namespaces (separados por ponto e vírgula):</label>
                    <input type="text" id="namespaces" name="namespaces" required>

                    <label for="patterns">Padrões de Pods (separados por ponto e vírgula):</label>
                    <input type="text" id="patterns" name="patterns" required>

                    <input type="submit" value="Executar">
                </form>

                <form method="POST" action="/test-connectivity">
                    <h3>Testar conectividade no pod</h3>
                    <label for="cluster">Cluster:</label>
                    <input type="text" id="cluster" name="cluster" required>

                    <label for="namespace">Namespace:</label>
                    <input type="text" id="namespace" name="namespace" required>

                    <label for="pod_name">Nome do Pod:</label>
                    <input type="text" id="pod_name" name="pod_name" required>

                    <label for="url">URL para testar:</label>
                    <input type="text" id="url" name="url" value="http://www.google.com" required>

                    <input type="submit" value="Testar Conectividade">
                </form>

                <form method="POST" action="/collect-logs">
                    <h3>Coletar logs do workload</h3>
                    <label for="cluster">Cluster:</label>
                    <input type="text" id="cluster" name="cluster" required>

                    <label for="namespace">Namespace:</label>
                    <input type="text" id="namespace" name="namespace" required>

                    <label for="pattern">Padrão de Pods (Workload):</label>
                    <input type="text" id="pattern" name="pattern" required>

                    <input type="submit" value="Coletar Logs">
                </form>
            </div>
        </body>
        </html>
        '''
        self.wfile.write(html.encode('utf-8'))  # Codifica o HTML em UTF-8 antes de enviar

    # Função para processar o logout
    def handle_logout(self):
        session_id = None
        if 'Cookie' in self.headers:
            cookies = self.headers.get('Cookie').split(';')
            for cookie in cookies:
                if 'session_id' in cookie:
                    session_id = cookie.split('=')[1].strip()
                    break
        if session_id and session_id in sessions:
            del sessions[session_id]
        # Limpa o cookie de sessão
        self.send_response(302)
        self.send_header('Location', '/')
        self.send_header('Set-Cookie', 'session_id=deleted; expires=Thu, 01 Jan 1970 00:00:00 GMT')
        self.end_headers()

    # Função para executar o script principal
    def execute_script(self, session):
        username = session['username']
        password = session['password']
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        params = urllib.parse.parse_qs(post_data.decode('utf-8'))
    
        clusters = params.get('clusters', [''])[0]
        namespaces = params.get('namespaces', [''])[0]
        patterns = params.get('patterns', [''])[0]
    
        # Verifica se todos os campos foram preenchidos
        if not all([clusters, namespaces, patterns]):
            self.send_response(400)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            mensagem = "Todos os campos são obrigatórios!"
            self.wfile.write(mensagem.encode('utf-8'))
            return
    
        try:
            # Chama a função generate_pods_report diretamente
            csv_file = generate_pods_report(clusters, namespaces, patterns, username, password)
    
            # Verifica se o arquivo CSV foi gerado
            if os.path.exists(csv_file):
                # Envia o arquivo CSV para download
                self.send_response(200)
                self.send_header('Content-Type', 'text/csv')
                self.send_header('Content-Disposition', f'attachment; filename="{os.path.basename(csv_file)}"')
                self.end_headers()
    
                # Lê e envia o conteúdo do arquivo CSV
                with open(csv_file, 'rb') as file:
                    self.wfile.write(file.read())
            else:
                # Caso o arquivo CSV não tenha sido gerado
                self.send_response(500)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                mensagem = "<h2>Erro: Arquivo CSV não foi gerado.</h2>"
                self.wfile.write(mensagem.encode('utf-8'))
    
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            mensagem = f"<h2>Erro ao executar o script:</h2><p>{str(e)}</p>"
            self.wfile.write(mensagem.encode('utf-8'))

    # Função para testar conectividade em um pod
    def test_connectivity(self, session):
        username = session['username']
        password = session['password']
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        params = urllib.parse.parse_qs(post_data.decode('utf-8'))

        cluster = params.get('cluster', [''])[0]
        namespace = params.get('namespace', [''])[0]
        pod_name = params.get('pod_name', [''])[0]
        url = params.get('url', [''])[0]

        # Verifica se todos os campos foram preenchidos
        if not all([cluster, namespace, pod_name, url]):
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
    def collect_logs(self, session):
        username = session['username']
        password = session['password']
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        params = urllib.parse.parse_qs(post_data.decode('utf-8'))

        cluster = params.get('cluster', [''])[0]
        namespace = params.get('namespace', [''])[0]
        pattern = params.get('pattern', [''])[0]

        # Verifica se todos os campos foram preenchidos
        if not all([cluster, namespace, pattern]):
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
