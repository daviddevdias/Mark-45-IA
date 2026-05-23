from __future__ import annotations

import asyncio
import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Any

import config

log = logging.getLogger("memory")

trava_memoria = RLock()

MAX_VALUE_LEN: int = 400

memoria_cache: dict | None = None

def pasta_raiz_app() -> Path:
    return Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent

MEMORY_PATH: Path = pasta_raiz_app() / "api" / "long_term.json"

def estrutura_memoria_vazia() -> dict:
    return {
        "identity": {"mestre": {"value": ""}},
        "preferences": {"cidade": {"value": ""}},
        "projects": {},
        "relationships": {},
        "wishes": {},
        "notes": {},
    }

def load_memory(force: bool = False) -> dict:
    global memoria_cache

    with trava_memoria:
        if memoria_cache is not None and not force:
            return memoria_cache

        if not MEMORY_PATH.exists():
            memoria_cache = estrutura_memoria_vazia()
            return memoria_cache

        try:
            data = json.loads(MEMORY_PATH.read_text(encoding="utf-8"))

            if not isinstance(data, dict):
                memoria_cache = estrutura_memoria_vazia()
                return memoria_cache

            base = estrutura_memoria_vazia()
            for k, v in base.items():
                data.setdefault(k, v)

            memoria_cache = data
            return memoria_cache

        except Exception:
            memoria_cache = estrutura_memoria_vazia()
            return memoria_cache

def save_memory(memory: dict):
    global memoria_cache

    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = MEMORY_PATH.with_suffix(".tmp")

    with trava_memoria:
        serializado = json.dumps(memory, indent=2, ensure_ascii=False)
        tmp.write_text(serializado, encoding="utf-8")
        tmp.replace(MEMORY_PATH)
        memoria_cache = json.loads(serializado)

def invalidate_cache():
    global memoria_cache
    with trava_memoria:
        memoria_cache = None

def get_nome():
    cfg_n = (getattr(config, "NOME_MESTRE", None) or "").strip()
    if cfg_n:
        return cfg_n
    v = load_memory().get("identity", {}).get("mestre", {}).get("value", "")
    return (v or "").strip() or "Usuário"

def get_cidade():
    cp = (getattr(config, "cidade_padrao", None) or "").strip()
    if cp:
        return cp
    return load_memory().get("preferences", {}).get("cidade", {}).get("value", "") or ""

def get_value(category: str, key: str, default: Any = None) -> Any:
    node = load_memory().get(category, {}).get(key, {})
    if isinstance(node, dict):
        return node.get("value", default)
    return node or default

def format_memory_for_prompt():
    mem = load_memory()
    out = ["[MEMORIA DO USUARIO]"]

    for cat, items in mem.items():
        if not isinstance(items, dict):
            continue
        out.append(f"\n{cat.upper()}:")
        for k, v in items.items():
            val = v.get("value") if isinstance(v, dict) else v
            out.append(f"  - {k}: {val}")

    return "\n".join(out)

def aplicar_patch_memoria(target: dict, updates: dict) -> bool:
    changed = False
    today = datetime.now().strftime("%Y-%m-%d")

    for key, value in updates.items():
        if value is None:
            continue

        if isinstance(value, dict) and "value" not in value:
            target.setdefault(key, {})
            if aplicar_patch_memoria(target[key], value):
                changed = True
        else:
            raw = value.get("value") if isinstance(value, dict) else value
            new = str(raw)[:MAX_VALUE_LEN].strip()
            old = target.get(key, {}).get("value") if isinstance(target.get(key), dict) else None

            if old != new:
                target[key] = {"value": new, "updated": today}
                changed = True

    return changed

def update_memory(patch: dict) -> dict:
    if not isinstance(patch, dict) or not patch:
        return load_memory()

    with trava_memoria:
        mem = load_memory(force=True)
        if aplicar_patch_memoria(mem, patch):
            save_memory(mem)
        return mem

LISTA_CATEGORIAS_MEMORIA = "identity, preferences, projects, relationships, wishes, notes"
TEXTO_PROMPT_EXTRACAO = "Extraia fatos da conversa e retorne apenas JSON:\n"

def json_da_resposta_ia(raw: str) -> dict | None:
    try:
        return json.loads(raw)
    except Exception:
        match = re.search(r"\{[\s\S]*\}", raw)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                return None
    return None

async def process_memory_logic(user_text: str, core_text: str):
    try:
        from engine.ia_router import router

        prompt = (
            f"{TEXTO_PROMPT_EXTRACAO}{LISTA_CATEGORIAS_MEMORIA}\n\n"
            f"Usuário disse: {user_text}\n"
            f"Assistente respondeu: {core_text}"
        )
        resposta = await router.responder(prompt)
        patch = json_da_resposta_ia(resposta)

        categorias_validas = set(estrutura_memoria_vazia().keys())
        if patch and isinstance(patch, dict):
            patch_filtrado = {k: v for k, v in patch.items() if k in categorias_validas}
            if patch_filtrado:
                update_memory(patch_filtrado)

    except Exception:
        pass