import os.path
from datetime import datetime, timedelta

from langchain.tools import tool

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


SCOPES = ["https://www.googleapis.com/auth/calendar"]

def get_calendar_service():
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

    return build("calendar", "v3", credentials=creds)


@tool
def criar_evento_na_agenda(titulo: str, data_hora_inicio_str: str, duracao_minutos: int = 60):
    """
    Cria um evento na agenda do Google. Use esta ferramenta para agendar compromissos.
    Argumentos:
        titulo (str): O título do evento.
        data_hora_inicio_str (str): A data e hora de início no formato ISO, ex: '2025-07-10T10:00:00-03:00'.
        duracao_minutos (int): A duração do evento em minutos. O padrão é 60.
    Retorna:
        str: Uma mensagem de confirmação com o link do evento ou uma mensagem de erro.
    """
    print(f"FERRAMENTA CHAMADA: criar_evento_na_agenda")
    print(f"Argumentos recebidos: titulo='{titulo}', data_hora='{data_hora_inicio_str}', duracao={duracao_minutos}")
    
    try:
        print("Obtendo serviço do Google Calendar...")
        service = get_calendar_service()
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