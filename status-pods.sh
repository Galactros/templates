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
printf "%-20s %-25s %-15s %-25s %-15s %-15s %-10s %-10s\n" "Namespace" "Pod Name" "Status" "Creation Time" "Recent Change" "Error Count" "CPU Usage" "Memory Usage" > $CSV_FILE

# Inicializa variáveis para contagem de status
TOTAL_PODS=0
TOTAL_OK=0
CURRENT_TIME=$(date +%s)

# Função para processar os pods em um namespace
function process_pods() {
    local namespace=$1
    local pattern=$2

    # Executa o comando oc e processa a saída JSON
    oc get pods -n $namespace -o json | jq -c --arg pattern "$pattern" '.items[] | select(.metadata.name | contains($pattern)) | {name: .metadata.name, status: .status.phase, creationTime: .metadata.creationTimestamp}' | while read -r pod; do
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
        
        # Adiciona as informações do pod ao CSV
        printf "%-20s %-25s %-15s %-25s %-15s %-15s %-10s %-10s\n" "$namespace" "$POD_NAME" "$POD_STATUS" "$CREATION_TIME" "$RECENT_CHANGE" "$ERROR_COUNT" "$CPU_USAGE" "$MEMORY_USAGE" >> $CSV_FILE
        
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
printf "%-135s\n" "Overall Status; $OVERALL_STATUS" >> $CSV_FILE

echo "CSV formatado gerado em $CSV_FILE"
