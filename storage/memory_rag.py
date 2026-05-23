from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sqlite3
import time
import unicodedata
from dataclasses import dataclass
from typing import Any

log = logging.getLogger("jarvis.memory_rag")

DB_PATH   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "rag_memory.db")
MAX_CURTA = 20
SCORE_MIN = 0.25

@dataclass
class MemoriaItem:
    id:       int
    tipo:     str
    chave:    str
    valor:    str
    contexto: str
    score:    float = 0.0
    ts:       float = 0.0

def conectar() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    c = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=5)
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA synchronous=NORMAL;")
    c.row_factory = sqlite3.Row
    c.execute("""
        CREATE TABLE IF NOT EXISTS memoria (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo          TEXT NOT NULL,
            chave         TEXT NOT NULL,
            valor         TEXT NOT NULL,
            contexto      TEXT DEFAULT '',
            acessos       INTEGER DEFAULT 0,
            criado_em     REAL NOT NULL,
            atualizado_em REAL NOT NULL
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_tipo  ON memoria(tipo)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_chave ON memoria(chave)")
    c.commit()
    return c

def normalizar_texto(texto: str) :
    t = unicodedata.normalize("NFD", texto.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", t).strip()

def tokenizar(texto: str) -> set[str]:
    return set(re.findall(r"\b\w{3,}\b", normalizar_texto(texto)))

def calcular_score(query_tokens: set[str], valor: str, contexto: str) -> float:
    item_tokens = tokenizar(valor) | tokenizar(contexto)
    if not item_tokens:
        return 0.0
    intersecao = query_tokens & item_tokens
    return len(intersecao) / max(len(query_tokens), 1)

class MemoriaRAG:

    def __init__(self):
        self.curta: list[dict] = []

    def salvar(self, tipo: str, chave: str, valor: str, contexto: str = ""):
        agora = time.time()
        try:
            with conectar() as c:
                existente = c.execute(
                    "SELECT id FROM memoria WHERE tipo=? AND chave=?", (tipo, chave)
                ).fetchone()
                if existente:
                    c.execute(
                        "UPDATE memoria SET valor=?, contexto=?, atualizado_em=? WHERE id=?",
                        (valor[:2000], contexto[:500], agora, existente["id"]),
                    )
                else:
                    c.execute(
                        "INSERT INTO memoria (tipo, chave, valor, contexto, criado_em, atualizado_em) "
                        "VALUES (?,?,?,?,?,?)",
                        (tipo, chave[:200], valor[:2000], contexto[:500], agora, agora),
                    )
                c.commit()
        except Exception as exc:
            log.error("RAG salvar: %s", exc)

        self.curta.append({"tipo": tipo, "chave": chave, "valor": valor, "ts": agora})
        if len(self.curta) > MAX_CURTA:
            self.curta = self.curta[-MAX_CURTA:]

    def registrar_interacao(self, comando: str, resposta: str):
        chave = hashlib.md5(comando.encode()).hexdigest()[:12]
        self.salvar("interacao", chave, resposta[:1000], contexto=comando[:300])

    def buscar(self, query: str, tipo: str | None = None, limite: int = 5) -> list[MemoriaItem]:
        tokens = tokenizar(query)
        if not tokens:
            return []

        resultados: list[MemoriaItem] = []

        for item in reversed(self.curta[-MAX_CURTA:]):
            if tipo and item["tipo"] != tipo:
                continue
            score = calcular_score(tokens, item["valor"], item.get("contexto", ""))
            if score >= SCORE_MIN:
                resultados.append(MemoriaItem(
                    id=0, tipo=item["tipo"], chave=item["chave"],
                    valor=item["valor"], contexto=item.get("contexto", ""),
                    score=score + 0.1, ts=item["ts"],
                ))

        try:
            with conectar() as c:
                filtro = "WHERE tipo=?" if tipo else ""
                params = (tipo,) if tipo else ()
                rows = c.execute(
                    f"SELECT id, tipo, chave, valor, contexto, atualizado_em FROM memoria {filtro} "
                    "ORDER BY atualizado_em DESC LIMIT 100",
                    params,
                ).fetchall()
                for row in rows:
                    score = calcular_score(tokens, row["valor"], row["contexto"] or "")
                    if score >= SCORE_MIN:
                        resultados.append(MemoriaItem(
                            id=row["id"], tipo=row["tipo"], chave=row["chave"],
                            valor=row["valor"], contexto=row["contexto"] or "",
                            score=score, ts=row["atualizado_em"],
                        ))
                        c.execute("UPDATE memoria SET acessos = acessos + 1 WHERE id=?", (row["id"],))
                c.commit()
        except Exception as exc:
            log.error("RAG buscar: %s", exc)

        vistos: set[str] = set()
        unicos: list[MemoriaItem] = []
        for item in sorted(resultados, key=lambda x: (x.score, x.ts), reverse=True):
            sig = f"{item.tipo}:{item.chave}"
            if sig not in vistos:
                vistos.add(sig)
                unicos.append(item)
            if len(unicos) >= limite:
                break
        return unicos

    def contexto_para_prompt(self, query: str, max_chars: int = 800) :
        itens = self.buscar(query, limite=4)
        if not itens:
            return ""
        partes = []
        total  = 0
        for item in itens:
            trecho = f"[{item.tipo}] {item.chave}: {item.valor}"[:200]
            if total + len(trecho) > max_chars:
                break
            partes.append(trecho)
            total += len(trecho)
        return "\n".join(partes)

    def salvar_preferencia(self, chave: str, valor: str):
        self.salvar("preferencia", chave, valor)

    def get_preferencia(self, chave: str, default: str = "") :
        try:
            with conectar() as c:
                row = c.execute(
                    "SELECT valor FROM memoria WHERE tipo='preferencia' AND chave=?", (chave,)
                ).fetchone()
                return row["valor"] if row else default
        except Exception:
            return default

    def purgar_antigos(self, dias: int = 30) -> int:
        limite = time.time() - dias * 86400
        try:
            with conectar() as c:
                cur = c.execute(
                    "DELETE FROM memoria WHERE tipo='interacao' AND atualizado_em < ?", (limite,)
                )
                c.commit()
                return cur.rowcount
        except Exception:
            return 0

rag = MemoriaRAG()