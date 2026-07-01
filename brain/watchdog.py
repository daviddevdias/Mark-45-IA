from __future__ import annotations
import logging, threading, time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

log = logging.getLogger("jarvis.watchdog")
INTERVALO_CHECK, MAX_FALHAS, COOLDOWN_RESET = 30.0, 3, 60.0


class StatusModulo(Enum):
    OK = "ok"
    DEGRADADO = "degradado"
    FALHOU = "falhou"
    REINICIANDO = "reiniciando"


@dataclass
class RegistroModulo:
    nome: str
    check_fn: Callable[[], bool]
    reset_fn: Callable[[], None] | None = None
    falhas: int = 0
    status: StatusModulo = StatusModulo.OK
    ultimo_check: float = 0.0
    ultimo_reset: float = 0.0
    historico: list[dict] = field(default_factory=list)


class Watchdog:
    def __init__(self):
        self.modulos: dict[str, RegistroModulo] = {}
        self.lock = threading.Lock()
        self.rodando = False
        self.thread: threading.Thread | None = None
        self.stop_event = threading.Event()

    def registrar(
        self,
        nome: str,
        check_fn: Callable[[], bool],
        reset_fn: Callable[[], None] | None = None,
    ):
        with self.lock:
            self.modulos[nome] = RegistroModulo(
                nome=nome, check_fn=check_fn, reset_fn=reset_fn
            )

    def _loop(self):
        while not self.stop_event.is_set():
            agora = time.time()
            for nome, reg in list(self.modulos.items()):
                if agora - reg.ultimo_check < INTERVALO_CHECK:
                    continue
                try:
                    ok = reg.check_fn()
                    with self.lock:
                        reg.ultimo_check = agora
                        if ok:
                            reg.falhas = 0
                            reg.status = StatusModulo.OK
                        else:
                            reg.falhas += 1
                            reg.status = (
                                StatusModulo.DEGRADADO
                                if reg.falhas < MAX_FALHAS
                                else StatusModulo.FALHOU
                            )
                            if (
                                reg.status == StatusModulo.FALHOU
                                and reg.reset_fn
                                and (agora - reg.ultimo_reset > COOLDOWN_RESET)
                            ):
                                reg.status = StatusModulo.REINICIANDO
                                reg.ultimo_reset = agora
                                threading.Thread(
                                    target=self._tentar_reset, args=(reg,), daemon=True
                                ).start()
                except Exception:
                    pass
            self.stop_event.wait(5.0)

    def _tentar_reset(self, reg: RegistroModulo):
        try:
            if reg.reset_fn:
                reg.reset_fn()
            with self.lock:
                reg.falhas = 0
                reg.status = StatusModulo.OK
        except Exception:
            with self.lock:
                reg.status = StatusModulo.FALHOU

    def iniciar(self):
        with self.lock:
            if self.rodando:
                return
            self.rodando = True
            self.stop_event.clear()
            self.thread = threading.Thread(
                target=self._loop, daemon=True, name="Watchdog"
            )
            self.thread.start()

    def parar(self):
        with self.lock:
            self.rodando = False
            self.stop_event.set()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)

    def get_status(self) -> dict:
        with self.lock:
            return {
                n: {
                    "status": r.status.value,
                    "falhas": r.falhas,
                    "ultimo_check": r.ultimo_check,
                }
                for n, r in self.modulos.items()
            }

    def todos_ok(self) -> bool:
        with self.lock:
            return all(r.status == StatusModulo.OK for r in self.modulos.values())


watchdog = Watchdog()


def check_ia() -> bool:
    try:
        import requests

        return (
            requests.get("http://127.0.0.1:1234/v1/models", timeout=2).status_code
            == 200
        )
    except Exception:
        return False


def reset_ia():
    try:
        from engine.ia_router import detectar_modelo
        import asyncio

        loop = asyncio.new_event_loop()
        loop.run_until_complete(asyncio.wait_for(detectar_modelo(), timeout=10))
        loop.close()
    except Exception:
        pass


def check_audio() -> bool:
    try:
        import audio.voz as m

        return callable(getattr(m, "falar", None))
    except Exception:
        return False


def check_lmstudio() -> bool:
    try:
        import aiohttp
        import asyncio

        loop = asyncio.new_event_loop()

        async def _check():
            try:
                async with aiohttp.ClientSession() as s:
                    async with s.get("http://127.0.0.1:1234/v1/models", timeout=2) as r:
                        return r.status == 200
            except:
                return False

        result = loop.run_until_complete(_check())
        loop.close()
        return result
    except:
        return False


def check_sentinela() -> bool:
    try:
        import threading

        return any(
            t.name == "Sentinela" and t.is_alive() for t in threading.enumerate()
        )
    except:
        return False


def registrar_modulos_padrao():
    watchdog.registrar("ia", check_ia, reset_ia)
    watchdog.registrar("audio", check_audio)
    watchdog.registrar("lmstudio", check_lmstudio)
    watchdog.registrar("sentinela", check_sentinela)
