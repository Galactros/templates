from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from urllib.parse import unquote
import json

app = FastAPI()

# Montando o diretório 'static' para servir arquivos estáticos
app.mount("/static", StaticFiles(directory="static"), name="static")

# Configurando os templates
templates = Jinja2Templates(directory="templates")

# Função para gerar o informativo em HTML formatado
def gerar_informativo_html(dados):
    texto = f"<h3>{dados['tipoComunicado'].upper()}</h3>"
    texto += f"<h4>{dados['titulo']}</h4>"
    texto += f"<p><strong>Status:</strong> {dados['status']}</p>"
    texto += f"<p><strong>Líder da Sala:</strong> {dados['lider']}</p>"
    texto += f"<p><strong>Ocorrência:</strong> {dados['ocorrencia']}</p>"
    texto += f"<p><strong>Horário de Início:</strong> {dados['inicio']} / <strong>Horário de Fim:</strong> {dados['fim'] or 'Em andamento'}</p>"
    texto += f"<p><strong>Canais Envolvidos:</strong> {dados['canais']}</p>"
    texto += f"<p><strong>Impacto:</strong> {dados['impacto']}</p>"
    texto += f"<p><strong>Causa Raiz:</strong> {dados['causa']}</p>"
    texto += f"<p><strong>Natureza do Incidente:</strong> {dados['natureza']}</p>"

    if dados['acoes']:
        texto += "<p><strong>Ações:</strong></p><ul>"
        for acao in dados['acoes']:
            texto += f"<li>{acao['hora']} - {acao['descricao']}</li>"
        texto += "</ul>"

    if dados['registro']:
        texto += f"<p><strong>Registro de Incidente:</strong> {dados['registro']}</p>"

    if dados['mudancas'] and dados['mudancas'].lower() != 'em análise':
        texto += f"<p><strong>Mudanças Relacionadas:</strong> {dados['mudancas']}</p>"

    texto += f"<p><strong>Envolvidos:</strong> {dados['envolvidos']}</p>"

    if dados['sala']:
        texto += f"<p><strong>Sala de Solução:</strong> <a href='{dados['sala']}' target='_blank'>{dados['sala']}</a></p>"

    return texto

# Função para gerar o informativo em texto plano
def gerar_informativo_plain(dados):
    texto = f"{dados['tipoComunicado'].upper()}\n\n"
    texto += f"{dados['titulo']}\n\n"
    texto += f"Status: {dados['status']}\n\n"
    texto += f"Líder da Sala: {dados['lider']}\n\n"
    texto += f"Ocorrência: {dados['ocorrencia']}\n\n"
    texto += f"Horário de Início: {dados['inicio']} / Horário de Fim: {dados['fim'] or 'Em andamento'}\n\n"
    texto += f"Canais Envolvidos: {dados['canais']}\n\n"
    texto += f"Impacto: {dados['impacto']}\n\n"
    texto += f"Causa Raiz: {dados['causa']}\n\n"
    texto += f"Natureza do Incidente: {dados['natureza']}\n\n"

    if dados['acoes']:
        texto += "Ações:\n"
        for acao in dados['acoes']:
            texto += f"- {acao['hora']} - {acao['descricao']}\n"
        texto += "\n"

    if dados['registro']:
        texto += f"Registro de Incidente: {dados['registro']}\n\n"

    if dados['mudancas'] and dados['mudancas'].lower() != 'em análise':
        texto += f"Mudanças Relacionadas: {dados['mudancas']}\n\n"

    texto += f"Envolvidos: {dados['envolvidos']}\n\n"

    if dados['sala']:
        texto += f"Sala de Solução: {dados['sala']}\n\n"

    return texto

@app.get("/", response_class=HTMLResponse)
async def read_index(request: Request):
    form_data_cookie = request.cookies.get("form_data")
    if form_data_cookie:
        try:
            # Decodificar o valor do cookie
            decoded_cookie = unquote(form_data_cookie)
            data = json.loads(decoded_cookie)
        except json.JSONDecodeError:
            data = {}
    else:
        data = {}
    return templates.TemplateResponse("index.html", {"request": request, "data": data})

@app.get("/panel", response_class=HTMLResponse)
async def read_panel(request: Request):
    return templates.TemplateResponse("panel.html", {"request": request})

@app.post("/update_form")
async def update_form(request: Request, json_input: str = Form(...)):
    try:
        data = json.loads(json_input)
        response = RedirectResponse(url="/", status_code=303)
        # Salvar o JSON no cookie
        json_data = json.dumps(data)
        response.set_cookie(key="form_data", value=json_data)
        return response
    except json.JSONDecodeError:
        return templates.TemplateResponse("panel.html", {"request": request, "error": "JSON inválido"})

@app.post("/generate_informativo", response_class=HTMLResponse)
async def generate_informativo(request: Request,
                               tipoComunicado: str = Form(...),
                               titulo: str = Form(...),
                               status: str = Form(...),
                               lider: str = Form(...),
                               ocorrencia: str = Form(...),
                               inicio: str = Form(...),
                               fim: str = Form(None),
                               canais: str = Form(...),
                               impacto: str = Form(None),
                               causa: str = Form(None),
                               natureza: str = Form(...),
                               registro: str = Form(None),
                               mudancas: str = Form(None),
                               envolvidos: str = Form(None),
                               sala: str = Form(None),
                               acoes_hora: list = Form(None),
                               acoes_desc: list = Form(None)):
    # Coletar os dados do formulário
    dados = {
        'tipoComunicado': tipoComunicado,
        'titulo': titulo,
        'status': status,
        'lider': lider,
        'ocorrencia': ocorrencia,
        'inicio': inicio,
        'fim': fim,
        'canais': canais,
        'impacto': impacto or 'Em análise',
        'causa': causa or 'Em análise',
        'natureza': natureza,
        'registro': registro,
        'mudancas': mudancas,
        'envolvidos': envolvidos,
        'sala': sala,
        'acoes': []
    }

    # Processar as ações
    if acoes_hora and acoes_desc:
        if isinstance(acoes_hora, str):
            acoes_hora = [acoes_hora]
        if isinstance(acoes_desc, str):
            acoes_desc = [acoes_desc]
        for hora, desc in zip(acoes_hora, acoes_desc):
            dados['acoes'].append({'hora': hora, 'descricao': desc})

    # Gerar o informativo
    informativo_html = gerar_informativo_html(dados)
    informativo_plain = gerar_informativo_plain(dados)

    # Renderizar o template com o informativo
    response = templates.TemplateResponse("informativo.html", {
        "request": request,
        "dados": dados,
        "informativo_html": informativo_html,
        "informativo_plain": informativo_plain
    })

    # Salvar os dados no cookie
    json_data = json.dumps(dados)
    response.set_cookie(key="form_data", value=json_data)

    return response
