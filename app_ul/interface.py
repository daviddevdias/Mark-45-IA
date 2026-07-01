import hashlib
import math
import signal
import sys
from dataclasses import dataclass

from PyQt6.QtCore import (
    QByteArray,
    QObject,
    QPoint,
    QPointF,
    QRectF,
    QSize,
    QSettings,
    Qt,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QAction,
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QMenu,
    QPushButton,
    QSystemTrayIcon,
    QWidget,
)


@dataclass
class KitPintura:
    """Paleta de QColor pré-calculada para um tema."""

    bg_tint: QColor  # halo de fundo
    glow_hot: QColor  # brilho quente externo
    glow_mid: QColor  # brilho médio externo
    scan_line: QColor  # linhas de varredura radar
    ring_outer: QColor  # anel externo tracejado
    accent: QColor  # cor de destaque geral
    core_white: QColor  # ponto branco central
    core_mid: QColor  # gradiente médio do núcleo
    core_outer: QColor  # borda do núcleo
    core_hot: QColor  # cor quente do núcleo
    tentacle: QColor  # tentáculos (base)
    tentacle_hot: QColor  # tentáculos (quente / blend)
    particle: QColor  # partículas orbitais
    arc: QColor  # arco externo segmentado
    title: QColor  # texto "J.A.R.V.I.S"
    subtitle: QColor  # texto "A C T I V E"


def _qc(r: int, g: int, b: int, a: int = 255) -> QColor:
    return QColor(r, g, b, a)


def _hc(hex_str: str, a: int = 255) -> QColor:
    c = QColor(hex_str)
    c.setAlpha(a)
    return c


# Definição de todos os temas

TEMAS_CORE: dict[str, dict] = {
    "LARANJA_MESA": {
        "label": "Laranja · Mesa",
        "danger": "#ff3b30",
        "accent": "#ff9500",
        "glow_h": "#ff6600",
        "glow_m": "#ff3300",
        "core1": "#ff9900",
        "core2": "#ff6600",
        "core3": "#ff3300",
        "tent": "#ff7700",
        "tent_h": "#ffaa44",
        "arc_c": "#ffaa33",
        "part_c": "#ffbb44",
        "ring_c": "#ff8800",
        "title_c": "#ffaa33",
    },
    "ARCO_REATOR": {
        "label": "Azul · Arco Reator",
        "danger": "#ff3b30",
        "accent": "#00b4ff",
        "glow_h": "#0088cc",
        "glow_m": "#003388",
        "core1": "#00cfff",
        "core2": "#0088cc",
        "core3": "#003388",
        "tent": "#0099ee",
        "tent_h": "#44ccff",
        "arc_c": "#44ccff",
        "part_c": "#66ddff",
        "ring_c": "#22aaff",
        "title_c": "#44ccff",
    },
    "PHANTOM_NEXUS": {
        "label": "Roxo · Phantom Nexus",
        "danger": "#ff3b30",
        "accent": "#bf5af2",
        "glow_h": "#9900cc",
        "glow_m": "#550077",
        "core1": "#cc44ff",
        "core2": "#9900cc",
        "core3": "#550077",
        "tent": "#aa22dd",
        "tent_h": "#dd77ff",
        "arc_c": "#dd77ff",
        "part_c": "#dd88ff",
        "ring_c": "#bb33ee",
        "title_c": "#cc66ff",
    },
    "ESMERALDA": {
        "label": "Verde · Esmeralda",
        "danger": "#ff3b30",
        "accent": "#00e676",
        "glow_h": "#00c853",
        "glow_m": "#005c28",
        "core1": "#69ff94",
        "core2": "#00e676",
        "core3": "#00c853",
        "tent": "#00c853",
        "tent_h": "#b9f6ca",
        "arc_c": "#69ff94",
        "part_c": "#b9f6ca",
        "ring_c": "#00e676",
        "title_c": "#69ff94",
    },
    "VERMELHO_ALERTA": {
        "label": "Vermelho · Alerta",
        "danger": "#ff6b6b",
        "accent": "#ff1744",
        "glow_h": "#d50000",
        "glow_m": "#7f0000",
        "core1": "#ff5252",
        "core2": "#ff1744",
        "core3": "#d50000",
        "tent": "#ff1744",
        "tent_h": "#ff867c",
        "arc_c": "#ff5252",
        "part_c": "#ff867c",
        "ring_c": "#ff1744",
        "title_c": "#ff5252",
    },
}


def kit_pintura(nome: str) -> KitPintura:
    r = TEMAS_CORE.get(nome, TEMAS_CORE["LARANJA_MESA"])
    return KitPintura(
        bg_tint=_hc(r["glow_h"], 22),
        glow_hot=_hc(r["glow_h"]),
        glow_mid=_hc(r["glow_m"]),
        scan_line=_hc(r["arc_c"], 9),
        ring_outer=_hc(r["ring_c"], 85),
        accent=_hc(r["accent"]),
        core_white=_qc(255, 255, 255),
        core_mid=_hc(r["core1"]),
        core_outer=_hc(r["core2"]),
        core_hot=_hc(r["core3"]),
        tentacle=_hc(r["tent"]),
        tentacle_hot=_hc(r["tent_h"]),
        particle=_hc(r["part_c"]),
        arc=_hc(r["arc_c"]),
        title=_hc(r["title_c"]),
        subtitle=_hc(r["title_c"], 155),
    )


def lista_temas() -> list[str]:
    return list(TEMAS_CORE.keys())


# Estilos QSS dos botões


def _qss_btn(bg: str, border: str, hover_bg: str) -> str:
    return f"""
        QPushButton {{
            background: {bg};
            border: 1px solid {border};
            border-radius: 8px;
            padding: 5px;
            min-width: 44px;
            min-height: 44px;
        }}
        QPushButton:hover {{
            background: {hover_bg};
            border-color: {border};
        }}
        QPushButton:pressed {{
            background: {border}55;
        }}
    """


def qss_botao_accent(raw: dict) -> str:
    a = raw.get("accent", "#ff9500")
    return _qss_btn("rgba(255,255,255,0.07)", a, f"{a}28")


def qss_botao_danger(raw: dict) -> str:
    d = raw.get("danger", "#ff3b30")
    return _qss_btn("rgba(255,59,48,0.08)", d, f"{d}28")


def qss_botao_muted(raw: dict) -> str:
    d = raw.get("danger", "#ff3b30")
    return _qss_btn(f"{d}18", d, f"{d}33")


#   VOZ


class VoiceState(QObject):
    speaking_changed = pyqtSignal(bool)
    intensity_target_changed = pyqtSignal(float)

    def __init__(self):
        super().__init__()
        self._speaking = False
        self._intensity_target = 0.1

    @property
    def speaking(self) -> bool:
        return self._speaking

    @property
    def intensity_target(self) -> float:
        return self._intensity_target

    def set_speaking(self, on: bool, vol: float = 1.0):
        new_target = max(0.2, min(1.0, float(vol))) if on else 0.1
        prev_s = self._speaking
        self._speaking = bool(on)
        if prev_s != self._speaking:
            self.speaking_changed.emit(self._speaking)
        if abs(self._intensity_target - new_target) > 1e-6:
            self._intensity_target = new_target
            self.intensity_target_changed.emit(self._intensity_target)


_voice_singleton: VoiceState | None = None


def get_voice_state() -> VoiceState:
    global _voice_singleton
    if _voice_singleton is None:
        _voice_singleton = VoiceState()
    return _voice_singleton


def falar_on(vol: float = 1.0):
    get_voice_state().set_speaking(True, vol)


def falar_off():
    get_voice_state().set_speaking(False)


#   ÍCONES SVG


_icon_cache: dict[tuple[str, int], QIcon] = {}


def svg_para_icone(svg_bytes: bytes, size: int = 28) -> QIcon:
    key = (hashlib.md5(svg_bytes).hexdigest(), int(size))
    hit = _icon_cache.get(key)
    if hit is not None:
        return hit
    renderer = QSvgRenderer(QByteArray(svg_bytes))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    ic = QIcon(pixmap)
    _icon_cache[key] = ic
    return ic


def svg_mic_on() -> bytes:
    return (
        b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        b'stroke="#f2f7ff" stroke-opacity="0.92" stroke-width="1.85" '
        b'stroke-linecap="round" stroke-linejoin="round">'
        b'<path d="M12 2a3 3 0 0 1 3 3v7a3 3 0 0 1-6 0V5a3 3 0 0 1 3-3z"/>'
        b'<path d="M19 10v2a7 7 0 0 1-14 0v-2"/>'
        b'<line x1="12" y1="19" x2="12" y2="23"/>'
        b'<line x1="8"  y1="23" x2="16" y2="23"/>'
        b"</svg>"
    )


def svg_mic_off(hex_c: str) -> bytes:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        f'stroke="{hex_c}" stroke-opacity="0.9" stroke-width="1.85" '
        f'stroke-linecap="round" stroke-linejoin="round">'
        f'<line x1="1" y1="1" x2="23" y2="23" stroke="{hex_c}"/>'
        f'<path d="M9 9v3a3 3 0 0 0 5.12 2.12M15 9.34V5a3 3 0 0 0-5.94-.6"/>'
        f'<path d="M17 16.95A7 7 0 0 1 5 12v-2m14 0v2a7 7 0 0 1-.11 1.23"/>'
        f'<line x1="12" y1="19" x2="12" y2="23"/>'
        f'<line x1="8"  y1="23" x2="16" y2="23"/>'
        f"</svg>"
    ).encode()


def svg_panel() -> bytes:
    return (
        b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        b'stroke="#f2f7ff" stroke-opacity="0.9" stroke-width="1.85" '
        b'stroke-linecap="round" stroke-linejoin="round">'
        b'<rect x="3"  y="3"  width="7" height="7"/>'
        b'<rect x="14" y="3"  width="7" height="7"/>'
        b'<rect x="14" y="14" width="7" height="7"/>'
        b'<rect x="3"  y="14" width="7" height="7"/>'
        b"</svg>"
    )


def svg_power(hex_c: str) -> bytes:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        f'stroke="{hex_c}" stroke-opacity="0.88" stroke-width="1.85" '
        f'stroke-linecap="round" stroke-linejoin="round">'
        f'<path d="M18.36 6.64a9 9 0 1 1-12.73 0"/>'
        f'<line x1="12" y1="2" x2="12" y2="12"/>'
        f"</svg>"
    ).encode()


def svg_orb_tray(hex_c: str) -> bytes:
    """Ícone circular para a bandeja do sistema."""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
        f"<defs>"
        f'<radialGradient id="g" cx="38%" cy="32%" r="65%">'
        f'<stop offset="0%"   stop-color="#ffffff" stop-opacity="1"/>'
        f'<stop offset="30%"  stop-color="{hex_c}" stop-opacity="0.95"/>'
        f'<stop offset="100%" stop-color="{hex_c}" stop-opacity="0.15"/>'
        f"</radialGradient>"
        f"</defs>"
        f'<circle cx="16" cy="16" r="14" fill="url(#g)"/>'
        f'<circle cx="16" cy="16" r="14" fill="none" '
        f'stroke="{hex_c}" stroke-width="1.2" stroke-opacity="0.55"/>'
        f'<circle cx="16" cy="16" r="4"  fill="#ffffff" fill-opacity="0.9"/>'
        f"</svg>"
    ).encode()


#   WIDGET PRINCIPAL


class JarvisUI(QWidget):

    def __init__(self, tema: str | None = None, voice: VoiceState | None = None, painel: QWidget | None = None):
        super().__init__()
        self.painel_core = painel

        # transparência
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._fixado_no_topo = False
        self._aplicar_flags_janela()

        self.setFixedSize(1200, 900)

        # estado interno
        self._voice = voice if voice is not None else get_voice_state()
        self.tempo_vivido = 0.0
        self.intensidade_interna = 0.0
        self._breath_factor = 1.0
        self.is_muted = False
        self.is_scanning = True
        self.posicao_arrasto = None
        self._opacidade = 1.0
        self._bg_cache = None
        self._bg_cache_tema = None
        self._cache_w = 0
        self._cache_h = 0

        # dados do HUD (atualizados dinamicamente)
        self._hud_neural = 97.4
        self._hud_energy = 3.21
        self._hud_tick = 0

        # persistência
        self._settings = QSettings("Mark_Jarvis", "HUD")
        st = self._settings

        nome = tema
        if nome is None:
            tv = st.value("theme", "LARANJA_MESA")
            nome = str(tv) if tv else "LARANJA_MESA"
        if nome not in TEMAS_CORE:
            nome = "LARANJA_MESA"

        self._tema_nome = nome
        self._raw = TEMAS_CORE[self._tema_nome]
        self._kit = kit_pintura(self._tema_nome)

        try:
            self._opacidade = float(st.value("opacity", 1.0))
        except Exception:
            self._opacidade = 1.0
        self.setWindowOpacity(max(0.15, min(1.0, self._opacidade)))

        self.setWindowIcon(svg_para_icone(svg_orb_tray(self._raw["accent"]), 32))
        self.centralizar_janela()

        vp = st.value("win_pos")
        if isinstance(vp, QPoint):
            self.move(vp)

        self._montar_barra_botoes()
        self._montar_bandeja()

        self.timer_repintar = QTimer(self)
        self.timer_repintar.timeout.connect(self.atualizar_animacao)
        self.timer_repintar.start(33)  # ~30 fps

    # gerenciamento de janela

    def _aplicar_flags_janela(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnBottomHint
        )

        self.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            False
        )

    def centralizar_janela(self):
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

    def prefer_reduce_motion(self) -> bool:
        try:
            sh = QApplication.styleHints()
            fn = getattr(sh, "preferReducedMotion", None)
            if callable(fn):
                return bool(fn())
        except Exception:
            pass
        return False

    # tema e opacidade

    def aplicar_tema(self, nome: str):
        if nome not in TEMAS_CORE:
            return
        self._tema_nome = nome
        self._raw = TEMAS_CORE[nome]
        self._kit = kit_pintura(nome)
        self._settings.setValue("theme", nome)

        hd = self._raw["danger"]
        self.btn_code.setIcon(svg_para_icone(svg_panel(), 26))
        self.btn_off.setIcon(svg_para_icone(svg_power(hd), 26))
        self.btn_code.setStyleSheet(qss_botao_accent(self._raw))
        self.btn_off.setStyleSheet(qss_botao_danger(self._raw))

        if self.is_muted:
            self.btn_mute.setIcon(svg_para_icone(svg_mic_off(hd), 28))
            self.btn_mute.setStyleSheet(qss_botao_muted(self._raw))
        else:
            self.btn_mute.setIcon(svg_para_icone(svg_mic_on(), 28))
            self.btn_mute.setStyleSheet(qss_botao_accent(self._raw))

        icon = svg_para_icone(svg_orb_tray(self._raw["accent"]), 32)
        self.setWindowIcon(icon)
        self._tray_icon.setIcon(icon)
        self.update()

    def _ciclar_opacidade(self):
        niveis = [1.0, 0.75, 0.50, 0.25]
        idx = 0
        for i, n in enumerate(niveis):
            if abs(self._opacidade - n) < 0.05:
                idx = i
                break
        self._opacidade = niveis[(idx + 1) % len(niveis)]
        self.setWindowOpacity(self._opacidade)
        self._settings.setValue("opacity", self._opacidade)

    def _alternar_topo(self):
        self._fixado_no_topo = not self._fixado_no_topo
        pos = self.pos()
        self._aplicar_flags_janela()
        self.show()
        self.move(pos)

    # menus

    def _qss_menu(self) -> str:
        a = self._raw.get("accent", "#ff9500")
        return (
            f"QMenu {{"
            f"  background:#090a0d; border:1px solid {a}44;"
            f"  border-radius:6px; padding:4px;"
            f"  color:#e8e0d0; font-family:'Courier New',monospace; font-size:11px;"
            f"}}"
            f"QMenu::item {{ padding:6px 20px 6px 10px; border-radius:3px; }}"
            f"QMenu::item:selected {{ background:{a}22; color:{a}; }}"
            f"QMenu::separator {{ height:1px; background:{a}22; margin:3px 6px; }}"
        )

    def menu_tema(self, pos):
        m = QMenu(self)
        m.setStyleSheet(self._qss_menu())

        # controles de voz e scan
        falar_txt = "🎙  Parar fala" if self._voice.speaking else "🎙  Iniciar fala"
        m.addAction(falar_txt).triggered.connect(self.alternar_falar)

        scan_txt = "🔍  Desativar scan" if self.is_scanning else "🔍  Ativar scan"
        m.addAction(scan_txt).triggered.connect(self.alternar_scan)

        m.addSeparator()

        # sub-menu temas
        sm = m.addMenu("🎨  Tema")
        sm.setStyleSheet(self._qss_menu())
        for nome, raw in TEMAS_CORE.items():
            label = raw.get("label", nome)
            prefix = "✓  " if nome == self._tema_nome else "    "
            act = sm.addAction(prefix + label)
            act.triggered.connect(lambda _=False, n=nome: self.aplicar_tema(n))

        m.addSeparator()

        niveis_label = {1.0: "100%", 0.75: "75%", 0.50: "50%", 0.25: "25%"}
        lbl_op = niveis_label.get(self._opacidade, "—")
        m.addAction(f"🔆  Opacidade: {lbl_op}").triggered.connect(
            self._ciclar_opacidade
        )

        topo_txt = (
            "📌  Fixar no topo" if not self._fixado_no_topo else "📌  Enviar para fundo"
        )
        m.addAction(topo_txt).triggered.connect(self._alternar_topo)

        m.addAction("⊕  Centralizar").triggered.connect(self.centralizar_janela)

        m.addSeparator()
        m.addAction("⏻  Encerrar sistema").triggered.connect(QApplication.quit)

        m.exec(self.barra_hud.mapToGlobal(pos))

    # bandeja do sistema

    def _montar_bandeja(self):
        self._tray_icon = QSystemTrayIcon(self)
        self._tray_icon.setIcon(svg_para_icone(svg_orb_tray(self._raw["accent"]), 32))
        self._tray_icon.setToolTip("J.A.R.V.I.S  ◈  Overlay Ativo")

        menu = QMenu()
        menu.setStyleSheet(self._qss_menu())

        a_toggle = QAction("◈  Mostrar / Ocultar", self)
        a_toggle.triggered.connect(self._toggle_visibilidade)
        menu.addAction(a_toggle)

        a_centro = QAction("⊕  Centralizar", self)
        a_centro.triggered.connect(self.centralizar_janela)
        menu.addAction(a_centro)

        menu.addSeparator()

        a_falar = QAction("🎙  Iniciar / Parar fala", self)
        a_falar.triggered.connect(self.alternar_falar)
        menu.addAction(a_falar)

        a_scan = QAction("🔍  Ativar / Desativar scan", self)
        a_scan.triggered.connect(self.alternar_scan)
        menu.addAction(a_scan)

        menu.addSeparator()

        sm_t = menu.addMenu("🎨  Tema")
        sm_t.setStyleSheet(self._qss_menu())
        for nome, raw in TEMAS_CORE.items():
            label = raw.get("label", nome)
            prefix = "✓  " if nome == self._tema_nome else "    "
            act = QAction(prefix + label, self)
            act.triggered.connect(lambda _=False, n=nome: self.aplicar_tema(n))
            sm_t.addAction(act)

        a_op = QAction("🔆  Ciclar opacidade", self)
        a_op.triggered.connect(self._ciclar_opacidade)
        menu.addAction(a_op)

        a_topo = QAction("📌  Alternar topo / fundo", self)
        a_topo.triggered.connect(self._alternar_topo)
        menu.addAction(a_topo)

        menu.addSeparator()
        a_sair = QAction("⏻  Encerrar sistema", self)
        a_sair.triggered.connect(QApplication.quit)
        menu.addAction(a_sair)

        self._tray_icon.setContextMenu(menu)
        self._tray_icon.activated.connect(self._tray_ativado)
        self._tray_icon.show()

    def _toggle_visibilidade(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()

    def _tray_ativado(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._toggle_visibilidade()

    # botões HUD

    def _montar_barra_botoes(self):
        self.barra_hud = QFrame(self)
        self.barra_hud.setObjectName("HudBar")
        self.barra_hud.setFixedSize(310, 90)
        self.barra_hud.setStyleSheet("QFrame#HudBar { background: transparent; }")
        self.barra_hud.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.barra_hud.customContextMenuRequested.connect(self.menu_tema)

        layout = QHBoxLayout(self.barra_hud)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        hd = self._raw["danger"]
        self.btn_mute = QPushButton()
        self.btn_code = QPushButton()
        self.btn_off = QPushButton()

        self.btn_mute.setIcon(svg_para_icone(svg_mic_on(), 28))
        self.btn_mute.setIconSize(QSize(28, 28))
        self.btn_code.setIcon(svg_para_icone(svg_panel(), 26))
        self.btn_code.setIconSize(QSize(26, 26))
        self.btn_off.setIcon(svg_para_icone(svg_power(hd), 26))
        self.btn_off.setIconSize(QSize(26, 26))

        self.btn_mute.setStyleSheet(qss_botao_accent(self._raw))
        self.btn_code.setStyleSheet(qss_botao_accent(self._raw))
        self.btn_off.setStyleSheet(qss_botao_danger(self._raw))

        self.btn_mute.setToolTip("Mutar / Desmutar microfone")
        self.btn_code.setToolTip("Abrir Painel J.A.R.V.I.S")
        self.btn_off.setToolTip("Encerrar sistema")

        self.btn_mute.clicked.connect(self.alternar_microfone)
        self.btn_code.clicked.connect(self.alternar_painel)
        self.btn_off.clicked.connect(QApplication.quit)

        for btn in (self.btn_mute, self.btn_code, self.btn_off):
            layout.addWidget(btn)

    def _qss_j_btn(self, active: bool) -> str:
        a = self._raw.get("accent", "#ff9500")
        if active:
            return (
                f"QPushButton {{"
                f"  background: {a}44; border: 1px solid {a};"
                f"  color: {a}; font-family:'Courier New',monospace;"
                f"  font-size:8px; letter-spacing:3px; padding:4px 12px;"
                f"  border-radius: 3px;"
                f"  box-shadow: 0 0 12px {a}88;"
                f"}}"
                f"QPushButton:hover {{ background: {a}66; }}"
            )
        else:
            return (
                f"QPushButton {{"
                f"  background: {a}18; border: 1px solid {a}77;"
                f"  color: {a}bb; font-family:'Courier New',monospace;"
                f"  font-size:8px; letter-spacing:3px; padding:4px 12px;"
                f"  border-radius: 3px;"
                f"}}"
                f"QPushButton:hover {{ background: {a}33; color: {a}; border-color: {a}; }}"
            )

    def alternar_falar(self):
        v = self._voice
        if v.speaking:
            v.set_speaking(False)
        else:
            v.set_speaking(True, 0.85)

    def alternar_scan(self):
        self.is_scanning = not self.is_scanning

    def _ciclar_tema(self):
        nomes = lista_temas()
        idx = nomes.index(self._tema_nome) if self._tema_nome in nomes else 0
        self.aplicar_tema(nomes[(idx + 1) % len(nomes)])

    def montar_barra_botoes(self):
        self._montar_barra_botoes()

    # ações dos botões

    def alternar_painel(self):
        if self.painel_core:
            visivel = self.painel_core.isVisible()
            self.painel_core.setVisible(not visivel)
            if not visivel:
                self.painel_core.raise_()

    def alternar_microfone(self):
        self.is_muted = not self.is_muted
        hd = self._raw["danger"]
        if self.is_muted:
            self.btn_mute.setIcon(svg_para_icone(svg_mic_off(hd), 28))
            self.btn_mute.setStyleSheet(qss_botao_muted(self._raw))
            print("[SISTEMA] Microfone MUTADO")
        else:
            self.btn_mute.setIcon(svg_para_icone(svg_mic_on(), 28))
            self.btn_mute.setStyleSheet(qss_botao_accent(self._raw))
            print("[SISTEMA] Microfone ATIVO")

    def atualizar_animacao(self):
        try:
            falando = self._voice.speaking
            alvo = self._voice.intensity_target if falando else 0.0
            vel = 0.22 if alvo > self.intensidade_interna else 0.055
            self.intensidade_interna += (alvo - self.intensidade_interna) * vel
            iv = self.intensidade_interna

            if falando:
                speed = 0.6 + iv * 2.4
                self.tempo_vivido += 0.05 * speed
                self._breath_factor = math.sin(self.tempo_vivido * 3.0) * 0.15 + 0.85
                self.update()
            elif iv > 0.001:
                self.tempo_vivido += 0.01
                self._breath_factor = 1.0
                self.update()
            else:
                self._breath_factor = 1.0
        except RuntimeError:
            self.timer_repintar.stop()

    # eventos Qt

    def closeEvent(self, event):
        self.timer_repintar.stop()
        self._settings.setValue("win_pos", self.pos())
        self._settings.setValue("theme", self._tema_nome)
        self._settings.setValue("opacity", self._opacidade)
        if hasattr(self, "_tray_icon"):
            self._tray_icon.hide()
        event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.posicao_arrasto = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )

    def mouseMoveEvent(self, event):
        if (
            event.buttons() == Qt.MouseButton.LeftButton
            and self.posicao_arrasto is not None
        ):
            self.move(event.globalPosition().toPoint() - self.posicao_arrasto)

    def mouseReleaseEvent(self, event):
        self.posicao_arrasto = None

    def contextMenuEvent(self, event):
        """Clique direito em qualquer ponto da janela abre o menu."""
        self.menu_tema(self.barra_hud.mapFromGlobal(event.globalPos()))

    # PINTURA

    def paintEvent(self, event):
        k = self._kit
        painter = QPainter(self)
        try:
            W = self.width()
            H = self.height()
            cx = W // 2
            cy = int(H // 2.15)
            iv = self.intensidade_interna
            t = self.tempo_vivido
            r_sol = 88 + iv * 24
            r_anel1 = r_sol * 1.65
            r_anel2 = r_sol * 2.60
            r_anel3 = r_sol * 3.40

            # fundo radial
            bg = QRadialGradient(cx, cy, r_anel3 * 1.1)
            bg.setColorAt(0, k.bg_tint)
            bg.setColorAt(1, QColor(0, 0, 0, 0))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(bg))
            painter.drawEllipse(
                int(cx - r_anel3 * 1.1), int(cy - r_anel3 * 1.1),
                int(r_anel3 * 2.2), int(r_anel3 * 2.2),
            )

            self.desenhar_scan_overlay(painter, W, H, k)
            self.desenhar_linhas_radar(painter, cx, cy, r_anel3, k)
            self.desenhar_aneis(painter, cx, cy, r_anel1, r_anel2, r_anel3, t, iv, k)

            # brilho externo
            glow_outer = QRadialGradient(cx, cy, r_sol * 4.0)
            glow_outer.setColorAt(0, k.glow_hot)
            glow_outer.setColorAt(0.4, k.glow_mid)
            glow_outer.setColorAt(1, QColor(0, 0, 0, 0))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(glow_outer))
            r4 = r_sol * 4
            painter.drawEllipse(int(cx - r4), int(cy - r4), int(r4 * 2), int(r4 * 2))

            red = self.prefer_reduce_motion()
            if iv > 0.04:
                self.desenhar_tentaculos(painter, cx, cy, r_sol, t, iv, k, red)

            self.desenhar_nucleo(painter, cx, cy, r_sol, iv, k)
            self.desenhar_particulas(painter, cx, cy, r_sol, r_anel2, t, iv, k, red)
            self.desenhar_arco(painter, cx, cy, r_anel1, t, iv, k)

            if self.is_scanning:
                self.desenhar_scan_rotator(painter, cx, cy, r_anel1, t, iv, k)

            y_texto = cy + r_anel2 + 100
            self.desenhar_titulos(painter, cx, y_texto, iv, k)
            hud_y = int(y_texto + 34)
            self.barra_hud.move(int(cx - self.barra_hud.width() // 2), hud_y)

        except Exception:
            pass
        finally:
            painter.end()

    # sub-rotinas de desenho

    def _renderizar_bg_cache(self, W, H, k):
        bg = QPixmap(W, H)
        bg.fill(Qt.GlobalColor.transparent)
        bp = QPainter(bg)
        c = QColor(k.arc)
        c.setAlpha(5)
        bp.setPen(QPen(c, 0.6))
        for y in range(0, H, 5):
            bp.drawLine(0, y, W, y)
        bp.end()
        self._bg_cache = bg
        self._bg_cache_tema = self._tema_nome
        self._cache_w = W
        self._cache_h = H

    def desenhar_scan_overlay(self, p, W, H, k):
        if (self._bg_cache is None or self._bg_cache_tema != self._tema_nome
                or self._cache_w != W or self._cache_h != H):
            self._renderizar_bg_cache(W, H, k)
        p.drawPixmap(0, 0, self._bg_cache)

    def desenhar_scan_rotator(self, p, cx, cy, r, t, iv, k):
        if iv < 0.01: return
        speed = 1.2 * (1.0 + iv * 1.5)
        p.save()
        p.translate(cx, cy)
        p.rotate(math.degrees(t * speed))
        c = QColor(k.core_mid)
        c.setAlpha(int(45 + iv * 60))
        p.setBrush(QBrush(c))
        p.setPen(Qt.PenStyle.NoPen)
        sweep = int((22 + iv * 18) * 16)
        rect = QRectF(-r, -r, r * 2, r * 2)
        p.drawPie(rect, 0, sweep)
        p.restore()

    def desenhar_linhas_radar(self, p, cx, cy, r, k):
        p.setPen(QPen(k.scan_line, 1.0))
        y0, y1 = int(cy - r), int(cy + r)
        for y in range(y0, y1, 14):
            dx = math.sqrt(max(0.0, r * r - (y - cy) ** 2))
            p.drawLine(int(cx - dx), y, int(cx + dx), y)

    def desenhar_aneis(self, p, cx, cy, r1, r2, r3, t, iv, k):
        if iv < 0.01:
            ac = QColor(k.accent)
            ac.setAlpha(40)
            p.setPen(QPen(ac, 0.8))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(cx, cy), r2, r2)
            return

        bf = self._breath_factor

        pen = QPen(k.ring_outer, 1.2)
        pen.setStyle(Qt.PenStyle.DashLine)
        pen.setDashPattern([6, 8])
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.save()
        p.translate(cx, cy)
        p.rotate(math.degrees(t * 0.18 * (1.0 + iv * 0.8)))
        p.drawEllipse(QPointF(0, 0), r3, r3)
        p.restore()

        ac = QColor(k.accent)
        ac.setAlpha(int(50 + iv * 100))
        p.setPen(QPen(ac, 1.0 + iv * 0.5))
        p.drawEllipse(QPointF(cx, cy), r2, r2)

        ac2 = QColor(k.accent)
        ac2.setAlpha(int(80 + iv * 120))
        pen3 = QPen(ac2, 1.5)
        pen3.setStyle(Qt.PenStyle.DotLine)
        p.setPen(pen3)
        p.save()
        p.translate(cx, cy)
        p.rotate(-math.degrees(t * 0.35 * (1.0 + iv * 0.6)))
        p.drawEllipse(QPointF(0, 0), r1, r1)
        p.restore()

        n_dots = 6 if iv > 0.3 else 4
        dot = QColor(k.accent)
        dot.setAlpha(int(50 + iv * 80 + 40))
        p.setBrush(QBrush(dot))
        p.setPen(Qt.PenStyle.NoPen)
        for i in range(n_dots):
            ang = math.radians(i * (360 / n_dots) + math.degrees(t * 0.4 * (1.0 + iv * 0.5)))
            sz = 4 + iv * 4
            p.drawEllipse(
                QPointF(cx + math.cos(ang) * r2, cy + math.sin(ang) * r2), sz, sz
            )

    def desenhar_nucleo(self, p, cx, cy, r, iv, k):
        bf = self._breath_factor
        r_efetivo = r * (1.0 + (bf - 1.0) * iv * 0.3)

        halo = QRadialGradient(cx, cy, r_efetivo * 1.5)
        hm = QColor(k.core_mid)
        hm.setAlpha(int(100 + iv * 120))
        halo.setColorAt(0, hm)
        halo.setColorAt(
            1, QColor(k.core_outer.red(), k.core_outer.green(), k.core_outer.blue(), 0)
        )
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(halo))
        p.drawEllipse(QPointF(cx, cy), r_efetivo * 1.5, r_efetivo * 1.5)

        sun = QRadialGradient(cx - r_efetivo * 0.12, cy - r_efetivo * 0.12, r_efetivo)
        sun.setColorAt(0.00, k.core_white)
        sun.setColorAt(0.15, k.core_mid)
        co = QColor(k.core_outer)
        sun.setColorAt(0.40, co)
        sun.setColorAt(0.70, QColor(co.red(), co.green(), co.blue(), 160 + int(iv * 60)))
        ch = k.core_hot
        sun.setColorAt(1.00, QColor(ch.red(), ch.green(), ch.blue(), 0))
        p.setBrush(QBrush(sun))
        p.drawEllipse(QPointF(cx, cy), r_efetivo, r_efetivo)

        core = QRadialGradient(cx, cy, r_efetivo * 0.18)
        core.setColorAt(0, k.core_white)
        r2 = QColor(255, 255, 255)
        r2.setAlpha(int(200 + iv * 55))
        core.setColorAt(1, r2)
        p.setBrush(QBrush(core))
        p.drawEllipse(QPointF(cx, cy), r_efetivo * 0.18 * bf, r_efetivo * 0.18 * bf)

    def desenhar_tentaculos(self, p, cx, cy, r_sol, t, iv, k, red):
        if red or iv < 0.05: return
        ang_base = math.radians((t * 10) % 360)
        n = 10 if iv < 0.25 else (12 if iv < 0.5 else 14)
        for i in range(n):
            ang = ang_base + math.radians(i * (360 / n))
            stretch = 1.0 + iv * 0.4
            dist = 180 + math.sin(t * 1.8 + i * 0.9) * 70 * stretch + iv * 80 + (i % 3) * 20

            tb = QColor(k.tentacle)
            tb.setAlpha(int(max(0, min(255, 40 + iv * 80 + math.sin(t + i) * 20))))
            width = 1.2 + iv * 2.4 - (i % 3) * 0.3

            th2 = QColor(k.tentacle_hot)
            blend = QColor(
                min(255, int((tb.red() + th2.red()) / 2) + i * 2),
                min(255, int((tb.green() + th2.green()) / 2)),
                min(255, int((tb.blue() + th2.blue()) / 2)),
                max(20, tb.alpha()),
            )
            p.setPen(QPen(blend, max(0.3, width)))
            self.desenhar_tentaculo_unico(p, cx, cy, r_sol, ang, i, t, dist)

    def desenhar_tentaculo_unico(self, p, cx, cy, r_sol, angle, idx, t, dist):
        perp = angle + math.pi / 2.8
        onda = 75 + math.cos(t * 1.1 + idx) * 45
        sx = cx + math.cos(angle) * (r_sol * 0.78)
        sy = cy + math.sin(angle) * (r_sol * 0.78)
        ex = cx + math.cos(angle) * dist
        ey = cy + math.sin(angle) * dist
        c1x = sx + math.cos(angle) * 55 + math.cos(perp) * onda
        c1y = sy + math.sin(angle) * 55 + math.sin(perp) * onda
        c2x = ex - math.cos(angle) * 55 - math.cos(perp) * onda
        c2y = ey - math.sin(angle) * 55 - math.sin(perp) * onda
        path = QPainterPath()
        path.moveTo(QPointF(sx, sy))
        path.cubicTo(QPointF(c1x, c1y), QPointF(c2x, c2y), QPointF(ex, ey))
        p.strokePath(path, p.pen())

    def desenhar_particulas(self, p, cx, cy, r_sol, r_max, t, iv, k, red):
        if iv < 0.02: return
        ang_base = math.radians((t * 10) % 360)
        if iv < 0.1:
            specs = ((8, 1.25, -1.5, 2, 160), (6, 2.0, 1.0, 2, 120))
        elif red:
            specs = ((10, 1.25, -1.5, 2, 160), (8, 2.0, 1.0, 2, 120))
        else:
            specs = (
                (18, 1.25, -1.5, 3, 200),
                (12, 2.00, 1.0, 2, 160),
                (8, 2.80, -0.6, 4, 130),
            )
        base = QColor(k.particle)
        for num, r_fac, speed_fac, size, base_alpha in specs:
            r_orbit = r_sol * r_fac
            for i in range(num):
                ang = ang_base * speed_fac + math.radians(i * 360 / num)
                px_ = cx + math.cos(ang) * r_orbit
                py_ = cy + math.sin(ang) * r_orbit
                col = QColor(base)
                col.setAlpha(int(min(255, base_alpha + iv * 55)))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(col))
                p.drawEllipse(QPointF(px_, py_), size, size)

    def desenhar_arco(self, p, cx, cy, r, t, iv, k):
        if iv < 0.01: return
        num_seg = 14 + int(iv * 16)
        gap_deg = 2.5 + (1.0 - iv) * 1.5
        seg_deg = (360 / num_seg) - gap_deg
        offset = math.degrees(t * 0.55 * (1.0 + iv * 0.4))

        arc_col = QColor(k.arc)
        arc_col.setAlpha(int(160 + iv * 95))
        p.setPen(QPen(arc_col, 2.5 + iv * 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.setBrush(Qt.BrushStyle.NoBrush)

        rect = QRectF(cx - r, cy - r, r * 2, r * 2)
        for i in range(num_seg):
            start_deg = i * (360 / num_seg) + offset
            p.drawArc(rect, int(start_deg * 16), int(seg_deg * 16))

        if iv > 0.3:
            arc_col2 = QColor(k.arc)
            arc_col2.setAlpha(int(iv * 60))
            p.setPen(QPen(arc_col2, 1.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            pulse_ang = math.degrees(t * 1.5 * (1.0 + iv)) % 360
            p.drawArc(rect, int(pulse_ang * 16), int(seg_deg * 8))

    def desenhar_titulos(self, p, cx, y, iv, k):
        alpha = int(130 + iv * 125)
        glow_boost = 1.0 + iv * 0.3

        tit = QColor(k.title)
        tit.setAlpha(alpha)
        fnt = QFont("Segoe UI", 19, QFont.Weight.Bold)
        fnt.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 7)
        p.setFont(fnt)
        texto = "J.A.R.V.I.S"
        fm = QFontMetrics(fnt)
        larg = fm.horizontalAdvance(texto)

        if iv > 0.2:
            glow = QColor(k.glow_hot)
            glow.setAlpha(int(iv * 30))
            p.setPen(QPen(glow, 3.0))
            for dx, dy in [(-2, 0), (2, 0), (0, -1), (0, 1)]:
                p.drawText(int(cx - larg // 2 + dx), int(y + dy), texto)

        p.setPen(QPen(tit))
        p.drawText(int(cx - larg // 2), int(y), texto)

        fnt2 = QFont("Segoe UI", 10, QFont.Weight.Bold)
        fnt2.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 5)
        p.setFont(fnt2)
        subc = QColor(k.subtitle)
        subc.setAlpha(int(alpha * 0.65))
        p.setPen(QPen(subc))
        sub = "A C T I V E"
        fm2 = QFontMetrics(fnt2)
        larg2 = fm2.horizontalAdvance(sub)
        p.drawText(int(cx - larg2 // 2), int(y + 22), sub)


#   ENTRY POINT


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # mantém vivo mesmo sem janelas visíveis

    janela = JarvisUI()
    janela.show()

    # Ctrl+C no terminal funciona
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    _unix_timer = QTimer()
    _unix_timer.start(200)
    _unix_timer.timeout.connect(lambda: None)

    # demo: alterna modo fala a cada 2.8 s
    def _demo_audio():
        v = get_voice_state()
        if v.speaking:
            v.set_speaking(False)
        else:
            v.set_speaking(True, 0.85)
        QTimer.singleShot(2800, _demo_audio)

    QTimer.singleShot(500, _demo_audio)
    sys.exit(app.exec())
