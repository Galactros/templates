import argparse
import json
import csv
import os
import tarfile
from pod_processor import process_pods
from node_processor import process_nodes
from report_utils import append_final_report_to_csv
from cluster_utils import login_to_cluster
from command_utils import run_command

def main():
    parser = argparse.ArgumentParser(description="Script para coletar informações de pods e nodes em clusters OpenShift.")
    parser.add_argument("-c", "--clusters", required=True, help="Lista de nomes dos clusters, separados por vírgulas (ex: cluster1,cluster2)")
    parser.add_argument("-n", "--namespaces", required=True, help="Lista de namespaces, separados por ponto e vírgula (um conjunto por cluster)")
    parser.add_argument("-p", "--patterns", required=True, help="Lista de padrões de nomes de pods, separados por ponto e vírgula (um conjunto por cluster)")
    parser.add_argument("-u", "--username", required=True, help="Username para login em todos os clusters")
    parser.add_argument("-pw", "--password", required=True, help="Senha para login em todos os clusters")
    args = parser.parse_args()

    clusters = args.clusters.split(',')
    namespaces = args.namespaces.split(';')
    patterns = args.patterns.split(';')
    username = args.username
    password = args.password

    if len(clusters) != len(namespaces) or len(namespaces) != len(patterns):
        print("Erro: O número de clusters, namespaces e padrões de pods deve ser igual.")
        exit(1)

    csv_file = "pods_status.csv"
    final_report_file_name = "final_report.tmp"

    with open(csv_file, mode="w", newline='') as csv_f, open(final_report_file_name, mode="w") as final_report_f:
        csv_writer = csv.writer(csv_f, delimiter=';')
        csv_writer.writerow(["Cluster", "Namespace", "Pod Name", "Status", "Creation Time", "Recent Change", "Error Count",
                             "CPU Usage", "Memory Usage", "CPU Request", "Memory Request", "CPU Limit", "Memory Limit",
                             "CPU Usage vs Limit", "Memory Usage vs Limit", "HPA Enabled", "HPA Min Replicas", 
                             "HPA Max Replicas", "HPA Current Replicas", "HPA CPU Target", "HPA CPU Current", "Restart Count"])

        for i, cluster_name in enumerate(clusters):
            # Login no cluster com o mesmo username e password para todos os clusters
            login_to_cluster(cluster_name, username, password)
            
            ns_list = namespaces[i].split(',')
            pattern_list = patterns[i].split(',')
            for j, ns in enumerate(ns_list):
                process_pods(cluster_name, ns, pattern_list[j], csv_writer, final_report_f)

            process_nodes(cluster_name, csv_writer, final_report_f)

    append_final_report_to_csv(csv_file, final_report_file_name)

    print(f"Relatório final gerado no CSV: {csv_file}")

def test_connectivity_in_pod(cluster, namespace, pod_name, url):
    """
    Função para testar conectividade dentro de um pod usando o comando curl -v
    """
    print(f"Testando conectividade no pod {pod_name} no cluster {cluster} para a URL {url}")

    # Muda para o contexto do cluster especificado
    run_command(f"oc config use-context {cluster}")

    # Executa o comando curl dentro do pod
    try:
        result = run_command(f"oc exec -n {namespace} {pod_name} -- curl -v {url}")
        return result
    except RuntimeError as e:
        return f"Erro ao executar curl no pod {pod_name}: {str(e)}"

def collect_logs_from_pods(cluster, namespace, pattern, username, password):
    """
    Coleta os logs de todos os pods que correspondem ao padrão no workload e compacta em um arquivo .tar.gz
    """
    # Muda para o contexto do cluster especificado
    login_to_cluster(cluster, username, password)

    # Cria diretório temporário para armazenar os logs
    log_dir = f"{cluster}_{namespace}_logs"
    os.makedirs(log_dir, exist_ok=True)

    # Obtem a lista de pods no namespace que correspondem ao padrão do workload
    pod_list = run_command(f"oc get pods -n {namespace} -o json")
    pod_list_json = json.loads(pod_list)

    log_files = []
    for pod in pod_list_json["items"]:
        pod_name = pod["metadata"]["name"]
        if pattern not in pod_name:
            continue

        # Coleta os logs do pod
        logs = run_command(f"oc logs -n {namespace} {pod_name}")

        # Salva os logs em um arquivo de texto dentro do diretório de logs
        log_file_path = os.path.join(log_dir, f"{pod_name}.log")
        with open(log_file_path, "w") as log_file:
            log_file.write(logs)
        log_files.append(log_file_path)

    # Compacta todos os arquivos de log em um único arquivo .tar.gz
    tar_file_path = f"{log_dir}.tar.gz"
    with tarfile.open(tar_file_path, "w:gz") as tar:
        for log_file in log_files:
            tar.add(log_file, arcname=os.path.basename(log_file))

    return tar_file_path

if __name__ == "__main__":
    main()
