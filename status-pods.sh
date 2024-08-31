#!/bin/bash

# Função para exibir o uso do script
function usage() {
    printf "Uso: %s -c <clusters> -n <namespaces> -p <pod patterns>\n" "$0"
    printf "  -c <clusters>      Lista de contextos dos clusters, separados por vírgulas\n"
    printf "  -n <namespaces>    Lista de namespaces, separados por vírgulas (um conjunto por cluster)\n"
    printf "  -p <pod patterns>  Lista de padrões de nomes de pods, separados por vírgulas (um conjunto por cluster)\n"
    exit 1
}

# Parseia os argumentos de linha de comando
while getopts "c:n:p:" opt; do
    case $opt in
        c)
            CLUSTERS=$OPTARG
            ;;
        n)
            NAMESPACES=$OPTARG
            ;;
        p)
            POD_PATTERNS=$OPTARG
            ;;
        *)
            usage
            ;;
    esac
done

# Verifica se todos os parâmetros foram fornecidos
if [[ -z "$CLUSTERS" ]] || [[ -z "$NAMESPACES" ]] || [[ -z "$POD_PATTERNS" ]]; then
    usage
fi

# Converte as listas de clusters, namespaces e pod patterns para arrays
IFS=',' read -r -a CLUSTERS_ARRAY <<< "$CLUSTERS"
IFS=';' read -r -a NAMESPACES_ARRAY <<< "$NAMESPACES"
IFS=';' read -r -a POD_PATTERNS_ARRAY <<< "$POD_PATTERNS"

# Verifica se o tamanho dos arrays é igual
if [[ "${#CLUSTERS_ARRAY[@]}" -ne "${#NAMESPACES_ARRAY[@]}" ]] || [[ "${#NAMESPACES_ARRAY[@]}" -ne "${#POD_PATTERNS_ARRAY[@]}" ]]; then
    printf "Erro: O número de clusters, namespaces e padrões de pods deve ser igual.\n" >&2
    exit 1
fi

# Define o nome do arquivo CSV
CSV_FILE="pods_status.csv"

# Define o arquivo temporário para o relatório final
FINAL_REPORT_FILE="final_report.tmp"

# Inicializa o arquivo CSV com o cabeçalho
printf "Cluster;Namespace;Pod Name;Status;Creation Time;Recent Change;Error Count;CPU Usage;Memory Usage;CPU Request;Memory Request;CPU Limit;Memory Limit;CPU Usage vs Limit;Memory Usage vs Limit;HPA Enabled;HPA Min Replicas;HPA Max Replicas;HPA Current Replicas;HPA CPU Target;HPA CPU Current;Restart Count\n" > "$CSV_FILE"

# Inicializa o arquivo de relatório final
> "$FINAL_REPORT_FILE"

# Função para processar os pods em um namespace dentro de um cluster
function process_pods() {
    local cluster namespace pattern
    cluster=$1
    namespace=$2
    pattern=$3

    printf "Processando cluster: %s, namespace: %s, padrão: %s\n" "$cluster" "$namespace" "$pattern"

    # Muda para o contexto do cluster especificado
    oc config use-context "$cluster"

    # Obtém todos os HPAs no namespace atual
    local hpa_list
    hpa_list=$(oc get hpa -n "$namespace" -o json)

    # Executa o comando oc e processa a saída JSON
    local pod_data pod_name pod_status creation_time creation_time_epoch time_diff recent_change error_count
    local resource_usage cpu_usage memory_usage cpu_request memory_request cpu_limit memory_limit hpa_info
    local hpa_enabled hpa_min_replicas hpa_max_replicas hpa_current_replicas hpa_cpu_target hpa_cpu_current
    local restart_count

    oc get pods -n "$namespace" -o json | jq -c --arg pattern "$pattern" \
    '.items[] | select(.metadata.name | contains($pattern)) | {name: .metadata.name, status: .status.phase, creationTime: .metadata.creationTimestamp, containers: .spec.containers, restartCount: .status.containerStatuses[].restartCount}' |
    while IFS= read -r pod_data; do
        pod_name=$(echo "$pod_data" | jq -r '.name')
        pod_status=$(echo "$pod_data" | jq -r '.status')
        creation_time=$(echo "$pod_data" | jq -r '.creationTime')

        # Log de processamento do pod
        printf "  Processando pod: %s\n" "$pod_name"

        # Converte a data de criação para segundos desde Epoch
        creation_time_epoch=$(date -d "$creation_time" +%s)
        time_diff=$((CURRENT_TIME - creation_time_epoch))

        # Verifica se o pod foi criado nas últimas 24 horas (86400 segundos)
        if [[ $time_diff -lt 86400 ]]; then
            recent_change="Yes"
        else
            recent_change="No"
        fi

        # Conta a quantidade de linhas com a palavra "ERRO" nos logs do pod
        error_count=$(oc logs -n "$namespace" "$pod_name" | grep -c "ERRO")

        # Verifica se o erro conta é alto
        if [[ "$error_count" -gt 2000 ]]; then
            printf "%s|%s|%s -> %d erros\n" "$cluster" "$namespace" "$pod_name" "$error_count" >> "$FINAL_REPORT_FILE"
        fi

        # Obtém o uso de CPU e Memória
        resource_usage=$(oc adm top pod "$pod_name" -n "$namespace" --no-headers --use-protocol-buffers)
        cpu_usage=$(echo "$resource_usage" | awk '{print $2}')
        memory_usage=$(echo "$resource_usage" | awk '{print $3}')

        # Obtém as requisições e limites de CPU e memória para o pod
        cpu_request=$(echo "$pod_data" | jq -r '.containers[].resources.requests.cpu // "N/A"')
        memory_request=$(echo "$pod_data" | jq -r '.containers[].resources.requests.memory // "N/A"')
        cpu_limit=$(echo "$pod_data" | jq -r '.containers[].resources.limits.cpu // "N/A"')
        memory_limit=$(echo "$pod_data" | jq -r '.containers[].resources.limits.memory // "N/A"')

        # Verifica se o pod está sob um HPA e coleta informações
        hpa_enabled="No"
        hpa_min_replicas="N/A"
        hpa_max_replicas="N/A"
        hpa_current_replicas="N/A"
        hpa_cpu_target="N/A"
        hpa_cpu_current="N/A"

        hpa_info=$(echo "$hpa_list" | jq -c --arg pod_name "$pod_name" '.items[] | select(.metadata.name | contains($pod_name))')
        if [[ -n "$hpa_info" ]]; then
            hpa_enabled="Yes"
            hpa_min_replicas=$(echo "$hpa_info" | jq -r '.spec.minReplicas')
            hpa_max_replicas=$(echo "$hpa_info" | jq -r '.spec.maxReplicas')
            hpa_current_replicas=$(echo "$hpa_info" | jq -r '.status.currentReplicas')
            hpa_cpu_target=$(echo "$hpa_info" | jq -r '.spec.targetCPUUtilizationPercentage // "N/A"')
            hpa_cpu_current=$(echo "$hpa_info" | jq -r '.status.currentCPUUtilizationPercentage // "N/A"')

            # Verifica se o HPA está acima de 80% do limite
            if [[ "$hpa_cpu_current" != "N/A" ]] && [[ "$hpa_cpu_current" -ge 80 ]]; then
                printf "%s|%s|%s -> %s%%\n" "$cluster" "$namespace" "$pod_name" "$hpa_cpu_current" >> "$FINAL_REPORT_FILE"
            fi
        fi

        # Verifica se o pod está com status diferente de "Running"
        if [[ "$pod_status" != "Running" ]]; then
            printf "%s|%s|%s -> %s\n" "$cluster" "$namespace" "$pod_name" "$pod_status" >> "$FINAL_REPORT_FILE"
        fi

        # Obtém a contagem de reinicializações do pod
        restart_count=$(echo "$pod_data" | jq -r '.restartCount')

        # Verifica se o pod teve reinicializações
        if [[ "$restart_count" -gt 0 ]]; then
            printf "%s|%s|%s -> %d reinicializações\n" "$cluster" "$namespace" "$pod_name" "$restart_count" >> "$FINAL_REPORT_FILE"
        fi

        # Adiciona as informações do pod ao CSV
        printf "%s;%s;%s;%s;%s;%s;%d;%s;%s;%s;%s;%s;%s;%s;%s;%s;%s;%s;%s;%s;%s;%d\n" \
        "$cluster" "$namespace" "$pod_name" "$pod_status" "$creation_time" "$recent_change" "$error_count" \
        "$cpu_usage" "$memory_usage" "$cpu_request" "$memory_request" "$cpu_limit" "$memory_limit" \
        "$CPU_PERCENTAGE" "$MEMORY_PERCENTAGE" "$hpa_enabled" "$hpa_min_replicas" "$hpa_max_replicas" \
        "$hpa_current_replicas" "$hpa_cpu_target" "$hpa_cpu_current" "$restart_count" >> "$CSV_FILE"
    done
}

# Processa as listas de clusters, namespaces e pod patterns corretamente
for index in "${!CLUSTERS_ARRAY[@]}"; do
    cluster="${CLUSTERS_ARRAY[$index]}"
    namespaces="${NAMESPACES_ARRAY[$index]}"
    pod_patterns="${POD_PATTERNS_ARRAY[$index]}"

    IFS=',' read -r -a namespace_array <<< "$namespaces"
    IFS=',' read -r -a pattern_array <<< "$pod_patterns"

    for i in "${!namespace_array[@]}"; do
        process_pods "$cluster" "${namespace_array[$i]}" "${pattern_array[$i]}"
    done
done

# Geração de informações dos nodes para cada cluster
printf "\nCluster;Node;CPU Usage;CPU Usage (%%);Memory Usage;Memory Usage (%%)\n" >> "$CSV_FILE"

for cluster in "${CLUSTERS_ARRAY[@]}"; do
    printf "Processando informações dos nodes para o cluster: %s\n" "$cluster"

    # Muda para o contexto do cluster especificado
    oc config use-context "$cluster"

    # Coleta as informações de todos os nodes usando o comando 'oc adm top nodes'
    oc adm top nodes --no-headers --use-protocol-buffers | while IFS= read -r line; do
        node_name=$(echo "$line" | awk '{print $1}')
        node_cpu_usage=$(echo "$line" | awk '{print $2}')
        node_cpu_percent=$(echo "$line" | awk '{print $3}')
        node_memory_usage=$(echo "$line" | awk '{print $4}')
        node_memory_percent=$(echo "$line" | awk '{print $5}')

        # Log de processamento do node
        printf "  Processando node: %s\n" "$node_name"

        # Verifica se o node está próximo de seu limite de CPU ou memória
        if [[ "${node_cpu_percent%?}" -ge 80 ]] || [[ "${node_memory_percent%?}" -ge 80 ]]; then
            printf "%s|%s -> CPU: %s, Memory: %s\n" "$cluster" "$node_name" "$node_cpu_percent" "$node_memory_percent" >> "$FINAL_REPORT_FILE"
        fi

        # Adiciona as informações do node ao CSV
        printf "%s;%s;%s;%s;%s;%s\n" "$cluster" "$node_name" "$node_cpu_usage" "$node_cpu_percent" "$node_memory_usage" "$node_memory_percent" >> "$CSV_FILE"
    done
done

# Adiciona o conteúdo do relatório final ao CSV principal
{
    printf "\nRelatório Final:\n"
    printf "\nPods com status diferente de 'Running':\n"
    grep -F -- "-->" "$FINAL_REPORT_FILE" | grep -E -- "--> (Pending|Failed|Unknown)"

    printf "\nPods com HPA acima de 80%% do limite:\n"
    grep -F -- "-->" "$FINAL_REPORT_FILE" | grep -F "HPA"

    printf "\nPods com mais de 2000 erros nos logs:\n"
    grep -F -- "-->" "$FINAL_REPORT_FILE" | grep -F "erros"

    printf "\nPods com reinicializações:\n"
    grep -F -- "-->" "$FINAL_REPORT_FILE" | grep -F "reinicializações"

    printf "\nNodes próximos ao limite de CPU ou memória:\n"
    grep -F -- "-->" "$FINAL_REPORT_FILE" | grep -F "CPU"
} >> "$CSV_FILE"

# Remove o arquivo temporário
rm -f "$FINAL_REPORT_FILE"

printf "Relatório final gerado no CSV: %s\n" "$CSV_FILE"
