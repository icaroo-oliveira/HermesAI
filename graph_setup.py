from langgraph.graph import StateGraph, START, END
from utils import add_to_history
from tools import criar_evento_na_agenda, email_handler
from llm_utils import llm_ask, extract_event_prompt
from typing import Any
import re

# Nó decisor
async def decision_node(state: Any) -> Any:
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
    decision = re.sub(r'[^A-Z]', '', decision)
    state["decision"] = decision
    return state

# Nó de extração e agendamento
def make_agendar_node():
    async def agendar_node(state: Any) -> Any:
        prompt = extract_event_prompt.replace('{mensagem_usuario}', state["user_input"])
        import json
        raw_response = await llm_ask(prompt, state["messages"])
        print('LLM retorno (extração de evento):', raw_response)
        json_str = None
        import re
        match = re.search(r'```json\s*(\{[\s\S]*?\})\s*```', raw_response)
        if match:
            json_str = match.group(1)
        else:
            match = re.search(r'```\s*(\{[\s\S]*?\})\s*```', raw_response)
            if match:
                json_str = match.group(1)
            else:
                match = re.search(r'(\{[\s\S]*?\})', raw_response)
                if match:
                    json_str = match.group(1)
        try:
            if not json_str:
                raise ValueError('Nenhum JSON encontrado na resposta do LLM.')
            data = json.loads(json_str)
            print(data,"dados")
            state["agenda"] = data
            state = criar_evento_na_agenda(state)
        except Exception as e:
            resposta = f"Não consegui extrair as informações do evento. Por favor, detalhe melhor. ({e})"
            state["invocation"] = resposta
        return state
    return agendar_node

# Nó de conversa
async def conversa_node(state: Any) -> Any:
    resposta = await llm_ask(state["user_input"], state["messages"])
    state["invocation"] = resposta
    return state


def build_graph(IcarusState):
    graph = StateGraph(IcarusState)
    graph.add_node("add_user_history", lambda state: add_to_history(state, "user", state["user_input"]))
    graph.add_node("decision_node", decision_node)
    graph.add_node("make_appointment", make_agendar_node())
    graph.add_node("email_handler", email_handler)
    graph.add_node("conversa_node", conversa_node)
    graph.add_node("add_assistant_history", lambda state: add_to_history(state, "assistant", state["invocation"]))
    graph.add_edge(START, "add_user_history")
    graph.add_edge("add_user_history", "decision_node")
    def decision_router(state):
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
    graph.add_edge("make_appointment", "add_assistant_history")
    graph.add_edge("email_handler", "add_assistant_history")
    graph.add_edge("conversa_node", "add_assistant_history")
    graph.add_edge("add_assistant_history", END)
    compiled_graph = graph.compile()
    return compiled_graph 