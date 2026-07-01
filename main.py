import os
import sys
import asyncio
import logging
import threading
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

# Configurações
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--no-sandbox --log-level=3"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
os.environ["QT_LOGGING_RULES"] = "qt.qpa.window=false"

# Setup de logs
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("jarvis")

# Importações do projeto
import config
from painel import PainelCore, set_loop
from audio.voz import ouvir_comando, falar
from engine.core import processar_comando, inicializar_ia
from engine.controller import get_shutdown_event
from tasks.monitor import iniciar_sentinela, registrar_loop_monitor_voz
from tasks.alarm import gerenciador_alarmes
from app_ul.interface import JarvisUI
from storage.wake import processar_wake, resposta_ativacao_aleatoria

# Criar aplicação Qt
QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)


async def processar_comando_voz(cmd: str):
    """Processa um comando de voz"""
    try:
        await processar_comando(cmd)
    except Exception as e:
        log.error(f"Erro ao processar: {e}")


async def loop_principal(ui: PainelCore):
    """Loop principal do Jarvis - ouve e processa comandos"""
    
    # Inicializa tudo
    await inicializar_ia()
    iniciar_sentinela()
    registrar_loop_monitor_voz(asyncio.get_running_loop())
    
    # Aguarda sinal de encerramento
    shutdown = get_shutdown_event()
    
    # Loop infinito
    while not shutdown.is_set():
        try:
            # Recarrega config
            config.recarregar_identidade_painel()
            
            # Ouve áudio
            audio = await ouvir_comando()
            if not audio or not isinstance(audio, str):
                await asyncio.sleep(0.1)
                continue
            
            # Verifica se foi ativado
            ativo, cmd = processar_wake(audio)
            if not ativo:
                continue
            
            # Se ativou mas sem comando, fala resposta
            if not cmd:
                await falar(resposta_ativacao_aleatoria())
                continue
            
            # Processa o comando
            await processar_comando_voz(cmd.strip())
            
        except Exception as e:
            log.exception("Erro no loop principal")
            await asyncio.sleep(0.3)


def rodar_engine(ui: PainelCore):
    """Roda o engine em uma thread separada"""
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
    
    # Cria a interface
    ui = PainelCore()
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
