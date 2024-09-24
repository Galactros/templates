import json
import time
from datetime import datetime
from command_utils import run_command

def find_deployment_for_pod(pod, namespace):
    owner_references = pod["metadata"].get("ownerReferences", [])
    for owner in owner_references:
        if owner.get("controller", False):
            owner_kind = owner["kind"]
            owner_name = owner["name"]
            if owner_kind == "ReplicaSet":
                # Get the ReplicaSet and find its owner
                rs_json = run_command(f"oc get replicaset {owner_name} -n {namespace} -o json")
                rs = json.loads(rs_json)
                rs_owner_references = rs["metadata"].get("ownerReferences", [])
                for rs_owner in rs_owner_references:
                    if rs_owner.get("controller", False):
                        rs_owner_kind = rs_owner["kind"]
                        rs_owner_name = rs_owner["name"]
                        if rs_owner_kind == "Deployment":
                            return rs_owner_name
            elif owner_kind == "Deployment":
                return owner_name
    return None

def process_pods(cluster, namespace, pattern, csv_writer, final_report_file):
    print(f"Processando cluster: {cluster}, namespace: {namespace}, padrao: {pattern}")
    
    run_command(f"oc config use-context {cluster}")
    hpa_list = run_command(f"oc get hpa -n {namespace} -o json")
    hpa_list_json = json.loads(hpa_list)
    current_time = time.time()
    pod_list = run_command(f"oc get pods -n {namespace} -o json")
    pod_list_json = json.loads(pod_list)

    # Build a mapping from (kind, name) to HPA
    hpa_targets = {}
    for hpa in hpa_list_json["items"]:
        scale_target_ref = hpa["spec"]["scaleTargetRef"]
        target_kind = scale_target_ref["kind"]
        target_name = scale_target_ref["name"]
        hpa_targets[(target_kind, target_name)] = hpa

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

        # Find the Deployment name
        deployment_name = find_deployment_for_pod(pod, namespace)
        if deployment_name:
            # Check if there is an HPA targeting this deployment
            hpa_info = hpa_targets.get(("Deployment", deployment_name), None)
        else:
            hpa_info = None

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
