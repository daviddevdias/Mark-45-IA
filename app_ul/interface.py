import hashlib
import math
import signal
import sys

from PyQt6.QtCore import QByteArray, QObject, QPoint, QPointF, QRectF, QSize, QSettings, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QApplication, QFrame, QHBoxLayout, QMenu, QPushButton, QWidget

from app_ul.theme import TEMAS_CORE, kit_pintura, lista_temas, qss_botao_accent, qss_botao_danger, qss_botao_muted


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
        b'<line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/>'
        b"</svg>"
    )


def svg_mic_off(hex_c: str) -> bytes:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        f'stroke="{hex_c}" stroke-opacity="0.9" stroke-width="1.85" stroke-linecap="round" stroke-linejoin="round">'
        f'<line x1="1" y1="1" x2="23" y2="23" stroke="{hex_c}"/>'
        f'<path d="M9 9v3a3 3 0 0 0 5.12 2.12M15 9.34V5a3 3 0 0 0-5.94-.6"/>'
        f'<path d="M17 16.95A7 7 0 0 1 5 12v-2m14 0v2a7 7 0 0 1-.11 1.23"/>'
        f'<line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/>'
        f"</svg>"
    ).encode()


def svg_panel() -> bytes:
    return (
        b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        b'stroke="#f2f7ff" stroke-opacity="0.9" stroke-width="1.85" stroke-linecap="round" stroke-linejoin="round">'
        b'<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/>'
        b'<rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>'
        b"</svg>"
    )


def svg_power(hex_c: str) -> bytes:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        f'stroke="{hex_c}" stroke-opacity="0.88" stroke-width="1.85" stroke-linecap="round" stroke-linejoin="round">'
        f'<path d="M18.36 6.64a9 9 0 1 1-12.73 0"/><line x1="12" y1="2" x2="12" y2="12"/>'
        f"</svg>"
    ).encode()


class JarvisUI(QWidget):
    def __init__(self, tema: str | None = None, voice: VoiceState | None = None):
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnBottomHint
            | Qt.WindowType.Tool
        )
        self.setFixedSize(1200, 900)
        self._voice = voice if voice is not None else get_voice_state()
        self.tempo_vivido = 0.0
        self.intensidade_interna = 0.0
        self.is_muted = False
        self.posicao_arrasto = None
        self.painel_referencia = None
        self._settings = QSettings("Mark_Jarvis", "HUD")
        st = self._settings
        nome = tema
        if nome is None:
            tv = st.value("theme", "LARANJA_MESA")
            nome = str(tv) if tv else "LARANJA_MESA"
        if nome == "PHANTOM":
            nome = "LARANJA_MESA"
        if nome not in TEMAS_CORE:
            nome = "LARANJA_MESA"
        self._tema_nome = nome
        self._raw = TEMAS_CORE[self._tema_nome]
        self._kit = kit_pintura(self._tema_nome)
        self.setWindowIcon(svg_para_icone(svg_panel(), 32))
        self.centralizar_janela()
        vp = st.value("win_pos")
        if isinstance(vp, QPoint):
            self.move(vp)
        self.montar_barra_botoes()
        self.timer_repintar = QTimer(self)
        self.timer_repintar.timeout.connect(self.atualizar_animacao)
        self.timer_repintar.start(16)

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
            return False
        return False

    def aplicar_tema(self, nome: str):
        if nome not in TEMAS_CORE:
            return
        self._tema_nome = nome
        self._raw = TEMAS_CORE[nome]
        self._kit = kit_pintura(nome)
        self._settings.setValue("theme", nome)
        hd = self._raw["danger"]
        self.btn_mute.setIcon(svg_para_icone(svg_mic_on(), 28))
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
        self.update()

    def menu_tema(self, pos):
        m = QMenu(self)
        sm = m.addMenu("Tema")
        for nome in lista_temas():
            act = sm.addAction(nome)
            act.triggered.connect(lambda _=False, n=nome: self.aplicar_tema(n))
        m.exec(self.barra_hud.mapToGlobal(pos))











    def montar_barra_botoes(self):
        self.barra_hud = QFrame(self)
        self.barra_hud.setObjectName("HudBar")
        self.barra_hud.setFixedSize(310, 90)
        self.barra_hud.setStyleSheet("QFrame#HudBar { background: transparent; }")
        self.barra_hud.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.barra_hud.customContextMenuRequested.connect(self.menu_tema)
        layout = QHBoxLayout(self.barra_hud)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)
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
        self.btn_code.clicked.connect(self.abrir_painel_principal)
        self.btn_off.clicked.connect(QApplication.quit)
        for btn in (self.btn_mute, self.btn_code, self.btn_off):
            layout.addWidget(btn)












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













    def abrir_painel_principal(self):
        if self.painel_referencia is not None and self.painel_referencia.isVisible():
            self.painel_referencia.raise_()
            self.painel_referencia.activateWindow()
            return
        try:
            from painel import PainelCore

            self.painel_referencia = PainelCore()
            self.painel_referencia.show()
        except Exception as e:
            print(f"[SISTEMA] Falha ao abrir painel: {e}")












    def atualizar_animacao(self):
        try:
            alvo = self._voice.intensity_target if self._voice.speaking else 0.1
            vel = 0.22 if alvo > self.intensidade_interna else 0.055
            self.intensidade_interna += (alvo - self.intensidade_interna) * vel
            speed = 0.28 + self.intensidade_interna * 1.6
            self.tempo_vivido += 0.05 * speed
            self.update()
        except RuntimeError:
            self.timer_repintar.stop()
















    def closeEvent(self, event):
        self.timer_repintar.stop()
        self._settings.setValue("win_pos", self.pos())
        self._settings.setValue("theme", self._tema_nome)
        event.accept()











    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.posicao_arrasto = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )












    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self.posicao_arrasto is not None:
            self.move(event.globalPosition().toPoint() - self.posicao_arrasto)








    def mouseReleaseEvent(self, event):
        self.posicao_arrasto = None











    def paintEvent(self, event):
        k = self._kit
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            cx = self.width() // 2
            cy = int(self.height() // 2.15)
            iv = self.intensidade_interna
            t = self.tempo_vivido
            ang_base = math.radians((t * 10) % 360)
            r_sol = 88 + iv * 24
            r_anel1 = r_sol * 1.65
            r_anel2 = r_sol * 2.60
            r_anel3 = r_sol * 3.40
            bg = QRadialGradient(cx, cy, r_anel3 * 1.1)
            bg.setColorAt(0, k.bg_tint)
            bg.setColorAt(1, QColor(0, 0, 0, 0))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(bg))
            painter.drawEllipse(
                int(cx - r_anel3 * 1.1),
                int(cy - r_anel3 * 1.1),
                int(r_anel3 * 2.2),
                int(r_anel3 * 2.2),
            )
            self.desenhar_linhas_radar(painter, cx, cy, r_anel3, k)
            self.desenhar_aneis(painter, cx, cy, r_anel1, r_anel2, r_anel3, t, iv, k)
            glow_outer = QRadialGradient(cx, cy, r_sol * 4.0)
            gh = QColor(k.glow_hot)
            gh.setAlpha(int(90 + iv * 60))
            gm = QColor(k.glow_mid)
            gm.setAlpha(int(30 + iv * 20))
            glow_outer.setColorAt(0, gh)
            glow_outer.setColorAt(0.4, gm)
            glow_outer.setColorAt(1, QColor(0, 0, 0, 0))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(glow_outer))
            r4 = r_sol * 4
            painter.drawEllipse(int(cx - r4), int(cy - r4), int(r4 * 2), int(r4 * 2))
            red = self.prefer_reduce_motion()
            if iv > 0.04 and not red:
                self.desenhar_tentaculos(painter, cx, cy, r_sol, ang_base, t, iv, k)
            elif iv > 0.04 and red:
                self.desenhar_tentaculos(painter, cx, cy, r_sol, ang_base, t, iv * 0.35, k)
            self.desenhar_nucleo(painter, cx, cy, r_sol, iv, k)
            self.desenhar_particulas(painter, cx, cy, r_sol, r_anel2, ang_base, iv, k, red)
            self.desenhar_arco(painter, cx, cy, r_anel1, t, k)
            y_texto = cy + r_anel2 + 44
            self.desenhar_titulos(painter, cx, y_texto, iv, k)
            hud_y = int(y_texto + 34)
            self.barra_hud.move(int(cx - self.barra_hud.width() // 2), hud_y)
        except Exception:
            pass
        finally:
            painter.end()







    def desenhar_linhas_radar(self, p, cx, cy, r, k):
        pen = QPen(k.scan_line, 1.0)
        p.setPen(pen)
        y0, y1 = int(cy - r), int(cy + r)
        for y in range(y0, y1, 14):
            dx = math.sqrt(max(0, r * r - (y - cy) ** 2))
            p.drawLine(int(cx - dx), y, int(cx + dx), y)











    def desenhar_aneis(self, p, cx, cy, r1, r2, r3, t, iv, k):
        pen = QPen(k.ring_outer, 1.2)
        pen.setStyle(Qt.PenStyle.DashLine)
        pen.setDashPattern([6, 8])
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.save()
        p.translate(cx, cy)
        p.rotate(math.degrees(t * 0.18))
        p.drawEllipse(QPointF(0, 0), r3, r3)
        p.restore()
        ac = QColor(k.accent)
        ac.setAlpha(int(50 + iv * 80))
        p.setPen(QPen(ac, 1.0))
        p.drawEllipse(QPointF(cx, cy), r2, r2)
        ac2 = QColor(k.accent)
        ac2.setAlpha(int(80 + iv * 100))
        pen3 = QPen(ac2, 1.5)
        pen3.setStyle(Qt.PenStyle.DotLine)
        p.setPen(pen3)
        p.save()
        p.translate(cx, cy)
        p.rotate(-math.degrees(t * 0.35))
        p.drawEllipse(QPointF(0, 0), r1, r1)
        p.restore()
        dot = QColor(k.accent)
        dot.setAlpha(int(50 + iv * 80 + 40))
        p.setBrush(QBrush(dot))
        p.setPen(Qt.PenStyle.NoPen)
        for i in range(4):
            ang = math.radians(i * 90 + math.degrees(t * 0.22))
            p.drawEllipse(QPointF(cx + math.cos(ang) * r2, cy + math.sin(ang) * r2), 4, 4)











    def desenhar_nucleo(self, p, cx, cy, r, iv, k):
        halo = QRadialGradient(cx, cy, r * 1.5)
        hm = QColor(k.core_mid)
        hm.setAlpha(int(100 + iv * 80))
        halo.setColorAt(0, hm)
        halo.setColorAt(1, QColor(k.core_outer.red(), k.core_outer.green(), k.core_outer.blue(), 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(halo))
        p.drawEllipse(QPointF(cx, cy), r * 1.5, r * 1.5)
        sun = QRadialGradient(cx - r * 0.12, cy - r * 0.12, r)
        sun.setColorAt(0.00, k.core_white)
        sun.setColorAt(0.15, k.core_mid)
        co = QColor(k.core_outer)
        sun.setColorAt(0.40, co)
        sun.setColorAt(0.70, QColor(co.red(), co.green(), co.blue(), 160))
        ch = k.core_hot
        sun.setColorAt(1.00, QColor(ch.red(), ch.green(), ch.blue(), 0))
        p.setBrush(QBrush(sun))
        p.drawEllipse(QPointF(cx, cy), r, r)
        core = QRadialGradient(cx, cy, r * 0.18)
        core.setColorAt(0, k.core_white)
        core.setColorAt(1, QColor(255, 255, 255, 0))
        p.setBrush(QBrush(core))
        p.drawEllipse(QPointF(cx, cy), r * 0.18, r * 0.18)








    def desenhar_tentaculos(self, p, cx, cy, r_sol, ang_base, t, iv, k):
        for i in range(12):
            ang = ang_base + math.radians(i * (360 / 12))
            dist = 180 + math.sin(t * 1.4 + i * 0.9) * 70 + iv * 50 + (i % 3) * 20
            tb = QColor(k.tentacle)
            tb.setAlpha(int(40 + iv * 60 + math.sin(t + i) * 20))
            width = 1.2 + iv * 1.8 - (i % 3) * 0.3
            th = QColor(k.tentacle_hot)
            blend = QColor(
                int((tb.red() + th.red()) / 2) + i * 2,
                int((tb.green() + th.green()) / 2),
                int((tb.blue() + th.blue()) / 2),
                max(20, tb.alpha()),
            )
            p.setPen(QPen(blend, width))
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













    def desenhar_particulas(self, p, cx, cy, r_sol, r_max, ang_base, iv, k, red):
        specs = (
            (22, 1.25, -1.5, 3, 200),
            (16, 2.00, 1.0, 2, 160),
            (10, 2.80, -0.6, 4, 130),
        )
        if red:
            specs = ((10, 1.25, -1.5, 2, 160), (8, 2.0, 1.0, 2, 120))
        base = QColor(k.particle)
        for num, r_fac, speed_fac, size, base_alpha in specs:
            r_orbit = r_sol * r_fac
            for i in range(num):
                ang = ang_base * speed_fac + math.radians(i * 360 / num)
                px_ = cx + math.cos(ang) * r_orbit
                py_ = cy + math.sin(ang) * r_orbit
                col = QColor(base)
                col.setAlpha(int(base_alpha + iv * 55))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(col))
                p.drawEllipse(QPointF(px_, py_), size, size)










    def desenhar_arco(self, p, cx, cy, r, t, k):
        num_seg = 24
        gap_deg = 4.0
        seg_deg = (360 / num_seg) - gap_deg
        offset = math.degrees(t * 0.55)
        arc_pen = QColor(k.arc)
        arc_pen.setAlpha(160)
        p.setPen(
            QPen(
                arc_pen,
                2.5,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
            )
        )
        p.setBrush(Qt.BrushStyle.NoBrush)
        rect = QRectF(cx - r, cy - r, r * 2, r * 2)
        for i in range(num_seg):
            start_deg = i * (360 / num_seg) + offset
            p.drawArc(rect, int(start_deg * 16), int(seg_deg * 16))

    def desenhar_titulos(self, p, cx, y, iv, k):
        alpha = int(130 + iv * 125)
        tit = QColor(k.title)
        tit.setAlpha(alpha)
        fnt = QFont("Segoe UI", 19, QFont.Weight.Bold)
        fnt.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 7)
        p.setFont(fnt)
        p.setPen(QPen(tit))
        texto = "J.A.R.V.I.S"
        fm = QFontMetrics(fnt)
        larg = fm.horizontalAdvance(texto)
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


if __name__ == "__main__":
    app = QApplication(sys.argv)
    janela = JarvisUI()
    janela.show()
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    timer_unix = QTimer()
    timer_unix.start(200)
    timer_unix.timeout.connect(lambda: None)

    def demo_audio_fake():
        v = get_voice_state()
        if v.speaking:
            v.set_speaking(False)
        else:
            v.set_speaking(True, 0.85)
        QTimer.singleShot(2800, demo_audio_fake)

    QTimer.singleShot(500, demo_audio_fake)
    sys.exit(app.exec())