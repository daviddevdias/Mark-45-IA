from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any

@dataclass
class EstadoSistema:
    ia_modo:         str   = "ollama"
    ia_disponivel:   bool  = False
    ia_modelo_ativo: str   = ""
    usuario_ativo:   str   = "Chefe"
    cidade_padrao:   str   = "Esteio,BR"
    voz_ativa:       bool  = True
    monitor_ativo:   bool  = False
    alarme_ativo:    bool  = False
    aguard_confirm:  bool  = False
    ultimo_comando:  str   = ""
    ultima_resposta: str   = ""
    ts_ultimo_cmd:   float = 0.0
    contexto_ativo:  dict  = field(default_factory=dict)
    flags:           dict  = field(default_factory=dict)

class StateManager:

    def __init__(self):
        self.estado   = EstadoSistema()
        self.lock     = threading.RLock()
        self.watchers: dict[str, list] = {}

    def get(self, chave: str, default: Any = None) -> Any:
        with self.lock:
            return getattr(self.estado, chave, default)

    def set(self, chave: str, valor: Any):
        with self.lock:
            antigo = getattr(self.estado, chave, None)
            if antigo == valor:
                return
            setattr(self.estado, chave, valor)

        for fn in self.watchers.get(chave, []):
            try:
                fn(chave, antigo, valor)
            except Exception:
                pass

        try:
            from brain.event_bus import bus, ESTADO_ALTERADO
            bus.publicar(ESTADO_ALTERADO, {"chave": chave, "antes": antigo, "depois": valor})
        except Exception:
            pass

    def update(self, dados: dict):
        for k, v in dados.items():
            self.set(k, v)

    def snapshot(self) -> dict:
        with self.lock:
            return {
                k: getattr(self.estado, k)
                for k in self.estado.__dataclass_fields__
            }

    def watch(self, chave: str, fn):
        self.watchers.setdefault(chave, []).append(fn)

    def set_contexto(self, chave: str, valor: Any):
        with self.lock:
            self.estado.contexto_ativo[chave] = valor

    def get_contexto(self, chave: str, default: Any = None) -> Any:
        with self.lock:
            return self.estado.contexto_ativo.get(chave, default)

    def set_flag(self, flag: str, valor: bool = True):
        with self.lock:
            self.estado.flags[flag] = valor

    def get_flag(self, flag: str) -> bool:
        with self.lock:
            return bool(self.estado.flags.get(flag, False))

state = StateManager()