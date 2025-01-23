from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
from fastapi.responses import FileResponse
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from kubernetes import client, config
from typing import List, Dict
import os

app = FastAPI()

# Base folder for cluster kubeconfig directories
base_kubeconfig_folder = "/arquvi/kube/clusters/"  # Substitua pelo caminho base

# Mount static files for HTML, CSS, and JS
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
def index():
    """Serve the main HTML interface."""
    with open("static/index.html", "r") as file:
        return file.read()

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
            
            # Extract tag (version of the image) from the container image
            tag = "N/A"
            if pod.spec.containers:
                container_image = pod.spec.containers[0].image
                tag = container_image.split(":")[-1] if ":" in container_image else "latest"

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

@app.get("/hpa/", response_model=List[Dict[str, str]])
def list_hpa(environment: str, cluster: str, namespace: str, deployment_name: str):
    """Lista os HPA de um deployment específico."""
    kubeconfig_path = os.path.join(base_kubeconfig_folder, environment, cluster, "kubeconfig")
    if not os.path.exists(kubeconfig_path):
        return {"error": f"Kubeconfig não encontrado para o cluster '{cluster}' no ambiente '{environment}'."}

    try:
        config.load_kube_config(config_file=kubeconfig_path)
        k8s_client = client.AutoscalingV1Api()

        hpas = k8s_client.list_namespaced_horizontal_pod_autoscaler(namespace=namespace)
        hpa_details = []

        for hpa in hpas.items:
            if hpa.spec.scale_target_ref.name == deployment_name:
                hpa_details.append({
                    "name": hpa.metadata.name,
                    "min_replicas": str(hpa.spec.min_replicas),
                    "max_replicas": str(hpa.spec.max_replicas),
                    "current_replicas": str(hpa.status.current_replicas),
                    "target_cpu_utilization_percentage": str(hpa.spec.target_cpu_utilization_percentage) if hpa.spec.target_cpu_utilization_percentage else "N/A"
                })

        return hpa_details
    except Exception as e:
        return {"error": f"Erro ao listar os HPAs do deployment '{deployment_name}' no namespace '{namespace}': {str(e)}"}

from fastapi.responses import JSONResponse

@app.get("/pod-logs/", response_class=FileResponse)
def download_pod_logs(environment: str, cluster: str, namespace: str, pod_name: str):
    """Download logs for a specific pod."""
    kubeconfig_path = os.path.join(base_kubeconfig_folder, environment, cluster, "kubeconfig")
    if not os.path.exists(kubeconfig_path):
        return JSONResponse(status_code=404, content={"error": f"Kubeconfig não encontrado para o cluster '{cluster}' no ambiente '{environment}'."})

    try:
        # Carrega o kubeconfig para o cluster
        config.load_kube_config(config_file=kubeconfig_path)
        k8s_client = client.CoreV1Api()

        # Obtém os logs do pod
        logs = k8s_client.read_namespaced_pod_log(name=pod_name, namespace=namespace)

        # Salva os logs em um arquivo temporário usando o codec 'utf-8' com erros ignorados
        log_file_path = f"/tmp/{pod_name}_logs.txt"
        with open(log_file_path, "w", encoding="utf-8", errors="replace") as log_file:
            log_file.write(logs)

        # Retorna o arquivo como resposta
        return FileResponse(log_file_path, media_type="text/plain", filename=f"{pod_name}_logs.txt")
    except client.exceptions.ApiException as e:
        return JSONResponse(status_code=e.status, content={"error": f"Erro ao obter logs do pod '{pod_name}': {e.reason}"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Erro interno: {str(e)}"})