from __future__ import annotations

import os
import sys
import faulthandler

faulthandler.enable()

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "hide")
os.environ["QT_LOGGING_RULES"]           = "qt.qpa.window=false"
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-logging --disable-gpu --no-sandbox"

import asyncio
import logging
import threading

from PyQt6.QtCore    import Qt
from PyQt6.QtWidgets import QApplication

import config
from painel            import PainelCore, set_loop
from audio.voz         import ouvir_comando, falar
from engine.core       import processar_comando, inicializar_ia
from engine.controller import get_shutdown_event
from storage.memory_bridge import sincronizar_config
from tasks.monitor     import iniciar_sentinela, registrar_falar, registrar_loop_monitor_voz
from tasks.alarm       import (
    iniciar_sistema_alarmes,
    registrar_falar_alarme,
    registrar_loop_alarme,
)
from app_ul.interface  import JarvisUI
from storage.wake      import processar_wake, resposta_ativacao_aleatoria
from integrations.telegram_bridge_auth_patch import iniciar_telegram

QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
logging.getLogger("faster_whisper").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

log = logging.getLogger(__name__)


async def _executar(cmd: str):
    await processar_comando(cmd)


async def _engine_loop(ui: PainelCore):
    await inicializar_ia()
    iniciar_sentinela()
    iniciar_sistema_alarmes()
    sincronizar_config()

    try:
        from brain.event_bus import bus
        from brain.watchdog  import watchdog, registrar_modulos_padrao
        bus.registrar_loop(asyncio.get_running_loop())
        registrar_modulos_padrao()
        watchdog.iniciar()
    except Exception as exc:
        log.warning("watchdog/event_bus indisponível: %s", exc)

    try:
        from storage.observability import registrar_acao, purgar_antigos
        purgar_antigos(dias=7)
        registrar_acao("startup", modulo="main", descricao="Jarvis inicializado", sucesso=True)
    except Exception as exc:
        log.warning("observability indisponível: %s", exc)

    threading.Thread(target=iniciar_telegram, daemon=True, name="TelegramBot").start()

    shutdown = get_shutdown_event()
    while not shutdown.is_set():
        try:
            config.recarregar_identidade_painel()
            resultado = await ouvir_comando()
            if not resultado or not isinstance(resultado, str):
                continue
            ativo, cmd = processar_wake(resultado)
            if not ativo or not isinstance(cmd, str):
                continue
            cmd = cmd.strip()
            if not cmd:
                await falar(resposta_ativacao_aleatoria())
                continue
            await _executar(cmd)
        except Exception:
            log.exception("erro no ciclo principal")
            await asyncio.sleep(0.3)


def _engine_thread(ui: PainelCore):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    set_loop(loop)
    registrar_loop_alarme(loop)
    registrar_loop_monitor_voz(loop)
    try:
        loop.run_until_complete(_engine_loop(ui))
    finally:
        loop.close()


def iniciar_sistema():
    ui  = PainelCore()
    hud = JarvisUI()

    try:
        hud.btn_code.clicked.disconnect()
    except TypeError:
        pass
    hud.btn_code.clicked.connect(
        lambda: (ui.show(), ui.raise_(), ui.activateWindow())
    )
    hud.show()

    registrar_falar(falar)
    registrar_falar_alarme(falar)

    threading.Thread(
        target=_engine_thread,
        args=(ui,),
        daemon=True,
        name="CoreEngine",
    ).start()

    sys.exit(app.exec())


if __name__ == "__main__":
    iniciar_sistema()