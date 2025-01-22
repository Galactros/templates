function fetchWorkloadPods() {
    const environment = $("#environment").val();
    const cluster = $("#cluster").val();
    const namespace = $("#namespace").val();
    const workload = $("#workload").val();

    $.get(`/workload-pods/?environment=${environment}&cluster=${cluster}&namespace=${namespace}&workload_name=${workload}`)
        .done((data) => {
            let resultHtml = '<table class="table table-bordered">';
            resultHtml += '<thead><tr><th>Pod Name</th><th>Status</th><th>Creation Time</th><th>Tag</th><th>Restarts</th></tr></thead><tbody>';
            data.forEach(pod => {
                resultHtml += `<tr>
                    <td>${pod.pod_name}</td>
                    <td>${pod.pod_status}</td>
                    <td>${pod.creation_time}</td>
                    <td>${pod.tag}</td>
                    <td>${pod.restarts}</td>
                </tr>`;
            });
            resultHtml += '</tbody></table>';
            $("#workload-pods-result").html(resultHtml);
        })
        .fail((err) => {
            $("#workload-pods-result").html(`<div class="alert alert-danger">${err.responseJSON.error}</div>`);
        });
}

function fetchHPA() {
    const environment = $("#hpa-environment").val();
    const cluster = $("#hpa-cluster").val();
    const namespace = $("#hpa-namespace").val();
    const deployment = $("#hpa-deployment").val();

    $.get(`/hpa/?environment=${environment}&cluster=${cluster}&namespace=${namespace}&deployment_name=${deployment}`)
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
        });
}
