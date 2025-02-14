from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.responses import JSONResponse, FileResponse
from fastapi.background import BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi import Depends
from kubernetes import client, config
from kubernetes.stream import stream
from typing import List, Dict, Optional
import os
import time

app = FastAPI()

# Base folder for cluster kubeconfig directories
base_kubeconfig_folder = "/arquvi/kube/clusters/"  # Substitua pelo caminho base

# Mount static files for HTML, CSS, and JS
app.mount("/static", StaticFiles(directory="static"), name="static")

# Definição de usuário e senha hardcoded (substitua por um banco de dados no futuro)
USERNAME = "admin"
PASSWORD = "senha123"

security = HTTPBasic()

@app.get("/", response_class=HTMLResponse)
def index():
    """Serve the main HTML interface."""
    with open("static/index.html", "r") as file:
        return file.read()

@app.post("/login/")
def login(credentials: HTTPBasicCredentials = Depends(security)):
    """Autenticação básica do usuário"""
    if credentials.username == USERNAME and credentials.password == PASSWORD:
        return {"message": "Login bem-sucedido"}
    raise HTTPException(status_code=401, detail="Credenciais inválidas")

@app.get("/pods/", response_model=List[str])
def list_pods(environment: str, cluster: str, namespace: str = Query(default="default", description="Namespace a ser consultado")):
    """Lista os pods em um namespace especificado em um cluster."""
    kubeconfig_path = os.path.join(base_kubeconfig_folder, environment, cluster, "kubeconfig")
    if not os.path.exists(kubeconfig_path):
        raise HTTPException(status_code=404, detail=f"Kubeconfig não encontrado para o cluster '{cluster}' no ambiente '{environment}'.")

    try:
        config.load_kube_config(config_file=kubeconfig_path)
        k8s_client = client.CoreV1Api()
        pods = k8s_client.list_namespaced_pod(namespace=namespace)
        pod_names = [pod.metadata.name for pod in pods.items]
        return pod_names
    except client.exceptions.ApiException as e:
        raise HTTPException(status_code=e.status, detail=f"Erro ao listar pods no cluster '{cluster}' e namespace '{namespace}': {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")

@app.get("/health")
def health_check():
    """Verifica a saúde da aplicação."""
    return {"status": "ok"}

@app.get("/cluster-resources/", response_model=Dict[str, Dict[str, str]])
def cluster_resources(environment: str, cluster: str):
    """Retorna as informações de utilização de CPU e memória dos clusters."""
    kubeconfig_path = os.path.join(base_kubeconfig_folder, environment, cluster, "kubeconfig")
    if not os.path.exists(kubeconfig_path):
        raise HTTPException(status_code=404, detail=f"Kubeconfig não encontrado para o cluster '{cluster}' no ambiente '{environment}'.")

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
    except client.exceptions.ApiException as e:
        raise HTTPException(status_code=e.status, detail=f"Erro ao obter recursos do cluster '{cluster}' no ambiente '{environment}': {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")

@app.get("/workload-pods/", response_model=List[Dict[str, str]])
def get_workload_pods(environment: str, cluster: str, namespace: str, workload_name: str):
    """Busca os pods de um workload específico e retorna informações detalhadas."""
    kubeconfig_path = os.path.join(base_kubeconfig_folder, environment, cluster, "kubeconfig")
    if not os.path.exists(kubeconfig_path):
        raise HTTPException(status_code=404, detail=f"Kubeconfig não encontrado para o cluster '{cluster}' no ambiente '{environment}'.")

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
    except client.exceptions.ApiException as e:
        raise HTTPException(status_code=e.status, detail=f"Erro ao buscar informações dos pods do workload '{workload_name}' no namespace '{namespace}': {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")

@app.get("/hpa/", response_model=List[Dict[str, str]])
def list_hpa(environment: str, cluster: str, namespace: str, deployment_name: str):
    """Lista os HPA de um deployment específico."""
    kubeconfig_path = os.path.join(base_kubeconfig_folder, environment, cluster, "kubeconfig")
    if not os.path.exists(kubeconfig_path):
        raise HTTPException(status_code=404, detail=f"Kubeconfig não encontrado para o cluster '{cluster}' no ambiente '{environment}'.")

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
    except client.exceptions.ApiException as e:
        raise HTTPException(status_code=e.status, detail=f"Erro ao listar os HPAs do deployment '{deployment_name}' no namespace '{namespace}': {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")

@app.get("/pod-logs/", response_class=FileResponse)
def download_pod_logs(
    environment: str,
    cluster: str,
    namespace: str,
    pod_name: str,
    background_tasks: BackgroundTasks
):
    """Download logs for a specific pod."""
    kubeconfig_path = os.path.join(base_kubeconfig_folder, environment, cluster, "kubeconfig")
    if not os.path.exists(kubeconfig_path):
        raise HTTPException(status_code=404, detail=f"Kubeconfig não encontrado para o cluster '{cluster}' no ambiente '{environment}'.")

    try:
        # Carrega o kubeconfig para o cluster
        config.load_kube_config(config_file=kubeconfig_path)
        k8s_client = client.CoreV1Api()

        # Obtém os logs do pod
        logs = k8s_client.read_namespaced_pod_log(name=pod_name, namespace=namespace)

        # Salva os logs em um arquivo temporário
        log_file_path = f"/tmp/{pod_name}_logs.txt"
        with open(log_file_path, "w", encoding="utf-8", errors="replace") as log_file:
            log_file.write(logs)

        # Adiciona a tarefa em segundo plano para apagar o arquivo
        background_tasks.add_task(delete_file, log_file_path)

        # Retorna o arquivo como resposta
        return FileResponse(log_file_path, media_type="text/plain", filename=f"{pod_name}_logs.txt")
    except client.exceptions.ApiException as e:
        raise HTTPException(status_code=e.status, detail=f"Erro ao obter logs do pod '{pod_name}': {e.reason}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")


def delete_file(file_path: str):
    """Remove o arquivo temporário."""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"Arquivo {file_path} removido com sucesso.")
    except Exception as e:
        print(f"Erro ao remover o arquivo {file_path}: {e}")

@app.get("/pod-events/", response_model=List[Dict[str, str]])
def get_pod_events(environment: str, cluster: str, namespace: str, workload_name: str):
    """Retorna eventos dos pods de um workload específico."""
    kubeconfig_path = os.path.join(base_kubeconfig_folder, environment, cluster, "kubeconfig")
    if not os.path.exists(kubeconfig_path):
        raise HTTPException(status_code=404, detail=f"Kubeconfig não encontrado para o cluster '{cluster}' no ambiente '{environment}'.")

    try:
        # Carrega o kubeconfig para o cluster
        config.load_kube_config(config_file=kubeconfig_path)
        k8s_client = client.CoreV1Api()

        # Lista os pods associados ao workload
        pods = k8s_client.list_namespaced_pod(namespace=namespace, label_selector=f"app={workload_name}")

        # Coleta eventos associados a cada pod
        events_data = []
        for pod in pods.items:
            pod_name = pod.metadata.name
            events = k8s_client.list_namespaced_event(namespace=namespace, field_selector=f"involvedObject.name={pod_name}")

            for event in events.items:
                events_data.append({
                    "pod_name": pod_name,
                    "event_type": event.type,
                    "reason": event.reason,
                    "message": event.message,
                    "timestamp": str(event.last_timestamp or event.first_timestamp),
                })

        return events_data
    except client.exceptions.ApiException as e:
        raise HTTPException(status_code=e.status, detail=f"Erro ao obter eventos dos pods: {e.reason}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")

@app.get("/pvc/", response_model=List[Dict[str, str]])
def list_pvcs(environment: str, cluster: str, namespace: str):
    """Retorna os PVCs em um namespace com informações detalhadas."""
    kubeconfig_path = os.path.join(base_kubeconfig_folder, environment, cluster, "kubeconfig")
    if not os.path.exists(kubeconfig_path):
        raise HTTPException(status_code=404, detail=f"Kubeconfig não encontrado para o cluster '{cluster}' no ambiente '{environment}'.")

    try:
        # Carrega o kubeconfig para o cluster
        config.load_kube_config(config_file=kubeconfig_path)
        k8s_client = client.CoreV1Api()

        # Lista os PVCs no namespace
        pvcs = k8s_client.list_namespaced_persistent_volume_claim(namespace=namespace)
        pvc_data = []

        for pvc in pvcs.items:
            # Nome do PVC e informações de capacidade
            pvc_name = pvc.metadata.name
            capacity = pvc.status.capacity.get("storage", "N/A")
            access_modes = pvc.spec.access_modes

            # Tamanho utilizado
            storage_used = pvc.status.capacity.get("storage", "N/A")

            # Obtém informações do workload associado
            workload = pvc.metadata.annotations.get("workload", "Unknown")

            pvc_data.append({
                "name": pvc_name,
                "capacity": capacity,
                "used": storage_used,
                "workload": workload,
                "access_modes": ", ".join(access_modes),
            })

        return pvc_data
    except client.exceptions.ApiException as e:
        raise HTTPException(status_code=e.status, detail=f"Erro ao listar PVCs no namespace '{namespace}': {e.reason}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")

@app.delete("/delete-pod/")
def delete_pod(environment: str, cluster: str, namespace: str, pod_name: str):
    """Deleta um pod específico."""
    kubeconfig_path = os.path.join(base_kubeconfig_folder, environment, cluster, "kubeconfig")
    if not os.path.exists(kubeconfig_path):
        raise HTTPException(status_code=404, detail=f"Kubeconfig não encontrado para o cluster '{cluster}' no ambiente '{environment}'.")

    try:
        # Carrega o kubeconfig para o cluster
        config.load_kube_config(config_file=kubeconfig_path)
        k8s_client = client.CoreV1Api()

        # Deleta o pod
        k8s_client.delete_namespaced_pod(name=pod_name, namespace=namespace)

        return {"message": f"Pod '{pod_name}' deletado com sucesso no namespace '{namespace}'."}
    except client.exceptions.ApiException as e:
        raise HTTPException(status_code=e.status, detail=f"Erro ao deletar pod '{pod_name}': {e.reason}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")

@app.post("/test-connectivity/")
def test_pod_connectivity(
    environment: str, cluster: str, namespace: str, pod_name: str, url: str, test_type: str
):
    """Executa um teste de conectividade dentro do pod"""
    kubeconfig_path = os.path.join(base_kubeconfig_folder, environment, cluster, "kubeconfig")
    if not os.path.exists(kubeconfig_path):
        raise HTTPException(status_code=404, detail=f"Kubeconfig não encontrado para o cluster '{cluster}' no ambiente '{environment}'.")

    try:
        # Carrega o kubeconfig para o cluster
        config.load_kube_config(config_file=kubeconfig_path)
        k8s_client = client.CoreV1Api()

        # Definir o comando com base no tipo de teste
        if test_type == "http":
            command = ["curl", "-kv", url]
        elif test_type == "tcp":
            command = ["curl", f"telnet://{url}"]
        else:
            raise HTTPException(status_code=400, detail="Tipo de teste inválido. Use 'http' ou 'tcp'.")

        # Executa o comando dentro do pod
        response = stream(
            k8s_client.connect_get_namespaced_pod_exec,
            pod_name,
            namespace,
            command=command,
            stderr=True,
            stdin=False,
            stdout=True,
            tty=False,
            _request_timeout=30  # Tempo máximo de resposta
        )

        return {"output": response}

    except client.exceptions.ApiException as e:
        raise HTTPException(status_code=e.status, detail=f"Erro ao conectar ao pod '{pod_name}': {e.reason}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno ao executar o teste: {str(e)}")

@app.delete("/delete-multiple-pods/")
def delete_multiple_pods(
    environment: str, cluster: str, namespace: str, workload_name: Optional[str] = None, delay: int = 0
):
    """Deleta todos os pods de um namespace ou de um workload específico, com tempo de espera entre as exclusões."""
    kubeconfig_path = os.path.join(base_kubeconfig_folder, environment, cluster, "kubeconfig")
    if not os.path.exists(kubeconfig_path):
        raise HTTPException(status_code=404, detail=f"Kubeconfig não encontrado para o cluster '{cluster}' no ambiente '{environment}'.")

    try:
        # Carrega o kubeconfig para o cluster
        config.load_kube_config(config_file=kubeconfig_path)
        k8s_client = client.CoreV1Api()

        # Lista os pods no namespace
        label_selector = f"app={workload_name}" if workload_name else ""
        pods = k8s_client.list_namespaced_pod(namespace=namespace, label_selector=label_selector)

        if not pods.items:
            return {"message": "Nenhum pod encontrado para deletar."}

        deleted_pods = []
        for pod in pods.items:
            pod_name = pod.metadata.name
            k8s_client.delete_namespaced_pod(name=pod_name, namespace=namespace)
            deleted_pods.append(pod_name)
            time.sleep(delay)  # Aguarda o tempo configurado antes de deletar o próximo pod

        return {"message": f"{len(deleted_pods)} pods deletados.", "deleted_pods": deleted_pods}

    except client.exceptions.ApiException as e:
        raise HTTPException(status_code=e.status, detail=f"Erro ao deletar pods: {e.reason}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")

@app.get("/namespace-pods/", response_model=List[Dict[str, str]])
def list_namespace_pods(environment: str, cluster: str, namespace: str):
    """Retorna todos os pods de um namespace"""
    kubeconfig_path = os.path.join(base_kubeconfig_folder, environment, cluster, "kubeconfig")
    if not os.path.exists(kubeconfig_path):
        raise HTTPException(status_code=404, detail=f"Kubeconfig não encontrado para o cluster '{cluster}' no ambiente '{environment}'.")

    try:
        # Carrega o kubeconfig para o cluster
        config.load_kube_config(config_file=kubeconfig_path)
        k8s_client = client.CoreV1Api()

        # Lista todos os pods no namespace
        pods = k8s_client.list_namespaced_pod(namespace=namespace)

        if not pods.items:
            return []

        pod_list = []
        for pod in pods.items:
            pod_list.append({"pod_name": pod.metadata.name})

        return pod_list
    except client.exceptions.ApiException as e:
        raise HTTPException(status_code=e.status, detail=f"Erro ao listar pods no namespace '{namespace}': {e.reason}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")
