from __future__ import annotations

import asyncio
import logging
import sqlite3
import os

log = logging.getLogger("jarvis.optimizer")

LOTE = 100
MINIMO = 50
TIMEOUT_IA = 30.0

def conectar_banco_auditoria() -> sqlite3.Connection:
    caminho_db = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs", "audit.db")
    conexao = sqlite3.connect(caminho_db, timeout=10)
    conexao.row_factory = sqlite3.Row
    conexao.execute("""
        CREATE TABLE IF NOT EXISTS audit_resumos (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            ts         TEXT    NOT NULL,
            periodo_de TEXT    NOT NULL,
            periodo_ate TEXT   NOT NULL,
            registros  INTEGER NOT NULL,
            resumo     TEXT    NOT NULL
        )
    """)
    conexao.execute("CREATE INDEX IF NOT EXISTS idx_resumos_ts ON audit_resumos(ts)")
    conexao.commit()
    return conexao

async def comprimir_banco_auditoria():
    conexao = conectar_banco_auditoria()
    try:
        cursor = conexao.cursor()

        cursor.execute("SELECT COUNT(*) as total FROM audit_log")
        total_antes = cursor.fetchone()["total"]
        if total_antes < MINIMO:
            return f"O banco já está otimizado. Registros atuais: {total_antes}."

        cursor.execute(
            "SELECT id, comando, resultado, ts FROM audit_log ORDER BY id ASC LIMIT ?",
            (LOTE,),
        )
        registros = cursor.fetchall()
        ids_lote = [r["id"] for r in registros]

        texto_logs = " ".join(
            f"[{r['ts']}] Cmd: {r['comando']} | Res: {r['resultado'][:50]}"
            for r in registros
        )

        try:
            from engine.ia_router import router
            prompt = (
                "Analise este bloco de logs antigos e crie um resumo técnico de 2 linhas "
                f"sobre o estado e comportamento do sistema. Logs: {texto_logs}"
            )
            resumo = await asyncio.wait_for(router.responder(prompt), timeout=TIMEOUT_IA)
            if not resumo:
                raise ValueError("IA retornou resposta vazia")

        except asyncio.TimeoutError:
            log.warning("[optimizer] IA não respondeu em %.0fs — abortando.", TIMEOUT_IA)
            return f"Compressão abortada: IA não respondeu em {TIMEOUT_IA:.0f}s. Nenhum registro apagado."

        except Exception as exc:
            log.error("[optimizer] Falha na IA: %s — abortando.", exc)
            return f"Compressão abortada: {exc}. Nenhum registro apagado."

        from datetime import datetime as dt
        ts_de  = registros[0]["ts"]  if registros else ""
        ts_ate = registros[-1]["ts"] if registros else ""

        cursor.execute(
            """INSERT INTO audit_resumos (ts, periodo_de, periodo_ate, registros, resumo)
               VALUES (?, ?, ?, ?, ?)""",
            (dt.now().isoformat(timespec="seconds"), ts_de, ts_ate, len(ids_lote), resumo),
        )

        placeholders = ",".join("?" * len(ids_lote))
        cursor.execute(f"DELETE FROM audit_log WHERE id IN ({placeholders})", ids_lote)
        conexao.commit()

        cursor.execute("SELECT COUNT(*) as total FROM audit_log")
        total_depois = cursor.fetchone()["total"]

        log.info("[optimizer] %d → %d registros. Resumo salvo em audit_resumos.", total_antes, total_depois)
        return (
            f"Registros reduzidos de {total_antes} para {total_depois}. "
            f"Resumo salvo em audit_resumos: {resumo}"
        )

    except Exception as exc:
        conexao.rollback()
        log.error("[optimizer] Erro inesperado: %s", exc)
        return f"Falha na otimização: {exc}. Nenhum registro apagado."

    finally:
        conexao.close()


def purgar_resumos_antigos(dias: int = 365) -> int:
    import time as _time
    limite = _time.time() - dias * 86400
    try:
        conexao = conectar_banco_auditoria()

        cur = conexao.execute(
            "DELETE FROM audit_resumos WHERE ts < datetime(?, 'unixepoch')",
            (limite,),
        )
        conexao.commit()
        removidos = cur.rowcount
        conexao.close()
        if removidos:
            log.info("[optimizer] purgar_resumos_antigos: %d resumo(s) removido(s).", removidos)
        return removidos
    except Exception as exc:
        log.warning("[optimizer] purgar_resumos_antigos falhou: %s", exc)
        return 0