import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote, urlparse, parse_qs, unquote
from state_types import IcarusState

def add_to_history(state, role, content):
    state["messages"].append({"role": role, "content": content})
    return state


# Funções utilitárias. As ferramentas principais foram movidas para a pasta tools/.
