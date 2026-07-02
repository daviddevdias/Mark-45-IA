from __future__ import annotations

import ctypes
import os
from datetime import datetime
from pathlib import Path


def _pictures_dir() -> Path:
    pasta = Path(os.path.expanduser("~")) / "Pictures" / "Screenshots"
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def _pyautogui():
    try:
        import pyautogui

        pyautogui.FAILSAFE = False
        return pyautogui
    except Exception:
        return None


def _normalizar_hotkey(keys: str) -> list[str]:
    mapa = {
        "ctrl": "ctrl",
        "control": "ctrl",
        "shift": "shift",
        "alt": "alt",
        "win": "win",
        "windows": "win",
        "super": "win",
        "enter": "enter",
        "return": "enter",
        "esc": "esc",
        "escape": "esc",
        "del": "delete",
    }
    partes = [p.strip().lower() for p in keys.replace("+", " ").split() if p.strip()]
    return [mapa.get(p, p) for p in partes]


def mutar_volume():
    pg = _pyautogui()
    if pg:
        pg.press("volumemute")


def definir_volume(nivel: int):
    pg = _pyautogui()
    if not pg:
        return
    nivel = max(0, min(100, int(nivel)))
    pg.press("volumedown", presses=50)
    if nivel:
        pg.press("volumeup", presses=max(1, round(nivel / 2)))


def bloquear_tela():
    ctypes.windll.user32.LockWorkStation()


def minimizar_janelas():
    pg = _pyautogui()
    if pg:
        pg.hotkey("win", "d")


def fechar_janela_ativa():
    pg = _pyautogui()
    if pg:
        pg.hotkey("alt", "f4")


def print_tela():
    destino = _pictures_dir() / f"screenshot_{datetime.now():%Y%m%d_%H%M%S}.png"
    try:
        from PIL import ImageGrab

        ImageGrab.grab(all_screens=True).save(destino)
        return str(destino)
    except Exception:
        pg = _pyautogui()
        if pg:
            pg.screenshot(str(destino))
            return str(destino)
    return ""


def limpar_lixeira():
    try:
        ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 0x00000001 | 0x00000002 | 0x00000004)
    except Exception:
        pass


def digitar_texto(texto: str):
    pg = _pyautogui()
    if pg:
        pg.write(texto, interval=0.01)


def pressionar_hotkey(keys: str):
    pg = _pyautogui()
    normalizadas = _normalizar_hotkey(keys)
    if pg and normalizadas:
        pg.hotkey(*normalizadas)


def computer_settings(args: dict):
    acao = str(args.get("action", "")).lower().strip()
    if acao == "fechar":
        fechar_janela_ativa()
        return "Janela ativa fechada."
    if acao == "minimizar_tudo":
        minimizar_janelas()
        return "Janelas minimizadas."
    if acao == "print":
        caminho = print_tela()
        return f"Screenshot salva em {caminho}." if caminho else "Não consegui capturar a tela."
    if acao == "bloqueio":
        bloquear_tela()
        return "Tela bloqueada."
    if acao == "limpar":
        limpar_lixeira()
        return "Lixeira limpa."
    if acao == "volume":
        definir_volume(args.get("nivel", 50))
        return f"Volume ajustado para {args.get('nivel', 50)}%."
    if acao == "mute":
        mutar_volume()
        return "Mute alternado."
    if acao == "type":
        texto = args.get("text", "")
        if texto:
            digitar_texto(str(texto))
            return "Texto digitado."
        return "Texto vazio."
    if acao == "hotkey":
        keys = args.get("keys", "")
        if keys:
            pressionar_hotkey(str(keys))
            return "Atalho enviado."
        return "Atalho vazio."
    return "Ação de computador não reconhecida."
