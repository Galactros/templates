#!/bin/bash

# Função para exibir o uso do script
function usage() {
    echo "Uso: $0 -c <clusters> -n <namespaces> -p <pod patterns>"
    echo "  -c <clusters>      Lista de contextos dos clusters, separados por vírgulas"
    echo "  -n <namespaces>    Lista de namespaces, separados por vírgulas (um conjunto por cluster)"
    echo "  -p <pod patterns>  Lista de padrões de nomes de pods, separados por vírgulas (um conjunto por cluster)"
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
if [ -z "$CLUSTERS" ] || [ -z "$NAMESPACES" ] || [ -z "$POD_PATTERNS" ]; then
    usage
fi

# Converte as listas de clusters, namespaces e pod patterns para arrays
IFS=',' read -r -a CLUSTERS_ARRAY <<< "$CLUSTERS"
IFS=';' read -r -a NAMESPACES_ARRAY <<< "$NAMESPACES"
IFS=';' read -r -a POD_PATTERNS_ARRAY <<< "$POD_PATTERNS"

# Verifica se o tamanho dos arrays é igual
if [ "${#CLUSTERS_ARRAY[@]}" -ne "${#NAMESPACES_ARRAY[@]}" ] || [ "${#NAMESPACES_ARRAY[@]}" -ne "${#POD_PATTERNS_ARRAY[@]}" ]; then
    echo "Erro: O número de clusters, namespaces e padrões de pods deve ser igual."
    exit 1
fi

# Define o nome do arquivo CSV
CSV_FILE="pods_status.csv"

# Inicializa o arquivo CSV com o cabeçalho
echo "Cluster;Namespace;Pod Name;Status;Creation Time;Recent Change;Error Count;CPU Usage;Memory Usage;CPU Request;Memory Request;CPU Limit;Memory Limit;CPU Usage vs Limit;Memory Usage vs Limit;HPA Enabled;HPA Min Replicas;HPA Max Replicas;HPA Current Replicas;HPA CPU Target;HPA CPU Current;Restart Count" > $CSV_FILE

# Inicializa variáveis para o relatório final
declare -A pod_status_errors
declare -A hpa_limit_exceeded
declare -A high_error_count
declare -A pods_with_restarts
declare -A node_limit_issues

# Função para processar os pods em um namespace dentro de um cluster
function process_pods() {
    local cluster=$1
    local namespace=$2
    local pattern=$3
    local -n ref_pod_status_errors=$4
    local -n ref_hpa_limit_exceeded=$5
    local -n ref_high_error_count=$6
    local -n ref_pods_with_restarts=$7

    # Muda para o contexto do cluster especificado
    oc config use-context $cluster

    # Obtém todos os HPAs no namespace atual
    HPA_LIST=$(oc get hpa -n $namespace -o json)

    # Executa o comando oc e processa a saída JSON
    oc get pods -n $namespace -o json | jq -c --arg pattern "$pattern" '.items[] | select(.metadata.name | contains($pattern)) | {name: .metadata.name, status: .status.phase, creationTime: .metadata.creationTimestamp, containers: .spec.containers, restartCount: .status.containerStatuses[].restartCount}' | while IFS= read -r pod; do
        POD_NAME=$(echo $pod | jq -r '.name')
        POD_STATUS=$(echo $pod | jq -r '.status')
        CREATION_TIME=$(echo $pod | jq -r '.creationTime')
        
        # Converte a data de criação para segundos desde Epoch
        CREATION_TIME_EPOCH=$(date -d "$CREATION_TIME" +%s)
        
        # Calcula a diferença de tempo
        TIME_DIFF=$((CURRENT_TIME - CREATION_TIME_EPOCH))
        
        # Verifica se o pod foi criado nas últimas 24 horas (86400 segundos)
        if [ $TIME_DIFF -lt 86400 ]; then
            RECENT_CHANGE="Yes"
        else
            RECENT_CHANGE="No"
        fi
        
        # Conta a quantidade de linhas com a palavra "ERRO" nos logs do pod
        ERROR_COUNT=$(oc logs -n $namespace $POD_NAME | grep -c "ERRO")
        
        # Verifica se o erro conta é alto
        if [ "$ERROR_COUNT" -gt 2000 ]; then
            ref_high_error_count["$cluster|$namespace|$POD_NAME"]=$ERROR_COUNT
        fi

        # Obtém o uso de CPU e Memória
        RESOURCE_USAGE=$(oc adm top pod $POD_NAME -n $namespace --no-headers --use-protocol-buffers)
        CPU_USAGE=$(echo $RESOURCE_USAGE | awk '{print $2}')
        MEMORY_USAGE=$(echo $RESOURCE_USAGE | awk '{print $3}')
        
        # Obtém as requisições e limites de CPU e memória para o pod
        CPU_REQUEST=$(echo $pod | jq -r '.containers[].resources.requests.cpu // "N/A"')
        MEMORY_REQUEST=$(echo $pod | jq -r '.containers[].resources.requests.memory // "N/A"')
        CPU_LIMIT=$(echo $pod | jq -r '.containers[].resources.limits.cpu // "N/A"')
        MEMORY_LIMIT=$(echo $pod | jq -r '.containers[].resources.limits.memory // "N/A"')
        
        # Verifica se o pod está sob um HPA e coleta informações
        HPA_ENABLED="No"
        HPA_MIN_REPLICAS="N/A"
        HPA_MAX_REPLICAS="N/A"
        HPA_CURRENT_REPLICAS="N/A"
        HPA_CPU_TARGET="N/A"
        HPA_CPU_CURRENT="N/A"

        HPA_INFO=$(echo $HPA_LIST | jq -c --arg pod_name "$POD_NAME" '.items[] | select(.metadata.name | contains($pod_name))')
        if [ -n "$HPA_INFO" ]; then
            HPA_ENABLED="Yes"
            HPA_MIN_REPLICAS=$(echo $HPA_INFO | jq -r '.spec.minReplicas')
            HPA_MAX_REPLICAS=$(echo $HPA_INFO | jq -r '.spec.maxReplicas')
            HPA_CURRENT_REPLICAS=$(echo $HPA_INFO | jq -r '.status.currentReplicas')
            HPA_CPU_TARGET=$(echo $HPA_INFO | jq -r '.spec.targetCPUUtilizationPercentage // "N/A"')
            HPA_CPU_CURRENT=$(echo $HPA_INFO | jq -r '.status.currentCPUUtilizationPercentage // "N/A"')

            # Verifica se o HPA está acima de 80% do limite
            if [ "$HPA_CPU_CURRENT" != "N/A" ] && [ "$HPA_CPU_CURRENT" -ge 80 ]; then
                ref_hpa_limit_exceeded["$cluster|$namespace|$POD_NAME"]=$HPA_CPU_CURRENT
            fi
        fi

        # Verifica se o pod está com status diferente de "Running"
        if [ "$POD_STATUS" != "Running" ]; then
            ref_pod_status_errors["$cluster|$namespace|$POD_NAME"]=$POD_STATUS
        fi

        # Obtém a contagem de reinicializações do pod
        RESTART_COUNT=$(echo $pod | jq -r '.restartCount')

        # Verifica se o pod teve reinicializações
        if [ "$RESTART_COUNT" -gt 0 ]; then
            ref_pods_with_restarts["$cluster|$namespace|$POD_NAME"]=$RESTART_COUNT
        fi

        # Adiciona as informações do pod ao CSV
        echo "$cluster;$namespace;$POD_NAME;$POD_STATUS;$CREATION_TIME;$RECENT_CHANGE;$ERROR_COUNT;$CPU_USAGE;$MEMORY_USAGE;$CPU_REQUEST;$MEMORY_REQUEST;$CPU_LIMIT;$MEMORY_LIMIT;$CPU_PERCENTAGE%;$MEMORY_PERCENTAGE%;$HPA_ENABLED;$HPA_MIN_REPLICAS;$HPA_MAX_REPLICAS;$HPA_CURRENT_REPLICAS;$HPA_CPU_TARGET;$HPA_CPU_CURRENT;$RESTART_COUNT" >> $CSV_FILE
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
        process_pods "$cluster" "${namespace_array[$i]}" "${pattern_array[$i]}" pod_status_errors hpa_limit_exceeded high_error_count pods_with_restarts
    done
done

# Geração de informações dos nodes para cada cluster
echo "" >> $CSV_FILE
echo "Cluster;Node;CPU Usage;CPU Usage (%);Memory Usage;Memory Usage (%)" >> $CSV_FILE

for cluster in "${CLUSTERS_ARRAY[@]}"; do
    # Muda para o contexto do cluster especificado
    oc config use-context $cluster
    
    # Coleta as informações de todos os nodes usando o comando 'oc adm top nodes'
    oc adm top nodes --no-headers --use-protocol-buffers | while IFS= read -r line; do
        NODE_NAME=$(echo $line | awk '{print $1}')
        NODE_CPU_USAGE=$(echo $line | awk '{print $2}')
        NODE_CPU_PERCENT=$(echo $line | awk '{print $3}')
        NODE_MEMORY_USAGE=$(echo $line | awk '{print $4}')
        NODE_MEMORY_PERCENT=$(echo $line | awk '{print $5}')

        # Verifica se o node está próximo de seu limite de CPU ou memória
        if [ "${NODE_CPU_PERCENT%?}" -ge 80 ] || [ "${NODE_MEMORY_PERCENT%?}" -ge 80 ]; then
            node_limit_issues["$cluster|$NODE_NAME"]="CPU: $NODE_CPU_PERCENT, Memory: $NODE_MEMORY_PERCENT"
        fi

        # Adiciona as informações do node ao CSV
        echo "$cluster;$NODE_NAME;$NODE_CPU_USAGE;$NODE_CPU_PERCENT;$NODE_MEMORY_USAGE;$NODE_MEMORY_PERCENT" >> $CSV_FILE
    done
done

# Geração do Relatório Final
echo "" >> $CSV_FILE
echo "Relatório Final:" >> $CSV_FILE

# Pods que não estão com status Running
echo "" >> $CSV_FILE
echo "Pods com status diferente de 'Running':" >> $CSV_FILE
for key in "${!pod_status_errors[@]}"; do
    echo "$key -> ${pod_status_errors[$key]}" >> $CSV_FILE
done

# Pods que estão utilizando 80% ou mais do limite de HPA
echo "" >> $CSV_FILE
echo "Pods com HPA acima de 80% do limite:" >> $CSV_FILE
for key in "${!hpa_limit_exceeded[@]}"; do
    echo "$key -> ${hpa_limit_exceeded[$key]}%" >> $CSV_FILE
done

# Pods com mais de 2000 erros nos logs
echo "" >> $CSV_FILE
echo "Pods com mais de 2000 erros nos logs:" >> $CSV_FILE
for key in "${!high_error_count[@]}"; do
    echo "$key -> ${high_error_count[$key]} erros" >> $CSV_FILE
done

# Pods com reinicializações
echo "" >> $CSV_FILE
echo "Pods com reinicializações:" >> $CSV_FILE
for key in "${!pods_with_restarts[@]}"; do
    echo "$key -> ${pods_with_restarts[$key]} reinicializações" >> $CSV_FILE
done

# Nodes próximos ao limite de CPU ou memória
echo "" >> $CSV_FILE
echo "Nodes próximos ao limite de CPU ou memória:" >> $CSV_FILE
for key in "${!node_limit_issues[@]}"; do
    echo "$key -> ${node_limit_issues[$key]}" >> $CSV_FILE
done

echo "Relatório final gerado no CSV: $CSV_FILE"
