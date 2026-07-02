from __future__ import annotations
import os
import sys
import asyncio
import logging
import threading
import time
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--no-sandbox --log-level=3"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
os.environ["QT_LOGGING_RULES"] = "qt.qpa.window=false"

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("jarvis")

import config
from painel import PainelCore, set_loop
from audio.voz import (
    ouvir_comando,
    falar,
    interromper_voz,
    iniciar_wake_listener,
    barge_cmd,
)
from engine.core import processar_comando, inicializar_ia
from engine.controller import get_shutdown_event, preaquecer_modelo
from tasks.monitor import iniciar_sentinela, registrar_loop_monitor_voz
from tasks.alarm import gerenciador_alarmes
from tasks.wake import processar_wake, resposta_ativacao_aleatoria
from tasks.pomodoro import registrar_falar_cb
from app_ul.interface import JarvisUI
from integrations.telegram_bridge_auth_patch import iniciar_telegram

from tasks.clap_detector import (
    iniciar_detector,
    registrar_callback_palma,
    parar_detector,
)
from brain.watchdog import watchdog, registrar_modulos_padrao
from engine.ConnectionManager import lm_manager

os.environ["QTWEBENGINE_REMOTE_DEBUGGING"] = "9222"

QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)

SLEEP_TIMEOUT = 30


async def acao_palma():
    log.info("Ação de palma disparada!")
    await falar("Bom dia senhor Davi, Estou operando a 100%")


async def executar(cmd: str):
    try:
        await processar_comando(cmd)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        log.error(f"Erro ao processar: {e}")


async def loop_principal(ui):
    await inicializar_ia()
    iniciar_sentinela()
    registrar_loop_monitor_voz(asyncio.get_running_loop())

    asyncio.create_task(preaquecer_modelo())

    registrar_modulos_padrao()
    watchdog.iniciar()
    log.info("Watchdog iniciado — monitorando IA, áudio, LM Studio e Sentinela")

    lm_manager.iniciar_monitoramento(asyncio.get_running_loop())
    log.info("LM Studio monitoring iniciado")

    iniciar_wake_listener()
    registrar_callback_palma(
        lambda: asyncio.run_coroutine_threadsafe(acao_palma(), loop_engine)
    )
    iniciar_detector()
    registrar_falar_cb(
        lambda t: asyncio.run_coroutine_threadsafe(falar(t), loop_engine)
    )

    threading.Thread(target=iniciar_telegram, daemon=True, name="telegram").start()

    shutdown = get_shutdown_event()
    modo_continuo = False
    ultimo_comando = 0.0
    task_atual: asyncio.Task | None = None

    while not shutdown.is_set():
        try:
            config.recarregar_identidade_painel()

            audio, task_atual = await aguardar_task_ou_barge(task_atual)
            if audio is not None:
                if task_atual is not None:
                    interromper_voz()
                    task_atual.cancel()
                    task_atual = None
            else:
                audio = await ouvir_comando()

            if not audio or not isinstance(audio, str):
                if (
                    modo_continuo
                    and ultimo_comando > 0
                    and (time.time() - ultimo_comando) > SLEEP_TIMEOUT
                ):
                    await falar("Encerrando escuta contínua.")
                    modo_continuo = False
                    ultimo_comando = 0.0
                continue

            ultimo_comando = time.time()

            if modo_continuo:
                ativo, cmd = processar_wake(audio)
                if ativo:
                    if cmd:
                        task_atual = asyncio.create_task(executar(cmd.strip()))
                    continue
                task_atual = asyncio.create_task(executar(audio.strip()))
                continue

            ativo, cmd = processar_wake(audio)
            if not ativo:
                continue

            modo_continuo = True
            if not cmd:
                task_atual = asyncio.create_task(falar(resposta_ativacao_aleatoria()))
                continue

            task_atual = asyncio.create_task(executar(cmd.strip()))
        except Exception as e:
            log.exception("Erro no loop principal")
            await asyncio.sleep(0.3)

    parar_detector()


async def aguardar_task_ou_barge(task: asyncio.Task | None):
    
    if task is None or task.done():
        return None, None
    while not task.done():
        done, _ = await asyncio.wait([task], timeout=0.15)
        if done:
            return None, None
        try:
            audio = barge_cmd.get_nowait()
            if audio:
                return audio, task
        except:
            pass
    return None, None


loop_engine = None


def rodar_engine(ui):
    global loop_engine
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop_engine = loop
    set_loop(loop)

    try:
        gerenciador_alarmes.registrar_callbacks(falar, loop)
    except Exception as e:
        log.warning(f"Aviso ao registrar alarmes: {e}")

    try:
        loop.run_until_complete(loop_principal(ui))
    finally:
        loop.close()


def main():
    painel = PainelCore()
    ui = JarvisUI(painel=painel)
    ui.show()

    thread_engine = threading.Thread(
        target=rodar_engine, args=(ui,), daemon=True, name="engine"
    )
    thread_engine.start()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
