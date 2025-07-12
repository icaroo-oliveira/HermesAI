from langgraph.graph import StateGraph, START, END
from utils import add_to_history
from tools.websearch import buscar_na_web_duckduckgo
from tools.agenda import criar_evento_na_agenda, listar_eventos_periodo, existe_conflito_agenda
from tools.email import email_handler
from tools.weather import obter_previsao_tempo_weatherapi
from llm_utils import llm_ask, extract_event_prompt
from typing import Any
import re
from date_extractor import extrair_datas_periodo_llm
from state_types import IcarusState


# Nó decisor
# Nó decisor com múltiplas intenções
async def decision_node(state: Any) -> Any:
    decision_prompt = '''
Você é Icarus, um assistente pessoal inteligente e contextual. Analise a mensagem do usuário e identifique quais ações, se houver, precisam ser realizadas. As ações possíveis são:

- AGENDAR: quando o usuário pede para marcar, adicionar ou alterar um compromisso, evento ou reunião.
- EMAIL: quando o usuário pede para ler, buscar ou listar e-mails.
- LISTAR_EVENTOS: quando o usuário pede para ver compromissos, agenda, eventos futuros ou passados.
- BUSCAR_WEB: quando o usuário pede informações externas, como notícias, fatos, pesquisas, previsão do tempo, etc.
- CONVERSAR: quando o usuário está apenas conversando, fazendo comentários, perguntas retóricas, piadas, ou não faz um pedido de ação claro.

REGRAS:
- Analise o contexto, o tom e a intenção da mensagem.
- Considere o histórico recente da conversa: se o usuário pedir para repetir, mostrar novamente, detalhar, relembrar ou referenciar uma ação já realizada (como links buscados, evento agendado, e-mails lidos, etc.), responda com base no histórico, sem acionar a ferramenta novamente.
- Só acione BUSCAR_WEB, AGENDAR, EMAIL ou LISTAR_EVENTOS se houver um pedido claro ou implícito de ação nova.
- Se a mensagem for apenas um comentário, curiosidade, piada ou pergunta retórica, classifique como CONVERSAR.
- Se houver múltiplos pedidos, retorne todas as ações relevantes, separadas por vírgula, na ordem em que aparecem na mensagem.
- Responda apenas com as palavras-chave das ações, separadas por vírgula, sem explicações.
- Não invente ações. Se não tiver certeza, prefira CONVERSAR.

Exemplos de contexto:
Usuário: "Me mostre de novo os links dos jogos do Flamengo"
Resposta: CONVERSAR (responda mostrando os links buscados anteriormente, sem buscar de novo)

Usuário: "Qual foi o último evento que marquei?"
Resposta: CONVERSAR (responda com o evento agendado mais recente, sem acionar a agenda)

Usuário: "Repita meus e-mails de hoje"
Resposta: CONVERSAR (responda com os e-mails já lidos, sem buscar de novo)

Usuário: "Me diga quando o Flamengo joga e marque uma reunião às 15h amanhã"
Resposta: BUSCAR_WEB, AGENDAR

Usuário: "Sabia que o Flamengo vai jogar amanhã?"
Resposta: CONVERSAR

Usuário: "Liste meus compromissos de hoje e mostre meus e-mails"
Resposta: LISTAR_EVENTOS, EMAIL

Usuário: "Quero agendar uma reunião"
Resposta: AGENDAR

Usuário: "Oi, tudo bem?"
Resposta: CONVERSAR

Usuário: "Traduza esse texto e me diga quem é o presidente do Brasil"
Resposta: CONVERSAR, BUSCAR_WEB

Usuário: "Me lembre de comprar pão e veja se vai chover amanhã"
Resposta: AGENDAR, BUSCAR_WEB

Usuário: "Qual a previsão do tempo para amanhã?"
Resposta: BUSCAR_WEB

Usuário: "Você gosta de futebol?"
Resposta: CONVERSAR

Usuário: "Me envie meus e-mails e marque dentista para sexta"
Resposta: EMAIL, AGENDAR

Usuário: "Quais meus compromissos amanhã?"
Resposta: LISTAR_EVENTOS

Usuário: "Me conte uma piada e mostre minha agenda de hoje"
Resposta: CONVERSAR, LISTAR_EVENTOS

Usuário: "Qual a capital da França?"
Resposta: BUSCAR_WEB

Usuário: "Me diga o clima e me envie meus e-mails"
Resposta: BUSCAR_WEB, EMAIL

Usuário: "Bom dia!"
Resposta: CONVERSAR

Usuário: "Me lembre de estudar e me diga as notícias do dia"
Resposta: AGENDAR, BUSCAR_WEB

Usuário: "Você sabe quando é o próximo feriado?"
Resposta: BUSCAR_WEB

Usuário: "Marque reunião para amanhã e me diga se vai chover"
Resposta: AGENDAR, BUSCAR_WEB

Usuário: "Meus e-mails e compromissos de hoje, por favor"
Resposta: EMAIL, LISTAR_EVENTOS

Usuário: "Me mostre meus e-mails, minha agenda e pesquise notícias do Flamengo"
Resposta: EMAIL, LISTAR_EVENTOS, BUSCAR_WEB

Mensagem do usuário: {mensagem_usuario}
'''.replace('{mensagem_usuario}', state["user_input"])

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


def add_all_assistant_history(state):
    for resposta in state.get("invocations_list", []):
        add_to_history(state, "assistant", resposta)
    return state


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
    graph.add_node("add_assistant_history", add_all_assistant_history)

    
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