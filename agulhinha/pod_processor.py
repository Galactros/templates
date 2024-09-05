import json
import time
from datetime import datetime
from command_utils import run_command

def process_pods(cluster, namespace, pattern, csv_writer, final_report_file):
    print(f"Processando cluster: {cluster}, namespace: {namespace}, padrao: {pattern}")
    
    run_command(f"oc config use-context {cluster}")
    hpa_list = run_command(f"oc get hpa -n {namespace} -o json")
    hpa_list_json = json.loads(hpa_list)
    current_time = time.time()
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

        logs = run_command(f"oc logs -n {namespace} {pod_name}")
        error_count = logs.count("ERRO")

        resource_usage = run_command(f"oc adm top pod {pod_name} -n {namespace} --no-headers --use-protocol-buffers")
        resource_usage_data = resource_usage.split()
        cpu_usage = resource_usage_data[1]
        memory_usage = resource_usage_data[2]

        containers = pod["spec"]["containers"]
        cpu_request = containers[0]["resources"].get("requests", {}).get("cpu", "N/A")
        memory_request = containers[0]["resources"].get("requests", {}).get("memory", "N/A")
        cpu_limit = containers[0]["resources"].get("limits", {}).get("cpu", "N/A")
        memory_limit = containers[0]["resources"].get("limits", {}).get("memory", "N/A")

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

        if pod_status != "Running":
            final_report_file.write(f"{cluster}|{namespace}|{pod_name} -> {pod_status}\n")

        restart_count = pod["status"]["containerStatuses"][0]["restartCount"]
        if restart_count > 0:
            final_report_file.write(f"{cluster}|{namespace}|{pod_name} -> {restart_count} reinicializacoes\n")

        csv_writer.writerow([
            cluster, namespace, pod_name, pod_status, creation_time, recent_change, error_count,
            cpu_usage, memory_usage, cpu_request, memory_request, cpu_limit, memory_limit,
            "N/A", "N/A", hpa_enabled, hpa_min_replicas, hpa_max_replicas, hpa_current_replicas,
            hpa_cpu_target, hpa_cpu_current, restart_count
        ])
