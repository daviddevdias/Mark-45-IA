import sqlite3
import re
import os
import time
import json
import threading
from collections import Counter

_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tasks", "logs", "answer_cache.db")
_lock = threading.Lock()
_MAX_ENTRIES = 500
_CACHE_TTL = 86400 * 7
_SIM_THRESHOLD = 0.35

def _conectar():
    os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(_DB_PATH, timeout=5)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pergunta TEXT NOT NULL,
            resposta TEXT NOT NULL,
            fingerprint TEXT NOT NULL,
            criado_em REAL NOT NULL,
            acessos INTEGER DEFAULT 0,
            UNIQUE(fingerprint)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_fp ON cache(fingerprint)")
    conn.commit()
    return conn

def _fingerprint(texto: str) -> str:
    t = texto.lower().strip()
    t = re.sub(r'[^\w\s]', '', t)
    t = re.sub(r'\s+', ' ', t)
    palavras = sorted(t.split())
    return " ".join(palavras)

def _ngrams(palavras, n=2):
    return set(zip(*[palavras[i:] for i in range(n)]))

def _similaridade(a: str, b: str) -> float:
    pa = re.sub(r'[^\w\s]', '', a.lower()).split()
    pb = re.sub(r'[^\w\s]', '', b.lower()).split()
    if not pa or not pb:
        return 0.0
    nga = _ngrams(pa)
    ngb = _ngrams(pb)
    if not nga or not ngb:
        return 0.0
    inter = len(nga & ngb)
    return inter / max(len(nga), len(ngb))

def buscar(pergunta: str) -> str | None:
    fp = _fingerprint(pergunta)
    with _lock:
        try:
            conn = _conectar()
            cur = conn.execute("SELECT fingerprint, resposta, acessos FROM cache")
            rows = cur.fetchall()
            for fp_db, resposta, acessos in rows:
                if fp_db == fp:
                    conn.execute("UPDATE cache SET acessos = acessos + 1 WHERE fingerprint = ?", (fp_db,))
                    conn.commit()
                    conn.close()
                    return resposta
            for fp_db, resposta, acessos in rows:
                sim = _similaridade(pergunta, fp_db)
                if sim >= _SIM_THRESHOLD:
                    conn.execute("UPDATE cache SET acessos = acessos + 1 WHERE fingerprint = ?", (fp_db,))
                    conn.commit()
                    conn.close()
                    return resposta
            conn.close()
        except:
            pass
    return None

def armazenar(pergunta: str, resposta: str):
    fp = _fingerprint(pergunta)
    with _lock:
        try:
            conn = _conectar()
            conn.execute(
                "INSERT OR REPLACE INTO cache (pergunta, resposta, fingerprint, criado_em) VALUES (?, ?, ?, ?)",
                (pergunta, resposta, fp, time.time())
            )
            conn.execute("DELETE FROM cache WHERE id NOT IN (SELECT id FROM cache ORDER BY acessos DESC LIMIT ?)", (_MAX_ENTRIES,))
            conn.execute("DELETE FROM cache WHERE criado_em < ?", (time.time() - _CACHE_TTL,))
            conn.commit()
            conn.close()
        except:
            pass
