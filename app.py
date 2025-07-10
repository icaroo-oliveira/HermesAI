import os
from dotenv import load_dotenv
import chainlit as cl

from tools import criar_evento_na_agenda

from langchain.agents import initialize_agent, AgentType
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.tools.render import render_text_description

#carregando variáveis de ambiente
load_dotenv()
hf_token = os.environ["HUGGINGFACEHUB_API_TOKEN"]


hf_llm = HuggingFaceEndpoint(
    repo_id="meta-llama/Meta-Llama-3-8B-Instruct",
    task="text-generation",
    max_new_tokens=512,
    do_sample=True,
    temperature=0.7,
    huggingfacehub_api_token=hf_token
)


llm = ChatHuggingFace(llm=hf_llm, verbose=True)

#tools 
tools = [criar_evento_na_agenda]
tool_desc = render_text_description(tools)

#prompt
custom_prompt = f"""Você é o Icarus, um assistente pessoal inteligente e amigável.

CAPACIDADES:
- Você tem acesso a ferramentas para ajudar o usuário
- Você pode agendar eventos na agenda do Google
- Você pode conversar naturalmente e responder perguntas

FERRAMENTAS DISPONÍVEIS:
{tool_desc}

COMO USAR A FERRAMENTA DE AGENDA:
Quando o usuário pedir para agendar algo, use a ferramenta criar_evento_na_agenda com:
- titulo: o título do evento
- data_hora_inicio_str: data e hora no formato ISO (ex: '2025-07-15T14:30:00-03:00')
- duracao_minutos: duração em minutos (opcional, padrão 60)

EXEMPLOS:
- "Agende uma reunião amanhã às 15h" → criar_evento_na_agenda(titulo="Reunião", data_hora_inicio_str="2025-07-11T15:00:00-03:00")
- "Marque consulta médica para sexta às 10h" → criar_evento_na_agenda(titulo="Consulta médica", data_hora_inicio_str="2025-07-11T10:00:00-03:00")

IMPORTANTE:
- Sempre converta datas relativas (hoje, amanhã, sexta) para datas específicas
- Use o fuso horário -03:00 (Brasil)
- Seja amigável e conversacional
- Se não souber a data exata, pergunte ao usuário

SOBRE CONFLITOS DE HORÁRIO:
- Se o usuário pedir para agendar em um horário que pode ter conflito, sugira horários alternativos
- Exemplos de sugestões: "Que tal às 16h em vez de 15h?" ou "Posso sugerir 14h ou 16h?"
- Se o usuário não especificar horário, sugira opções: "Que horário você prefere? Posso sugerir 10h, 14h ou 16h"

Agora responda ao usuário e use as ferramentas quando necessário!
"""

#agente com prompt customizado
agent_executor = initialize_agent(
    tools=tools,
    llm=llm,
    agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
    verbose=True,
    agent_kwargs={
        "prefix": custom_prompt
    }
)

#histórico por sessão
chat_histories = {}

@cl.on_chat_start
async def start():
    session = cl.user_session.get("id")
    chat_histories[session] = []
    await cl.Message(content="Olá! Sou Icarus, seu assistente pessoal. Posso ajudar com conversas e agendar eventos na sua agenda! Como posso ajudar?").send()

@cl.on_message
async def main(message: cl.Message):
    session = cl.user_session.get("id")
    hist = chat_histories.setdefault(session, [])

    #versão síncrona sem async
    result = agent_executor.run(input=message.content, chat_history=hist)

    #outra versao async usando asyncio_to_thread
    # from langchain.utilities.asyncio import asyncio_to_thread
    # result = await asyncio_to_thread(agent_executor.run, input=message.content, chat_history=hist)

    await cl.Message(content=result).send()

    hist.append({"role": "user", "content": message.content})
    hist.append({"role": "assistant", "content": result})
