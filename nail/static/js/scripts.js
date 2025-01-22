function fetchWorkloadPods() {
    const environment = $("#environment").val();
    const cluster = $("#cluster").val();
    const namespace = $("#namespace").val();
    const workload = $("#workload").val();

    $.get(`/workload-pods/?environment=${environment}&cluster=${cluster}&namespace=${namespace}&workload_name=${workload}`)
        .done((data) => {
            // Render table...
        })
        .fail((err) => {
            // Handle errors...
        });
}

function fetchHPA() {
    const environment = $("#hpa-environment").val();
    const cluster = $("#hpa-cluster").val();
    const namespace = $("#hpa-namespace").val();
    const deployment = $("#hpa-deployment").val();

    $.get(`/hpa/?environment=${environment}&cluster=${cluster}&namespace=${namespace}&deployment_name=${deployment}`)
        .done((data) => {
            // Render table...
        })
        .fail((err) => {
            // Handle errors...
        });
}
