import hashlib, hmac, os, time
from functools import wraps
from typing import Callable

ALLOWED_IDS: set[int] = set()
AUTH_TOKEN: str = ""
PENDING_AUTH: dict[int, float] = {}
AUTH_TTL = 300


def carregar_config():
    global ALLOWED_IDS, AUTH_TOKEN
    ids_raw = os.environ.get("TELEGRAM_ALLOWED_IDS", "")
    for part in ids_raw.split(","):
        if part.strip().isdigit():
            ALLOWED_IDS.add(int(part.strip()))
    try:
        import config as cfg
        ids_cfg = getattr(cfg, "TELEGRAM_ALLOWED_IDS", [])
        if isinstance(ids_cfg, (list, set, tuple)):
            ALLOWED_IDS.update(int(i) for i in ids_cfg if str(i).isdigit())
        token = getattr(cfg, "TELEGRAM_AUTH_TOKEN", "") or os.environ.get("TELEGRAM_AUTH_TOKEN", "")
        if token:
            AUTH_TOKEN = token
    except:
        pass


def adicionar_id_autorizado(chat_id: int):
    ALLOWED_IDS.add(chat_id)


def e_autorizado(chat_id: int) -> bool:
    return chat_id in ALLOWED_IDS if ALLOWED_IDS else False


def verificar_token(token_fornecido: str) -> bool:
    if not AUTH_TOKEN:
        return False
    return hmac.compare_digest(
        hashlib.sha256(token_fornecido.encode()).hexdigest(),
        hashlib.sha256(AUTH_TOKEN.encode()).hexdigest(),
    )


def marcar_pendente_auth(chat_id: int):
    PENDING_AUTH[chat_id] = time.time()


def esta_pendente_auth(chat_id: int) -> bool:
    ts = PENDING_AUTH.get(chat_id)
    if ts is None:
        return False
    if time.time() - ts > AUTH_TTL:
        del PENDING_AUTH[chat_id]
        return False
    return True


def limpar_pendente(chat_id: int):
    PENDING_AUTH.pop(chat_id, None)


def requer_autorizacao(fn: Callable) -> Callable:
    @wraps(fn)
    async def wrapper(update, context, *args, **kwargs):
        chat_id = update.effective_chat.id
        if e_autorizado(chat_id):
            return await fn(update, context, *args, **kwargs)
        if esta_pendente_auth(chat_id):
            if verificar_token((update.message.text or "").strip()):
                adicionar_id_autorizado(chat_id)
                limpar_pendente(chat_id)
                await update.message.reply_text("Acesso autorizado.")
                return
            await update.message.reply_text("Token inválido. Tente novamente.")
            return
        marcar_pendente_auth(chat_id)
        await update.message.reply_text("Acesso restrito. Envie o token de autenticação.")

    return wrapper


carregar_config()
