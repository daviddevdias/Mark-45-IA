from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from dataclasses import dataclass, field, asdict
from typing import Any

_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "observability.db")
log = logging.getLogger("jarvis.obs")

def conectar_banco() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
    c = sqlite3.connect(_DB_PATH, check_same_thread=False, timeout=5)
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA synchronous=NORMAL;")
    c.row_factory = sqlite3.Row
    c.execute("""
        CREATE TABLE IF NOT EXISTS acoes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ts          REAL    NOT NULL,
            tipo        TEXT    NOT NULL,
            modulo      TEXT    DEFAULT '',
            descricao   TEXT    DEFAULT '',
            duracao_ms  INTEGER DEFAULT 0,
            sucesso     INTEGER DEFAULT 1,
            dados_json  TEXT    DEFAULT '{}'
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS metricas (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            ts      REAL    NOT NULL,
            nome    TEXT    NOT NULL,
            valor   REAL    NOT NULL,
            unidade TEXT    DEFAULT ''
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_acoes_tipo ON acoes(tipo)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_acoes_ts   ON acoes(ts)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_metricas_nome ON metricas(nome)")
    c.commit()
    return c

def registrar_acao(
    tipo: str,
    descricao: str = "",
    modulo: str = "",
    duracao_ms: int = 0,
    sucesso: bool = True,
    dados: dict | None = None,
):
    try:
        with conectar_banco() as c:
            c.execute(
                "INSERT INTO acoes (ts, tipo, modulo, descricao, duracao_ms, sucesso, dados_json) "
                "VALUES (?,?,?,?,?,?,?)",
                (
                    time.time(),
                    tipo,
                    modulo,
                    descricao[:300],
                    duracao_ms,
                    int(sucesso),
                    json.dumps(dados or {}, default=str),
                ),
            )
            c.commit()
    except Exception as exc:
        log.debug("obs registrar_acao: %s", exc)

def registrar_metrica(nome: str, valor: float, unidade: str = ""):
    try:
        with conectar_banco() as c:
            c.execute(
                "INSERT INTO metricas (ts, nome, valor, unidade) VALUES (?,?,?,?)",
                (time.time(), nome, valor, unidade),
            )
            c.commit()
    except Exception as exc:
        log.debug("obs registrar_metrica: %s", exc)

class Temporizador:

    def __init__(self, tipo: str, modulo: str = "", dados: dict | None = None):
        self._tipo    = tipo
        self._modulo  = modulo
        self._dados   = dados or {}
        self._inicio  = 0.0

    def __enter__(self) -> "Temporizador":
        self._inicio = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duracao_ms = int((time.time() - self._inicio) * 1000)
        sucesso    = exc_type is None
        registrar_acao(
            tipo=self._tipo,
            modulo=self._modulo,
            duracao_ms=duracao_ms,
            sucesso=sucesso,
            dados=self._dados,
        )
        registrar_metrica(f"duracao.{self._tipo}", duracao_ms, "ms")

def historico_acoes(tipo: str | None = None, limite: int = 50) -> list[dict]:
    try:
        with conectar_banco() as c:
            if tipo:
                rows = c.execute(
                    "SELECT ts, tipo, modulo, descricao, duracao_ms, sucesso, dados_json "
                    "FROM acoes WHERE tipo=? ORDER BY id DESC LIMIT ?",
                    (tipo, limite),
                ).fetchall()
            else:
                rows = c.execute(
                    "SELECT ts, tipo, modulo, descricao, duracao_ms, sucesso, dados_json "
                    "FROM acoes ORDER BY id DESC LIMIT ?",
                    (limite,),
                ).fetchall()
            return [dict(r) for r in rows]
    except Exception:
        return []

def resumo_metricas(nome: str, janela_s: int = 3600) -> dict:
    limite_ts = time.time() - janela_s
    try:
        with conectar_banco() as c:
            rows = c.execute(
                "SELECT valor FROM metricas WHERE nome=? AND ts > ?",
                (nome, limite_ts),
            ).fetchall()
            valores = [r["valor"] for r in rows]
            if not valores:
                return {"nome": nome, "amostras": 0}
            return {
                "nome":     nome,
                "amostras": len(valores),
                "media":    round(sum(valores) / len(valores), 2),
                "min":      round(min(valores), 2),
                "max":      round(max(valores), 2),
                "janela_s": janela_s,
            }
    except Exception:
        return {"nome": nome, "amostras": 0}

def taxa_erros(janela_s: int = 3600) -> float:
    limite_ts = time.time() - janela_s
    try:
        with conectar_banco() as c:
            total = c.execute(
                "SELECT COUNT(*) FROM acoes WHERE ts > ?", (limite_ts,)
            ).fetchone()[0]
            erros = c.execute(
                "SELECT COUNT(*) FROM acoes WHERE ts > ? AND sucesso=0", (limite_ts,)
            ).fetchone()[0]
            return round(erros / total, 4) if total else 0.0
    except Exception:
        return 0.0

def purgar_antigos(dias: int = 7) -> int:
    limite = time.time() - dias * 86400
    try:
        with conectar_banco() as c:
            n1 = c.execute("DELETE FROM acoes   WHERE ts < ?", (limite,)).rowcount
            n2 = c.execute("DELETE FROM metricas WHERE ts < ?", (limite,)).rowcount
            c.commit()
            return n1 + n2
    except Exception:
        return 0