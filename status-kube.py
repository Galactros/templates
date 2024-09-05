import subprocess
import os
import csv
import time
from datetime import datetime

# Funcoes para verificar conexao e login
def is_connected(cluster_name):
    """
    Verifica se o usuário está conectado ao cluster usando o comando 'oc whoami'.
    Retorna True se estiver conectado, False caso contrário.
    """
    try:
        # Verifica se estamos conectados ao cluster (oc whoami retorna o usuário atual)
        subprocess.run(['oc', 'whoami'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # Aqui poderíamos verificar se o contexto atual corresponde ao cluster correto
        current_context = subprocess.run(['oc', 'config', 'current-context'], check=True, stdout=subprocess.PIPE, text=True).stdout.strip()
        if cluster_name in current_context:
            return True
        return False
    except subprocess.CalledProcessError:
        return False

def login_to_cluster(cluster_name, username, password):
    """
    Conecta ao cluster usando o comando 'oc login'.
    O cluster_name é o nome do cluster, que será formatado na URL.
    """
    # Formata a URL do cluster
    cluster_url = f"https://api.{cluster_name}.producao.ibm.cloud:6443"
    
    # Executa o comando 'oc login' com usuário, senha e a URL do cluster
    try:
        login_command = ['oc', 'login', cluster_url, '--username', username, '--password', password]
        result = subprocess.run(login_command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"Conectado com sucesso ao cluster: {cluster_name}")
    except subprocess.CalledProcessError as e:
        print(f"Erro ao conectar ao cluster {cluster_name}: {e.stderr.decode('utf-8')}")

def connect_to_cluster_if_needed(cluster_name, username, password):
    """
    Verifica se já estamos conectados ao cluster.
    Caso contrário, realiza o login com os dados fornecidos.
    """
    if is_connected(cluster_name):
        print(f"Já conectado ao cluster: {cluster_name}")
    else:
        print(f"Tentando conectar ao cluster: {cluster_name}")
        login_to_cluster(cluster_name, username, password)

# Função que executa os comandos de verificação de pods e nós para cada cluster
def process_pods_and_nodes(username, password, clusters, namespaces, patterns):
    pod_data_list = []
    node_data_list = []

    # Caminho para o arquivo CSV
    csv_file = "pods_status.csv"
    final_report_file_name = "final_report.tmp"

    # Abre o arquivo temporário para o relatório final
    with open(final_report_file_name, mode="w") as final_report_f:

        # Processa cada cluster
        for i, cluster in enumerate(clusters):
            connect_to_cluster_if_needed(cluster, username, password)  # Conecta ao cluster se necessário

            ns_list = namespaces[i].split(',')
            pattern_list = patterns[i].split(',')
            for j, ns in enumerate(ns_list):
                process_pods(cluster, ns, pattern_list[j], pod_data_list, final_report_f)

            # Processa as informacoes dos nodes
            process_nodes(cluster, node_data_list, final_report_f)

    # Grava os dados dos pods e nodes no arquivo CSV
    with open(csv_file, mode='w', newline='') as csv_f:
        csv_writer = csv.writer(csv_f, delimiter=';')
        
        # Cabeçalhos do arquivo CSV
        csv_writer.writerow(["Cluster", "Namespace", "Pod Name", "Status", "Creation Time", "Recent Change", "Error Count",
                             "CPU Usage", "Memory Usage", "CPU Request", "Memory Request", "CPU Limit", "Memory Limit",
                             "CPU Usage vs Limit", "Memory Usage vs Limit", "HPA Enabled", "HPA Min Replicas", 
                             "HPA Max Replicas", "HPA Current Replicas", "HPA CPU Target", "HPA CPU Current", "Restart Count"])

        # Escreve os dados dos pods
        csv_writer.writerows(pod_data_list)
        
        # Adiciona um separador para os nós
        csv_writer.writerow([])
        csv_writer.writerow(["Cluster", "Node Name", "CPU Usage", "CPU Usage (%)", "Memory Usage", "Memory Usage (%)"])

        # Escreve os dados dos nós
        csv_writer.writerows(node_data_list)

    # Adiciona o conteudo do final_report.tmp ao final do CSV
    append_final_report_to_csv(csv_file, final_report_file_name)

    print(f"Relatório final gerado no CSV: {csv_file}")

# Funções auxiliares para processar pods e nós (definições anteriores)
def process_pods(cluster, namespace, pattern, pod_data_list, final_report_file):
    """
    Simula o processamento dos pods.
    Aqui você deve incluir a lógica para capturar os dados reais.
    """
    # Exemplo de dados simulados para um pod
    pod_data_list.append([
        cluster, namespace, f"{pattern}-pod-1", "Running", "2023-09-01T12:00:00Z", "No", 0,
        "200m", "500Mi", "100m", "200Mi", "500m", "1Gi", "40%", "50%", "Yes", "1", "5", "3", "50%", "30%", 1
    ])

def process_nodes(cluster, node_data_list, final_report_file):
    """
    Simula o processamento dos nós.
    Aqui você deve incluir a lógica para capturar os dados reais.
    """
    # Exemplo de dados simulados para um nó
    node_data_list.append([cluster, "node-1", "1500m", "75%", "2000Mi", "80%"])

def append_final_report_to_csv(csv_file, final_report_file_name):
    """
    Adiciona o conteúdo do final_report.tmp ao final do CSV.
    """
    with open(final_report_file_name, "r") as final_report_f, open(csv_file, "a", newline='') as csv_f:
        csv_f.write("\nRelatório Final:\n")
        csv_f.write(final_report_f.read())

# Função principal
def main():
    # Dados do usuário e credenciais
    username = "seu_usuario"
    password = "sua_senha"

    clusters = ["cluster1", "cluster2"]  # Exemplo de clusters
    namespaces = ["namespace1,namespace2", "namespace3,namespace4"]  # Exemplo de namespaces para cada cluster
    patterns = ["pattern1,pattern2", "pattern3,pattern4"]  # Exemplo de padrões para cada cluster

    # Processa pods e nós para cada cluster com o login automático
    process_pods_and_nodes(username, password, clusters, namespaces, patterns)

if __name__ == '__main__':
    main()
