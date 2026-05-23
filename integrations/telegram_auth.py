from __future__ import annotations

import hashlib
import hmac
import logging
import os
import time
from functools import wraps
from typing import Callable

log = logging.getLogger("jarvis.telegram_security")

_ALLOWED_IDS: set[int] = set()
_AUTH_TOKEN: str = ""
_PENDING_AUTH: dict[int, float] = {}
_AUTH_TTL = 300







def carregar_config():
    global _ALLOWED_IDS, _AUTH_TOKEN
    ids_raw = os.environ.get("TELEGRAM_ALLOWED_IDS", "")
    if ids_raw:
        for part in ids_raw.split(","):
            part = part.strip()
            if part.isdigit():
                _ALLOWED_IDS.add(int(part))
    try:
        import config as cfg
        ids_cfg = getattr(cfg, "TELEGRAM_ALLOWED_IDS", [])
        if isinstance(ids_cfg, (list, set, tuple)):
            _ALLOWED_IDS.update(int(i) for i in ids_cfg if str(i).isdigit())
        token = getattr(cfg, "TELEGRAM_AUTH_TOKEN", "") or os.environ.get("TELEGRAM_AUTH_TOKEN", "")
        if token:
            _AUTH_TOKEN = token
    except Exception:
        pass
    if not _ALLOWED_IDS:
        log.warning(
            "[Telegram] Nenhum TELEGRAM_ALLOWED_IDS configurado. "
            "Defina em config.py ou na variável de ambiente TELEGRAM_ALLOWED_IDS."
        )







def adicionar_id_autorizado(chat_id: int):
    _ALLOWED_IDS.add(chat_id)







def e_autorizado(chat_id: int) -> bool:
    if not _ALLOWED_IDS:
        return False
    return chat_id in _ALLOWED_IDS







def verificar_token(token_fornecido: str) -> bool:
    if not _AUTH_TOKEN:
        return False
    return hmac.compare_digest(
        hashlib.sha256(token_fornecido.encode()).hexdigest(),
        hashlib.sha256(_AUTH_TOKEN.encode()).hexdigest(),
    )







def marcar_pendente_auth(chat_id: int):
    _PENDING_AUTH[chat_id] = time.time()







def esta_pendente_auth(chat_id: int) -> bool:
    ts = _PENDING_AUTH.get(chat_id)
    if ts is None:
        return False
    if time.time() - ts > _AUTH_TTL:
        del _PENDING_AUTH[chat_id]
        return False
    return True







def limpar_pendente(chat_id: int):
    _PENDING_AUTH.pop(chat_id, None)







def requer_autorizacao(fn: Callable) -> Callable:
    @wraps(fn)
    async def wrapper(update, context, *args, **kwargs):
        chat_id = update.effective_chat.id
        if e_autorizado(chat_id):
            return await fn(update, context, *args, **kwargs)
        if esta_pendente_auth(chat_id):
            texto = (update.message.text or "").strip()
            if verificar_token(texto):
                adicionar_id_autorizado(chat_id)
                limpar_pendente(chat_id)
                log.info("[Telegram] chat_id %d autenticado com sucesso.", chat_id)
                await update.message.reply_text("Acesso autorizado.")
                return
            else:
                log.warning("[Telegram] Token inválido de chat_id %d.", chat_id)
                await update.message.reply_text("Token inválido. Tente novamente.")
                return
        log.warning("[Telegram] Acesso negado para chat_id %d.", chat_id)
        marcar_pendente_auth(chat_id)
        await update.message.reply_text(
            "Acesso restrito. Envie o token de autenticação para continuar."
        )
        return
    return wrapper







carregar_config()