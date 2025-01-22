from fastapi import FastAPI, Query
from kubernetes import client, config
from typing import List, Dict

app = FastAPI()

# Carrega o kubeconfig no início da aplicação
try:
    config.load_kube_config(config_file="/path/to/kubeconfig")
    k8s_client = client.CoreV1Api()
except Exception as e:
    k8s_client = None
    print(f"Erro ao carregar o kubeconfig: {e}")

@app.get("/pods/", response_model=List[str])
def list_pods(namespace: str = Query(default="default", description="Namespace a ser consultado")):
    """Lista os pods em um namespace especificado."""
    if not k8s_client:
        return {"error": "Erro ao conectar-se ao Kubernetes API. Verifique o kubeconfig."}

    try:
        pods = k8s_client.list_namespaced_pod(namespace=namespace)
        pod_names = [pod.metadata.name for pod in pods.items]
        return pod_names
    except client.exceptions.ApiException as e:
        return {"error": f"Erro ao listar pods no namespace '{namespace}': {e.reason}"}

@app.get("/health")
def health_check():
    """Verifica a saúde da aplicação."""
    return {"status": "ok"}

@app.get("/cluster-resources/", response_model=Dict[str, Dict[str, str]])
def cluster_resources():
    """Retorna as informações de utilização de CPU e memória dos clusters."""
    if not k8s_client:
        return {"error": "Erro ao conectar-se ao Kubernetes API. Verifique o kubeconfig."}

    try:
        nodes = k8s_client.list_node()

        cluster_data = {}

        for node in nodes.items:
            node_name = node.metadata.name
            allocatable = node.status.allocatable
            capacity = node.status.capacity

            # Calcula a utilização de CPU e memória
            cpu_allocatable = int(allocatable["cpu"].strip("m")) / 1000
            cpu_capacity = int(capacity["cpu"].strip("m")) / 1000
            memory_allocatable = int(allocatable["memory"].strip("Ki")) / 1024 / 1024
            memory_capacity = int(capacity["memory"].strip("Ki")) / 1024 / 1024

            cpu_usage_percentage = (cpu_allocatable / cpu_capacity) * 100
            memory_usage_percentage = (memory_allocatable / memory_capacity) * 100

            cluster_data[node_name] = {
                "cpu_usage_percentage": f"{cpu_usage_percentage:.2f}%",
                "memory_usage_percentage": f"{memory_usage_percentage:.2f}%",
                "cpu_allocatable": f"{cpu_allocatable:.2f} cores",
                "cpu_capacity": f"{cpu_capacity:.2f} cores",
                "memory_allocatable": f"{memory_allocatable:.2f} GiB",
                "memory_capacity": f"{memory_capacity:.2f} GiB",
            }

        return cluster_data
    except Exception as e:
        return {"error": f"Erro ao obter recursos do cluster: {str(e)}"}
