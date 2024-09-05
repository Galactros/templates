import subprocess
import os
import csv
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs

# Funcoes para verificar conexao e login
def is_connected(cluster_name):
    """
    Verifica se o usuario esta conectado ao cluster usando o comando 'oc whoami'.
    Retorna True se estiver conectado, False caso contrario.
    """
    try:
        subprocess.run(['oc', 'whoami'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        current_context = subprocess.run(['oc', 'config', 'current-context'], check=True, stdout=subprocess.PIPE, text=True).stdout.strip()
        if cluster_name in current_context:
            return True
        return False
    except subprocess.CalledProcessError:
        return False

def login_to_cluster(cluster_name, username, password):
    """
    Conecta ao cluster usando o comando 'oc login'.
    O cluster_name e o nome do cluster, que sera formatado na URL.
    """
    cluster_url = f"https://api.{cluster_name}.producao.ibm.cloud:6443"
    
    try:
        login_command = ['oc', 'login', cluster_url, '--username', username, '--password', password]
        subprocess.run(login_command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"Conectado com sucesso ao cluster: {cluster_name}")
    except subprocess.CalledProcessError as e:
        print(f"Erro ao conectar ao cluster {cluster_name}: {e.stderr.decode('utf-8')}")

def connect_to_cluster_if_needed(cluster_name, username, password):
    """
    Verifica se ja estamos conectados ao cluster.
    Caso contrario, realiza o login com os dados fornecidos.
    """
    if is_connected(cluster_name):
        print(f"Ja conectado ao cluster: {cluster_name}")
    else:
        print(f"Tentando conectar ao cluster: {cluster_name}")
        login_to_cluster(cluster_name, username, password)

# Funcao que executa os comandos de verificacao de pods e nos para cada cluster
def process_pods_and_nodes(username, password, clusters, namespaces, patterns):
    pod_data_list = []
    node_data_list = []

    # Caminho para o arquivo CSV
    csv_file = "pods_status.csv"
    final_report_file_name = "final_report.tmp"

    # Abre o arquivo temporario para o relatorio final
    with open(final_report_file_name, mode="w") as final_report_f:

        # Processa cada cluster
        for i, cluster in enumerate(clusters):
            connect_to_cluster_if_needed(cluster, username, password)  # Conecta ao cluster se necessario

            ns_list = namespaces[i].split(',')
            pattern_list = patterns[i].split(',')
            for j, ns in enumerate(ns_list):
                process_pods(cluster, ns, pattern_list[j], pod_data_list, final_report_f)

            # Processa as informacoes dos nos
            process_nodes(cluster, node_data_list, final_report_f)

    # Grava os dados dos pods e nos no arquivo CSV
    with open(csv_file, mode='w', newline='') as csv_f:
        csv_writer = csv.writer(csv_f, delimiter=';')
        
        # Cabecalhos do arquivo CSV
        csv_writer.writerow(["Cluster", "Namespace", "Pod Name", "Status", "Creation Time", "Recent Change", "Error Count",
                             "CPU Usage", "Memory Usage", "CPU Request", "Memory Request", "CPU Limit", "Memory Limit",
                             "CPU Usage vs Limit", "Memory Usage vs Limit", "HPA Enabled", "HPA Min Replicas", 
                             "HPA Max Replicas", "HPA Current Replicas", "HPA CPU Target", "HPA CPU Current", "Restart Count"])

        # Escreve os dados dos pods
        csv_writer.writerows(pod_data_list)
        
        # Adiciona um separador para os nos
        csv_writer.writerow([])
        csv_writer.writerow(["Cluster", "Node Name", "CPU Usage", "CPU Usage (%)", "Memory Usage", "Memory Usage (%)"])

        # Escreve os dados dos nos
        csv_writer.writerows(node_data_list)

    # Adiciona o conteudo do final_report.tmp ao final do CSV
    append_final_report_to_csv(csv_file, final_report_file_name)

    print(f"Relatorio final gerado no CSV: {csv_file}")

# Funcoes auxiliares para processar pods e nos (definicoes anteriores)
def process_pods(cluster, namespace, pattern, pod_data_list, final_report_file):
    """
    Simula o processamento dos pods.
    Aqui voce deve incluir a logica para capturar os dados reais.
    """
    # Exemplo de dados simulados para um pod
    pod_data_list.append([
        cluster, namespace, f"{pattern}-pod-1", "Running", "2023-09-01T12:00:00Z", "No", 0,
        "200m", "500Mi", "100m", "200Mi", "500m", "1Gi", "40%", "50%", "Yes", "1", "5", "3", "50%", "30%", 1
    ])

def process_nodes(cluster, node_data_list, final_report_file):
    """
    Simula o processamento dos nos.
    Aqui voce deve incluir a logica para capturar os dados reais.
    """
    node_data_list.append([cluster, "node-1", "1500m", "75%", "2000Mi", "80%"])

def append_final_report_to_csv(csv_file, final_report_file_name):
    """
    Adiciona o conteudo do final_report.tmp ao final do CSV.
    """
    with open(final_report_file_name, "r") as final_report_f, open(csv_file, "a", newline='') as csv_f:
        csv_f.write("\nRelatorio Final:\n")
        csv_f.write(final_report_f.read())

# Handler HTTP para o servidor web
class MyHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        """
        Responde com o formulario HTML.
        """
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

        # Formulario HTML para o usuario inserir os dados
        html_content = '''
        <html>
            <body>
                <h1>Gerar Relatorio de Pods e Nos</h1>
                <form action="/generate_report" method="post">
                    <label for="username">Usuario:</label><br>
                    <input type="text" id="username" name="username" required><br><br>
                    <label for="password">Senha:</label><br>
                    <input type="password" id="password" name="password" required><br><br>
                    <label for="clusters">Clusters (separados por virgula):</label><br>
                    <input type="text" id="clusters" name="clusters" required><br><br>
                    <label for="namespaces">Namespaces (separados por ponto e virgula, um conjunto por cluster):</label><br>
                    <input type="text" id="namespaces" name="namespaces" required><br><br>
                    <label for="patterns">Padroes de Pods (separados por ponto e virgula, um conjunto por cluster):</label><br>
                    <input type="text" id="patterns" name="patterns" required><br><br>
                    <input type="submit" value="Gerar Relatorio">
                </form>
            </body>
        </html>
        '''
        self.wfile.write(html_content.encode('utf-8'))

    def do_POST(self):
        """
        Processa o formulario e gera o relatorio CSV.
        """
        if self.path == '/generate_report':
            # Le os dados do formulario enviados via POST
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length).decode('utf-8')
            form_data = parse_qs(post_data)

            # Pega os valores do formulario
            username = form_data['username'][0]
            password = form_data['password'][0]
            clusters = form_data['clusters'][0].split(',')
            namespaces = form_data['namespaces'][0].split(';')
            patterns = form_data['patterns'][0].split(';')

            # Executa a logica para processar os pods e nos
            process_pods_and_nodes(username, password, clusters, namespaces, patterns)

            # Caminho para o arquivo CSV
            csv_file = 'pods_status.csv'

            # Verifica se o arquivo foi gerado e envia para download
            if os.path.exists(csv_file):
                self.send_response(200)
                self.send_header('Content-Type', 'application/octet-stream')
                self.send_header('Content-Disposition', 'attachment; filename="pods_status.csv"')
                self.end_headers()
                with open(csv_file, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"Erro: Arquivo CSV nao encontrado.")

# Inicia o servidor web
def run(server_class=HTTPServer, handler_class=MyHandler, port=8080):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f"Servidor rodando na porta {port}...")
    httpd.serve_forever()

if __name__ == '__main__':
    run()
