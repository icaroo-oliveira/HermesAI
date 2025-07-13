import os
from dotenv import load_dotenv
import chainlit as cl
from typing import TypedDict, Optional, List, Dict, Any
from graph.graph_setup import build_graph
from tools.weather import obter_previsao_tempo_weatherapi
from graph.state_types import IcarusState

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
        "invocations_list": [],
    }
    chat_histories[session] = initial_state
    compiled_graph = build_graph(IcarusState)
    chat_histories[session + "_graph"] = compiled_graph
    previsao = obter_previsao_tempo_weatherapi()
    mensagem_inicial = (
        "Olá! Sou Icarus, seu assistente pessoal. Posso ajudar com conversas, agendar eventos na sua agenda e ler seus e-mails do Gmail! Como posso ajudar?\n\n" + previsao
    )
    await cl.Message(content=mensagem_inicial).send()

@cl.on_message
async def main(message: cl.Message):
    session = cl.user_session.get("id")
    state = chat_histories.get(session)
    compiled_graph = chat_histories.get(session + "_graph")
    state["user_input"] = message.content
    # Limpa a lista de respostas antes de processar nova mensagem
    state["invocations_list"] = []
    result_state = await compiled_graph.ainvoke(state)
    chat_histories[session] = result_state
    respostas = result_state.get("invocations_list", [])
    resposta_final = "\n\n".join(respostas) if respostas else result_state.get("invocation", "")
    await cl.Message(content=resposta_final).send()
    

    
