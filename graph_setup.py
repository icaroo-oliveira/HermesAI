from langgraph.graph import StateGraph, START, END
from utils import add_to_history,buscar_na_web_duckduckgo
from tools import criar_evento_na_agenda, email_handler, listar_eventos_periodo, existe_conflito_agenda
from llm_utils import llm_ask, extract_event_prompt
from typing import Any
import re
from date_extractor import extrair_datas_periodo_llm
from state_types import IcarusState


# Nó decisor
# Nó decisor com múltiplas intenções
async def decision_node(state: Any) -> Any:
    decision_prompt = """
Você é Icarus, um assistente pessoal inteligente. Sua tarefa é analisar a mensagem do usuário e retornar uma ou mais das seguintes ações que precisam ser realizadas:

- AGENDAR → quando o usuário deseja marcar, adicionar ou alterar um compromisso, evento ou reunião
- EMAIL → quando o usuário pede para ler, buscar ou listar e-mails
- LISTAR_EVENTOS → quando o usuário quer saber o que está na agenda ou ver eventos futuros/passados
- BUSCAR_WEB → quando o usuário quer informações externas, como notícias, fatos ou pesquisas gerais
- CONVERSAR → quando o usuário está apenas conversando, pedindo explicações, traduções ou interagindo sem nenhuma ação específica

REGRAS:
- Retorne uma lista separada por vírgulas com as ações detectadas, em letras maiúsculas.
- Não explique sua resposta.
- Retorne apenas combinações válidas dessas palavras (máximo 3).

Exemplos:

Usuário: "Me diga quando o Flamengo joga e marque uma reunião às 15h amanhã"
Resposta: BUSCAR_WEB, AGENDAR

Usuário: "Liste meus compromissos de hoje e mostre meus e-mails"
Resposta: LISTAR_EVENTOS, EMAIL

Usuário: "Quero agendar uma reunião"
Resposta: AGENDAR

Usuário: "Oi, tudo bem?"
Resposta: CONVERSAR

Usuário: "Traduza esse texto e me diga quem é o presidente do Brasil"
Resposta: CONVERSAR, BUSCAR_WEB

Mensagem do usuário: {mensagem_usuario}

Responda apenas com uma lista separada por vírgulas: AGENDAR, EMAIL, LISTAR_EVENTOS, BUSCAR_WEB, CONVERSAR.
""".replace('{mensagem_usuario}', state["user_input"])

    #faz a chamada ao LLM
    resposta = (await llm_ask(decision_prompt, state["messages"])).strip().upper()

    #limpa e extrai as decisões
    decisoes = [d.strip() for d in re.split(r'[,\n]+', resposta) if d.strip() in {
        "AGENDAR", "EMAIL", "LISTAR_EVENTOS", "BUSCAR_WEB", "CONVERSAR"
    }]

    #atualiza o estado
    state["decisions"] = decisoes

    print(state)
    return state




async def executar_acoes_em_ordem(state: IcarusState) -> IcarusState:
    print(state)
    decisions = state.get("decisions", [])
    print(f"[executar_acoes_em_ordem] decisions: {decisions}, current_action: {state.get('current_action')}")
    if decisions:
        next_action = decisions.pop(0)
        state["current_action"] = next_action
        state["decisions"] = decisions
    else:
        state["current_action"] = None
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
    graph.add_node("executar_acoes_em_ordem", executar_acoes_em_ordem)
    graph.add_node("make_appointment", make_agendar_node())
    graph.add_node("email_handler", email_handler)
    graph.add_node("conversa_node", conversa_node)
    graph.add_node("listar_eventos_periodo_node", make_listar_eventos_periodo_node())
    graph.add_node("extrair_datas_agendamento_llm_node", extrair_datas_agendamento_llm_node)
    graph.add_node("extrair_datas_listagem_llm_node", extrair_datas_listagem_llm_node)
    graph.add_node("add_assistant_history", lambda state: add_to_history(state, "assistant", state["invocation"]))

    
    graph.add_node("buscar_internet", buscar_na_web_duckduckgo)



    graph.add_edge(START, "add_user_history")
    graph.add_edge("add_user_history", "decision_node")
    graph.add_edge("decision_node", "executar_acoes_em_ordem")

    graph.add_conditional_edges(
        "executar_acoes_em_ordem",
        lambda state: state.get("current_action") or "FIM",
        {
            "AGENDAR": "extrair_datas_agendamento_llm_node",
            "EMAIL": "email_handler",
            "LISTAR_EVENTOS": "extrair_datas_listagem_llm_node",
            "CONVERSAR": "conversa_node",
            "BUSCAR_WEB": "buscar_internet",
            "FIM": END  # Finalização
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

    #buscar na web

    graph.add_edge("buscar_internet", "add_assistant_history")

    graph.add_edge("add_assistant_history", "executar_acoes_em_ordem")

    
    compiled_graph = graph.compile()
    return compiled_graph 