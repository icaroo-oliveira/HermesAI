from langchain_core.messages import HumanMessage
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
import os
from dotenv import load_dotenv
from faiss_memory.memory import long_term_memory

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

async def llm_ask(prompt, hist=None, store_in_memory=True, user_input=None):
    """
    Faz uma pergunta ao LLM com suporte à memória de longo prazo
    
    Args:
        prompt: O prompt para enviar ao LLM
        hist: Histórico de conversa (opcional)
        store_in_memory: Se deve armazenar na memória de longo prazo
        user_input: Entrada original do usuário (para armazenar na memória)
    """
    # Recupera contexto relevante da memória de longo prazo
    long_term_context = ""
    if user_input:
        long_term_context = long_term_memory.get_conversation_context(user_input)
        print(f"[DEBUG] Contexto recuperado para '{user_input}': {len(long_term_context)} chars")
        if long_term_context:
            print(f"[DEBUG] Contexto: {long_term_context[:300]}...")
    
    # Prepara o contexto completo
    context = ""
    
    # Adiciona contexto de longo prazo se disponível
    if long_term_context:
        context += f"Contexto de conversas anteriores:\n{long_term_context}\n\n"
    
    # Adiciona histórico recente se disponível
    if hist:
        for msg in hist:
            if msg["role"] == "user":
                context += f"Usuário: {msg['content']}\n"
            elif msg["role"] == "assistant":
                context += f"Assistente: {msg['content']}\n"
    
    # Combina o contexto com o prompt de forma mais clara
    if context:
        full_prompt = f"""
{context}

INSTRUÇÃO: Use as informações das conversas anteriores acima para responder à pergunta abaixo.

PERGUNTA: {prompt}

IMPORTANTE: Se a pergunta for sobre algo mencionado nas conversas anteriores, use essas informações. Se não souber, seja honesto.
"""
    else:
        full_prompt = prompt
    
    # Faz a chamada ao LLM
    response = llm.invoke([HumanMessage(content=full_prompt)])
    response_content = response.content
    
    # Armazena na memória de longo prazo se solicitado
    if store_in_memory and user_input:
        try:
            long_term_memory.store_conversation(
                user_input=user_input,
                assistant_response=response_content,
                context=context if context else None
            )
        except Exception as e:
            print(f"Erro ao armazenar na memória: {e}")
    
    return response_content

async def llm_ask_with_memory(prompt, user_input, hist=None):
    """
    Versão simplificada que sempre usa memória
    """
    return await llm_ask(prompt, hist, store_in_memory=True, user_input=user_input) 