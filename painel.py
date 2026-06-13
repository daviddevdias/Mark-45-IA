import asyncio
import json
from pathlib import Path
import config
import psutil
from PyQt6.QtCore import QObject, QTimer, QUrl, Qt, pyqtSignal, pyqtSlot
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import QApplication, QMainWindow

main_async_loop = None
CONFIG_CORE_FILE = "config_core.json"
SMART_FILE = "config_smart.json"
NOTAS_FILE = "notas.json"

CAMPOS_CONFIG_CORE = {
    "qwen",
    "gemini",
    "current_model",
    "spotify_id",
    "spotify_sec",
    "smartthings",
    "smartthings_tv_id",
    "telegram_token",
    "telegram_auth_token",
    "telegram_allowed_ids",
    "openweather_api_key",
    "deepgram_api_key",
    "whisper_model",
    "nome_mestre",
    "voz",
    "voz_atual",
    "device_index",
    "tema_ativo",
    "notas",
    "cidade_padrao",
}


def resolver_arquivo(chave: str) -> str:
    if chave == "notas":
        return NOTAS_FILE
    if chave in CAMPOS_CONFIG_CORE:
        return CONFIG_CORE_FILE
    return SMART_FILE


def limpar_prefixo(cmd: str) -> str:
    c = cmd.strip().lower()
    for prefixo in ("core,", "core"):
        if c.startswith(prefixo):
            c = c[len(prefixo) :].strip()
    return c


def montar_biblioteca_comandos() -> list[dict]:
    biblioteca = []
    try:
        from engine.controller import ROUTES

        visto = set()
        for keywords, handler in ROUTES:
            chave = "|".join(keywords)
            if chave in visto:
                continue
            visto.add(chave)
            biblioteca.append(
                {
                    "cmd": " ".join(keywords).strip().upper(),
                    "cat": "VOZ",
                    "desc": f"Reconhecimento: «{' '.join(keywords)}».",
                    "passos": list(keywords),
                    "handler": getattr(handler, "__name__", ""),
                    "icon": "◈",
                    "poder": "⚡",
                }
            )
    except:
        pass
    try:
        from engine.tools import TOOL_DECLARATIONS

        for t in TOOL_DECLARATIONS or []:
            nome = (t.get("function", {}).get("name") or "").strip()
            if not nome:
                continue
            params = t.get("function", {}).get("parameters", {}).get("properties", {})
            passos = [
                f"{k} ({v.get('type')})" if isinstance(v, dict) and v.get("type") else k
                for k, v in params.items()
            ]
            biblioteca.append(
                {
                    "cmd": f"TOOL: {nome}",
                    "cat": "FERRAMENTAS",
                    "desc": t.get("function", {}).get("description", "Ação Jarvis."),
                    "passos": passos[:10],
                    "handler": nome,
                    "icon": "⚙",
                    "poder": "◆",
                }
            )
    except:
        pass
    biblioteca.extend(
        [
            {
                "cmd": "CONFIRMAR AJUDA",
                "cat": "CONFIRMAÇÃO",
                "desc": "Confirmação longa.",
                "passos": ["pedido aceito"],
                "handler": "confirmacao",
                "icon": "✔",
                "poder": "◇",
            },
            {
                "cmd": "DISPENSAR AJUDA",
                "cat": "CONFIRMAÇÃO",
                "desc": "Recusa longa.",
                "passos": ["dispensa ajuda"],
                "handler": "recusa",
                "icon": "✖",
                "poder": "◇",
            },
            {
                "cmd": "OLÁ JARVIS",
                "cat": "CHAT",
                "desc": "Mensagem livre.",
                "passos": ["chat"],
                "handler": "chat",
                "icon": "◇",
                "poder": "◆",
            },
            {
                "cmd": "CLIMA",
                "cat": "CLIMA",
                "desc": "Tempo.",
                "passos": ["clima"],
                "handler": "weather",
                "icon": "◎",
                "poder": "◆",
            },
            {
                "cmd": "QUICK",
                "cat": "ATALHOS",
                "desc": "Ações rápidas.",
                "passos": ["bloquear"],
                "handler": "quick",
                "icon": "⬡",
                "poder": "◇",
            },
        ]
    )
    return biblioteca


async def run_test_voice():
    from audio.voz import falar

    await falar("PainelJARVIS operacional no Linux.")


class JarvisBridge(QObject):
    dados_para_ui = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.cpu_atual = 0.0
        self.ram_atual = 0.0
        self.window_ref = None

    def bind_window(self, w: QMainWindow):
        self.window_ref = w

    @pyqtSlot()
    def ocultar_painel(self):
        if self.window_ref:
            self.window_ref.hide()

    @pyqtSlot(str)
    def executar_comando(self, cmd: str):
        global main_async_loop
        diretriz = limpar_prefixo(cmd)
        if main_async_loop and not main_async_loop.is_closed():
            asyncio.run_coroutine_threadsafe(
                self.executar_e_emitir(diretriz), main_async_loop
            )

    async def executar_e_emitir(self, diretriz: str):
        try:
            from engine.core import processar_comando

            texto = await processar_comando(diretriz)
            if texto:
                self.dados_para_ui.emit(json.dumps({"resposta": texto}))
        except Exception as e:
            self.dados_para_ui.emit(json.dumps({"erro": str(e)}))

    @pyqtSlot(str, result=str)
    def alternar_ia(self, modo: str) -> str:
        from engine.ia_router import router

        msg = router.definir_modo(modo)
        self.dados_para_ui.emit(
            json.dumps({"resposta": msg, "ia_status": router.status})
        )
        return json.dumps({"ok": True, "modo": modo, "msg": msg})

    @pyqtSlot(result=str)
    def obter_ia_status(self) -> str:
        from engine.ia_router import router

        return json.dumps(router.status)

    @pyqtSlot(str, str)
    def salvar_configuracao(self, chave: str, valor: str):
        config.definir_valor_ui(chave, valor)
        try:
            config.salvar_json(resolver_arquivo(chave), {chave: valor})
        except:
            pass

    @pyqtSlot(result=str)
    def obter_biblioteca_comandos(self) -> str:
        return json.dumps(montar_biblioteca_comandos())

    @pyqtSlot(result=str)
    def obter_configuracoes_atuais(self) -> str:
        from engine.ia_router import router

        dados = config.ler_json(config.API_DIR / CONFIG_CORE_FILE)
        return json.dumps(
            {
                "gemini": getattr(config, "GEMINI_API_KEY", ""),
                "qwen": getattr(config, "QWEN_API_KEY", ""),
                "current_model": getattr(
                    config, "CURRENT_MODEL", "qwen/qwen2.5-vl-72b-instruct"
                ),
                "openweather_api_key": getattr(config, "OPENWEATHER_API_KEY", ""),
                "telegram_token": getattr(config, "TELEGRAM_TOKEN", ""),
                "telegram_auth_token": getattr(config, "TELEGRAM_AUTH_TOKEN", ""),
                "telegram_allowed_ids": getattr(config, "TELEGRAM_ALLOWED_IDS", []),
                "spotify_id": getattr(config, "SPOTIFY_ID", ""),
                "spotify_sec": getattr(config, "SPOTIFY_SECRET", ""),
                "smartthings": getattr(config, "SMARTTHINGS_TOKEN", ""),
                "smartthings_tv_id": getattr(config, "SMARTTHINGS_TV_DEVICE_ID", ""),
                "deepgram_api_key": getattr(config, "DEEPGRAM_API_KEY", ""),
                "whisper_model": getattr(config, "WHISPER_MODEL", "small"),
                "nome_mestre": getattr(config, "NOME_MESTRE", "Chefe"),
                "voz": getattr(config, "voz_atual", "pt-BR-AntonioNeural"),
                "device_index": getattr(config, "DEVICE_INDEX", 1),
                "tema_ativo": getattr(config, "tema_ativo", "MIDNIGHT_MINIMAL"),
                "notas": getattr(config, "notas", ""),
                "cidade_padrao": dados.get("cidade_padrao", ""),
                "ia_mode": router.status.get("modelo", "ollama"),
            }
        )

    @pyqtSlot(result=str)
    def obter_tema_ativo(self) -> str:
        dados = config.ler_json(config.API_DIR / CONFIG_CORE_FILE)
        tema = dados.get("tema", dados.get("tema_ativo", ""))
        return json.dumps(tema if isinstance(tema, dict) else str(tema) if tema else "")

    @pyqtSlot(result=str)
    def obter_config_voz(self) -> str:
        try:
            from audio.voz import listar_microfones

            mics = listar_microfones()
        except:
            mics = []
        return json.dumps(
            {
                "device_index": int(getattr(config, "DEVICE_INDEX", 0) or 0),
                "microfones": mics,
            }
        )

    @pyqtSlot()
    def testar_voz_painel(self):
        global main_async_loop
        if main_async_loop and not main_async_loop.is_closed():
            asyncio.run_coroutine_threadsafe(run_test_voice(), main_async_loop)

    @pyqtSlot()
    def interromper_voz_painel(self):
        try:
            from audio.voz import interromper_voz

            interromper_voz()
        except:
            pass

    @pyqtSlot()
    def desligar_sistema(self):
        try:
            from engine.controller import get_shutdown_event

            get_shutdown_event().set()
        except:
            pass
        app = QApplication.instance()
        if app:
            app.quit()

    @pyqtSlot(result=str)
    def get_status(self) -> str:
        return json.dumps(
            {"cpu": self.cpu_atual, "ram": self.ram_atual, "online": True}
        )

    @pyqtSlot()
    def solicitar_analise_visual(self):
        global main_async_loop
        if main_async_loop and not main_async_loop.is_closed():
            asyncio.run_coroutine_threadsafe(self.rotina_visao_ui(), main_async_loop)

    @pyqtSlot(str)
    def solicitar_analise_visual_com_prompt(self, prompt: str):
        global main_async_loop
        if main_async_loop and not main_async_loop.is_closed():
            asyncio.run_coroutine_threadsafe(
                self.rotina_visao_ui(prompt), main_async_loop
            )

    async def rotina_visao_ui(self, prompt_personalizado: str = None):
        try:
            from vision.capture import analisar_tela, capturar_frame_base64

            prompt_final = prompt_personalizado or "Descreve o ecrã e erros óbvios."
            self.dados_para_ui.emit(json.dumps({"visao_status": "Capturando..."}))
            await asyncio.sleep(0.8)
            b64 = await asyncio.get_running_loop().run_in_executor(
                None, capturar_frame_base64
            )
            if not b64:
                self.dados_para_ui.emit(json.dumps({"visao_erro": "Falha na captura."}))
                return
            self.dados_para_ui.emit(json.dumps({"visao_status": "Analisando..."}))
            analise = await analisar_tela(prompt_final)
            self.dados_para_ui.emit(
                json.dumps({"visao_img": b64, "visao_resultado": analise})
            )
        except Exception as e:
            self.dados_para_ui.emit(json.dumps({"visao_erro": str(e)}))

    @pyqtSlot(str)
    def solicitar_clima(self, cidade: str):
        cidade = (
            cidade
            or (getattr(config, "cidade_padrao", None) or "").strip()
            or config.ler_json(config.API_DIR / CONFIG_CORE_FILE).get(
                "cidade_padrao", "São Paulo"
            )
        )
        global main_async_loop
        if main_async_loop and not main_async_loop.is_closed():
            asyncio.run_coroutine_threadsafe(self.rotina_clima(cidade), main_async_loop)

    async def rotina_clima(self, cidade: str):
        try:
            from tasks.weather import obter_clima_raw

            resultado = json.loads(
                await asyncio.get_running_loop().run_in_executor(
                    None, obter_clima_raw, cidade
                )
            )
            self.dados_para_ui.emit(
                json.dumps({"clima_dados": resultado, "cidade_buscada": cidade})
            )
        except Exception as e:
            self.dados_para_ui.emit(json.dumps({"erro": f"Clima: {e}"}))

    @pyqtSlot(result=str)
    def obter_alarmes(self) -> str:
        try:
            from tasks.alarm import carregar_alarmes

            return json.dumps(carregar_alarmes())
        except:
            return "[]"

    @pyqtSlot(str)
    def salvar_alarme(self, dados_json: str):
        try:
            from tasks.alarm import gerenciador_alarmes

            req = json.loads(dados_json)
            gerenciador_alarmes.adicionar_alarme(
                hora=req.get("hora", ""),
                missao=req.get("missao", "Alarme"),
                repetir=req.get("repetir", False),
                musica=req.get("musica", ""),
                data=req.get("data"),
                dias_semana=req.get("dias_semana"),
            )
            if (
                gerenciador_alarmes.falar_callback
                and gerenciador_alarmes.alarm_loop_ativo
                and not gerenciador_alarmes.alarm_loop_ativo.is_closed()
            ):
                asyncio.run_coroutine_threadsafe(
                    gerenciador_alarmes.falar_callback("Despertador configurado."),
                    gerenciador_alarmes.alarm_loop_ativo,
                )
        except:
            pass

    @pyqtSlot(str)
    def remover_alarme(self, dados_json: str):
        try:
            from tasks.alarm import gerenciador_alarmes

            req = json.loads(dados_json)
            gerenciador_alarmes.remover_alarme(
                (req.get("hora") or "").strip(),
                (req.get("missao") or "").strip(),
                req.get("data"),
            )
        except:
            pass

    @pyqtSlot()
    def parar_alarme(self):
        try:
            from tasks.alarm import gerenciador_alarmes

            gerenciador_alarmes.parar_alarme_total()
        except:
            pass

    @pyqtSlot()
    def limpar_alarmes_concluidos(self):
        try:
            from tasks.alarm import gerenciador_alarmes

            gerenciador_alarmes.limpar_alarmes_concluidos()
        except:
            pass


class PainelCore(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("J.A.R.V.I.S ◈ MARK XXVIII")
        self.resize(1480, 750)
        try:
            app = QApplication.instance()
            if app:
                app.setQuitOnLastWindowClosed(False)
            self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)
        except:
            pass

        self.view = QWebEngineView()
        self.setCentralWidget(self.view)
        self.channel = QWebChannel()
        self.bridge = JarvisBridge()
        self.bridge.bind_window(self)
        self.channel.registerObject("jarvis", self.bridge)
        self.view.page().setWebChannel(self.channel)
        self.view.load(
            QUrl.fromLocalFile(
                str(Path(__file__).resolve().parent / "web" / "index.html")
            )
        )

        self.timer_metricas = QTimer()
        self.timer_metricas.timeout.connect(self.atualizar_hardware)
        self.timer_metricas.start(2000)

        self.timer_ia = QTimer()
        self.timer_ia.timeout.connect(self.atualizar_ia_status)
        self.timer_ia.start(15000)

        try:
            from engine.core import registrar_ui_bridge

            registrar_ui_bridge(self.bridge)
        except:
            pass

        def hook_voz(on: bool, vol: float = 1.0):
            try:
                self.bridge.dados_para_ui.emit(
                    json.dumps({"voz_speaking": bool(on), "voz_vol": float(vol)})
                )
            except:
                pass

        config.registrar_callback_voz_painel(hook_voz)

    def closeEvent(self, event):
        self.hide()
        event.ignore()

    def enviar_para_html(self, json_str: str):
        self.view.page().runJavaScript(
            f"if(window.receberDoJarvis){{window.receberDoJarvis({json_str});}}"
        )

    def atualizar_hardware(self):
        try:
            cpu, ram = psutil.cpu_percent(), psutil.virtual_memory().percent
            self.bridge.cpu_atual, self.bridge.ram_atual = cpu, ram
            self.enviar_para_html(json.dumps({"cpu": cpu, "ram": ram}))
        except:
            pass

    def atualizar_ia_status(self):
        try:
            from engine.ia_router import router

            self.enviar_para_html(json.dumps({"ia_status": router.status}))
        except:
            pass


def set_loop(loop: asyncio.AbstractEventLoop):
    global main_async_loop
    main_async_loop = loop
