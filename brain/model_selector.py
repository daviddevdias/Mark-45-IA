from __future__ import annotations

import re
import logging
from dataclasses import dataclass
from enum import Enum

log = logging.getLogger("jarvis.model_selector")

class NivelModelo(Enum):
    RAPIDO        = "rapido"
    INTERMEDIARIO = "intermediario"
    PESADO        = "pesado"

@dataclass
class PerfilModelo:
    nome:          str
    nivel:         NivelModelo
    max_tokens:    int
    adequado_para: list[str]

PERFIS: dict[str, PerfilModelo] = {
    "phi3":             PerfilModelo("phi3",             NivelModelo.RAPIDO,        512,  ["saudacao", "comando_simples", "status"]),
    "llama3":           PerfilModelo("llama3",           NivelModelo.INTERMEDIARIO, 1024, ["busca", "clima", "spotify", "app"]),
    "qwen/qwen2.5-vl-72b-instruct": PerfilModelo("qwen/qwen2.5-vl-72b-instruct", NivelModelo.PESADO,        2048, ["visao", "codigo", "plano", "analise", "agente"]),
}

RAPIDO_REGEX = re.compile(
    r"^(oi|ol[aá]|ei|ok|sim|n[aã]o|obrigado|tchau|status|volume|parar|continuar|"
    r"pr[oó]xim[ao]|anterior|pausar|ligar|desligar|hora|data)\b",
    re.IGNORECASE,
)
PESADO_REGEX = re.compile(
    r"(codi(go|ficar)|progra(mar|me)|an[aá]l(ise|isa)|plan(eja|o|ejar)|"
    r"expli(que|ca)|resumo|resumir|complexo|detalh|escreva|cri(e|ar)|desenvolv|arquitetura|debug)",
    re.IGNORECASE,
)
VISAO_REGEX = re.compile(
    r"(tela|ecr[aã]|imagem|foto|captur|veja|olh(e|a)|vis[aã]o|mostr[ae])",
    re.IGNORECASE,
)

def modelos_ollama() -> set[str]:
    try:
        import requests
        r = requests.get("http://127.0.0.1:11434/api/tags", timeout=1)
        if r.status_code == 200:
            return {m["name"] for m in r.json().get("models", [])}

    except Exception:
        pass
    return set()

def modelo_rapido(modelos: set[str]):
    for c in ("phi3:mini", "phi3", "llama3:8b", "llama3"):
        if c in modelos:
            return c

    return None

def modelo_atual():
    try:
        from engine.ia_router import modelo as m
        return m or "qwen/qwen2.5-vl-72b-instruct"
    except Exception:
        return "qwen/qwen2.5-vl-72b-instruct"

def complexidade_heuristica(comando: str) -> float:
    palavras = comando.split()
    n = len(palavras)
    if n == 0:
        return 0.0

    comprimento_score = min(n / 20, 1.0)
    densidade_score   = len(set(palavras)) / n
    punct_score       = min(comando.count(",") / 3, 1.0)

    return round((comprimento_score * 0.5 + densidade_score * 0.3 + punct_score * 0.2), 3)

def escolher_modelo(contexto: dict):
    comando       = contexto.get("comando", "")
    tem_imagem    = bool(contexto.get("imagem"))
    forcado       = contexto.get("modelo_forcado", "")
    historico_len = contexto.get("historico_len", 0)

    if forcado and forcado in PERFIS:
        return forcado

    if tem_imagem or VISAO_REGEX.search(comando):
        return "qwen/qwen2.5-vl-72b-instruct"

    if PESADO_REGEX.search(comando):
        return modelo_atual()

    complexidade = complexidade_heuristica(comando)
    if complexidade >= 0.65 or historico_len > 10:
        return modelo_atual()

    if RAPIDO_REGEX.match(comando.strip()) and historico_len < 3:
        rapido = modelo_rapido(modelos_ollama())
        if rapido:
            return rapido

    return modelo_atual()

def nivel_do_modelo(nome: str) -> NivelModelo:
    if nome in PERFIS:
        return PERFIS[nome].nivel

    if "phi" in nome.lower():
        return NivelModelo.RAPIDO

    if any(s in nome.lower() for s in ("llama3", "mistral")):
        return NivelModelo.INTERMEDIARIO

    return NivelModelo.PESADO