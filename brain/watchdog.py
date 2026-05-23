from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

log = logging.getLogger("jarvis.watchdog")

INTERVALO_CHECK = 30.0
MAX_FALHAS      = 3
COOLDOWN_RESET  = 60.0

class StatusModulo(Enum):
    OK          = "ok"
    DEGRADADO   = "degradado"
    FALHOU      = "falhou"
    REINICIANDO = "reiniciando"

@dataclass
class RegistroModulo:
    nome:         str
    check_fn:     Callable[[], bool]
    reset_fn:     Callable[[], None] | None = None
    falhas:       int                       = 0
    status:       StatusModulo              = StatusModulo.OK
    ultimo_check: float                     = 0.0
    ultimo_reset: float                     = 0.0
    historico:    list[dict]                = field(default_factory=list)

class Watchdog:

    def __init__(self):
        self.modulos: dict[str, RegistroModulo] = {}
        self.lock    = threading.Lock()
        self.rodando = False
        self.thread: threading.Thread | None = None
        self.stop_event = threading.Event()

    def registrar(self, nome: str, check_fn: Callable[[], bool],
                  reset_fn: Callable[[], None] | None = None):
        with self.lock:
            self.modulos[nome] = RegistroModulo(nome=nome, check_fn=check_fn, reset_fn=reset_fn)
        log.info("[Watchdog] Módulo '%s' registrado.", nome)

    def checar(self, reg: RegistroModulo):
        agora = time.time()
        reg.ultimo_check = agora
        try:
            ok = reg.check_fn()
        except Exception as exc:
            ok = False
            log.warning("[Watchdog] check '%s' lançou exceção: %s", reg.nome, exc)

        if ok:
            if reg.falhas > 0:
                log.info("[Watchdog] '%s' recuperado após %d falha(s).", reg.nome, reg.falhas)
                try:
                    from brain.event_bus import bus, MODULO_RECUPERADO
                    bus.publicar(MODULO_RECUPERADO, {"modulo": reg.nome})
                except Exception:
                    pass

            reg.falhas = 0
            reg.status = StatusModulo.OK
        else:
            reg.falhas += 1
            log.warning("[Watchdog] '%s' falhou (%d/%d).", reg.nome, reg.falhas, MAX_FALHAS)
            reg.status = StatusModulo.DEGRADADO if reg.falhas < MAX_FALHAS else StatusModulo.FALHOU
            if reg.falhas >= MAX_FALHAS:
                try:
                    from brain.event_bus import bus, ERRO_MODULO
                    bus.publicar(ERRO_MODULO, {"modulo": reg.nome, "falhas": reg.falhas})
                except Exception:
                    pass

                if reg.reset_fn and (agora - reg.ultimo_reset) > COOLDOWN_RESET:
                    self.resetar(reg)

        reg.historico.append({"ts": agora, "ok": ok})
        if len(reg.historico) > 50:
            reg.historico = reg.historico[-50:]

    def resetar(self, reg: RegistroModulo):
        reg.status = StatusModulo.REINICIANDO
        log.info("[Watchdog] Reiniciando '%s'...", reg.nome)
        try:
            reg.reset_fn()
            reg.falhas       = 0
            reg.ultimo_reset = time.time()
            reg.status       = StatusModulo.OK
            log.info("[Watchdog] '%s' reiniciado com sucesso.", reg.nome)
        except Exception as exc:
            log.error("[Watchdog] Falha ao reiniciar '%s': %s", reg.nome, exc)
            reg.status = StatusModulo.FALHOU

    def loop_watchdog(self):
        while self.rodando:
            with self.lock:
                modulos = list(self.modulos.values())
            for reg in modulos:
                try:
                    self.checar(reg)
                except Exception as exc:
                    log.error("[Watchdog] Erro interno em '%s': %s", reg.nome, exc)

            self.stop_event.wait(timeout=INTERVALO_CHECK)
            self.stop_event.clear()

    def iniciar(self):
        if self.rodando:
            return

        self.stop_event.clear()
        self.rodando = True
        self.thread  = threading.Thread(target=self.loop_watchdog, daemon=True, name="Watchdog")
        self.thread.start()
        log.info("[Watchdog] Iniciado.")

    def parar(self):
        self.rodando = False
        self.stop_event.set()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)

        log.info("[Watchdog] Parado.")

    def get_status(self) -> dict:
        with self.lock:
            return {n: {"status": r.status.value, "falhas": r.falhas, "ultimo_check": r.ultimo_check}
                    for n, r in self.modulos.items()}

    def todos_ok(self) -> bool:
        with self.lock:
            return all(r.status == StatusModulo.OK for r in self.modulos.values())

watchdog = Watchdog()

def check_ia() -> bool:
    try:
        import requests
        return requests.get("http://127.0.0.1:1234/v1/models", timeout=2).status_code == 200
    except Exception:
        return False

def reset_ia():
    try:
        from engine.ia_router import detectar_modelo
        import asyncio
        loop = asyncio.new_event_loop()
        loop.run_until_complete(asyncio.wait_for(detectar_modelo(), timeout=10))
        loop.close()
    except Exception as exc:
        raise RuntimeError(f"reset IA: {exc}")

def check_audio() -> bool:
    try:
        import audio.voz as m
        return callable(getattr(m, "falar", None))
    except Exception:
        return False

def registrar_modulos_padrao():
    watchdog.registrar("ia",      check_ia,      reset_ia)
    watchdog.registrar("audio",   check_audio,   None)
    watchdog.registrar("audio", check_audio, None)
