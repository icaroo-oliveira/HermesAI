import os
from dotenv import load_dotenv
import chainlit as cl

from tools import criar_evento_na_agenda

from langchain.agents import initialize_agent, AgentType
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from typing import TypedDict, Optional, List, Dict, Any
from langchain_core.messages import HumanMessage

class AgendaState(TypedDict):
    user_input: str  # Texto enviado pelo usuário
    decision: Optional[str]  # "AGENDAR" ou "RESPONDER"
    titulo_evento: Optional[str]  # Título extraído ou definido para o evento
    data_hora_evento: Optional[str]  # Data/hora no formato ISO
    duracao_minutos: Optional[int]  # Duração do evento (padrão: 60)
    invocation: Optional[Any]  # Resultado da ação (resposta ou agendamento)
    messages: List[Dict[str, Any]]  # Histórico de mensagens usadas pelo LLM


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


# Prompt para extrair informações do evento
extract_event_prompt = """
Extraia do texto abaixo as informações para agendar um evento na agenda do Google. Responda em JSON com as chaves: titulo, data_hora_inicio_str (formato ISO, ex: 2025-07-15T14:30:00-03:00), e duracao_minutos (opcional, padrão 60).

Exemplo de resposta:
{"titulo": "Reunião", "data_hora_inicio_str": "2025-07-11T15:00:00-03:00", "duracao_minutos": 60}

Texto: {mensagem_usuario}
"""

# Utilitário para histórico

def add_to_history(hist, role, content):
    hist.append({"role": role, "content": content})

# Utilitário para invocar o LLM
async def llm_ask(prompt, hist=None):
    # Se houver histórico, inclua no contexto
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

# Nó decisor
async def decision_node(message, hist=None):
    decision_prompt = """
Você é Icarus, um assistente pessoal inteligente. Sua tarefa é analisar a mensagem do usuário e decidir se ele está pedindo para AGENDAR um evento, LER EMAILS ou apenas deseja CONVERSAR normalmente, essa etapa da conversa pode envolver o uma ação anterior (tipo AGENDAR ou LER EMAILS)

REGRAS:
- Se a mensagem do usuário for um pedido para criar, marcar, agendar, adicionar ou alterar um evento, reunião, compromisso, consulta, etc., responda apenas com: AGENDAR
- Se a mensagem pedir para ler, mostrar, listar, acessar ou buscar e-mails, responda apenas com: EMAIL
- Se a mensagem for apenas uma pergunta, conversa, saudação ou qualquer outro assunto que NÃO envolva o **PEDIDO EXPLICITO** de agendamento ou leitura de e-mails, responda apenas com: CONVERSAR. - Tenha discernimento, por que o usuário pode se referir a suas respostas anteriores (por exemplo a respeito de e-mail ou agenda) mas não necessariamente está lhe pedindo especificamente pra fazer uma ação
- Não explique sua resposta, apenas retorne AGENDAR, EMAIL ou CONVERSAR.

Exemplos:
Usuário: "Agende uma reunião amanhã às 15h"  
Resposta: AGENDAR

Usuário: "Quais são meus e-mails novos?"  
Resposta: EMAIL

Usuário: "Oi, tudo bem?"  
Resposta: CONVERSAR

Usuário: "À respeito dos e-mails que você listou, qual a gravidade do primeiro e-mail que da lista?"  
Resposta: CONVERSAR

Mensagem do usuário: {mensagem_usuario}

Responda apenas com AGENDAR, EMAIL ou CONVERSAR.
""".replace('{mensagem_usuario}', message.content)
    return (await llm_ask(decision_prompt, hist)).strip().upper()

# Nó de extração e agendamento
async def agendar_node(message):
    prompt = extract_event_prompt.replace('{mensagem_usuario}', message.content)
    import json
    import re
    raw_response = await llm_ask(prompt)
    print('LLM retorno (extração de evento):', raw_response)
    # Extrair JSON de bloco markdown ou texto
    json_str = None
    # Tenta extrair entre ```json ... ```
    match = re.search(r'```json\s*(\{[\s\S]*?\})\s*```', raw_response)
    if match:
        json_str = match.group(1)
    else:
        # Tenta extrair entre ``` ... ```
        match = re.search(r'```\s*(\{[\s\S]*?\})\s*```', raw_response)
        if match:
            json_str = match.group(1)
        else:
            # Tenta extrair o primeiro objeto JSON
            match = re.search(r'(\{[\s\S]*?\})', raw_response)
            if match:
                json_str = match.group(1)
    try:
        if not json_str:
            raise ValueError('Nenhum JSON encontrado na resposta do LLM.')
        data = json.loads(json_str)
        print(data,"dados")
        # titulo = data.get('titulo', 'Evento')
        # data_hora = data.get('data_hora_inicio_str', None)
        # duracao = data.get('duracao_minutos', 60)
        # if not data_hora:
        #     return "Não consegui identificar a data/hora do evento. Por favor, especifique!"
        # print('aqui')
        criar_evento_na_agenda(data)
        resposta = f"Evento '{data.get('titulo')}' agendado para {data.get('data_hora_inicio_str')}!"
    except Exception as e:
        resposta = f"Não consegui extrair as informações do evento. Por favor, detalhe melhor. ({e})"
    return resposta

# Nó de conversa
async def conversa_node(message, hist=None):
    return await llm_ask(message.content, hist)


@cl.on_chat_start
async def start():
    session = cl.user_session.get("id")
    chat_histories[session] = []
    await cl.Message(content="Olá! Sou Icarus, seu assistente pessoal. Posso ajudar com conversas, agendar eventos na sua agenda e ler seus e-mails do Gmail! Como posso ajudar?").send()

# Handler principal
@cl.on_message
async def main(message: cl.Message):
    session = cl.user_session.get("id")
    hist = chat_histories.setdefault(session, [])
    add_to_history(hist, "user", message.content)
    decision = await decision_node(message, hist)

    if decision == "AGENDAR":
        resposta = await agendar_node(message)
    elif decision == "EMAIL":
        from tools import email_handler
        resposta = email_handler()
        if isinstance(resposta, list):
            if resposta:
                resposta = "Assuntos dos e-mails encontrados:\n" + "\n".join(f"- {s}" for s in resposta)
                add_to_history(hist, "assistant",resposta)
            else:
                resposta = "Nenhum e-mail encontrado na caixa de entrada."
    else:
        resposta = await conversa_node(message, hist)
    add_to_history(hist, "assistant", resposta)
    await cl.Message(content=resposta).send()
    

    
