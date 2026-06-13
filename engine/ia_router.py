from __future__ import annotations
from engine.controller import (
    IARRouter,
    Historico,
    detectar_modelo,
    check,
    system_msg,
    router,
    modelo,
    disponivel,
    ultimo_check,
    ligar_monitor,
    ROUTES,
    buscar_handler,
    processar_diretriz,
    normalizar,
    extrair_numero,
    extrair_termo,
    get_shutdown_event,
)

try:
    from engine.controller import info_monitor, desligar_monitor
except ImportError:
    from vision.capture import status_monitor as info_monitor, parar_monitor as desligar_monitor

__all__ = [
    "IARRouter",
    "Historico",
    "detectar_modelo",
    "check",
    "system_msg",
    "router",
    "modelo",
    "disponivel",
    "ultimo_check",
    "info_monitor",
    "desligar_monitor",
    "ligar_monitor",
    "ROUTES",
    "buscar_handler",
    "processar_diretriz",
    "normalizar",
    "extrair_numero",
    "extrair_termo",
    "get_shutdown_event",
]
