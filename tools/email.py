from typing import Any
from .agenda import get_permission_google_service
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from utils.llm_utils import llm_ask
import chainlit as cl

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

def send_email(to_email, subject, body, cc=None, bcc=None):
    """
    Envia um e-mail usando a API do Gmail.
    
    Args:
        to_email (str): Endereço de e-mail do destinatário
        subject (str): Assunto do e-mail
        body (str): Corpo do e-mail
        cc (str, optional): Endereços de e-mail em cópia (separados por vírgula)
        bcc (str, optional): Endereços de e-mail em cópia oculta (separados por vírgula)
    
    Returns:
        dict: Resultado da operação com status e mensagem
    """
    try:
        service = get_permission_google_service("gmail", "v1")
        
        #cria a mensagem
        message = MIMEMultipart()
        message['to'] = to_email
        message['subject'] = subject
        
        #cc se fornecido
        if cc:
            message['cc'] = cc
            
        #bcc se fornecido
        if bcc:
            message['bcc'] = bcc
        
        #ccorpo do email
        text_part = MIMEText(body, 'plain', 'utf-8')
        message.attach(text_part)
        
        #mensagem em base64
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        
        #envia o e-mail
        sent_message = service.users().messages().send(userId="me", body={'raw': raw_message}).execute()
        
        return {
            "success": True,
            "message": "E-mail enviado com sucesso!",
            "message_id": sent_message['id']
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"Erro ao enviar e-mail: {str(e)}"
        }

async def send_email_handler(state: Any) -> Any:
    """
    Handler para envio de e-mails que extrai informações do texto do usuário
    usando LLM e pede confirmação antes de enviar.
    
    # BUG: Atualmente, a mensagem de revisão do e-mail aparece duplicada na interface.
    # Isso ocorre porque ela é enviada tanto via cl.Message (com botões) quanto adicionada ao invocations_list,
    # que é exibido novamente no final do ciclo do grafo.
    # SOLUÇÃO FUTURA: Adicionar um flag no estado (ex: state["skip_final_message"] = True) e, no handler principal,
    # evitar enviar a resposta final se esse flag estiver presente. Assim, a mensagem fica no histórico mas não duplica na interface.
    """
    try:
        #extrai informações do e-mail usando LLM
        prompt = f"""
Extraia do texto abaixo as informações para enviar um e-mail. Responda em JSON com as chaves:
- to_email (endereço de e-mail do destinatário)
- subject (assunto do e-mail)
- body (corpo do e-mail)
- cc (opcional, endereços de e-mail em cópia separados por vírgula)
- bcc (opcional, endereços de e-mail em cópia oculta separados por vírgula)

Se alguma informação estiver faltando, use valores padrão apropriados.
Se o texto não for sobre enviar e-mail, retorne null.

Texto: {state['user_input']}
"""
        
        llm_response = await llm_ask(prompt, state.get('messages', []))
        
        #tenta extrair JSON da resposta
        import json
        import re
        
        match = re.search(r'(\{[\s\S]*?\})', llm_response)
        if not match:
            state["invocation"] = "Não consegui extrair as informações do e-mail. Por favor, forneça destinatário, assunto e mensagem."
            state["invocations_list"].append(state["invocation"])
            return state
            
        try:
            email_data = json.loads(match.group(1))
            
            #valida campos obrigatórios
            if not email_data.get('to_email') or not email_data.get('subject') or not email_data.get('body'):
                state["invocation"] = "Informações incompletas. Preciso de destinatário, assunto e mensagem para enviar o e-mail."
                state["invocations_list"].append(state["invocation"])
                return state
            
            #monta a mensagem de confirmação
            confirmation_message = f"""📧 **E-MAIL PARA REVISÃO**

**Para:** {email_data['to_email']}
**Assunto:** {email_data['subject']}
**Mensagem:**
{email_data['body']}"""

            if email_data.get('cc'):
                confirmation_message += f"\n**CC:** {email_data['cc']}"
            if email_data.get('bcc'):
                confirmation_message += f"\n**BCC:** {email_data['bcc']}"

            confirmation_message += """

⚠️ **ATENÇÃO:** Este e-mail será enviado imediatamente se você confirmar."""

            #salva os dados do e-mail no estado para uso posterior
            state["email"]["pending_email"] = email_data
            
            #envia a mensagem com botões usando Chainlit
            await cl.Message(
                content=confirmation_message,
                actions=[
                    cl.Action(name="send_email", label="✅ Enviar E-mail", payload={"action": "send"}),
                    cl.Action(name="cancel_email", label="❌ Cancelar", payload={"action": "cancel"})
                ]
            ).send()
            
            state["invocation"] = confirmation_message
            state["invocations_list"].append(state["invocation"])
            
        except json.JSONDecodeError:
            state["invocation"] = "Erro ao processar as informações do e-mail. Tente novamente."
            state["invocations_list"].append(state["invocation"])
            
    except Exception as e:
        state["invocation"] = f"Erro ao processar envio de e-mail: {str(e)}"
        state["invocations_list"].append(state["invocation"])
    
    return state

 