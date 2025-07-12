import os.path
from datetime import datetime, timedelta

from langchain.tools import tool

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


SCOPES = ["https://www.googleapis.com/auth/calendar","https://www.googleapis.com/auth/gmail.readonly"]

def get_permission_google_service(tool_type,version):
    """
    Autentica com a API do Google Calendar e retorna um objeto de serviço.
    Usa o token.json se existir, caso contrário, inicia o fluxo de login.
    """
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=8080)
        
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    return build(tool_type, version, credentials=creds)

#gmail e v1...

def criar_evento_na_agenda(data):
    """
    Cria um evento no Google Calendar do usuário autenticado.

    Parâmetros:
        data (dict): Dicionário com as seguintes chaves:
            - 'titulo' (str, opcional): Título do evento. Padrão: 'Evento'.
            - 'data_hora_inicio_str' (str, obrigatório): Data e hora de início no formato ISO 8601, ex: '2025-07-10T10:00:00-03:00'.
            - 'duracao_minutos' (int, opcional): Duração do evento em minutos. Padrão: 60.

    Retorna:
        str: Mensagem de confirmação com o link do evento criado, ou mensagem de erro em caso de falha.

    Requisitos:
        - O arquivo 'credentials.json' deve estar presente para autenticação Google.
        - O usuário deve conceder permissão na primeira execução.
    """
    
    titulo = data.get('titulo', 'Evento')
    data_hora_inicio_str = data.get('data_hora_inicio_str', None)
    duracao_minutos = data.get('duracao_minutos', 60)
    
    print(f"FERRAMENTA CHAMADA: criar_evento_na_agenda")
    print(f"Argumentos recebidos: titulo='{titulo}', data_hora='{data_hora_inicio_str}', duracao={duracao_minutos}")
    
    
    try:
        print("Obtendo serviço do Google Calendar...")
        service = get_permission_google_service("calendar","v3")
        print("Serviço obtido com sucesso!")

        print(f"Convertendo data: {data_hora_inicio_str}")
        dt_inicio = datetime.fromisoformat(data_hora_inicio_str)
        dt_fim = dt_inicio + timedelta(minutes=duracao_minutos)
        print(f"Evento: {dt_inicio} até {dt_fim}")

        event = {
            "summary": titulo,
            "start": {
                "dateTime": dt_inicio.isoformat(),
                "timeZone": "America/Sao_Paulo",
            },
            "end": {
                "dateTime": dt_fim.isoformat(),
                "timeZone": "America/Sao_Paulo",
            },
        }
        
        print(f"Criando evento: {event}")
        created_event = service.events().insert(calendarId="primary", body=event).execute()
        
        print(f"Evento criado: {created_event.get('htmlLink')}")
        return f"Evento '{titulo}' criado com sucesso! Link: {created_event.get('htmlLink')}"

    except Exception as e:
        print(f"ERRO na criação do evento: {e}")
        return f"Ocorreu um erro ao criar o evento: {e}"
    

def email_handler():
    """
    Lê e lista os 10 e-mails mais recentes da caixa de entrada (INBOX) do usuário autenticado no Gmail.

    Retorna:
        list | str: Uma lista com os assuntos (snippets) dos e-mails encontrados, ou uma mensagem de erro/caso não haja e-mails.

    Requisitos:
        - O arquivo 'credentials.json' deve estar presente para autenticação Google.
        - O usuário deve conceder permissão na primeira execução.
    """

    print(f"FERRAMENTA CHAMADA: listando emails")
    
    try:
        # Call the Gmail API
        service = get_permission_google_service("gmail","v1")
        results = (
            service.users().messages().list(userId="me", labelIds=["INBOX"], maxResults=10).execute()
        )
        messages = results.get("messages", [])

        if not messages:
            print("No messages found.")
            return "Nenhum e-mail encontrado na caixa de entrada."

        print("Messages:")
        subjects = []
        for message in messages:
            print(f'Message ID: {message["id"]}')
            msg = (
                service.users().messages().get(userId="me", id=message["id"]).execute()
            )
            snippet = msg.get("snippet", "(sem assunto)")
            print(f'  Subject: {snippet}')
            subjects.append(snippet)
        return subjects

    except HttpError as error:
        print(f"An error occurred: {error}")
        return f"Ocorreu um erro ao listar os e-mails: {error}"


def get_email_by_id(email_id):
    """
    Busca e retorna detalhes de um e-mail específico pelo ID na conta Gmail autenticada.

    Parâmetros:
        email_id (str): O ID do e-mail a ser buscado.
    Retorna:
        dict | str: Dicionário com informações do e-mail (assunto, remetente, data, snippet), ou mensagem de erro.
    Requisitos:
        - O arquivo 'credentials.json' deve estar presente para autenticação Google.
        - O usuário deve conceder permissão na primeira execução.
    """
    try:
        service = get_permission_google_service("gmail", "v1")
        msg = service.users().messages().get(userId="me", id=email_id, format="full").execute()
        headers = msg.get("payload", {}).get("headers", [])
        subject = next((h["value"] for h in headers if h["name"] == "Subject"), "(sem assunto)")
        from_ = next((h["value"] for h in headers if h["name"] == "From"), "(remetente desconhecido)")
        date = next((h["value"] for h in headers if h["name"] == "Date"), "(data desconhecida)")
        snippet = msg.get("snippet", "")
        return {
            "assunto": subject,
            "remetente": from_,
            "data": date,
            "snippet": snippet,
            "id": email_id
        }
    except Exception as e:
        print(f"Erro ao buscar e-mail por ID: {e}")
        return f"Ocorreu um erro ao buscar o e-mail: {e}"