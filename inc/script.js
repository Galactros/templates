$(document).ready(function() {
    // Inicializando os tooltips
    $('[data-toggle="tooltip"]').tooltip();

    var acaoCount = 0;

    $('#addAcao').click(function() {
        acaoCount++;
        $('#acoes').append(
            '<div class="form-row align-items-center mb-2 action-row">' +
            '<div class="col-auto">' +
            '<label data-toggle="tooltip" data-placement="top" title="Hora em que a ação foi realizada">' +
            '<input type="time" class="form-control" name="acao_hora_' + acaoCount + '" required>' +
            '</label>' +
            '</div>' +
            '<div class="col">' +
            '<label data-toggle="tooltip" data-placement="top" title="Descreva a ação realizada">' +
            '<input type="text" class="form-control" name="acao_desc_' + acaoCount + '" placeholder="Descrição da ação" required>' +
            '</label>' +
            '</div>' +
            '<button type="button" class="btn btn-danger removeAcao">×</button>' +
            '</div>'
        );
        // Re-inicializando os tooltips para os novos elementos
        $('[data-toggle="tooltip"]').tooltip();
    });

    $(document).on('click', '.removeAcao', function() {
        $(this).closest('.action-row').remove();
    });

    var textoInformativoPlain = ''; // Variável para armazenar o texto plano

    $('#incidenteForm').submit(function(e) {
        e.preventDefault();

        // Coletando os dados do formulário
        var dados = {
            tipoComunicado: $('#tipoComunicado').val(),
            titulo: $('#titulo').val(),
            status: $('#status').val(),
            lider: $('#lider').val(),
            ocorrencia: $('#ocorrencia').val(),
            inicio: $('#inicio').val(),
            fim: $('#fim').val(),
            canais: $('#canais').val(),
            impacto: $('#impacto').val() || 'Em análise',
            causa: $('#causa').val() || 'Em análise',
            natureza: $('#natureza').val(),
            registro: $('#registro').val(),
            mudancas: $('#mudancas').val(),
            envolvidos: $('#envolvidos').val(),
            sala: $('#sala').val()
        };

        // Coletando as ações
        dados.acoes = [];
        $('#acoes .action-row').each(function() {
            var hora = $(this).find('input[name^="acao_hora_"]').val();
            var descricao = $(this).find('input[name^="acao_desc_"]').val();
            dados.acoes.push({ hora: hora, descricao: descricao });
        });

        // Gerando o informativo em HTML formatado e texto plano
        var informativoHTML = gerarInformativoHTML(dados);
        textoInformativoPlain = gerarInformativoPlain(dados);

        // Exibindo o resultado
        $('#resultado').html(informativoHTML + '<button id="copyButton" class="btn btn-secondary">Copiar Informativo</button>');

        // Função para copiar o conteúdo
        $('#copyButton').click(function() {
            copiarTexto(textoInformativoPlain);
        });
    });

    function gerarInformativoHTML(dados) {
        var texto = '<h3>' + dados.tipoComunicado.toUpperCase() + '</h3>';
        texto += '<h4>' + dados.titulo + '</h4>';
        texto += '<p><strong>Status:</strong> ' + dados.status + '</p>';
        texto += '<p><strong>Líder da Sala:</strong> ' + dados.lider + '</p>';
        texto += '<p><strong>Ocorrência:</strong> ' + dados.ocorrencia + '</p>';
        texto += '<p><strong>Horário de Início:</strong> ' + dados.inicio + ' / <strong>Horário de Fim:</strong> ' + (dados.fim || 'Em andamento') + '</p>';
        texto += '<p><strong>Canais Envolvidos:</strong> ' + dados.canais + '</p>';
        texto += '<p><strong>Impacto:</strong> ' + dados.impacto + '</p>';
        texto += '<p><strong>Causa Raiz:</strong> ' + dados.causa + '</p>';
        texto += '<p><strong>Natureza do Incidente:</strong> ' + dados.natureza + '</p>';

        if (dados.acoes.length > 0) {
            texto += '<p><strong>Ações:</strong></p><ul>';
            dados.acoes.forEach(function(acao) {
                texto += '<li>' + acao.hora + ' - ' + acao.descricao + '</li>';
            });
            texto += '</ul>';
        }

        if (dados.registro) {
            texto += '<p><strong>Registro de Incidente:</strong> ' + dados.registro + '</p>';
        }

        if (dados.mudancas && dados.mudancas.toLowerCase() !== 'em análise') {
            texto += '<p><strong>Mudanças Relacionadas:</strong> ' + dados.mudancas + '</p>';
        }

        texto += '<p><strong>Envolvidos:</strong> ' + dados.envolvidos + '</p>';

        if (dados.sala) {
            texto += '<p><strong>Sala de Solução:</strong> ' + dados.sala + '</p>';
        }

        return texto;
    }

    function gerarInformativoPlain(dados) {
        var texto = dados.tipoComunicado.toUpperCase() + '\n\n';
        texto += dados.titulo + '\n\n';
        texto += 'Status: ' + dados.status + '\n\n';
        texto += 'Líder da Sala: ' + dados.lider + '\n\n';
        texto += 'Ocorrência: ' + dados.ocorrencia + '\n\n';
        texto += 'Horário de Início: ' + dados.inicio + ' / Horário de Fim: ' + (dados.fim || 'Em andamento') + '\n\n';
        texto += 'Canais Envolvidos: ' + dados.canais + '\n\n';
        texto += 'Impacto: ' + dados.impacto + '\n\n';
        texto += 'Causa Raiz: ' + dados.causa + '\n\n';
        texto += 'Natureza do Incidente: ' + dados.natureza + '\n\n';

        if (dados.acoes.length > 0) {
            texto += 'Ações:\n';
            dados.acoes.forEach(function(acao) {
                texto += '- ' + acao.hora + ' - ' + acao.descricao + '\n';
            });
            texto += '\n';
        }

        if (dados.registro) {
            texto += 'Registro de Incidente: ' + dados.registro + '\n\n';
        }

        if (dados.mudancas && dados.mudancas.toLowerCase() !== 'em análise') {
            texto += 'Mudanças Relacionadas: ' + dados.mudancas + '\n\n';
        }

        texto += 'Envolvidos: ' + dados.envolvidos + '\n\n';

        if (dados.sala) {
            texto += 'Sala de Solução: ' + dados.sala + '\n\n';
        }

        return texto;
    }

    function copiarTexto(texto) {
        var textarea = document.createElement('textarea');
        textarea.textContent = texto;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
    }
});
