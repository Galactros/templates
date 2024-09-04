import subprocess
import json
import csv
import datetime
import os
import argparse

# Função para executar comandos do sistema
def run_command(command):
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, text=True)
    if result.returncode != 0:
        print(f"Erro ao executar comando: {command}\n{result.stderr}")
    return result.stdout

# Função para processar os pods em um namespace dentro de um cluster
def process_pods(cluster, namespace, pattern, csv_writer, final_report):
    print(f"Processando cluster: {cluster}, namespace: {namespace}, padrão: {pattern}")

    # Muda para o contexto do cluster especificado
    run_command(f"oc config use-context {cluster}")

    # Obtém todos os HPAs no namespace atual
    hpa_list = run_command(f"oc get hpa -n {namespace} -o json")
    hpa_list = json.loads(hpa_list) if hpa_list else {}

    # Obtém os pods no namespace atual
    pods_output = run_command(f"oc get pods -n {namespace} -o json")
    pods = json.loads(pods_output)["items"]

    # Processa cada pod que corresponde ao padrão
    current_time = datetime.datetime.now().timestamp()

    for pod in pods:
        pod_name = pod["metadata"]["name"]
        if pattern not in pod_name:
            continue

        pod_status = pod["status"]["phase"]
        creation_time = pod["metadata"]["creationTimestamp"]
        creation_time_epoch = datetime.datetime.strptime(creation_time, '%Y-%m-%dT%H:%M:%SZ').timestamp()

        # Verifica se o pod foi criado nas últimas 24 horas
        time_diff = current_time - creation_time_epoch
        recent_change = "Yes" if time_diff < 86400 else "No"

        # Conta a quantidade de linhas com a palavra "ERRO" nos logs do pod
        error_count = run_command(f"oc logs -n {namespace} {pod_name} | grep -c 'ERRO'")
        error_count = int(error_count) if error_count else 0
        if error_count > 2000:
            final_report.append(f"{cluster}|{namespace}|{pod_name} -> {error_count} erros")

        # Obtém o uso de CPU e Memória
        resource_usage = run_command(f"oc adm top pod {pod_name} -n {namespace} --no-headers --use-protocol-buffers")
        cpu_usage, memory_usage = resource_usage.split()[1:3] if resource_usage else ("N/A", "N/A")

        # Requisições e limites de CPU e Memória
        containers = pod["spec"]["containers"]
        cpu_request = containers[0]["resources"]["requests"].get("cpu", "N/A")
        memory_request = containers[0]["resources"]["requests"].get("memory", "N/A")
        cpu_limit = containers[0]["resources"]["limits"].get("cpu", "N/A")
        memory_limit = containers[0]["resources"]["limits"].get("memory", "N/A")

        # Verifica se o pod está sob um HPA
        hpa_info = next((item for item in hpa_list.get("items", []) if item["metadata"]["name"] == pod_name), None)
        hpa_enabled, hpa_min_replicas, hpa_max_replicas, hpa_current_replicas, hpa_cpu_target, hpa_cpu_current = ("No", "N/A", "N/A", "N/A", "N/A", "N/A")

        if hpa_info:
            hpa_enabled = "Yes"
            hpa_min_replicas = hpa_info["spec"]["minReplicas"]
            hpa_max_replicas = hpa_info["spec"]["maxReplicas"]
            hpa_current_replicas = hpa_info["status"]["currentReplicas"]
            hpa_cpu_target = hpa_info["spec"].get("targetCPUUtilizationPercentage", "N/A")
            hpa_cpu_current = hpa_info["status"].get("currentCPUUtilizationPercentage", "N/A")

            if hpa_cpu_current != "N/A" and int(hpa_cpu_current) >= 80:
                final_report.append(f"{cluster}|{namespace}|{pod_name} -> {hpa_cpu_current}%")

        # Verifica se o pod está com status diferente de "Running"
        if pod_status != "Running":
            final_report.append(f"{cluster}|{namespace}|{pod_name} -> {pod_status}")

        # Conta reinicializações
        restart_count = pod["status"]["containerStatuses"][0]["restartCount"]

        if restart_count > 0:
            final_report.append(f"{cluster}|{namespace}|{pod_name} -> {restart_count} reinicializações")

        # Adiciona as informações do pod ao CSV
        csv_writer.writerow([cluster, namespace, pod_name, pod_status, creation_time, recent_change, error_count, 
                             cpu_usage, memory_usage, cpu_request, memory_request, cpu_limit, memory_limit,
                             hpa_enabled, hpa_min_replicas, hpa_max_replicas, hpa_current_replicas,
                             hpa_cpu_target, hpa_cpu_current, restart_count])

# Função para gerar informações dos nodes
def process_nodes(cluster, csv_writer, final_report):
    print(f"Processando informações dos nodes para o cluster: {cluster}")

    # Muda para o contexto do cluster especificado
    run_command(f"oc config use-context {cluster}")

    # Coleta as informações de todos os nodes usando o comando 'oc adm top nodes'
    nodes_output = run_command(f"oc adm top nodes --no-headers --use-protocol-buffers")

    for line in nodes_output.splitlines():
        node_name, node_cpu_usage, node_cpu_percent, node_memory_usage, node_memory_percent = line.split()

        # Verifica se o node está próximo de seu limite de CPU ou memória
        if int(node_cpu_percent.strip('%')) >= 80 or int(node_memory_percent.strip('%')) >= 80:
            final_report.append(f"{cluster}|{node_name} -> CPU: {node_cpu_percent}, Memory: {node_memory_percent}")

        # Adiciona as informações do node ao CSV
        csv_writer.writerow([cluster, node_name, node_cpu_usage, node_cpu_percent, node_memory_usage, node_memory_percent])

# Função principal
def main():
    parser = argparse.ArgumentParser(description="Script para gerar relatório de pods e nodes.")
    parser.add_argument("-c", "--clusters", required=True, help="Lista de clusters separados por vírgula")
    parser.add_argument("-n", "--namespaces", required=True, help="Lista de namespaces separados por ';'")
    parser.add_argument("-p", "--patterns", required=True, help="Lista de padrões de pods separados por ';'")
    
    args = parser.parse_args()

    clusters = args.clusters.split(',')
    namespaces = args.namespaces.split(';')
    patterns = args.patterns.split(';')

    if not (len(clusters) == len(namespaces) == len(patterns)):
        print("Erro: O número de clusters, namespaces e padrões deve ser igual.")
        exit(1)

    csv_file = "pods_status.csv"
    final_report = []

    with open(csv_file, mode="w", newline="") as file:
        csv_writer = csv.writer(file)
        csv_writer.writerow(["Cluster", "Namespace", "Pod Name", "Status", "Creation Time", "Recent Change", 
                             "Error Count", "CPU Usage", "Memory Usage", "CPU Request", "Memory Request", 
                             "CPU Limit", "Memory Limit", "HPA Enabled", "HPA Min Replicas", "HPA Max Replicas", 
                             "HPA Current Replicas", "HPA CPU Target", "HPA CPU Current", "Restart Count"])

        # Processa pods
        for cluster, ns_list, pattern_list in zip(clusters, namespaces, patterns):
            for namespace, pattern in zip(ns_list.split(','), pattern_list.split(',')):
                process_pods(cluster, namespace, pattern, csv_writer, final_report)

        # Processa nodes
        csv_writer.writerow(["Cluster", "Node", "CPU Usage", "CPU Usage (%)", "Memory Usage", "Memory Usage (%)"])
        for cluster in clusters:
            process_nodes(cluster, csv_writer, final_report)

    # Adiciona o relatório final ao CSV
    with open(csv_file, mode="a", newline="") as file:
        csv_writer = csv.writer(file)
        csv_writer.writerow([])
        csv_writer.writerow(["Relatório Final:"])
        csv_writer.writerows([[item] for item in final_report])

    print(f"Relatório gerado no arquivo {csv_file}")

if __name__ == "__main__":
    main()
