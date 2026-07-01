from __future__ import annotations
import json, logging, os, time
from datetime import datetime, date

import config

log = logging.getLogger("calendario")

caminho_arquivo = "api/eventos_calendario.json"
cache_eventos: list[dict] = []

def obter_caminho_ics():
    caminho = getattr(config, "CALENDAR_ICS_PATH", "")
    return caminho if caminho and os.path.isfile(caminho) else None

def carregar_eventos() -> list[dict]:
    global cache_eventos
    if cache_eventos:
        return cache_eventos
    eventos = []
    if os.path.exists(caminho_arquivo):
        try:
            with open(caminho_arquivo, "r", encoding="utf-8") as f:
                eventos = json.load(f)
        except:
            eventos = []
    caminho_ics = obter_caminho_ics()
    if caminho_ics:
        try:
            with open(caminho_ics, "r", encoding="utf-8") as f:
                import re as _re
                ical = f.read()
                vevents = _re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", ical, _re.DOTALL)
                for v in vevents:
                    dtstart = _re.search(r"DTSTART[;:](\d{8})", v)
                    summary = _re.search(r"SUMMARY:(.*)", v)
                    if dtstart and summary:
                        data = dtstart.group(1)
                        data_fmt = f"{data[:4]}-{data[4:6]}-{data[6:8]}"
                        eventos.append({
                            "titulo": summary.group(1).strip(),
                            "data": data_fmt,
                            "hora": "",
                            "fonte": "ics",
                        })
        except Exception as e:
            log.warning(f"Erro ao ler ICS: {e}")
    cache_eventos = eventos
    return eventos

def salvar_eventos(eventos: list[dict]):
    os.makedirs("api", exist_ok=True)
    with open(caminho_arquivo, "w", encoding="utf-8") as f:
        json.dump(eventos, f, indent=2, ensure_ascii=False)
    global cache_eventos
    cache_eventos = eventos

def obter_eventos(data: str | None = None) -> list[dict]:
    eventos = carregar_eventos()
    if data:
        return [e for e in eventos if e.get("data") == data]
    return eventos

def adicionar_evento(titulo: str, data: str, hora: str = "") -> str:
    eventos = carregar_eventos()
    eventos.append({
        "titulo": titulo,
        "data": data,
        "hora": hora,
        "fonte": "voz",
    })
    salvar_eventos(eventos)
    return f"Evento {titulo} adicionado em {data}."

def eventos_para_fala(data: str | None = None) -> str:
    hoje = data or date.today().isoformat()
    eventos = obter_eventos(hoje)
    if not eventos:
        return f"Nenhum evento para {hoje}."
    partes = [f"{e['titulo']} às {e['hora']}" if e.get("hora") else e["titulo"] for e in eventos]
    return f"Eventos de {hoje}: " + " | ".join(partes)
