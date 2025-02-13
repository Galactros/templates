let selectedEnvironment = '';
let podToDelete = null;

function setEnvironment(env) {
    selectedEnvironment = env;
    $('#environmentDropdown').text(`Environment: ${env}`);
}

function showForm(formId) {
    $('.form-section').addClass('d-none');
    $(`#${formId}-form`).removeClass('d-none');
}

function showLoadingSpinner() {
    $('#loading-spinner').removeClass('d-none');
}

function hideLoadingSpinner() {
    $('#loading-spinner').addClass('d-none');
}

function fetchWorkloadPods() {
    if (!selectedEnvironment) {
        alert('Please select an environment.');
        return;
    }
    const cluster = $("#cluster").val();
    const namespace = $("#namespace").val();
    const workload = $("#workload").val();

    showLoadingSpinner();
    $.get(`/workload-pods/?environment=${selectedEnvironment}&cluster=${cluster}&namespace=${namespace}&workload_name=${workload}`)
        .done((data) => {
            let resultHtml = '<table class="table table-bordered">';
            resultHtml += '<thead><tr>' +
                '<th>Pod Name</th><th>Status</th><th>Creation Time</th>' +
                '<th>Tag</th><th>Restarts</th><th>CPU Usage</th>' +
                '<th>Memory Usage</th><th>CPU Limit</th><th>Memory Limit</th>' +
                '<th>Actions</th>' +
                '</tr></thead><tbody>';
            data.forEach(pod => {
                resultHtml += `<tr>
                    <td>${pod.pod_name}</td>
                    <td>${pod.pod_status}</td>
                    <td>${pod.creation_time}</td>
                    <td>${pod.tag}</td>
                    <td>${pod.restarts}</td>
                    <td>${pod.cpu_usage}</td>
                    <td>${pod.memory_usage}</td>
                    <td>${pod.cpu_limit}</td>
                    <td>${pod.memory_limit}</td>
                    <td>
                        <button class="btn btn-sm btn-danger" onclick="showDeletePodModal('${pod.pod_name}')">Delete</button>
                        <button class="btn btn-sm btn-secondary" onclick="downloadPodLogs('${pod.pod_name}')">Download Logs</button>
                    </td>
                </tr>`;
            });
            resultHtml += '</tbody></table>';
            $("#workload-pods-result").html(resultHtml);
        })
        .fail((err) => {
            let errorMessage = err.responseJSON && err.responseJSON.error ? err.responseJSON.error : "Erro ao buscar os pods.";
            $("#workload-pods-result").html(`<div class="alert alert-danger">${errorMessage}</div>`);
        })
        .always(() => {
            hideLoadingSpinner();
        });
}

function downloadPodLogs(podName) {
    if (!selectedEnvironment) {
        alert('Please select an environment.');
        return;
    }
    const cluster = $("#cluster").val();
    const namespace = $("#namespace").val();

    const url = `/pod-logs/?environment=${selectedEnvironment}&cluster=${cluster}&namespace=${namespace}&pod_name=${podName}`;

    showLoadingSpinner();

    fetch(url)
        .then(response => {
            if (!response.ok) {
                throw new Error(`Failed to fetch logs for pod: ${podName}`);
            }
            return response.blob();
        })
        .then(blob => {
            // Cria um link para baixar o arquivo
            const link = document.createElement('a');
            link.href = window.URL.createObjectURL(blob);
            link.download = `${podName}_logs.txt`;
            link.click();
            link.remove();
        })
        .catch(error => {
            alert(`Error downloading logs for pod: ${podName}\n${error.message}`);
        })
        .finally(() => {
            hideLoadingSpinner();
        });
}

function fetchHPA() {
    if (!selectedEnvironment) {
        alert('Please select an environment.');
        return;
    }
    const cluster = $("#hpa-cluster").val();
    const namespace = $("#hpa-namespace").val();
    const deployment = $("#hpa-deployment").val();

    showLoadingSpinner();
    $.get(`/hpa/?environment=${selectedEnvironment}&cluster=${cluster}&namespace=${namespace}&deployment_name=${deployment}`)
        .done((data) => {
            let resultHtml = '<table class="table table-bordered">';
            resultHtml += '<thead><tr><th>HPA Name</th><th>Min Replicas</th><th>Max Replicas</th><th>Current Replicas</th><th>Target CPU Utilization</th></tr></thead><tbody>';
            data.forEach(hpa => {
                resultHtml += `<tr>
                    <td>${hpa.name}</td>
                    <td>${hpa.min_replicas}</td>
                    <td>${hpa.max_replicas}</td>
                    <td>${hpa.current_replicas}</td>
                    <td>${hpa.target_cpu_utilization_percentage}</td>
                </tr>`;
            });
            resultHtml += '</tbody></table>';
            $("#hpa-result").html(resultHtml);
        })
        .fail((err) => {
            $("#hpa-result").html(`<div class="alert alert-danger">${err.responseJSON.error}</div>`);
        })
        .always(() => {
            hideLoadingSpinner();
        });
}

function fetchPodEvents() {
    if (!selectedEnvironment) {
        alert('Please select an environment.');
        return;
    }
    const cluster = $("#events-cluster").val();
    const namespace = $("#events-namespace").val();
    const workload = $("#events-workload").val();

    showLoadingSpinner();

    $.get(`/pod-events/?environment=${selectedEnvironment}&cluster=${cluster}&namespace=${namespace}&workload_name=${workload}`)
        .done((data) => {
            let resultHtml = '<table class="table table-bordered">';
            resultHtml += '<thead><tr><th>Pod Name</th><th>Event Type</th><th>Reason</th><th>Message</th><th>Timestamp</th></tr></thead><tbody>';
            data.forEach(event => {
                resultHtml += `<tr>
                    <td>${event.pod_name}</td>
                    <td>${event.event_type}</td>
                    <td>${event.reason}</td>
                    <td>${event.message}</td>
                    <td>${event.timestamp}</td>
                </tr>`;
            });
            resultHtml += '</tbody></table>';
            $("#events-pods-result").html(resultHtml);
        })
        .fail((err) => {
            $("#events-pods-result").html(`<div class="alert alert-danger">${err.responseJSON.error}</div>`);
        })
        .always(() => {
            hideLoadingSpinner();
        });
}

function fetchPVCs() {
    if (!selectedEnvironment) {
        alert('Please select an environment.');
        return;
    }
    const cluster = $("#pvc-cluster").val();
    const namespace = $("#pvc-namespace").val();

    showLoadingSpinner();

    $.get(`/pvc/?environment=${selectedEnvironment}&cluster=${cluster}&namespace=${namespace}`)
        .done((data) => {
            let resultHtml = '<table class="table table-bordered">';
            resultHtml += '<thead><tr>' +
                '<th>Name</th><th>Capacity</th><th>Used</th>' +
                '<th>Workload</th><th>Access Modes</th>' +
                '</tr></thead><tbody>';
            data.forEach(pvc => {
                resultHtml += `<tr>
                    <td>${pvc.name}</td>
                    <td>${pvc.capacity}</td>
                    <td>${pvc.used}</td>
                    <td>${pvc.workload}</td>
                    <td>${pvc.access_modes}</td>
                </tr>`;
            });
            resultHtml += '</tbody></table>';
            $("#pvc-result").html(resultHtml);
        })
        .fail((err) => {
            $("#pvc-result").html(`<div class="alert alert-danger">${err.responseJSON.error}</div>`);
        })
        .always(() => {
            hideLoadingSpinner();
        });
}

function confirmDeletePod() {
    if (!selectedEnvironment) {
        alert("Por favor, selecione um ambiente.");
        return;
    }
    const cluster = $("#cluster").val();
    const namespace = $("#namespace").val();

    if (!podToDelete) {
        alert("Erro: Nenhum pod selecionado.");
        return;
    }

    showLoadingSpinner();

    $.ajax({
        url: `/delete-pod/?environment=${selectedEnvironment}&cluster=${cluster}&namespace=${namespace}&pod_name=${podToDelete}`,
        type: "DELETE",
        success: function (response) {
            alert(response.message);
            fetchWorkloadPods(); // Atualiza a lista de pods após a exclusão
        },
        error: function (err) {
            let errorMessage =
                err.responseJSON && err.responseJSON.detail
                    ? err.responseJSON.detail
                    : "Erro ao deletar o pod.";
            alert(errorMessage);
        },
        complete: function () {
            hideLoadingSpinner();
            $("#deletePodModal").modal("hide"); // Fecha o modal após a ação
        },
    });
}

function showDeletePodModal(podName) {
    podToDelete = podName;
    $("#deletePodName").text(podName);
    $("#deletePodModal").modal("show");
}

// Associar evento ao botão de confirmação no modal
$("#confirmDeletePod").click(function () {
    confirmDeletePod();
});


function testConnectivity() {
    if (!selectedEnvironment) {
        alert('Por favor, selecione um ambiente.');
        return;
    }
    const cluster = $("#connectivity-cluster").val();
    const namespace = $("#connectivity-namespace").val();
    const podName = $("#connectivity-pod").val();
    const url = $("#connectivity-url").val();
    const testType = $("#connectivity-test-type").val();

    if (!podName || !url) {
        alert("Por favor, preencha todos os campos.");
        return;
    }

    showLoadingSpinner();

    $.ajax({
        url: `/test-connectivity/?environment=${selectedEnvironment}&cluster=${cluster}&namespace=${namespace}&pod_name=${podName}&url=${url}&test_type=${testType}`,
        type: "POST",
        success: function(response) {
            $("#connectivity-output").val(response.output);
        },
        error: function(err) {
            let errorMessage = err.responseJSON && err.responseJSON.detail
                ? err.responseJSON.detail
                : "Erro ao executar o teste.";
            $("#connectivity-output").val(errorMessage);
        },
        complete: function() {
            hideLoadingSpinner();
        }
    });
}


function copyToClipboard() {
    const outputField = document.getElementById("connectivity-output");
    outputField.select();
    document.execCommand("copy");
    alert("Resultado copiado para a área de transferência!");
}
