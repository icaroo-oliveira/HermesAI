import os.path
from datetime import datetime, timedelta
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from typing import Any

SCOPES = ["https://www.googleapis.com/auth/calendar","https://www.googleapis.com/auth/gmail.readonly"]

def get_permission_google_service(tool_type,version):
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

def criar_evento_na_agenda(state: Any) -> Any:
    try:
        data = state["agenda"]
        titulo = data.get('titulo', 'Evento')
        data_hora_inicio_str = data.get('data_hora_inicio_str', None)
        duracao_minutos = data.get('duracao_minutos', 60)
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
        created_event = service.events().insert(calendarId="primary", body=event).execute()
        resposta = f"Evento '{titulo}' criado com sucesso! Link: {created_event.get('htmlLink')}"
        resposta = resposta.strip()
        state["invocation"] = resposta
        state["invocations_list"].append(resposta)
        return state
    except Exception as e:
        resposta = f"Erro ao criar evento: {e}"
        state["invocation"] = resposta
        state["invocations_list"].append(resposta)
        return state

def buscar_eventos_no_intervalo(state, inicio: datetime, fim: datetime):
    try:
        service = get_permission_google_service("calendar", "v3")
        time_min = inicio.strftime('%Y-%m-%dT%H:%M:%S-03:00')
        time_max = fim.strftime('%Y-%m-%dT%H:%M:%S-03:00')
        events_result = service.events().list(
            calendarId="primary",
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime"
        ).execute()
        eventos = events_result.get("items", [])
        return eventos
    except Exception as e:
        return []

def existe_conflito_agenda(state, inicio: datetime, fim: datetime):
    eventos = buscar_eventos_no_intervalo(state, inicio, fim)
    return len(eventos) > 0

def listar_eventos_periodo(state, data_inicial, data_final=None):
    if data_final is None:
        data_final = data_inicial + timedelta(days=1)
    eventos = buscar_eventos_no_intervalo(state, data_inicial, data_final)
    if not eventos:
        resposta = f"Você não tem compromissos para o período solicitado."
    else:
        resposta = f"Seus compromissos de {data_inicial.strftime('%d/%m/%Y')} até {data_final.strftime('%d/%m/%Y')}:\n"
        for ev in eventos:
            hora = ev.get('start', {}).get('dateTime', '')
            resumo = ev.get('summary', '(sem título)')
            resposta += f"- {resumo} às {hora}\n"
    resposta = resposta.strip()
    state['invocation'] = resposta
    state['invocations_list'].append(resposta)
    return state 