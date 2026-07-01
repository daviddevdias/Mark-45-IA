from __future__ import annotations
import os
import sys
import asyncio
import logging
import threading
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

# ===== CONFIGURAÇÕES AMBIENTE =====
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--no-sandbox --log-level=3"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
os.environ["QT_LOGGING_RULES"] = "qt.qpa.window=false"

# ===== SETUP LOGS =====
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("jarvis")
for mod in ["httpx", "httpcore", "telegram", "urllib3"]:
    logging.getLogger(mod).setLevel(logging.WARNING)

# ===== IMPORTAÇÕES DO PROJETO =====
import config
from painel import PainelCore, set_loop
from audio.voz import ouvir_comando, falar
from engine.core import processar_comando, inicializar_ia
from engine.controller import get_shutdown_event
from tasks.monitor import iniciar_sentinela, registrar_loop_monitor_voz
from tasks.alarm import gerenciador_alarmes
from tasks.wake import processar_wake, resposta_ativacao_aleatoria
from app_ul.interface import JarvisUI
from integrations.telegram_bridge_auth_patch import iniciar_telegram

# ===== APLICAÇÃO QT =====
QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)


async def executar(cmd: str):
    """Executa um comando de voz"""
    try:
        await processar_comando(cmd)
    except Exception as e:
        log.error(f"Erro ao processar: {e}")


async def loop_principal(ui: PainelCore):
    """
    Loop principal do Jarvis.
    - Ouve áudio
    - Detecta ativação
    - Processa comandos
    """
    # Inicializa componentes
    await inicializar_ia()
    iniciar_sentinela()
    registrar_loop_monitor_voz(asyncio.get_running_loop())
    
    # Inicia telegram em thread separada
    threading.Thread(target=iniciar_telegram, daemon=True, name="telegram").start()
    
    # Aguarda sinal de encerramento
    shutdown = get_shutdown_event()
    
    # Loop infinito
    while not shutdown.is_set():
        try:
            # Recarrega configuração
            config.recarregar_identidade_painel()
            
            # Ouve áudio do usuário
            audio = await ouvir_comando()
            if not audio or not isinstance(audio, str):
                await asyncio.sleep(0.1)
                continue
            
            # Verifica se foi ativado (wake word + comando)
            ativo, cmd = processar_wake(audio)
            if not ativo:
                continue
            
            # Se ativou sem comando, responde aleatoriamente
            if not cmd:
                await falar(resposta_ativacao_aleatoria())
                continue
            
            # Processa o comando
            await executar(cmd.strip())
            
        except Exception as e:
            log.exception("Erro no loop principal")
            await asyncio.sleep(0.3)


def rodar_engine(ui: PainelCore):
    """
    Roda o engine em uma thread separada.
    Cria um novo event loop assíncrono.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    set_loop(loop)
    
    try:
        # Registra callbacks dos alarmes
        gerenciador_alarmes.registrar_callbacks(falar, loop)
    except Exception as e:
        log.warning(f"Aviso ao registrar alarmes: {e}")
    
    try:
        loop.run_until_complete(loop_principal(ui))
    finally:
        loop.close()


def main():
    """Função principal - inicia tudo"""
    
    # Cria a interface gráfica
    ui = JarvisUI()
    ui.show()
    
    # Inicia o engine em uma thread separada
    thread_engine = threading.Thread(
        target=rodar_engine,
        args=(ui,),
        daemon=True,
        name="engine"
    )
    thread_engine.start()
    
    # Inicia a aplicação Qt
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
