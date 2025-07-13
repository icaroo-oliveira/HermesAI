import os
from dotenv import load_dotenv
import chainlit as cl
from typing import TypedDict, Optional, List, Dict, Any
from graph.graph_setup import build_graph
from tools.weather import obter_previsao_tempo_weatherapi
from graph.state_types import IcarusState
from tools.email import send_email

load_dotenv()

#histórico por sessão
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

@cl.action_callback("send_email")
async def on_send_email(action):
    session = cl.user_session.get("id")
    state = chat_histories.get(session)
    
    if state and state.get("email", {}).get("pending_email"):
        pending_email = state["email"]["pending_email"]
        
        #envia o eail
        result = send_email(
            to_email=pending_email['to_email'],
            subject=pending_email['subject'],
            body=pending_email['body'],
            cc=pending_email.get('cc'),
            bcc=pending_email.get('bcc')
        )
        
        if result['success']:
            await cl.Message(
                content=f"✅ {result['message']}\n\nPara: {pending_email['to_email']}\nAssunto: {pending_email['subject']}"
            ).send()
        else:
            await cl.Message(content=f"❌ {result['message']}").send()
        
        #remove o email pendente
        state["email"].pop("pending_email", None)
        chat_histories[session] = state
    else:
        await cl.Message(content="❌ Não há e-mail pendente para enviar.").send()

@cl.action_callback("cancel_email")
async def on_cancel_email(action):
    session = cl.user_session.get("id")
    state = chat_histories.get(session)
    
    if state and state.get("email", {}).get("pending_email"):
        #remove o email pendente
        state["email"].pop("pending_email", None)
        chat_histories[session] = state
        await cl.Message(content="❌ Envio de e-mail cancelado.").send()
    else:
        await cl.Message(content="❌ Não há e-mail pendente para cancelar.").send()
    

    
