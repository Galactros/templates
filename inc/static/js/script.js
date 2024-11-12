// static/js/script.js
$(document).ready(function() {
    // Inicializando os tooltips
    $('[data-toggle="tooltip"]').tooltip();

    // Adicionar nova ação
    $('#addAcao').click(function() {
        $('#acoes').append(
            '<div class="form-row align-items-center mb-2 action-row">' +
            '<div class="col-auto">' +
            '<label data-toggle="tooltip" data-placement="top" title="Hora em que a ação foi realizada">' +
            '<input type="time" class="form-control" name="acoes_hora" required>' +
            '</label>' +
            '</div>' +
            '<div class="col">' +
            '<label data-toggle="tooltip" data-placement="top" title="Descreva a ação realizada">' +
            '<input type="text" class="form-control" name="acoes_desc" placeholder="Descrição da ação" required>' +
            '</label>' +
            '</div>' +
            '<button type="button" class="btn btn-danger removeAcao">×</button>' +
            '</div>'
        );
        // Re-inicializar os tooltips
        $('[data-toggle="tooltip"]').tooltip();
    });

    // Remover ação
    $(document).on('click', '.removeAcao', function() {
        $(this).closest('.action-row').remove();
    });

    // Limpar formulário
    $('#clearFormButton').click(function() {
        $('#incidenteForm')[0].reset();
        $('#acoes').empty();
        clearFormCookie();
    });

    // Função para apagar o cookie do formulário
    function clearFormCookie() {
        document.cookie = "form_data=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
    }
});
