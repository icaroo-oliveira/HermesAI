import os
from dotenv import load_dotenv
import chainlit as cl

from tools import criar_evento_na_agenda
from tools import email_handler
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
from typing import TypedDict, Optional, List, Dict, Any
from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, START, END
from utils import add_to_history

class AgendaData(TypedDict, total=False):
    titulo: Optional[str]
    data_hora_inicio_str: Optional[str]
    duracao_minutos: Optional[int]

class EmailData(TypedDict, total=False):
    emails: Optional[List[Dict[str, Any]]]
    email_selecionado: Optional[Dict[str, Any]]

class IcarusState(TypedDict):
    user_input: str  #texto do usuário
    decision: Optional[str]  #"AGENDAR", "EMAIL" ou "CONVERSAR"
    messages: List[Dict[str, Any]]  #Histórico de mensagens
    agenda: AgendaData  #dados de agendamento
    email: EmailData   #dados de e-mail
    invocation: Optional[Any]  #resultado da última ação


load_dotenv()
hf_token = os.environ["HUGGINGFACEHUB_API_TOKEN"]

#histórico por sessão
chat_histories = {}

hf_llm = HuggingFaceEndpoint(
    repo_id="meta-llama/Meta-Llama-3-8B-Instruct",
    task="text-generation",
    max_new_tokens=512,
    do_sample=True,
    temperature=0.7,
    huggingfacehub_api_token=hf_token
)


llm = ChatHuggingFace(llm=hf_llm, verbose=True)


#prompt para extrair informações do evento
extract_event_prompt = """
Extraia do texto abaixo as informações para agendar um evento na agenda do Google. Responda em JSON com as chaves: titulo, data_hora_inicio_str (formato ISO, ex: 2025-07-15T14:30:00-03:00), e duracao_minutos (opcional, padrão 60).

Exemplo de resposta:
{"titulo": "Reunião", "data_hora_inicio_str": "2025-07-11T15:00:00-03:00", "duracao_minutos": 60}

Texto: {mensagem_usuario}
"""


# Utilitário para invocar o LLM
async def llm_ask(prompt, hist=None):
    #se houver histórico, inclua no contexto
    if hist:
        context = ""
        for msg in hist:
            if msg["role"] == "user":
                context += f"Usuário: {msg['content']}\n"
            elif msg["role"] == "assistant":
                context += f"Assistente: {msg['content']}\n"
        prompt = context + "\n" + prompt
    response = llm.invoke([HumanMessage(content=prompt)])
    return response.content

#nó decisor
import re
async def decision_node(state: IcarusState) -> IcarusState:
    decision_prompt = """
Você é Icarus, um assistente pessoal inteligente. Sua tarefa é analisar a mensagem do usuário e decidir se ele está pedindo para AGENDAR um evento, LER EMAILS ou apenas deseja CONVERSAR normalmente.

REGRAS:
- Se a mensagem do usuário for um pedido explícito para criar, marcar, agendar, adicionar ou alterar um evento, reunião, compromisso, consulta, etc., responda apenas com: AGENDAR
- Se a mensagem pedir explicitamente para ler, mostrar, listar, acessar ou buscar e-mails, responda apenas com: EMAIL
- Se a mensagem for uma pergunta, comentário, pedido de tradução, explicação, resumo, ou qualquer referência a informações já apresentadas anteriormente (como “traduza o último e-mail retornado”, “explique o e-mail anterior”, “me mostre o corpo do e-mail listado”, etc.), responda apenas com: CONVERSAR
- Não acione a busca de e-mails ou agenda se o usuário estiver apenas conversando sobre resultados anteriores.
- Não explique sua resposta, apenas retorne AGENDAR, EMAIL ou CONVERSAR.

Exemplos:
Usuário: "Agende uma reunião amanhã às 15h"  
Resposta: AGENDAR

Usuário: "Quais são meus e-mails novos?"  
Resposta: EMAIL

Usuário: "Traduza o último e-mail retornado"  
Resposta: CONVERSAR

Usuário: "Me mostre o corpo do segundo e-mail da lista"  
Resposta: CONVERSAR

Usuário: "Oi, tudo bem?"  
Resposta: CONVERSAR

Mensagem do usuário: {mensagem_usuario}

Responda apenas com AGENDAR, EMAIL ou CONVERSAR.
""".replace('{mensagem_usuario}', state["user_input"])
    decision = (await llm_ask(decision_prompt, state["messages"])).strip().upper()
    decision = re.sub(r'[^A-Z]', '', decision)  # Remove tudo que não for letra maiúscula
    state["decision"] = decision
    return state

#nó de extração e agendamento
async def agendar_node(state: IcarusState) -> IcarusState:
    prompt = extract_event_prompt.replace('{mensagem_usuario}', state["user_input"])
    import json
    import re
    raw_response = await llm_ask(prompt, state["messages"])
    print('LLM retorno (extração de evento):', raw_response)
    json_str = None
    #tenta extrair entre ```json ... ```
    match = re.search(r'```json\s*(\{[\s\S]*?\})\s*```', raw_response)
    if match:
        json_str = match.group(1)
    else:
        #tenta extrair entre ``` ... ```
        match = re.search(r'```\s*(\{[\s\S]*?\})\s*```', raw_response)
        if match:
            json_str = match.group(1)
        else:
            #tenta extrair o primeiro objeto JSON
            match = re.search(r'(\{[\s\S]*?\})', raw_response)
            if match:
                json_str = match.group(1)
    try:
        if not json_str:
            raise ValueError('Nenhum JSON encontrado na resposta do LLM.')
        data = json.loads(json_str)
        print(data,"dados")
        state["agenda"] = data
        state = criar_evento_na_agenda(state)  # Chama a função no padrão do grafo
    except Exception as e:
        resposta = f"Não consegui extrair as informações do evento. Por favor, detalhe melhor. ({e})"
        state["invocation"] = resposta
    return state

#nó de conversa
async def conversa_node(state: IcarusState) -> IcarusState:
    resposta = await llm_ask(state["user_input"], state["messages"])
    state["invocation"] = resposta
    return state


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

    graph = StateGraph(IcarusState)

    #adiciona os nós
    graph.add_node("add_user_history", lambda state: add_to_history(state, "user", state["user_input"]))
    graph.add_node("decision_node", decision_node)
    graph.add_node("make_appointment", agendar_node)
    graph.add_node("email_handler", email_handler)  # Adapte para receber/retornar estado!
    graph.add_node("conversa_node", conversa_node)
    graph.add_node("add_assistant_history", lambda state: add_to_history(state, "assistant", state["invocation"]))

    #ddges
    graph.add_edge(START, "add_user_history")
    graph.add_edge("add_user_history", "decision_node")

    #decisão dinâmica baseada no estado
    def decision_router(state: IcarusState):
        return state["decision"]

    graph.add_conditional_edges(
        "decision_node",
        decision_router,
        {
            "AGENDAR": "make_appointment",
            "EMAIL": "email_handler",
            "CONVERSAR": "conversa_node"
        }
    )

    #após a resposta, salva no histórico do assistente/tool
    graph.add_edge("make_appointment", "add_assistant_history")
    graph.add_edge("email_handler", "add_assistant_history")
    graph.add_edge("conversa_node", "add_assistant_history")

    #fim
    graph.add_edge("add_assistant_history", END)

    #compile o graph
    compiled_graph = graph.compile()

    chat_histories[session + "_graph"] = compiled_graph

    await cl.Message(content="Olá! Sou Icarus, seu assistente pessoal. Posso ajudar com conversas, agendar eventos na sua agenda e ler seus e-mails do Gmail! Como posso ajudar?").send()



#handler principal
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
    

    
