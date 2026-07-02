from __future__ import annotations

import os
import shutil
import subprocess
import webbrowser
from pathlib import Path

import psutil


SYSTEM_ROOT = Path(os.environ.get("SystemRoot", r"C:\Windows"))
PROGRAM_FILES = [Path(p) for p in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")) if p]
LOCAL_APP_DATA = Path(os.environ.get("LOCALAPPDATA", ""))
USER_PROFILE = Path(os.path.expanduser("~"))


APP_ALIASES: dict[str, str] = {
    "whatsapp": "whatsapp:",
    "chrome": "chrome.exe",
    "google": "chrome.exe",
    "firefox": "firefox.exe",
    "spotify": "spotify:",
    "vscode": "code",
    "visual studio code": "code",
    "discord": "discord.exe",
    "telegram": "telegram.exe",
    "instagram": "https://instagram.com",
    "tiktok": "https://tiktok.com",
    "notepad": "notepad.exe",
    "bloco de notas": "notepad.exe",
    "calculator": "calc.exe",
    "calculadora": "calc.exe",
    "cmd": "cmd.exe",
    "terminal": "wt.exe",
    "powershell": "powershell.exe",
    "explorer": "explorer.exe",
    "arquivos": "explorer.exe",
    "paint": "mspaint.exe",
    "word": "winword.exe",
    "excel": "excel.exe",
    "powerpoint": "powerpnt.exe",
    "vlc": "vlc.exe",
    "zoom": "zoom.exe",
    "slack": "slack.exe",
    "steam": "steam.exe",
    "task manager": "taskmgr.exe",
    "gerenciador de tarefas": "taskmgr.exe",
    "settings": "ms-settings:",
    "configuracoes": "ms-settings:",
    "configurações": "ms-settings:",
    "edge": "msedge.exe",
    "brave": "brave.exe",
    "postman": "postman.exe",
    "figma": "https://figma.com",
}


COMMON_APP_PATHS = {
    "chrome.exe": [
        r"Google\Chrome\Application\chrome.exe",
    ],
    "msedge.exe": [
        r"Microsoft\Edge\Application\msedge.exe",
    ],
    "brave.exe": [
        r"BraveSoftware\Brave-Browser\Application\brave.exe",
    ],
    "firefox.exe": [
        r"Mozilla Firefox\firefox.exe",
    ],
    "code": [
        r"Microsoft VS Code\Code.exe",
        r"Programs\Microsoft VS Code\Code.exe",
    ],
    "discord.exe": [
        r"Discord\Update.exe",
    ],
    "telegram.exe": [
        r"Telegram Desktop\Telegram.exe",
        r"Programs\Telegram Desktop\Telegram.exe",
    ],
    "spotify.exe": [
        r"Spotify\Spotify.exe",
    ],
    "zoom.exe": [
        r"Zoom\bin\Zoom.exe",
    ],
    "slack.exe": [
        r"slack\slack.exe",
    ],
    "postman.exe": [
        r"Postman\Postman.exe",
    ],
}


def _normalizar_nome(nome: str) -> str:
    return nome.lower().strip().replace(".exe", "")


def verificar_processo(app: str) -> bool:
    alvo = _normalizar_nome(Path(app).name)
    if not alvo:
        return False
    for proc in psutil.process_iter(["name", "exe"]):
        try:
            nome = _normalizar_nome(proc.info.get("name") or "")
            exe = _normalizar_nome(Path(proc.info.get("exe") or "").name)
            if alvo in {nome, exe} or alvo in nome or alvo in exe:
                return True
        except (psutil.Error, OSError, ValueError):
            continue
    return False


def padronizar(raw: str) -> str:
    chave = raw.lower().strip()
    if chave in APP_ALIASES:
        return APP_ALIASES[chave]
    for alias, comando in APP_ALIASES.items():
        if alias in chave or chave in alias:
            return comando
    return raw.strip()


def _candidatos_caminho(comando: str) -> list[Path]:
    candidatos: list[Path] = []
    nome = Path(comando).name

    if not nome:
        return candidatos

    for base in PROGRAM_FILES:
        for rel in COMMON_APP_PATHS.get(nome.lower(), []):
            candidatos.append(base / rel)

    if LOCAL_APP_DATA:
        for rel in COMMON_APP_PATHS.get(nome.lower(), []):
            candidatos.append(LOCAL_APP_DATA / rel)

    candidatos.extend(
        [
            SYSTEM_ROOT / "System32" / nome,
            SYSTEM_ROOT / nome,
            USER_PROFILE / "AppData" / "Local" / "Microsoft" / "WindowsApps" / nome,
        ]
    )
    return candidatos


def _abrir_url_ou_uri(comando: str) -> bool:
    if comando.startswith(("http://", "https://")):
        webbrowser.open(comando)
        return True
    if ":" in comando and " " not in comando and not Path(comando).drive:
        os.startfile(comando)  [attr-defined]
        return True
    return False


def disparar(app: str) -> bool:
    comando = app.strip()
    if not comando:
        return False

    try:
        if _abrir_url_ou_uri(comando):
            return True
    except OSError:
        pass

    partes = comando.split()
    exe = partes[0]
    args = partes[1:]

    localizado = shutil.which(exe)
    if localizado:
        subprocess.Popen([localizado, *args], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True

    caminho = Path(exe).expanduser()
    if caminho.exists():
        subprocess.Popen([str(caminho), *args], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True

    for candidato in _candidatos_caminho(exe):
        if candidato.exists():
            cmd = [str(candidato), *args]
            if candidato.name.lower() == "update.exe" and "discord" in str(candidato).lower():
                cmd.extend(["--processStart", "Discord.exe"])
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True

    try:
        os.startfile(comando)  [attr-defined]
        return True
    except OSError:
        return False


def open_app(params=None, **kwargs):
    app = (params or {}).get("app_name", "").strip()
    if not app:
        return "Qual aplicativo?"

    norm = padronizar(app)
    processo = Path(norm).name or app
    if processo and processo.endswith(".exe") and verificar_processo(processo):
        return f"{app} já está ativo."

    sucesso = disparar(norm)
    if not sucesso and norm != app:
        sucesso = disparar(app)
    return f"{app} iniciado." if sucesso else "Atalho não localizado no Windows."
