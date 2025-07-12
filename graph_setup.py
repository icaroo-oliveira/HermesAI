from langgraph.graph import StateGraph, START, END
from utils import add_to_history
from tools import criar_evento_na_agenda, email_handler, listar_eventos_periodo, existe_conflito_agenda
from llm_utils import llm_ask, extract_event_prompt
from typing import Any
import re
from date_extractor import extrair_datas_periodo_llm

# Nó decisor
async def decision_node(state: Any) -> Any:
    decision_prompt = """
Você é Icarus, um assistente pessoal inteligente. Sua tarefa é analisar a mensagem do usuário e decidir se ele está pedindo para AGENDAR um evento, LER EMAILS, LISTAR EVENTOS/COMPROMISSOS ou apenas deseja CONVERSAR normalmente.

REGRAS:
- Se a mensagem do usuário for um pedido explícito para criar, marcar, agendar, adicionar ou alterar um evento, reunião, compromisso, consulta, etc., responda apenas com: AGENDAR
- Se a mensagem pedir explicitamente para ler, mostrar, listar, acessar ou buscar e-mails, responda apenas com: EMAIL
- Se a mensagem pedir para listar, mostrar, exibir, consultar, ver, saber, ou perguntar sobre compromissos, eventos, agenda, reuniões já marcadas, responda apenas com: LISTAR_EVENTOS
- Se a mensagem for uma pergunta, comentário, pedido de tradução, explicação, resumo, ou qualquer referência a informações já apresentadas anteriormente, responda apenas com: CONVERSAR
- Não explique sua resposta, apenas retorne AGENDAR, EMAIL, LISTAR_EVENTOS ou CONVERSAR.

Exemplos:
Usuário: "Agende uma reunião amanhã às 15h"
Resposta: AGENDAR

Usuário: "Quais são meus e-mails novos?"
Resposta: EMAIL

Usuário: "Liste meus compromissos de hoje"
Resposta: LISTAR_EVENTOS

Usuário: "O que tenho na agenda amanhã?"
Resposta: LISTAR_EVENTOS

Usuário: "Traduza o último e-mail retornado"
Resposta: CONVERSAR

Usuário: "Oi, tudo bem?"
Resposta: CONVERSAR

Mensagem do usuário: {mensagem_usuario}

Responda apenas com AGENDAR, EMAIL, LISTAR_EVENTOS ou CONVERSAR.
""".replace('{mensagem_usuario}', state["user_input"])
    decision = (await llm_ask(decision_prompt, state["messages"])).strip().upper()
    decision = re.sub(r'[^A-Z_]', '', decision)
    state["decision"] = decision
    return state

# Nó de extração e agendamento
def make_agendar_node():
    from datetime import datetime, timedelta
    async def agendar_node(state: Any) -> Any:
        try:
            data = state["agenda"]
            # Compatibiliza campos vindos do LLM
            if "data_inicial" in data and "data_hora_inicio_str" not in data:
                data["data_hora_inicio_str"] = data["data_inicial"]
            if "duracao_minutos" not in data:
                data["duracao_minutos"] = 60
            if "titulo" not in data:
                data["titulo"] = "Evento"
            state["agenda"] = data
            print(data, "dados")
            # Verificação de conflito
            dt_inicio = datetime.fromisoformat(data['data_hora_inicio_str'])
            duracao = data.get('duracao_minutos', 60)
            dt_fim = dt_inicio + timedelta(minutes=duracao)
            if existe_conflito_agenda(state, dt_inicio, dt_fim):
                state["invocation"] = "Já existe um compromisso nesse horário. Por favor, escolha outro horário."
            else:
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


def make_listar_eventos_periodo_node():
    from datetime import datetime, timedelta
    def parse_datas(state):
        # espera que state['agenda'] tenha 'data_inicial' e (opcional) 'data_final' como string ISO
        data_inicial_str = state.get('agenda', {}).get('data_inicial')
        data_final_str = state.get('agenda', {}).get('data_final')
        if data_inicial_str:
            data_inicial = datetime.fromisoformat(data_inicial_str)
        else:
            data_inicial = datetime.now()
        if data_final_str:
            data_final = datetime.fromisoformat(data_final_str)
        else:
            data_final = None
        return data_inicial, data_final

    def node(state):
        data_inicial, data_final = parse_datas(state)
        return listar_eventos_periodo(state, data_inicial, data_final)
    return node


async def extrair_datas_agendamento_llm_node(state):
    # Pode customizar o prompt se quiser, mas por padrão usa extrair_datas_periodo_llm
    return await extrair_datas_periodo_llm(state)

async def extrair_datas_listagem_llm_node(state):
    return await extrair_datas_periodo_llm(state)


def build_graph(IcarusState):
    graph = StateGraph(IcarusState)
    graph.add_node("add_user_history", lambda state: add_to_history(state, "user", state["user_input"]))
    graph.add_node("decision_node", decision_node)
    graph.add_node("make_appointment", make_agendar_node())
    graph.add_node("email_handler", email_handler)
    graph.add_node("conversa_node", conversa_node)
    graph.add_node("listar_eventos_periodo_node", make_listar_eventos_periodo_node())
    graph.add_node("extrair_datas_agendamento_llm_node", extrair_datas_agendamento_llm_node)
    graph.add_node("extrair_datas_listagem_llm_node", extrair_datas_listagem_llm_node)
    graph.add_node("add_assistant_history", lambda state: add_to_history(state, "assistant", state["invocation"]))
    graph.add_edge(START, "add_user_history")
    graph.add_edge("add_user_history", "decision_node")
    # Adapte o roteamento condicional para reconhecer 'LISTAR_EVENTOS'
    def decision_router(state):
        return state["decision"]
    # Adapte o roteamento condicional para que AGENDAR passe por extrair_datas_periodo_llm_node
    graph.add_conditional_edges(
        "decision_node",
        decision_router,
        {
            "AGENDAR": "extrair_datas_agendamento_llm_node",
            "EMAIL": "email_handler",
            "CONVERSAR": "conversa_node",
            "LISTAR_EVENTOS": "extrair_datas_listagem_llm_node"
        }
    )
    # AGENDAR: extrair_datas_agendamento_llm_node -> make_appointment -> add_assistant_history
    graph.add_edge("extrair_datas_agendamento_llm_node", "make_appointment")
    graph.add_edge("make_appointment", "add_assistant_history")
    # LISTAR_EVENTOS: extrair_datas_listagem_llm_node -> listar_eventos_periodo_node -> add_assistant_history
    graph.add_edge("extrair_datas_listagem_llm_node", "listar_eventos_periodo_node")
    graph.add_edge("listar_eventos_periodo_node", "add_assistant_history")
    graph.add_edge("email_handler", "add_assistant_history")
    graph.add_edge("conversa_node", "add_assistant_history")
    graph.add_edge("add_assistant_history", END)
    compiled_graph = graph.compile()
    return compiled_graph 