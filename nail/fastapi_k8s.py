from fastapi import FastAPI, Query
from kubernetes import client, config
from typing import List, Dict
import os

app = FastAPI()

# Base folder for cluster kubeconfig directories
base_kubeconfig_folder = "/arquvi/kube/clusters/"  # Substitua pelo caminho base

@app.get("/pods/", response_model=List[str])
def list_pods(environment: str, cluster: str, namespace: str = Query(default="default", description="Namespace a ser consultado")):
    """Lista os pods em um namespace especificado em um cluster."""
    kubeconfig_path = os.path.join(base_kubeconfig_folder, environment, cluster, "kubeconfig")
    if not os.path.exists(kubeconfig_path):
        return {"error": f"Kubeconfig não encontrado para o cluster '{cluster}' no ambiente '{environment}'."}

    try:
        config.load_kube_config(config_file=kubeconfig_path)
        k8s_client = client.CoreV1Api()
        pods = k8s_client.list_namespaced_pod(namespace=namespace)
        pod_names = [pod.metadata.name for pod in pods.items]
        return pod_names
    except Exception as e:
        return {"error": f"Erro ao listar pods no cluster '{cluster}' e namespace '{namespace}': {str(e)}"}

@app.get("/health")
def health_check():
    """Verifica a saúde da aplicação."""
    return {"status": "ok"}

@app.get("/cluster-resources/", response_model=Dict[str, Dict[str, str]])
def cluster_resources(environment: str, cluster: str):
    """Retorna as informações de utilização de CPU e memória dos clusters."""
    kubeconfig_path = os.path.join(base_kubeconfig_folder, environment, cluster, "kubeconfig")
    if not os.path.exists(kubeconfig_path):
        return {"error": f"Kubeconfig não encontrado para o cluster '{cluster}' no ambiente '{environment}'."}

    try:
        config.load_kube_config(config_file=kubeconfig_path)
        k8s_client = client.CoreV1Api()
        nodes = k8s_client.list_node()

        cluster_data = {}

        for node in nodes.items:
            node_name = node.metadata.name
            allocatable = node.status.allocatable
            capacity = node.status.capacity

            cluster_data[node_name] = {
                "cpu_allocatable": allocatable["cpu"],
                "cpu_capacity": capacity["cpu"],
                "memory_allocatable": allocatable["memory"],
                "memory_capacity": capacity["memory"],
            }

        return cluster_data
    except Exception as e:
        return {"error": f"Erro ao obter recursos do cluster '{cluster}' no ambiente '{environment}': {str(e)}"}

@app.get("/workload-pods/", response_model=List[Dict[str, str]])
def get_workload_pods(environment: str, cluster: str, namespace: str, workload_name: str):
    """Busca os pods de um workload específico e retorna informações detalhadas."""
    kubeconfig_path = os.path.join(base_kubeconfig_folder, environment, cluster, "kubeconfig")
    if not os.path.exists(kubeconfig_path):
        return {"error": f"Kubeconfig não encontrado para o cluster '{cluster}' no ambiente '{environment}'."}

    try:
        config.load_kube_config(config_file=kubeconfig_path)
        k8s_client = client.CoreV1Api()
        metrics_client = client.CustomObjectsApi()

        pods = k8s_client.list_namespaced_pod(namespace=namespace, label_selector=f"app={workload_name}")
        pod_details = []

        for pod in pods.items:
            pod_name = pod.metadata.name
            pod_status = pod.status.phase
            creation_time = pod.metadata.creation_timestamp
            restarts = sum(container.restart_count for container in pod.status.container_statuses or [])
            tag = pod.metadata.labels.get("tag", "N/A")

            # Initialize values for requests and limits
            cpu_request, memory_request, cpu_limit, memory_limit = "0", "0", "0", "0"
            for container in pod.spec.containers:
                if container.resources.requests:
                    cpu_request = container.resources.requests.get("cpu", "0")
                    memory_request = container.resources.requests.get("memory", "0")
                if container.resources.limits:
                    cpu_limit = container.resources.limits.get("cpu", "0")
                    memory_limit = container.resources.limits.get("memory", "0")

            # Fetch metrics (if available)
            cpu_usage = "N/A"
            memory_usage = "N/A"
            try:
                metrics = metrics_client.get_namespaced_custom_object(
                    group="metrics.k8s.io",
                    version="v1beta1",
                    namespace=namespace,
                    plural="pods",
                    name=pod_name
                )
                container_metrics = metrics["containers"][0]
                cpu_usage = container_metrics["usage"].get("cpu", "N/A")
                memory_usage = container_metrics["usage"].get("memory", "N/A")
            except Exception as e:
                pass  # Ignore if metrics are not available

            pod_details.append({
                "pod_name": pod_name,
                "pod_status": pod_status,
                "creation_time": str(creation_time),
                "cpu_usage": cpu_usage,
                "memory_usage": memory_usage,
                "cpu_request": cpu_request,
                "memory_request": memory_request,
                "cpu_limit": cpu_limit,
                "memory_limit": memory_limit,
                "restarts": str(restarts),
                "tag": tag
            })

        return pod_details
    except Exception as e:
        return {"error": f"Erro ao buscar informações dos pods do workload '{workload_name}' no namespace '{namespace}': {str(e)}"}
