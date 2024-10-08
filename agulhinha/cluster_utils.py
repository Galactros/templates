from command_utils import run_command

def is_logged_in(cluster_name):
    """
    Verifica se já está conectado ao cluster verificando o contexto atual
    e se a autenticação está válida usando 'oc whoami'.
    """
    try:
        # Verifica se o contexto atual corresponde ao cluster
        current_context = run_command("oc config current-context").strip()
        if cluster_name != current_context:
            return False

        # Tenta executar 'oc whoami' para verificar se o token é válido
        run_command("oc whoami")
        return True
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
            login_command = f"oc login --insecure-skip-tls-verify=true {cluster_url} --username {username} --password {password}"
            run_command(login_command)

            # Obtém o contexto atual após o login
            current_context = run_command("oc config current-context").strip()

            # Renomeia o contexto para o nome do cluster
            rename_command = f"oc config rename-context '{current_context}' '{cluster_name}'"
            run_command(rename_command)

            print(f"O contexto foi renomeado para '{cluster_name}'.")
        else:
            print(f"Já conectado ao cluster {cluster_name}.")
    except RuntimeError as e:
        print(f"Erro ao tentar se conectar ao cluster {cluster_name}: {str(e)}")
