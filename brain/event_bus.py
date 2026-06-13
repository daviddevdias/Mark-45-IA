from __future__ import annotations
import asyncio, logging, time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable, Coroutine

log = logging.getLogger("jarvis.event_bus")

VOZ_RECEBIDA, COMANDO_EXECUTADO, ALARME_DISPARADO, IA_RESPOSTA = (
    "voz_recebida",
    "comando_executado",
    "alarme_disparado",
    "ia_resposta",
)
ERRO_MODULO, MODULO_RECUPERADO, ESTADO_ALTERADO = (
    "erro_modulo",
    "modulo_recuperado",
    "estado_alterado",
)
FERRAMENTA_USADA, MONITOR_ALERTA = "ferramenta_usada", "monitor_alerta"


@dataclass
class Evento:
    tipo: str
    dados: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    origem: str = ""


Handler = Callable[[Evento], Coroutine | None]


class EventBus:
    def __init__(self):
        self.listeners: dict[str, list[Handler]] = defaultdict(list)
        self.historico: list[Evento] = []
        self.max_hist = 200
        self.loop: asyncio.AbstractEventLoop | None = None

    def registrar_loop(self, loop: asyncio.AbstractEventLoop):
        self.loop = loop

    def assinar(self, tipo: str, handler: Handler):
        if handler not in self.listeners[tipo]:
            self.listeners[tipo].append(handler)

    def cancelar(self, tipo: str, handler: Handler):
        if handler in self.listeners[tipo]:
            self.listeners[tipo].remove(handler)

    def publicar(self, tipo: str, dados: dict | None = None, origem: str = ""):
        ev = Evento(tipo=tipo, dados=dados or {}, origem=origem)
        self.guardar(ev)
        for handler in list(self.listeners.get(tipo, [])):
            try:
                result = handler(ev)
                if asyncio.iscoroutine(result) and self.loop and self.loop.is_running():
                    asyncio.run_coroutine_threadsafe(result, self.loop)
            except Exception as exc:
                log.error("Handler falhou: %s", exc)

    async def publicar_async(
        self, tipo: str, dados: dict | None = None, origem: str = ""
    ):
        ev = Evento(tipo=tipo, dados=dados or {}, origem=origem)
        self.guardar(ev)
        for handler in list(self.listeners.get(tipo, [])):
            try:
                result = handler(ev)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as exc:
                log.error("Handler async falhou: %s", exc)

    def guardar(self, ev: Evento):
        self.historico.append(ev)
        if len(self.historico) > self.max_hist:
            self.historico = self.historico[-self.max_hist :]

    def get_historico(self, tipo: str | None = None, limite: int = 50) -> list[dict]:
        return [
            {"tipo": e.tipo, "dados": e.dados, "ts": e.timestamp, "origem": e.origem}
            for e in [e for e in self.historico if tipo is None or e.tipo == tipo][
                -limite:
            ]
        ]

    def on(self, tipo: str):
        def decorator(fn: Handler):
            self.assinar(tipo, fn)
            return fn

        return decorator


bus = EventBus()
