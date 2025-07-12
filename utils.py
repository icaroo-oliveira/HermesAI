import os
import requests
from bs4 import BeautifulSoup

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