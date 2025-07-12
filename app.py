import os
from dotenv import load_dotenv
import chainlit as cl
from typing import TypedDict, Optional, List, Dict, Any
from graph_setup import build_graph

class AgendaData(TypedDict, total=False):
    titulo: Optional[str]
    data_hora_inicio_str: Optional[str]
    duracao_minutos: Optional[int]

class EmailData(TypedDict, total=False):
    emails: Optional[List[Dict[str, Any]]]
    email_selecionado: Optional[Dict[str, Any]]

class IcarusState(TypedDict):
    user_input: str  # Texto enviado pelo usuário
    decision: Optional[str]  # "AGENDAR", "EMAIL" ou "CONVERSAR"
    messages: List[Dict[str, Any]]  # Histórico de mensagens
    agenda: AgendaData  # Dados de agendamento
    email: EmailData   # Dados de e-mail
    invocation: Optional[Any]  # Resultado da última ação

load_dotenv()

# histórico por sessão
chat_histories = {}

@cl.on_chat_start
async def start():
    session = cl.user_session.get("id")
    initial_state = {
        "user_input": "",
        "decision": None,
        "messages": [],
        "agenda": {},
        "email": {},
        "invocation": None,
    }
    chat_histories[session] = initial_state
    compiled_graph = build_graph(IcarusState)
    chat_histories[session + "_graph"] = compiled_graph
    await cl.Message(content="Olá! Sou Icarus, seu assistente pessoal. Posso ajudar com conversas, agendar eventos na sua agenda e ler seus e-mails do Gmail! Como posso ajudar?").send()

@cl.on_message
async def main(message: cl.Message):
    session = cl.user_session.get("id")
    state = chat_histories.get(session)
    compiled_graph = chat_histories.get(session + "_graph")
    state["user_input"] = message.content
    result_state = await compiled_graph.ainvoke(state)
    chat_histories[session] = result_state
    resposta = result_state["invocation"]
    await cl.Message(content=resposta).send()
    

    
