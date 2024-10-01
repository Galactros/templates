import os
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.parse
import subprocess
from main import test_connectivity_in_pod, login_to_cluster, collect_logs_from_pods

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
        elif self.path.startswith('/download-file'):
            self.serve_file()
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
            <meta charset="utf-8">  <!-- Especifica a codificação no HTML -->
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
                /* Estilos para o overlay de carregamento e spinner */
                #loading-overlay {{
                    position: fixed;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    background-color: rgba(0, 0, 0, 0.5);
                    z-index: 9999;
                    display: none;
                    flex-direction: column;
                    justify-content: center;
                    align-items: center;
                    color: #fff;
                }}

                .spinner {{
                    border: 16px solid #f3f3f3;
                    border-top: 16px solid #3498db;
                    border-radius: 50%;
                    width: 120px;
                    height: 120px;
                    animation: spin 2s linear infinite;
                    margin-bottom: 20px;
                }}

                @keyframes spin {{
                    0% {{ transform: rotate(0deg); }}
                    100% {{ transform: rotate(360deg); }}
                }}
            </style>
            <script>
                function showLoadingOverlay() {{
                    document.getElementById('loading-overlay').style.display = 'flex';
                }}

                function hideLoadingOverlay() {{
                    document.getElementById('loading-overlay').style.display = 'none';
                }}

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
                    }} else {{
                        showLoadingOverlay();
                    }}
                }}

                window.onload = function() {{
                    const form = document.querySelector('form');
                    form.addEventListener('submit', validateForm);

                    const iframe = document.getElementById('invisible_iframe');
                    if (iframe) {{
                        iframe.onload = function() {{
                            hideLoadingOverlay();
                        }};
                    }}
                }};
            </script>
        </head>
        <body>
            <div class="login-container">
                <h2>Login</h2>
                {f"<p class='error-message'>{error_message}</p>" if error_message else ""}
                <form method="POST" action="/login" target="invisible_iframe">
                    <label for="username">Username:</label><br>
                    <input type="text" id="username" name="username" required><br><br>
                    <label for="password">Senha:</label><br>
                    <input type="password" id="password" name="password" required><br><br>
                    <input type="submit" value="Entrar">
                </form>
            </div>
            <!-- Overlay de carregamento -->
            <div id="loading-overlay">
                <div class="spinner"></div>
                <p>Processando sua solicitação...</p>
            </div>
            <!-- Iframe oculto -->
            <iframe id="invisible_iframe" name="invisible_iframe" style="display:none;"></iframe>
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
            <meta charset="utf-8">  <!-- Especifica a codificação no HTML -->
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
                /* Estilos para o overlay de carregamento e spinner */
                #loading-overlay {{
                    position: fixed;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    background-color: rgba(0, 0, 0, 0.5);
                    z-index: 9999;
                    display: none;
                    flex-direction: column;
                    justify-content: center;
                    align-items: center;
                    color: #fff;
                }}

                .spinner {{
                    border: 16px solid #f3f3f3;
                    border-top: 16px solid #3498db;
                    border-radius: 50%;
                    width: 120px;
                    height: 120px;
                    animation: spin 2s linear infinite;
                    margin-bottom: 20px;
                }}

                @keyframes spin {{
                    0% {{ transform: rotate(0deg); }}
                    100% {{ transform: rotate(360deg); }}
                }}
            </style>
            <script>
                function showLoadingOverlay() {{
                    document.getElementById('loading-overlay').style.display = 'flex';
                }}

                function hideLoadingOverlay() {{
                    document.getElementById('loading-overlay').style.display = 'none';
                }}

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
                    }} else {{
                        showLoadingOverlay();
                    }}
                }}

                window.onload = function() {{
                    const forms = document.querySelectorAll('form');
                    forms.forEach(form => {{
                        form.addEventListener('submit', validateForm);
                    }});

                    const iframe = document.getElementById('invisible_iframe');
                    iframe.onload = function() {{
                        // Oculta o overlay de carregamento
                        hideLoadingOverlay();
                    }};
                }};
            </script>
        </head>
        <body>
            <div class="container">
                <div class="logout">
                    <a href="/logout">Logout</a>
                </div>
                <h2>Bem-vindo, {username}</h2>
                
                <form method="POST" action="/execute-script" target="invisible_iframe">
                    <h3>Executar OpenShift Tool</h3>
                    <label for="clusters">Clusters (separados por vírgulas):</label>
                    <input type="text" id="clusters" name="clusters" required>

                    <label for="namespaces">Namespaces (separados por ponto e vírgula):</label>
                    <input type="text" id="namespaces" name="namespaces" required>

                    <label for="patterns">Padrões de Pods (separados por ponto e vírgula):</label>
                    <input type="text" id="patterns" name="patterns" required>

                    <input type="submit" value="Executar">
                </form>

                <form method="POST" action="/test-connectivity" target="invisible_iframe">
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

                <form method="POST" action="/collect-logs" target="invisible_iframe">
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
            <!-- Overlay de carregamento -->
            <div id="loading-overlay">
                <div class="spinner"></div>
                <p>Processando sua solicitação...</p>
            </div>
            <!-- Iframe oculto -->
            <iframe id="invisible_iframe" name="invisible_iframe" style="display:none;"></iframe>
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
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                mensagem = f"<h2>Erro ao executar o script:</h2><pre>{stderr.decode('utf-8')}</pre>"
                self.wfile.write(mensagem.encode('utf-8'))
                return

            # Nome do arquivo CSV gerado
            csv_file = "pods_status.csv"

            # Verifica se o arquivo foi gerado
            if os.path.exists(csv_file):
                # Envia o arquivo CSV para download
                self.send_response(200)
                self.send_header('Content-Type', 'application/octet-stream')
                self.send_header('Content-Disposition', f'attachment; filename="{csv_file}"')
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

    # Função para servir arquivos para download
    def serve_file(self):
        session = self.get_session()
        if session is None:
            self.send_response(302)
            self.send_header('Location', '/')
            self.end_headers()
            return

        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        filename = params.get('filename', [''])[0]

        if filename and os.path.exists(filename):
            self.send_response(200)
            self.send_header('Content-Type', 'application/octet-stream')
            self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
            self.end_headers()
            with open(filename, 'rb') as f:
                self.wfile.write(f.read())
        else:
            self.send_response(404)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            mensagem = "<h2>Arquivo não encontrado.</h2>"
            self.wfile.write(mensagem.encode('utf-8'))

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
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            mensagem = "Todos os campos são obrigatórios!"
            self.wfile.write(mensagem.encode('utf-8'))
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
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            mensagem = f"<h2>Erro ao coletar logs:</h2><p>{str(e)}</p>"
            self.wfile.write(mensagem.encode('utf-8'))

def run(server_class=HTTPServer, handler_class=WebInterface, port=4545):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f'Servidor web iniciado na porta {port}...')
    httpd.serve_forever()

if __name__ == "__main__":
    run()
