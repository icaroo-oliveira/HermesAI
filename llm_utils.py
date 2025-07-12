from langchain_core.messages import HumanMessage
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
import os
from dotenv import load_dotenv

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

extract_event_prompt = """
Extraia do texto abaixo as informações para agendar um evento na agenda do Google. Responda em JSON com as chaves: titulo, data_hora_inicio_str (formato ISO, ex: 2025-07-15T14:30:00-03:00), e duracao_minutos (opcional, padrão 60).

Exemplo de resposta:
{"titulo": "Reunião", "data_hora_inicio_str": "2025-07-11T15:00:00-03:00", "duracao_minutos": 60}

Texto: {mensagem_usuario}
"""

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