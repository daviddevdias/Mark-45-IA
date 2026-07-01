from __future__ import annotations
import email, logging, time
from email.header import decode_header

import config

log = logging.getLogger("email")

cache_emails: list[dict] = []
cache_ttl = 120
ultimo_check: float = 0

def decodificar(s: bytes | str) -> str:
    if not s:
        return ""
    try:
        partes = decode_header(s)
        return "".join(
            p.decode(charset or "utf-8") if isinstance(p, bytes) else p
            for p, charset in partes
        )
    except:
        return str(s)

async def verificar_email(limite: int = 5) -> list[dict]:
    global ultimo_check, cache_emails
    agora = time.time()
    if cache_emails and (agora - ultimo_check) < cache_ttl:
        return cache_emails[:limite]

    host = getattr(config, "EMAIL_IMAP_HOST", "")
    usuario = getattr(config, "EMAIL_USER", "")
    senha = getattr(config, "EMAIL_PASS", "")

    if not host or not usuario or not senha:
        return []

    try:
        import imaplib
        conn = imaplib.IMAP4_SSL(host, timeout=10)
        conn.login(usuario, senha)
        conn.select("INBOX")
        _, data = conn.search(None, "UNSEEN")
        msgs = []
        for num in data[0].split()[:limite]:
            _, msg_data = conn.fetch(num, "(RFC822)")
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)
            msgs.append({
                "de": decodificar(msg.get("From", "")),
                "assunto": decodificar(msg.get("Subject", "")),
                "data": msg.get("Date", ""),
            })
        conn.logout()
        cache_emails = msgs
        ultimo_check = time.time()
        return msgs
    except Exception as e:
        log.warning(f"Erro email: {e}")
        return []

async def contar_nao_lidos() -> int:
    msgs = await verificar_email(50)
    return len(msgs)

async def emails_para_fala(limite: int = 3) -> str:
    msgs = await verificar_email(limite)
    if not msgs:
        return "Nenhum e-mail novo."
    partes = [f"{m['assunto']} — de {m['de'].split('<')[0].strip()}" for m in msgs]
    return "E-mails: " + " | ".join(partes)
