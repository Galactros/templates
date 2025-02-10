let selectedEnvironment = '';

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
                    <td><button class="btn btn-sm btn-secondary" onclick="downloadPodLogs('${pod.pod_name}')">Download Logs</button></td>
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
            let errorMessage = err.responseJSON && err.responseJSON.error ? err.responseJSON.error : "Erro ao buscar os Hpas.";
            $("#hpa-result").html(`<div class="alert alert-danger">${errorMessage}</div>`);
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
            let errorMessage = err.responseJSON && err.responseJSON.error ? err.responseJSON.error : "Erro ao buscar os Pods Events.";
            $("#events-pods-result").html(`<div class="alert alert-danger">${errorMessage}</div>`);
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
            let errorMessage = err.responseJSON && err.responseJSON.error ? err.responseJSON.error : "Erro ao buscar PVCs.";
            $("#pvc-result").html(`<div class="alert alert-danger">${errorMessage}</div>`);
        })
        .always(() => {
            hideLoadingSpinner();
        });
}
