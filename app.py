import chainlit as cl
from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import Tool
import os
from dotenv import load_dotenv 

load_dotenv() 


#MODELO
MODELO_ESCOLHIDO = "GEMINI"


openai_api_key = os.environ.get("OPENAI_API_KEY")
google_api_key = os.environ.get("GOOGLE_API_KEY")


if MODELO_ESCOLHIDO == "OPENAI":
    from langchain_openai import ChatOpenAI
    print("Usando o modelo da OpenAI (GPT)")
    llm = ChatOpenAI(model="gpt-4o", temperature=0, api_key=openai_api_key) # Passamos a chave aqui
elif MODELO_ESCOLHIDO == "GEMINI":
    from langchain_google_genai import ChatGoogleGenerativeAI
    print("Usando o modelo do Google (Gemini)")
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro-latest", temperature=0, google_api_key=google_api_key, convert_system_message_to_human=True) # E aqui
else:
    raise ValueError("Modelo não suportado. Escolha 'OPENAI' ou 'GEMINI'.")


#(TOOLS)
tools = [
    Tool(
        name="ferramenta_exemplo",
        func=lambda x: "Esta é uma ferramenta de exemplo. Ainda não sei fazer nada.",
        description="Uma ferramenta de exemplo que não faz nada útil ainda.",
    )
]

#PROMPT DO AGENTE v1
prompt_template = """
Você é um assistente pessoal. Responda ao usuário da melhor forma possível.
Você tem acesso às seguintes ferramentas:
{tools}
Use o seguinte formato:
Pergunta: a pergunta de entrada que você deve responder
Pensamento: você deve sempre pensar sobre o que fazer
Ação: a ação a ser tomada, deve ser uma das [{tool_names}]
Entrada da Ação: a entrada para a ação
Observação: o resultado da ação
... (este Pensamento/Ação/Entrada da Ação/Observação pode se repetir N vezes)
Pensamento: Agora eu sei a resposta final
Resposta Final: a resposta final para a pergunta original
Comece!
Pergunta: {input}
Pensamento: {agent_scratchpad}
"""
prompt = ChatPromptTemplate.from_template(prompt_template)


@cl.on_chat_start
async def start():
    agent = create_react_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        handle_parsing_errors=True,
    )
    cl.user_session.set("agent_executor", agent_executor)
    await cl.Message(content=f"Olá! Sou seu assistente pessoal, usando o modelo {MODELO_ESCOLHIDO}. Como posso ajudar?").send()


@cl.on_message
async def main(message: cl.Message):
    agent_executor = cl.user_session.get("agent_executor")
    cb = cl.LangchainCallbackHandler(stream_final_answer=True)
    await agent_executor.ainvoke(
        {"input": message.content},
        callbacks=[cb]
    )