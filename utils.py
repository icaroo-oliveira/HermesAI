import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote, urlparse, parse_qs, unquote
from state_types import IcarusState

def add_to_history(state, role, content):
    state["messages"].append({"role": role, "content": content})
    return state


def obter_previsao_tempo_weatherapi(cidade="Feira de Santana", api_key=None):
    if api_key is None:
        api_key = os.environ.get("WEATHERAPI_KEY", "")
    url = f"http://api.weatherapi.com/v1/current.json?key={api_key}&q={cidade}&lang=pt"
    try:
        response = requests.get(url)
        if response.status_code != 200:
            return f"Não foi possível obter a previsão do tempo para {cidade}."
        data = response.json()
        temp = data['current']['temp_c']
        condicao = data['current']['condition']['text']
        return f"Previsão para {cidade}: {temp}°C, {condicao}."
    except Exception as e:
        return f"Erro ao obter previsão do tempo: {e}" 
    



def buscar_na_web_duckduckgo(state: IcarusState) -> IcarusState:
    print("função chamada a de busca")

    query = state["user_input"]  
    url = f"https://duckduckgo.com/html/?q={quote(query)}"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code != 200:
            resultado = "Não foi possível buscar na web."
        else:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, "html.parser")
            results = []
            for a in soup.select('.result__a'):
                raw_link = a['href']
                parsed = urlparse(raw_link)
                real_url = parse_qs(parsed.query).get("uddg", [raw_link])[0]
                real_url = unquote(real_url)
                title = a.get_text()
                results.append(f"{title}\n{real_url}")
                if len(results) >= 3:
                    break
            resultado = "\n\n".join(results) if results else "Nenhum resultado encontrado."
    except Exception as e:
        resultado = f"Erro ao buscar: {e}"

    state['invocation'] = resultado
    state['invocations_list'].append(resultado)
    state['websearch'] = {
        "query": query,
        "search_results": resultado
    }
    return state
