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
