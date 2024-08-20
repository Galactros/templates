#!/bin/bash

# Função para exibir o uso do script
function usage() {
    echo "Uso: $0 -n <namespaces> -p <pod patterns>"
    echo "  -n <namespaces>     Lista de namespaces, separados por vírgulas"
    echo "  -p <pod patterns>   Lista de padrões de nomes de pods, separados por vírgulas"
    exit 1
}

# Parseia os argumentos de linha de comando
while getopts "n:p:" opt; do
    case $opt in
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

# Verifica se ambos os parâmetros foram fornecidos
if [ -z "$NAMESPACES" ] || [ -z "$POD_PATTERNS" ]; then
    usage
fi

# Converte as listas de namespaces e pod patterns para arrays
IFS=',' read -r -a NAMESPACES_ARRAY <<< "$NAMESPACES"
IFS=',' read -r -a POD_PATTERNS_ARRAY <<< "$POD_PATTERNS"

# Verifica se o tamanho dos arrays é igual
if [ "${#NAMESPACES_ARRAY[@]}" -ne "${#POD_PATTERNS_ARRAY[@]}" ]; then
    echo "Erro: O número de namespaces e padrões de pods deve ser igual."
    exit 1
fi

# Define o nome do arquivo CSV
CSV_FILE="pods_status.csv"

# Inicializa o arquivo CSV com o cabeçalho
echo "Namespace;Pod Name;Status;Creation Time;Recent Change;Error Count;CPU Usage;Memory Usage;CPU Request;Memory Request;CPU Limit;Memory Limit;CPU Usage vs Limit;Memory Usage vs Limit;HPA Enabled;HPA Min Replicas;HPA Max Replicas;HPA Current Replicas;HPA CPU Target;HPA CPU Current;Restart Count" > $CSV_FILE

# Inicializa variáveis para contagem de status
TOTAL_PODS=0
TOTAL_OK=0
CURRENT_TIME=$(date +%s)

# Função para converter memória de formato como "Mi", "Gi" para bytes
function convert_memory_to_bytes() {
    local memory=$1
    local value=$(echo $memory | sed 's/[a-zA-Z]*$//') # Remove o sufixo
    local unit=$(echo $memory | sed 's/[0-9]*//g') # Extrai a unidade

    case $unit in
        Ki) echo $(($value * 1024)) ;;
        Mi) echo $(($value * 1024 * 1024)) ;;
        Gi) echo $(($value * 1024 * 1024 * 1024)) ;;
        Ti) echo $(($value * 1024 * 1024 * 1024 * 1024)) ;;
        *) echo $value ;; # Para o caso de não haver unidade ou um valor inesperado
    esac
}

# Função para converter memória de bytes para gigabytes
function convert_bytes_to_gigabytes() {
    local bytes=$1
    echo $(awk "BEGIN {printf \"%.2f\", $bytes / (1024 * 1024 * 1024)}")
}

# Função para processar os pods em um namespace
function process_pods() {
    local namespace=$1
    local pattern=$2

    # Obtém todos os HPAs no namespace atual
    HPA_LIST=$(oc get hpa -n $namespace -o json)

    # Executa o comando oc e processa a saída JSON
    oc get pods -n $namespace -o json | jq -c --arg pattern "$pattern" '.items[] | select(.metadata.name | contains($pattern)) | {name: .metadata.name, status: .status.phase, creationTime: .metadata.creationTimestamp, containers: .spec.containers, restartCount: .status.containerStatuses[].restartCount}' | while read -r pod; do
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
        
        # Obtém o uso de CPU e Memória
        RESOURCE_USAGE=$(oc adm top pod $POD_NAME -n $namespace --no-headers --use-protocol-buffers)
        CPU_USAGE=$(echo $RESOURCE_USAGE | awk '{print $2}')
        MEMORY_USAGE=$(echo $RESOURCE_USAGE | awk '{print $3}')
        
        # Obtém as requisições e limites de CPU e memória para o pod
        CPU_REQUEST=$(echo $pod | jq -r '.containers[].resources.requests.cpu // "N/A"')
        MEMORY_REQUEST=$(echo $pod | jq -r '.containers[].resources.requests.memory // "N/A"')
        CPU_LIMIT=$(echo $pod | jq -r '.containers[].resources.limits.cpu // "N/A"')
        MEMORY_LIMIT=$(echo $pod | jq -r '.containers[].resources.limits.memory // "N/A"')

        # Converte os valores de uso, requisições e limites para um formato comparável (milicores para CPU e bytes para memória)
        CPU_USAGE_MILICORES=$(echo $CPU_USAGE | sed 's/m//')
        CPU_REQUEST_MILICORES=$(echo $CPU_REQUEST | sed 's/m//')
        CPU_LIMIT_MILICORES=$(echo $CPU_LIMIT | sed 's/m//')
        MEMORY_USAGE_BYTES=$(convert_memory_to_bytes $MEMORY_USAGE)
        MEMORY_REQUEST_BYTES=$(convert_memory_to_bytes $MEMORY_REQUEST)
        MEMORY_LIMIT_BYTES=$(convert_memory_to_bytes $MEMORY_LIMIT)
        
        # Calcula a porcentagem de uso em relação aos limites
        if [ "$CPU_LIMIT" != "N/A" ]; then
            CPU_PERCENTAGE=$(awk "BEGIN {printf \"%.2f\", ($CPU_USAGE_MILICORES / $CPU_LIMIT_MILICORES) * 100}")
        else
            CPU_PERCENTAGE="N/A"
        fi

        if [ "$MEMORY_LIMIT" != "N/A" ]; then
            MEMORY_PERCENTAGE=$(awk "BEGIN {printf \"%.2f\", ($MEMORY_USAGE_BYTES / $MEMORY_LIMIT_BYTES) * 100}")
        else
            MEMORY_PERCENTAGE="N/A"
        fi
        
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
        fi

        # Obtém a contagem de reinicializações do pod
        RESTART_COUNT=$(echo $pod | jq -r '.restartCount')

        # Adiciona as informações do pod ao CSV
        echo "$namespace;$POD_NAME;$POD_STATUS;$CREATION_TIME;$RECENT_CHANGE;$ERROR_COUNT;$CPU_USAGE;$MEMORY_USAGE;$CPU_REQUEST;$MEMORY_REQUEST;$CPU_LIMIT;$MEMORY_LIMIT;$CPU_PERCENTAGE%;$MEMORY_PERCENTAGE%;$HPA_ENABLED;$HPA_MIN_REPLICAS;$HPA_MAX_REPLICAS;$HPA_CURRENT_REPLICAS;$HPA_CPU_TARGET;$HPA_CPU_CURRENT;$RESTART_COUNT" >> $CSV_FILE
        
        # Incrementa contagem de pods
        TOTAL_PODS=$((TOTAL_PODS+1))
        if [[ "$POD_STATUS" == "Running" ]]; then
            TOTAL_OK=$((TOTAL_OK+1))
        fi
    done
}

# Processa as listas de namespaces e pod patterns em pares
for i in "${!NAMESPACES_ARRAY[@]}"; do
    process_pods "${NAMESPACES_ARRAY[$i]}" "${POD_PATTERNS_ARRAY[$i]}"
done

# Adiciona o resultado geral no final do CSV
if [[ $TOTAL_PODS -eq $TOTAL_OK ]]; then
    OVERALL_STATUS="All Pods are Running"
else
    OVERALL_STATUS="Some Pods are not Running"
fi
echo "" >> $CSV_FILE
echo "Overall Status;" >> $CSV_FILE
echo $OVERALL_STATUS >> $CSV_FILE

# Geração de informações dos nodes
echo "" >> $CSV_FILE
echo "Node;CPU Usage (%);CPU Capacity (Cores);Memory Usage (GB);Memory Capacity (GB)" >> $CSV_FILE

# Coleta as informações de todos os nodes
oc get nodes -o json | jq -c '.items[] | {name: .metadata.name, cpuCapacity: .status.capacity.cpu, memoryCapacity: .status.capacity.memory}' | while read -r node; do
    NODE_NAME=$(echo $node | jq -r '.name')

    # Obtém o uso de CPU e memória atual do node
    NODE_RESOURCE_USAGE=$(oc adm top node $NODE_NAME --no-headers --use-protocol-buffers)
    NODE_CPU_USAGE=$(echo $NODE_RESOURCE_USAGE | awk '{print $2}')
    NODE_MEMORY_USAGE=$(echo $NODE_RESOURCE_USAGE | awk '{print $4}')

    # Obtém a capacidade de CPU e memória do node
    NODE_CPU_CAPACITY=$(echo $node | jq -r '.cpuCapacity')
    NODE_MEMORY_CAPACITY_BYTES=$(convert_memory_to_bytes $(echo $node | jq -r '.memoryCapacity'))
    NODE_MEMORY_CAPACITY_GB=$(convert_bytes_to_gigabytes $NODE_MEMORY_CAPACITY_BYTES)

    # Converte a capacidade de CPU para porcentagem
    NODE_CPU_USAGE_PERCENT=$(awk "BEGIN {printf \"%.2f\", ($NODE_CPU_USAGE / $NODE_CPU_CAPACITY) * 100}")

    # Converte a capacidade de memória usada para gigabytes e calcula a porcentagem
    NODE_MEMORY_USAGE_BYTES=$(convert_memory_to_bytes $NODE_MEMORY_USAGE)
    NODE_MEMORY_USAGE_GB=$(convert_bytes_to_gigabytes $NODE_MEMORY_USAGE_BYTES)
    NODE_MEMORY_USAGE_PERCENT=$(awk "BEGIN {printf \"%.2f\", ($NODE_MEMORY_USAGE_BYTES / $NODE_MEMORY_CAPACITY_BYTES) * 100}")

    # Adiciona as informações do node ao CSV
    echo "$NODE_NAME;$NODE_CPU_USAGE_PERCENT;$NODE_CPU_CAPACITY;$NODE_MEMORY_USAGE_GB;$NODE_MEMORY_CAPACITY_GB" >> $CSV_FILE
done

echo "CSV gerado em $CSV_FILE"
