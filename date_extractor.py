from llm_utils import llm_ask
from datetime import datetime, timedelta
import re

def substituir_datas_naturais(texto):
    hoje = datetime.now()
    substituicoes = {
        r'\bhoje\b': hoje.strftime('%Y-%m-%d'),
        r'\bamanhã\b': (hoje + timedelta(days=1)).strftime('%Y-%m-%d'),
        r'\bdepois de amanhã\b': (hoje + timedelta(days=2)).strftime('%Y-%m-%d'),
        r'\bontem\b': (hoje - timedelta(days=1)).strftime('%Y-%m-%d'),
    }
    for padrao, valor in substituicoes.items():
        texto = re.sub(padrao, valor, texto, flags=re.IGNORECASE)
    return texto

async def extrair_datas_periodo_llm(state):
    """
    Usa o LLM para extrair datas de início e fim do texto do usuário e preenche no estado.
    Não altera state['user_input'] nem outros campos além de agenda.
    """
    texto_processado = substituir_datas_naturais(state['user_input'])
    ano_atual = datetime.now().year
    prompt = f'''
Extraia do texto abaixo as datas de início e fim (se houver) para um período de eventos. Responda em JSON com as chaves:
- data_inicial (formato ISO 8601, ex: 2025-07-15T00:00:00)
- data_final (formato ISO 8601, ex: 2025-07-20T23:59:59, opcional)
Se não houver data_final, retorne apenas data_inicial.
Se o ano não for especificado, use o ano atual: {ano_atual}.
Se o texto pedir apenas "hoje", use apenas o dia de hoje como período, não um intervalo maior.
Se for para agendar um evento para "hoje", use apenas o dia de hoje.

Exemplos:
"Quais meus compromissos 2025-07-14?"
Resposta: {{"data_inicial": "2025-07-14T00:00:00"}}

"Quais meus compromissos de 2025-07-13 até 2025-07-18?"
Resposta: {{"data_inicial": "2025-07-13T00:00:00", "data_final": "2025-07-18T23:59:59"}}

Texto: {{texto}}
'''.replace('{texto}', texto_processado)
    raw = await llm_ask(prompt, state.get('messages', []))
    # Extrai JSON da resposta
    match = re.search(r'(\{[\s\S]*?\})', raw)
    if match:
        import json
        try:
            datas = json.loads(match.group(1))
            agenda = state.get('agenda', {}).copy()
            if 'data_inicial' in datas:
                agenda['data_inicial'] = datas['data_inicial']
            if 'data_final' in datas:
                agenda['data_final'] = datas['data_final']
            state['agenda'] = agenda
        except Exception as e:
            print(f'[DEBUG] Erro ao extrair datas do LLM: {e}')
    else:
        print('[DEBUG] LLM não retornou JSON de datas.')
    return state 