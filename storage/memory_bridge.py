from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Final, TypeVar

import config
from storage.memory_manager import load_memory

log = logging.getLogger("memory_bridge")

T = TypeVar("T")
Coercer = Callable[[Any], T]

@dataclass
class SyncReport:
    applied: dict[str, Any] = field(default_factory=dict)
    skipped: dict[str, str] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors

    def __str__(self):
        parts = []
        if self.applied:
            parts.append(f"aplicados={list(self.applied)}")
        if self.skipped:
            parts.append(f"ignorados={list(self.skipped)}")
        if self.errors:
            parts.append(f"erros={list(self.errors)}")
        return "SyncReport(" + ", ".join(parts) + ")" if parts else "SyncReport(sem_mudanças)"

_TRUTHY: Final = frozenset({"true", "1", "sim", "yes", "on", "verdadeiro"})
_FALSY: Final = frozenset({"false", "0", "nao", "não", "no", "off", "falso"})

def coerce_bool(raw: Any) -> bool:
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, int):
        return bool(raw)
    if isinstance(raw, str):
        v = raw.strip().lower()
        if v in _TRUTHY:
            return True
        if v in _FALSY:
            return False
    raise ValueError(f"Não é possível converter {raw!r} para bool")

def coerce_str(raw: Any, min_len: int = 1, max_len: int = 256):
    v = str(raw).strip()
    if len(v) < min_len:
        raise ValueError(f"Mínimo {min_len} caractere(s), recebeu {len(v)}")
    if len(v) > max_len:
        raise ValueError(f"Máximo {max_len} caracteres, recebeu {len(v)}")
    return v

def coerce_float(raw: Any) -> float:
    return float(raw)

@dataclass(frozen=True)
class FieldSpec:
    mem_path: tuple[str, ...]
    config_attr: str
    coerce: Coercer
    default: Any = None
    required: bool = False

FIELD_MAP: Final[tuple[FieldSpec, ...]] = (
    FieldSpec(
        mem_path=("identity", "mestre"),
        config_attr="NOME_MESTRE",
        coerce=lambda v: coerce_str(v, max_len=64),
        default="David",
    ),
    FieldSpec(
        mem_path=("preferences", "tema_ativo"),
        config_attr="tema_ativo",
        coerce=lambda v: coerce_str(v, max_len=64),
        default="default",
    ),
    FieldSpec(
        mem_path=("preferences", "voz"),
        config_attr="voz_atual",
        coerce=lambda v: coerce_str(v, max_len=128),
        default=None,
    ),
    FieldSpec(
        mem_path=("preferences", "idioma"),
        config_attr="idioma",
        coerce=lambda v: coerce_str(v, min_len=2, max_len=10),
        default="pt-BR",
    ),
    FieldSpec(
        mem_path=("preferences", "fuso_horario"),
        config_attr="fuso_horario",
        coerce=lambda v: coerce_str(v, max_len=64),
        default=None,
    ),
    FieldSpec(
        mem_path=("preferences", "velocidade_fala"),
        config_attr="velocidade_fala",
        coerce=coerce_float,
        default=1.0,
    ),
    FieldSpec(
        mem_path=("preferences", "volume"),
        config_attr="volume",
        coerce=coerce_float,
        default=1.0,
    ),
    FieldSpec(
        mem_path=("preferences", "modo_debug"),
        config_attr="modo_debug",
        coerce=coerce_bool,
        default=False,
    ),
    FieldSpec(
        mem_path=("preferences", "cidade"),
        config_attr="cidade_mestre",
        coerce=lambda v: coerce_str(v, max_len=128),
        default="",
    ),
)

def ler_valor_na_memoria(memory: dict, path: tuple[str, ...]) -> tuple[bool, Any]:
    node: Any = memory
    for key in path:
        if not isinstance(node, dict) or key not in node:
            return False, None
        node = node[key]

    if isinstance(node, dict) and "value" in node:
        node = node["value"]

    return True, node

def sincronizar_um_campo(spec: FieldSpec, memory: dict, report: SyncReport):
    attr = spec.config_attr
    found, raw = ler_valor_na_memoria(memory, spec.mem_path)

    if not found or raw is None:
        if spec.required:
            msg = f"Campo obrigatório ausente: {'.'.join(spec.mem_path)}"
            log.error("[bridge] %s → %s: %s", spec.mem_path, attr, msg)
            report.errors[attr] = msg
        else:
            log.debug("[bridge] %s ausente na memória — ignorando", attr)
            report.skipped[attr] = "ausente na memória"
        return

    try:
        value = spec.coerce(raw)
    except (ValueError, TypeError) as exc:
        msg = f"Valor inválido {raw!r}: {exc}"
        log.warning("[bridge] %s → %s: %s", spec.mem_path, attr, msg)
        report.errors[attr] = msg
        return

    current = getattr(config, attr, spec.default)
    if current == value:
        log.debug("[bridge] %s inalterado (%r)", attr, value)
        report.skipped[attr] = "valor idêntico"
        return

    setattr(config, attr, value)
    log.info("[bridge] %s: %r → %r", attr, current, value)
    report.applied[attr] = value

def sincronizar_config(memory: dict | None = None) -> SyncReport:
    report = SyncReport()

    try:
        mem = memory if memory is not None else load_memory()
    except Exception as exc:
        msg = f"Falha ao carregar memória: {exc}"
        log.error("[bridge] %s", msg)
        report.errors["__load__"] = msg
        return report

    if not isinstance(mem, dict):
        msg = f"Memória com tipo inesperado: {type(mem).__name__}"
        log.error("[bridge] %s", msg)
        report.errors["__load__"] = msg
        return report

    for spec in FIELD_MAP:
        try:
            sincronizar_um_campo(spec, mem, report)
        except Exception as exc:
            log.exception("[bridge] Erro inesperado em '%s'", spec.config_attr)
            report.errors[spec.config_attr] = str(exc)

    log.debug("[bridge] Concluído → %s", report)
    return report