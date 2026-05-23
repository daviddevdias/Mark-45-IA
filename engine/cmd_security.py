from __future__ import annotations

import os
import re
import shlex
import ast
import sqlite3
import subprocess
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, Callable

log = logging.getLogger("jarvis.cmd_security")

_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "audit.db")

def _get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False, timeout=5)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            ts         TEXT    NOT NULL,
            origem     TEXT    DEFAULT 'cmd',
            ferramenta TEXT    DEFAULT '',
            comando    TEXT    NOT NULL,
            resultado  TEXT    DEFAULT '',
            bloqueado  INTEGER DEFAULT 0,
            motivo     TEXT    DEFAULT ''
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ts ON audit_log(ts)")
    conn.commit()
    return conn

def _audit(
    comando: str,
    resultado: str = "",
    bloqueado: bool = False,
    motivo: str = "",
    origem: str = "cmd",
    ferramenta: str = "",
) -> None:
    try:
        with _get_conn() as conn:
            conn.execute(
                "INSERT INTO audit_log (ts, origem, ferramenta, comando, resultado, bloqueado, motivo) "
                "VALUES (?,?,?,?,?,?,?)",
                (
                    datetime.now().isoformat(timespec="seconds"),
                    origem, ferramenta,
                    comando[:500], resultado[:500],
                    int(bloqueado), motivo[:200],
                ),
            )
            conn.commit()
    except Exception as e:
        log.error("[Audit] Falha ao registrar: %s", e)

class Categoria(Enum):
    LEITURA    = "leitura"
    SISTEMA    = "sistema"
    REDE       = "rede"
    DESTRUTIVO = "destrutivo"
    BLOQUEADO  = "bloqueado"

@dataclass
class Regra:
    padrao:    re.Pattern
    categoria: Categoria
    shell:     bool = False

@dataclass
class Avaliacao:
    permitido: bool
    confirmar: bool      = False
    categoria: Categoria = Categoria.BLOQUEADO
    motivo:    str       = ""
    cmd:       Optional[str] = None

BLOQUEIOS = [
    r"rm\s+-rf\s+[/~\$]",
    r"mkfs", r"dd\s+if=",
    r":\(\)\{.*\}",
    r"chmod\s+-R\s+777\s+/",
    r"(wget|curl).+\|\s*(bash|sh|python)",
    r">\s*/dev/sda",
    r"format\s+c:", r"del\s+/f\s+/s\s+/q\s+[cC]:",
    r"rd\s+/s\s+/q\s+[cC]:\\",
    r"Remove-Item\s+-Recurse\s+-Force\s+[cC]:",
    r"shutdown\s+/[fsr]",
    r"\b(halt|poweroff|reboot)\b",
    r"systemctl\s+(halt|poweroff|reboot)",
    r"__import__", r"eval\s*\(", r"exec\s*\(",
    r"base64\s+-d.*\|\s*(bash|sh)",
    r"nc\s+-[el]", r"netcat",
    r"/etc/(passwd|shadow)",
    r"sudo\s+(su|-s)",
]

REGRAS: list[Regra] = [
    Regra(re.compile(r"^(ls|dir|echo|pwd|whoami|date|uptime|df|du|free|ps|top|cat\s+\S+\.(txt|log|json)|type\s+\S+)"), Categoria.LEITURA),
    Regra(re.compile(r"^(python3?|node|npm|pip)\s+"),              Categoria.SISTEMA),
    Regra(re.compile(r"^(mkdir|touch|cp|mv)\s+"),                  Categoria.SISTEMA),
    Regra(re.compile(r"^(ping|nslookup|curl\s+https?://|wget\s+https?://)\s+"), Categoria.REDE),
    Regra(re.compile(r"^(tasklist|taskkill|Get-Process|Stop-Process|systemctl\s+status|service\s+\S+\s+status)"), Categoria.SISTEMA, shell=True),
    Regra(re.compile(r"^(rm|del|rmdir|rd|Remove-Item|shred)\s+"),  Categoria.DESTRUTIVO, shell=True),
    Regra(re.compile(r"^(kill|taskkill\s+/f|Stop-Process\s+-Force)\s+"), Categoria.DESTRUTIVO, shell=True),
    Regra(re.compile(r"^(pip\s+install|npm\s+install|apt\s+install|brew\s+install|winget\s+install)"), Categoria.SISTEMA, shell=True),
    Regra(re.compile(r"^(powershell|cmd|bash|sh|zsh|fish)\s+"),    Categoria.SISTEMA, shell=True),
    Regra(re.compile(r"^(netsh|iptables|ufw|firewall-cmd)\s+"),    Categoria.DESTRUTIVO, shell=True),
    Regra(re.compile(r"^(reg\s+|regedit|regedt32)"),               Categoria.DESTRUTIVO, shell=True),
]

BLOQUEIOS_COMPILADOS = [re.compile(p, re.IGNORECASE) for p in BLOQUEIOS]
INJECOES = [";", "&&", "||", "`", "$(", ">{", "<(", "2>&1 |"]

def sanitizar(cmd: str):
    return re.sub(r"\s+", " ", cmd.strip())

def tem_injecao(cmd: str) -> bool:
    return any(s in cmd.lower() for s in INJECOES)

def avaliar(comando: str) -> Avaliacao:
    cmd = sanitizar(comando)

    if not cmd:
        return Avaliacao(permitido=False, motivo="Comando vazio.")

    for padrao in BLOQUEIOS_COMPILADOS:
        if padrao.search(cmd):
            log.warning("Bloqueado: %s", cmd[:80])
            _audit(cmd, bloqueado=True, motivo="Padrão proibido detectado.")
            return Avaliacao(permitido=False, motivo="Padrão proibido detectado.")

    if tem_injecao(cmd):
        log.warning("Injeção detectada: %s", cmd[:80])
        _audit(cmd, bloqueado=True, motivo="Operadores de encadeamento suspeitos.")
        return Avaliacao(permitido=False, motivo="Operadores de encadeamento suspeitos (;, &&, ||).")

    for regra in REGRAS:
        if regra.padrao.match(cmd):
            return Avaliacao(
                permitido=True,
                confirmar=regra.categoria == Categoria.DESTRUTIVO,
                categoria=regra.categoria,
                cmd=cmd,
            )

    return Avaliacao(
        permitido=True,
        confirmar=True,
        categoria=Categoria.SISTEMA,
        cmd=cmd,
        motivo="Comando não catalogado.",
    )

def executar(
    comando: str,
    timeout: int = 15,
    confirmar_fn: Optional[Callable] = None,
    origem: str = "cmd",
    ferramenta: str = "",
):
    av = avaliar(comando)

    if not av.permitido:
        _audit(comando, resultado=f"BLOQUEADO: {av.motivo}", bloqueado=True,
               motivo=av.motivo, origem=origem, ferramenta=ferramenta)
        return f"Bloqueado: {av.motivo}"

    if av.confirmar:
        if confirmar_fn is None:
            return (
                f"Comando '{av.categoria.value}' requer confirmação.\n"
                f"Use: executar_confirmado('{comando}')"
            )
        if not confirmar_fn(comando, av):
            _audit(comando, resultado="CANCELADO pelo usuário", origem=origem, ferramenta=ferramenta)
            return "Execução cancelada."

    cmd = av.cmd or comando
    usar_shell = any(r.shell and r.padrao.match(cmd) for r in REGRAS)

    try:
        if usar_shell:
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        else:
            try:
                args = shlex.split(cmd)
            except ValueError:
                args = cmd.split()
            res = subprocess.run(args, shell=False, capture_output=True, text=True, timeout=timeout)

        saida = (res.stdout or res.stderr or "Executado sem saída.").strip()
        if res.returncode != 0:
            log.warning("Código %d: %s", res.returncode, cmd[:60])

        saida_truncada = saida[:600]
        _audit(cmd, resultado=saida_truncada, origem=origem, ferramenta=ferramenta)
        return saida_truncada

    except subprocess.TimeoutExpired:
        msg = f"Timeout: excedeu {timeout}s."
        _audit(cmd, resultado=msg, origem=origem, ferramenta=ferramenta)
        return msg
    except FileNotFoundError:
        msg = f"Comando não encontrado: {cmd.split()[0]}"
        _audit(cmd, resultado=msg, origem=origem, ferramenta=ferramenta)
        return msg
    except Exception as e:
        msg = f"Erro: {e}"
        log.error("Erro ao executar '%s': %s", cmd[:60], e)
        _audit(cmd, resultado=msg, origem=origem, ferramenta=ferramenta)
        return msg

class SecurityBlockError(Exception):
    pass

def validar_codigo_ast(codigo_fonte: str) -> bool:
    modulos_proibidos = {'os', 'sys', 'shutil', 'subprocess', 'socket', 'requests', 'pty'}
    funcoes_proibidas = {'eval', 'exec', 'open', '__import__', 'getattr', 'setattr', 'compile'}

    try:
        arvore = ast.parse(codigo_fonte)
    except SyntaxError as e:
        log.error("Erro de sintaxe gerado pelo Agent S: %s", e)
        return False

    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            for alias in no.names:
                if alias.name.split('.')[0] in modulos_proibidos:
                    log.warning("Agent S tentou importar módulo proibido: %s", alias.name)
                    return False
        elif isinstance(no, ast.ImportFrom):
            if no.module and no.module.split('.')[0] in modulos_proibidos:
                log.warning("Agent S tentou importar de módulo proibido: %s", no.module)
                return False
        elif isinstance(no, ast.Call):
            if isinstance(no.func, ast.Name) and no.func.id in funcoes_proibidas:
                log.warning("Agent S tentou usar função crítica: %s", no.func.id)
                return False

    return True

def audit_recente(limite: int = 50) -> list[dict]:
    try:
        with _get_conn() as conn:
            rows = conn.execute(
                "SELECT ts, origem, ferramenta, comando, resultado, bloqueado, motivo "
                "FROM audit_log ORDER BY id DESC LIMIT ?",
                (limite,),
            ).fetchall()
            return [dict(r) for r in rows]
    except Exception:
        return []

avaliar_comando = avaliar
executar_seguro = executar