import os.path
from typing import Any


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

def criar_evento_na_agenda(state: Any) -> Any:
    """
    Cria um evento no Google Calendar do usuário autenticado, usando os dados em state['agenda'].
    Atualiza o estado com a confirmação ou erro em state['invocation'].
    """
    print("[DEBUG] Entrando em criar_evento_na_agenda")
    try:
        data = state["agenda"]
        print(f"[DEBUG] Dados recebidos para agendamento: {data}")
        # --- Lógica original de criação de evento ---
        titulo = data.get('titulo', 'Evento')
        data_hora_inicio_str = data.get('data_hora_inicio_str', None)
        duracao_minutos = data.get('duracao_minutos', 60)
        print(f"FERRAMENTA CHAMADA: criar_evento_na_agenda")
        print(f"Argumentos recebidos: titulo='{titulo}', data_hora='{data_hora_inicio_str}', duracao={duracao_minutos}")
        from datetime import datetime, timedelta
        service = get_permission_google_service("calendar","v3")
        dt_inicio = datetime.fromisoformat(data_hora_inicio_str)
        dt_fim = dt_inicio + timedelta(minutes=duracao_minutos)
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
        print(f"[DEBUG] Evento a ser criado: {event}")
        created_event = service.events().insert(calendarId="primary", body=event).execute()
        resposta = f"Evento '{titulo}' criado com sucesso! Link: {created_event.get('htmlLink')}"
        print(f"[DEBUG] Evento criado com sucesso: {created_event.get('htmlLink')}")
        state["invocation"] = resposta
        print("[DEBUG] Saindo de criar_evento_na_agenda com sucesso")
        return state
    except Exception as e:
        resposta = f"Ocorreu um erro ao criar o evento: {e}"
        print(f"[DEBUG] ERRO em criar_evento_na_agenda: {e}")
        state["invocation"] = resposta
        return state
    

def email_handler(state: Any) -> Any:
    """
    Lê e lista os 10 e-mails mais recentes da caixa de entrada (INBOX) do usuário autenticado no Gmail.
    Atualiza o estado com os e-mails encontrados e a resposta para o usuário.
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
            resposta = "Nenhum e-mail encontrado na caixa de entrada."
            state["invocation"] = resposta
            return state

        print("Messages:")
        emails = []
        for message in messages:
            print(f'Message ID: {message["id"]}')
            msg = (
                service.users().messages().get(userId="me", id=message["id"]).execute()
            )
            snippet = msg.get("snippet", "(sem assunto)")
            remetente = "(remetente desconhecido)"  # Adapte se quiser extrair o remetente
            emails.append({"assunto": snippet, "remetente": remetente, "id": message["id"]})

        # Salva os e-mails no estado
        state["email"]["emails"] = emails
        # Formata a resposta para o usuário
        resposta = "Assuntos dos e-mails encontrados:\n" + "\n".join(f"- {e['assunto']}" for e in emails)
        state["invocation"] = resposta
        return state

    except HttpError as error:
        print(f"An error occurred: {error}")
        resposta = f"Ocorreu um erro ao listar os e-mails: {error}"
        state["invocation"] = resposta
        return state


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