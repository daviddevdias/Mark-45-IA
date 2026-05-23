from __future__ import annotations

import logging
import os
import platform

log = logging.getLogger("jarvis.computer_control")

SISTEMA = platform.system()


def fechar_janela_ativa() -> str:
    try:
        import pyautogui

        pyautogui.hotkey("alt", "f4")
        log.info("Janela ativa fechada via Alt+F4.")
        return "Janela fechada com sucesso."

    except ImportError:
        log.warning("pyautogui não encontrado. Tentando via keyboard...")
        try:
            import keyboard
            keyboard.press_and_release("alt+f4")
            return "Janela fechada."
        except Exception as erro:
            log.error("Erro ao fechar janela: %s", erro)
            return f"Não consegui fechar a janela: {erro}"

    except Exception as erro:
        log.error("Erro inesperado ao fechar janela: %s", erro)
        return f"Erro ao fechar janela: {erro}"


def mutar_volume() -> str:
    try:
        import pyautogui
        pyautogui.press("volumemute")
        log.info("Volume alternado (mute/unmute).")
        return "Volume alternado."
    except Exception as erro:
        log.error("Erro ao mutar volume: %s", erro)
        return f"Erro ao mutar volume: {erro}"


def bloquear_tela() -> str:
    try:
        if SISTEMA == "Windows":
            import ctypes
            ctypes.windll.user32.LockWorkStation()

        elif SISTEMA == "Linux":
            os.system("loginctl lock-session")

        elif SISTEMA == "Darwin":
            os.system('/System/Library/CoreServices/Menu\\ Extras/User.menu/Contents/Resources/CGSession -suspend')

        log.info("Tela bloqueada.")
        return "Tela bloqueada."

    except Exception as erro:
        log.error("Erro ao bloquear tela: %s", erro)
        return f"Erro ao bloquear tela: {erro}"


def minimizar_janelas() -> str:
    try:
        import pyautogui

        if SISTEMA == "Windows":
            pyautogui.hotkey("win", "d")
        elif SISTEMA == "Linux":
            pyautogui.hotkey("super", "d")
        elif SISTEMA == "Darwin":
            pyautogui.hotkey("command", "m")

        log.info("Janelas minimizadas.")
        return "Janelas minimizadas."

    except Exception as erro:
        log.error("Erro ao minimizar janelas: %s", erro)
        return f"Erro ao minimizar: {erro}"


def print_tela() -> str:
    try:
        import pyautogui
        from datetime import datetime

        nome_arquivo = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"

        pasta_desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        caminho = os.path.join(pasta_desktop, nome_arquivo)

        pyautogui.screenshot(caminho)
        log.info("Screenshot salvo em: %s", caminho)
        return f"Screenshot salvo em: {caminho}"

    except Exception as erro:
        log.error("Erro ao tirar screenshot: %s", erro)
        return f"Erro ao tirar screenshot: {erro}"


def limpar_lixeira() -> str:
    try:
        if SISTEMA == "Windows":
            import winshell
            winshell.recycle_bin().empty(confirm=False, show_progress=False, sound=False)

        elif SISTEMA == "Linux":
            import shutil
            pasta_lixo = os.path.expanduser("~/.local/share/Trash")
            if os.path.exists(pasta_lixo):
                shutil.rmtree(pasta_lixo)
                os.makedirs(pasta_lixo)

        elif SISTEMA == "Darwin":
            os.system("rm -rf ~/.Trash/*")

        log.info("Lixeira esvaziada.")
        return "Lixeira esvaziada."

    except ImportError:
        log.warning("winshell não encontrado. Tentando via PowerShell...")
        try:
            os.system('powershell -command "Clear-RecycleBin -Force"')
            return "Lixeira esvaziada via PowerShell."
        except Exception as erro:
            return f"Erro ao limpar lixeira: {erro}"

    except Exception as erro:
        log.error("Erro ao limpar lixeira: %s", erro)
        return f"Erro ao limpar lixeira: {erro}"


def computer_settings(argumentos: dict) -> str:
    acao = argumentos.get("action", "status").lower()

    if acao == "fechar":
        return fechar_janela_ativa()

    elif acao == "minimizar_tudo":
        return minimizar_janelas()

    elif acao in ("print", "screenshot"):
        return print_tela()

    elif acao == "bloqueio":
        return bloquear_tela()

    elif acao == "limpar":
        return limpar_lixeira()

    elif acao == "volume":
        nivel = argumentos.get("nivel", 50)
        return _ajustar_volume(nivel)

    elif acao == "mutar":
        return mutar_volume()

    elif acao == "type":
        texto = argumentos.get("text", "")
        return _digitar_texto(texto)

    elif acao == "hotkey":
        teclas = argumentos.get("keys", "")
        return _pressionar_atalho(teclas)

    elif acao == "status":
        return "Sistema operacional online e funcional."

    else:
        return f"Ação '{acao}' não reconhecida. Ações disponíveis: fechar, minimizar_tudo, print, bloqueio, limpar, volume, mutar, type, hotkey, status."


def _ajustar_volume(nivel: int) -> str:
    try:
        nivel = max(0, min(100, int(nivel)))

        if SISTEMA == "Windows":
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            volume.SetMasterVolumeLevelScalar(nivel / 100.0, None)

        elif SISTEMA == "Linux":
            os.system(f"amixer sset Master {nivel}%")

        elif SISTEMA == "Darwin":
            os.system(f"osascript -e 'set volume output volume {nivel}'")

        return f"Volume ajustado para {nivel}%."

    except Exception as erro:
        log.error("Erro ao ajustar volume: %s", erro)
        return f"Erro ao ajustar volume: {erro}"


def _digitar_texto(texto: str) -> str:
    if not texto:
        return "Nenhum texto para digitar."
    try:
        import pyautogui
        pyautogui.write(texto, interval=0.05)
        return f"Texto '{texto[:30]}...' digitado." if len(texto) > 30 else f"Texto '{texto}' digitado."
    except Exception as erro:
        return f"Erro ao digitar texto: {erro}"


def _pressionar_atalho(teclas: str) -> str:
    if not teclas:
        return "Nenhum atalho especificado."
    try:
        import pyautogui
        partes = [t.strip() for t in teclas.split("+")]
        pyautogui.hotkey(*partes)
        return f"Atalho '{teclas}' executado."
    except Exception as erro:
        return f"Erro ao executar atalho '{teclas}': {erro}"