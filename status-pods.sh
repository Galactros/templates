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

# Define o nome do arquivo CSV
CSV_FILE="pods_status.csv"

# Inicializa o arquivo CSV com o cabeçalho
echo "Namespace;Pod Name;Status;Creation Time;Recent Change;Error Count" > $CSV_FILE

# Inicializa variáveis para contagem de status
TOTAL_PODS=0
TOTAL_OK=0
CURRENT_TIME=$(date +%s)

# Função para processar os pods em um namespace
function process_pods() {
    local namespace=$1
    local pattern=$2

    # Executa o comando kubectl e processa a saída JSON
    kubectl get pods -n $namespace -o json | jq -c --arg pattern "$pattern" '.items[] | select(.metadata.name | contains($pattern)) | {name: .metadata.name, status: .status.phase, creationTime: .metadata.creationTimestamp}' | while read -r pod; do
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
        ERROR_COUNT=$(kubectl logs -n $namespace $POD_NAME | grep -c "ERRO")
        
        # Adiciona as informações do pod ao arquivo CSV
        echo "$namespace;$POD_NAME;$POD_STATUS;$CREATION_TIME;$RECENT_CHANGE;$ERROR_COUNT" >> $CSV_FILE
        
        # Incrementa contagem de pods
        TOTAL_PODS=$((TOTAL_PODS+1))
        if [[ "$POD_STATUS" == "Running" ]]; then
            TOTAL_OK=$((TOTAL_OK+1))
        fi
    done
}

# Processa cada namespace e pod pattern
for namespace in "${NAMESPACES_ARRAY[@]}"; do
    for pattern in "${POD_PATTERNS_ARRAY[@]}"; do
        process_pods "$namespace" "$pattern"
    done
done

# Adiciona o resultado geral no final do CSV
if [[ $TOTAL_PODS -eq $TOTAL_OK ]]; then
    OVERALL_STATUS="All Pods are Running"
else
    OVERALL_STATUS="Some Pods are not Running"
fi
echo -e "\nOverall Status;" >> $CSV_FILE
echo $OVERALL_STATUS >> $CSV_FILE

echo "CSV gerado em $CSV_FILE"
