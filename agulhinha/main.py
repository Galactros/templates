import argparse
import csv
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

if __name__ == "__main__":
    main()
