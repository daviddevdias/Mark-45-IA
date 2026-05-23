from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine

log = logging.getLogger("jarvis.event_bus")

VOZ_RECEBIDA      = "voz_recebida"
COMANDO_EXECUTADO = "comando_executado"
ALARME_DISPARADO  = "alarme_disparado"
IA_RESPOSTA       = "ia_resposta"
ERRO_MODULO       = "erro_modulo"
MODULO_RECUPERADO = "modulo_recuperado"
ESTADO_ALTERADO   = "estado_alterado"
FERRAMENTA_USADA  = "ferramenta_usada"
MONITOR_ALERTA    = "monitor_alerta"

@dataclass
class Evento:
    tipo:      str
    dados:     dict  = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    origem:    str   = ""

Handler = Callable[[Evento], Coroutine | None]

class EventBus:

    def __init__(self):
        self.listeners: dict[str, list[Handler]] = defaultdict(list)
        self.historico: list[Evento]             = []
        self.max_hist = 200
        self.loop: asyncio.AbstractEventLoop | None = None

    def registrar_loop(self, loop: asyncio.AbstractEventLoop):
        self.loop = loop

    def assinar(self, tipo: str, handler: Handler):
        if handler not in self.listeners[tipo]:
            self.listeners[tipo].append(handler)
            log.debug("Handler %s registrado em '%s'", getattr(handler, "__name__", "?"), tipo)

    def cancelar(self, tipo: str, handler: Handler):
        try:
            self.listeners[tipo].remove(handler)
        except ValueError:
            pass

    def obter_loop(self) -> asyncio.AbstractEventLoop | None:
        try:
            return asyncio.get_running_loop()
        except RuntimeError:
            return None

    def publicar(self, tipo: str, dados: dict | None = None, origem: str = ""):
        ev = Evento(tipo=tipo, dados=dados or {}, origem=origem)
        self._guardar(ev)

        for handler in list(self.listeners.get(tipo, [])):
            try:
                result = handler(ev)
                if asyncio.iscoroutine(result):
                    loop = self.loop or self.obter_loop()
                    if loop and not loop.is_closed():
                        asyncio.run_coroutine_threadsafe(result, loop)
            except Exception as exc:
                log.error("Handler '%s' falhou no evento '%s': %s",
                          getattr(handler, "__name__", "?"), tipo, exc)

    async def publicar_async(self, tipo: str, dados: dict | None = None, origem: str = ""):
        ev = Evento(tipo=tipo, dados=dados or {}, origem=origem)
        self._guardar(ev)

        for handler in list(self.listeners.get(tipo, [])):
            try:
                result = handler(ev)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as exc:
                log.error("Handler async '%s' falhou: %s",
                          getattr(handler, "__name__", "?"), exc)

    def _guardar(self, ev: Evento):
        self.historico.append(ev)
        if len(self.historico) > self.max_hist:
            self.historico = self.historico[-self.max_hist:]

    def get_historico(self, tipo: str | None = None, limite: int = 50) -> list[dict]:
        base = [e for e in self.historico if tipo is None or e.tipo == tipo]
        return [{"tipo": e.tipo, "dados": e.dados, "ts": e.timestamp, "origem": e.origem}
                for e in base[-limite:]]

    def on(self, tipo: str):
        def decorator(fn: Handler) -> Handler:
            self.assinar(tipo, fn)
            return fn
        return decorator

bus = EventBus()