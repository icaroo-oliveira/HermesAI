from typing import TypedDict, Optional, List, Dict, Any

class AgendaData(TypedDict, total=False):
    titulo: Optional[str]
    data_hora_inicio_str: Optional[str]
    duracao_minutos: Optional[int]

class EmailData(TypedDict, total=False):
    emails: Optional[List[Dict[str, Any]]]
    email_selecionado: Optional[Dict[str, Any]]

class IcarusState(TypedDict):
    user_input: str
    decision: Optional[str]
    messages: List[Dict[str, Any]]
    agenda: AgendaData
    email: EmailData
    invocation: Optional[Any] 
    decisions: List[Optional[str]]
    invocations_list:List[str]