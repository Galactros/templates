from fastapi import FastAPI, Query
from kubernetes import client, config
from typing import List

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
