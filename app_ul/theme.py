"""
app_ul/theme.py
Paletas de cores e utilitários de estilo para a HUD JarvisUI.
"""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtGui import QColor



# Estrutura de pintura (kit de cores resolvidas para QPainter)


@dataclass
class KitPintura:
    accent:        QColor
    scan_line:     QColor
    ring_outer:    QColor
    core_white:    QColor
    core_mid:      QColor
    core_outer:    QColor
    core_hot:      QColor
    tentacle:      QColor
    tentacle_hot:  QColor
    particle:      QColor
    arc:           QColor
    title:         QColor
    subtitle:      QColor



# Definição dos temas  (dict raw com strings hex / rgba)


def _tema_laranja_mesa() -> dict:
    return {
        "accent":        "#FF8C00",
        "scan_line":     "#FF8C0022",
        "ring_outer":    "#FF8C0055",
        "core_white":    "#FFFFFF",
        "core_mid":      "#FFB347",
        "core_outer":    "#FF6600",
        "core_hot":      "#CC3300",
        "tentacle":      "#FF8C00",
        "tentacle_hot":  "#FF4500",
        "particle":      "#FFA040",
        "arc":           "#FF8C00",
        "title":         "#FFD580",
        "subtitle":      "#FFA040",
        "danger":        "#FF3333",
    }


def _tema_azul_artico() -> dict:
    return {
        "accent":        "#00BFFF",
        "scan_line":     "#00BFFF22",
        "ring_outer":    "#00BFFF55",
        "core_white":    "#FFFFFF",
        "core_mid":      "#66D9FF",
        "core_outer":    "#007ACC",
        "core_hot":      "#005F99",
        "tentacle":      "#00BFFF",
        "tentacle_hot":  "#0080FF",
        "particle":      "#40D0FF",
        "arc":           "#00BFFF",
        "title":         "#B0EEFF",
        "subtitle":      "#66CCFF",
        "danger":        "#FF4444",
    }


def _tema_verde_matrix() -> dict:
    return {
        "accent":        "#00FF41",
        "scan_line":     "#00FF4122",
        "ring_outer":    "#00FF4155",
        "core_white":    "#CCFFCC",
        "core_mid":      "#00CC33",
        "core_outer":    "#007700",
        "core_hot":      "#004400",
        "tentacle":      "#00FF41",
        "tentacle_hot":  "#00CC22",
        "particle":      "#66FF88",
        "arc":           "#00FF41",
        "title":         "#AAFFAA",
        "subtitle":      "#66FF66",
        "danger":        "#FF3333",
    }


def _tema_roxo_nebula() -> dict:
    return {
        "accent":        "#BF5FFF",
        "scan_line":     "#BF5FFF22",
        "ring_outer":    "#BF5FFF55",
        "core_white":    "#F0DDFF",
        "core_mid":      "#9933FF",
        "core_outer":    "#660099",
        "core_hot":      "#440066",
        "tentacle":      "#BF5FFF",
        "tentacle_hot":  "#9900FF",
        "particle":      "#D088FF",
        "arc":           "#BF5FFF",
        "title":         "#E8BBFF",
        "subtitle":      "#CC99FF",
        "danger":        "#FF3355",
    }


def _tema_vermelho_marte() -> dict:
    return {
        "accent":        "#FF2222",
        "scan_line":     "#FF222222",
        "ring_outer":    "#FF222255",
        "core_white":    "#FFDDDD",
        "core_mid":      "#FF5555",
        "core_outer":    "#CC0000",
        "core_hot":      "#880000",
        "tentacle":      "#FF2222",
        "tentacle_hot":  "#FF6600",
        "particle":      "#FF6666",
        "arc":           "#FF2222",
        "title":         "#FFAAAA",
        "subtitle":      "#FF7777",
        "danger":        "#FF6600",
    }



# Registro central


TEMAS_CORE: dict[str, dict] = {
    "LARANJA_MESA":  _tema_laranja_mesa(),
    "AZUL_ARTICO":   _tema_azul_artico(),
    "VERDE_MATRIX":  _tema_verde_matrix(),
    "ROXO_NEBULA":   _tema_roxo_nebula(),
    "VERMELHO_MARTE": _tema_vermelho_marte(),
}



# Helpers públicos


def lista_temas() -> list[str]:
    """Retorna os nomes de todos os temas disponíveis."""
    return list(TEMAS_CORE.keys())


def _qc(hex_or_rgba: str) -> QColor:
    """Converte string hex (#RRGGBB ou #RRGGBBAA) em QColor."""
    return QColor(hex_or_rgba)


def kit_pintura(nome: str) -> KitPintura:
    """Resolve um tema pelo nome e devolve um KitPintura pronto para QPainter."""
    raw = TEMAS_CORE.get(nome, TEMAS_CORE["LARANJA_MESA"])
    return KitPintura(
        accent       = _qc(raw["accent"]),
        scan_line    = _qc(raw["scan_line"]),
        ring_outer   = _qc(raw["ring_outer"]),
        core_white   = _qc(raw["core_white"]),
        core_mid     = _qc(raw["core_mid"]),
        core_outer   = _qc(raw["core_outer"]),
        core_hot     = _qc(raw["core_hot"]),
        tentacle     = _qc(raw["tentacle"]),
        tentacle_hot = _qc(raw["tentacle_hot"]),
        particle     = _qc(raw["particle"]),
        arc          = _qc(raw["arc"]),
        title        = _qc(raw["title"]),
        subtitle     = _qc(raw["subtitle"]),
    )



# QSS helpers para botões


def _hex(raw: dict, chave: str) -> str:
    """Extrai a cor hex de uma chave do dict raw."""
    return raw[chave]


def qss_botao_accent(raw: dict) -> str:
    ac = _hex(raw, "accent")
    return f"""
        QPushButton {{
            background: transparent;
            border: 1.5px solid {ac};
            border-radius: 8px;
            color: {ac};
            padding: 4px 8px;
        }}
        QPushButton:hover {{
            background: {ac}33;
        }}
        QPushButton:pressed {{
            background: {ac}66;
        }}
    """


def qss_botao_danger(raw: dict) -> str:
    dg = _hex(raw, "danger")
    return f"""
        QPushButton {{
            background: transparent;
            border: 1.5px solid {dg};
            border-radius: 8px;
            color: {dg};
            padding: 4px 8px;
        }}
        QPushButton:hover {{
            background: {dg}33;
        }}
        QPushButton:pressed {{
            background: {dg}66;
        }}
    """


def qss_botao_muted(raw: dict) -> str:
    dg = _hex(raw, "danger")
    return f"""
        QPushButton {{
            background: {dg}22;
            border: 1.5px solid {dg}88;
            border-radius: 8px;
            color: {dg};
            padding: 4px 8px;
        }}
        QPushButton:hover {{
            background: {dg}44;
        }}
        QPushButton:pressed {{
            background: {dg}66;
        }}
    """