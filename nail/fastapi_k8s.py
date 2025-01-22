from fastapi import FastAPI, Query
from fastapi.openapi.utils import get_openapi
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
    """Retorna as informações de CPU e memória utilizadas e totais do cluster."""
    if not k8s_client:
        return {"error": "Erro ao conectar-se ao Kubernetes API. Verifique o kubeconfig."}

    try:
        metrics_client = client.CustomObjectsApi()
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
        return {"error": f"Erro ao obter recursos do cluster: {str(e)}"}

# Configuração do Swagger personalizado
@app.get("/openapi.json")
def custom_openapi():
    """Gera o esquema OpenAPI para o Swagger."""
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="API Kubernetes",
        version="1.0.0",
        description="API para interagir com o Kubernetes utilizando kubeconfig",
        routes=app.routes,
    )
    app.openapi_schema = openapi_schema
    return app.openapi_schema
