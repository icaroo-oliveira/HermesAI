from urllib.parse import quote, urlparse, parse_qs, unquote
import requests
from bs4 import BeautifulSoup
from state_types import IcarusState

def buscar_na_web_duckduckgo(state: IcarusState) -> IcarusState:
    query = state["user_input"]  
    url = f"https://duckduckgo.com/html/?q={quote(query)}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code != 200:
            resultado = "Não foi possível buscar na web."
        else:
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