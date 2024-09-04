import argparse
import subprocess
import json
import csv
import time
from datetime import datetime

# Função para executar comandos no shell
def run_command(command):
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Command '{command}' failed with error: {result.stderr}")
    return result.stdout

# Função para processar os pods de um namespace dentro de um cluster
def process_pods(cluster, namespace, pattern, csv_writer, final_report_file):
    print(f"Processando cluster: {cluster}, namespace: {namespace}, padrão: {pattern}")

    # Muda para o contexto do cluster especificado
    run_command(f"oc config use-context {cluster}")

    # Obtém todos os HPAs no namespace atual
    hpa_list = run_command(f"oc get hpa -n {namespace} -o json")
    hpa_list_json = json.loads(hpa_list)

    # Obtém a data/hora atual para comparar com o tempo de criação dos pods
    current_time = time.time()

    # Obtém os pods no namespace e filtra pelo padrão de nome
    pod_list = run_command(f"oc get pods -n {namespace} -o json")
    pod_list_json = json.loads(pod_list)

    for pod in pod_list_json["items"]:
        pod_name = pod["metadata"]["name"]
        if pattern not in pod_name:
            continue

        pod_status = pod["status"]["phase"]
        creation_time = pod["metadata"]["creationTimestamp"]
        creation_time_epoch = datetime.strptime(creation_time, "%Y-%m-%dT%H:%M:%SZ").timestamp()
        time_diff = current_time - creation_time_epoch
        recent_change = "Yes" if time_diff < 86400 else "No"

        # Verifica os logs para contagem de erros
        logs = run_command(f"oc logs -n {namespace} {pod_name}")
        error_count = logs.count("ERRO")

        # Verifica o uso de CPU e memória
        resource_usage = run_command(f"oc adm top pod {pod_name} -n {namespace} --no-headers --use-protocol-buffers")
        resource_usage_data = resource_usage.split()
        cpu_usage = resource_usage_data[1]
        memory_usage = resource_usage_data[2]

        # Obtém requisições e limites de CPU/memória
        containers = pod["spec"]["containers"]
        cpu_request = containers[0]["resources"]["requests"].get("cpu", "N/A")
        memory_request = containers[0]["resources"]["requests"].get("memory", "N/A")
        cpu_limit = containers[0]["resources"]["limits"].get("cpu", "N/A")
        memory_limit = containers[0]["resources"]["limits"].get("memory", "N/A")

        # Verifica se o pod está sob um HPA e coleta informações
        hpa_info = next((hpa for hpa in hpa_list_json["items"] if pod_name in hpa["metadata"]["name"]), None)
        hpa_enabled = "No"
        hpa_min_replicas = hpa_max_replicas = hpa_current_replicas = hpa_cpu_target = hpa_cpu_current = "N/A"
        
        if hpa_info:
            hpa_enabled = "Yes"
            hpa_min_replicas = hpa_info["spec"].get("minReplicas", "N/A")
            hpa_max_replicas = hpa_info["spec"].get("maxReplicas", "N/A")
            hpa_current_replicas = hpa_info["status"].get("currentReplicas", "N/A")
            hpa_cpu_target = hpa_info["spec"].get("targetCPUUtilizationPercentage", "N/A")
            hpa_cpu_current = hpa_info["status"].get("currentCPUUtilizationPercentage", "N/A")
            if hpa_cpu_current != "N/A" and int(hpa_cpu_current) >= 80:
                final_report_file.write(f"{cluster}|{namespace}|{pod_name} -> {hpa_cpu_current}%\n")

        # Verifica se o pod está com status diferente de "Running"
        if pod_status != "Running":
            final_report_file.write(f"{cluster}|{namespace}|{pod_name} -> {pod_status}\n")

        # Verifica o número de reinicializações
        restart_count = pod["status"]["containerStatuses"][0]["restartCount"]
        if restart_count > 0:
            final_report_file.write(f"{cluster}|{namespace}|{pod_name} -> {restart_count} reinicializações\n")

        # Adiciona as informações ao CSV
        csv_writer.writerow([
            cluster, namespace, pod_name, pod_status, creation_time, recent_change, error_count,
            cpu_usage, memory_usage, cpu_request, memory_request, cpu_limit, memory_limit,
            "N/A", "N/A", hpa_enabled, hpa_min_replicas, hpa_max_replicas, hpa_current_replicas,
            hpa_cpu_target, hpa_cpu_current, restart_count
        ])

# Função para processar os nodes de um cluster
def process_nodes(cluster, csv_writer, final_report_file):
    print(f"Processando informações dos nodes para o cluster: {cluster}")

    # Muda para o contexto do cluster especificado
    run_command(f"oc config use-context {cluster}")

    # Coleta as informações de todos os nodes
    node_list = run_command("oc adm top nodes --no-headers --use-protocol-buffers")
    
    for line in node_list.splitlines():
        node_data = line.split()
        node_name = node_data[0]
        node_cpu_usage = node_data[1]
        node_cpu_percent = node_data[2]
        node_memory_usage = node_data[3]
        node_memory_percent = node_data[4]

        if int(node_cpu_percent.strip('%')) >= 80 or int(node_memory_percent.strip('%')) >= 80:
            final_report_file.write(f"{cluster}|{node_name} -> CPU: {node_cpu_percent}, Memory: {node_memory_percent}\n")

        # Adiciona ao CSV
        csv_writer.writerow([cluster, node_name, node_cpu_usage, node_cpu_percent, node_memory_usage, node_memory_percent])

def main():
    # Parseia os argumentos de linha de comando
    parser = argparse.ArgumentParser(description="Script para coletar informações de pods e nodes em clusters OpenShift.")
    parser.add_argument("-c", "--clusters", required=True, help="Lista de contextos dos clusters, separados por vírgulas")
    parser.add_argument("-n", "--namespaces", required=True, help="Lista de namespaces, separados por vírgulas (um conjunto por cluster)")
    parser.add_argument("-p", "--patterns", required=True, help="Lista de padrões de nomes de pods, separados por vírgulas (um conjunto por cluster)")
    args = parser.parse_args()

    clusters = args.clusters.split(',')
    namespaces = args.namespaces.split(';')
    patterns = args.patterns.split(';')

    if len(clusters) != len(namespaces) or len(namespaces) != len(patterns):
        print("Erro: O número de clusters, namespaces e padrões de pods deve ser igual.")
        exit(1)

    # Define o nome do arquivo CSV
    csv_file = "pods_status.csv"
    final_report_file_name = "final_report.tmp"

    # Abre os arquivos CSV e o relatório temporário
    with open(csv_file, mode="w", newline='') as csv_f, open(final_report_file_name, mode="w") as final_report_f:
        csv_writer = csv.writer(csv_f, delimiter=';')
        csv_writer.writerow(["Cluster", "Namespace", "Pod Name", "Status", "Creation Time", "Recent Change", "Error Count",
                             "CPU Usage", "Memory Usage", "CPU Request", "Memory Request", "CPU Limit", "Memory Limit",
                             "CPU Usage vs Limit", "Memory Usage vs Limit", "HPA Enabled", "HPA Min Replicas", 
                             "HPA Max Replicas", "HPA Current Replicas", "HPA CPU Target", "HPA CPU Current", "Restart Count"])

        # Processa os clusters, namespaces e padrões de pods
        for i, cluster in enumerate(clusters):
            ns_list = namespaces[i].split(',')
            pattern_list = patterns[i].split(',')
            for j, ns in enumerate(ns_list):
                process_pods(cluster, ns, pattern_list[j], csv_writer, final_report_f)

            # Processa as informações dos nodes
            process_nodes(cluster, csv_writer, final_report_f)

    print(f"Relatório final gerado no CSV: {csv_file}")

if __name__ == "__main__":
    main()
