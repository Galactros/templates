from command_utils import run_command

def is_logged_in(cluster_name):
    """
    Verifica se já está conectado ao cluster verificando o comando `oc whoami`
    """
    try:
        current_context = run_command("oc config current-context")
        return cluster_name in current_context
    except RuntimeError:
        return False

def login_to_cluster(cluster_name, username, password):
    """
    Tenta fazer login no cluster usando o padrão de URL baseado no nome do cluster
    """
    cluster_url = f"https://api.{cluster_name}.producao.ibm.cloud:6443"
    
    try:
        if not is_logged_in(cluster_name):
            print(f"Conectando ao cluster {cluster_name}...")
            login_command = f"oc login --insecure-skip-tls-verify=true --context={cluster_name} {cluster_url} --username {username} --password {password}"
            run_command(login_command)
        else:
            print(f"Já conectado ao cluster {cluster_name}.")
    except RuntimeError as e:
        print(f"Erro ao tentar se conectar ao cluster {cluster_name}: {str(e)}")
