from __future__ import annotations
import json, logging, os, subprocess, webbrowser

log = logging.getLogger("comandos")

caminho_arquivo = "api/custom_commands.json"
cache_comandos: list[dict] = []

def carregar_cache() -> list[dict]:
    global cache_comandos
    if cache_comandos:
        return cache_comandos
    if not os.path.exists(caminho_arquivo):
        return []
    try:
        with open(caminho_arquivo, "r", encoding="utf-8") as f:
            cache_comandos = json.load(f)
            return cache_comandos
    except:
        return []

def salvar_cache(cmd: list[dict]):
    os.makedirs("api", exist_ok=True)
    with open(caminho_arquivo, "w", encoding="utf-8") as f:
        json.dump(cmd, f, indent=2, ensure_ascii=False)
    global cache_comandos
    cache_comandos = cmd

def listar_comandos() -> list[dict]:
    return carregar_cache()

def executar_comando(nome: str) -> str | None:
    cmds = carregar_cache()
    for c in cmds:
        if c.get("nome", "").lower() == nome.lower():
            tipo = c["tipo"]
            valor = c["valor"]
            if tipo == "app":
                try:
                    subprocess.Popen(valor, shell=True)
                    return None
                except:
                    return f"Erro ao abrir {valor}"
            elif tipo == "url":
                webbrowser.open(valor)
                return None
            elif tipo == "comando":
                try:
                    subprocess.Popen(valor, shell=True)
                    return None
                except:
                    return f"Erro ao executar {valor}"
            elif tipo == "fala":
                return valor
    return None

def adicionar_comando(nome: str, tipo: str, valor: str) -> str:
    cmds = carregar_cache()
    for c in cmds:
        if c.get("nome", "").lower() == nome.lower():
            c["tipo"] = tipo
            c["valor"] = valor
            salvar_cache(cmds)
            return f"Comando {nome} atualizado."
    cmds.append({"nome": nome, "tipo": tipo, "valor": valor})
    salvar_cache(cmds)
    return f"Comando {nome} adicionado."

def remover_comando(nome: str) -> str:
    cmds = carregar_cache()
    novos = [c for c in cmds if c.get("nome", "").lower() != nome.lower()]
    if len(novos) == len(cmds):
        return f"Comando {nome} não encontrado."
    salvar_cache(novos)
    return f"Comando {nome} removido."
