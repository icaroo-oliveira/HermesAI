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