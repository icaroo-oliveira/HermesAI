from typing import Any
from .agenda import get_permission_google_service

def email_handler(state: Any) -> Any:
    try:
        service = get_permission_google_service("gmail","v1")
        results = (
            service.users().messages().list(userId="me", labelIds=["INBOX"], maxResults=10).execute()
        )
        messages = results.get("messages", [])
        if not messages:
            resposta = "Nenhum e-mail encontrado na caixa de entrada."
            resposta = resposta.strip()
            state["invocation"] = resposta
            state["invocations_list"].append(resposta)
            return state
        emails = []
        for message in messages:
            msg = (
                service.users().messages().get(userId="me", id=message["id"]).execute()
            )
            snippet = msg.get("snippet", "(sem assunto)")
            remetente = "(remetente desconhecido)"
            emails.append({"assunto": snippet, "remetente": remetente, "id": message["id"]})
        state["email"]["emails"] = emails
        resposta = "Assuntos dos e-mails encontrados:\n" + "\n".join(f"- {e['assunto']}" for e in emails)
        resposta = resposta.strip()
        state["invocation"] = resposta
        state["invocations_list"].append(resposta)
        return state
    except Exception as e:
        resposta = f"Erro ao buscar e-mails: {e}"
        state["invocation"] = resposta
        state["invocations_list"].append(resposta)
        return state

def get_email_by_id(email_id):
    try:
        service = get_permission_google_service("gmail", "v1")
        msg = service.users().messages().get(userId="me", id=email_id, format="full").execute()
        headers = msg.get("payload", {}).get("headers", [])
        subject = next((h["value"] for h in headers if h["name"] == "Subject"), "(sem assunto)")
        from_ = next((h["value"] for h in headers if h["name"] == "From"), "(remetente desconhecido)")
        date = next((h["value"] for h in headers if h["name"] == "Date"), "(data desconhecida)")
        snippet = msg.get("snippet", "")
        return {
            "assunto": subject,
            "remetente": from_,
            "data": date,
            "snippet": snippet,
            "id": email_id
        }
    except Exception as e:
        return f"Ocorreu um erro ao buscar o e-mail: {e}" 