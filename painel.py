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
SMART_FILE       = "config_smart.json"
NOTAS_FILE       = "notas.json"

CAMPOS_CONFIG_CORE = {
    "nome_mestre", "cidade_padrao", "voz", "device_index",
    "tema_ativo", "THEME_ACTIVE", "tema", "tema_custom_accent",
    "tema_custom_secondary", "tema_custom_bg", "ia_mode",
    "gemini", "qwen",
    "openweather_api_key", "telegram_token", "telegram_auth_token",
    "deepgram_api_key", "openai_api_key", "openai_tts_voice", "whisper_model",
    "fish_audio_api_key", "fish_audio_voice_id",
    "spotify_id", "spotify_sec",
    "smartthings", "smartthings_tv_id",
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
            c = c[len(prefixo):].strip()
    return c


def montar_biblioteca_comandos() -> list[dict]:
    biblioteca: list[dict] = []

    try:
        from engine.controller import ROUTES
        visto: set[str] = set()
        for keywords, handler in ROUTES:
            chave = "|".join(keywords)
            if chave in visto:
                continue
            visto.add(chave)
            exemplo = " ".join(keywords).strip()
            biblioteca.append({
                "cmd":     exemplo.upper(),
                "cat":     "VOZ",
                "desc":    f"Frase reconhecida (após normalização): «{exemplo}».",
                "passos":  list(keywords),
                "handler": getattr(handler, "__name__", ""),
                "icon":    "◈",
                "poder":   "⚡",
            })
    except Exception:
        pass

    try:
        from engine.tools import TOOL_DECLARATIONS
        for t in TOOL_DECLARATIONS or []:
            fn   = (t or {}).get("function") or {}
            nome = (fn.get("name") or "").strip()
            if not nome:
                continue
            desc   = (fn.get("description") or "").strip() or "Ferramenta de ação do Jarvis."
            params = (fn.get("parameters") or {}).get("properties") or {}
            passos = []
            for k, v in params.items():
                tip = v.get("type") if isinstance(v, dict) else None
                passos.append(f"{k}{f' ({tip})' if tip else ''}")
            biblioteca.append({
                "cmd":     f"TOOL: {nome}",
                "cat":     "FERRAMENTAS",
                "desc":    desc,
                "passos":  passos[:10],
                "handler": nome,
                "icon":    "⚙",
                "poder":   "◆",
            })
    except Exception:
        pass

    biblioteca.append({
        "cmd":     "CONFIRMAR AJUDA (MONITOR)",
        "cat":     "CONFIRMAÇÃO",
        "desc":    "Quando o Jarvis pergunta se pode ajudar, use frases longas (melhor reconhecimento).",
        "passos":  ["pedido aceito, pode ajudar", "pode analisar", "pode resolver", "aceito a ajuda", "confirmado"],
        "handler": "confirmacao_monitor",
        "icon":    "✔",
        "poder":   "◇",
    })
    biblioteca.append({
        "cmd":     "DISPENSAR AJUDA (MONITOR)",
        "cat":     "CONFIRMAÇÃO",
        "desc":    "Para recusar a ajuda do monitor sem usar 'não' curto.",
        "passos":  ["dispensa ajuda", "não precisa de ajuda", "ignora isso", "pode ignorar", "agora não", "depois"],
        "handler": "recusa_monitor",
        "icon":    "✖",
        "poder":   "◇",
    })

    extras = [
        {
            "cmd":     "OLÁ JARVIS",
            "cat":     "CHAT",
            "desc":    "Mensagem livre para o modelo de IA no painel ou por voz.",
            "passos":  ["Use o chat ou fale após o wake word."],
            "handler": "chat",
            "icon":    "◇",
            "poder":   "◆",
        },
        {
            "cmd":     "CLIMA / PREVISÃO",
            "cat":     "CLIMA",
            "desc":    "Perguntas sobre tempo na cidade padrão ou nomeada.",
            "passos":  ["Ex.: «como está o clima»", "«vai chover amanhã»"],
            "handler": "weather",
            "icon":    "◎",
            "poder":   "◆",
        },
        {
            "cmd":     "QUICK — DASHBOARD",
            "cat":     "ATALHOS",
            "desc":    "Botões rápidos do diagnóstico.",
            "passos":  ["bloquear", "captura", "limpar lixeira", "minimizar", "fechar", "trabalho"],
            "handler": "quick",
            "icon":    "⬡",
            "poder":   "◇",
        },
    ]
    biblioteca.extend(extras)
    return biblioteca


async def run_test_voice():
    from audio.voz import falar
    await falar("Teste de síntese de voz. Painel JARVIS operacional.")


class JarvisBridge(QObject):
    dados_para_ui = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.cpu_atual  = 0.0
        self.ram_atual  = 0.0
        self.window_ref = None

    def bind_window(self, w: QMainWindow):
        self.window_ref = w

    @pyqtSlot()
    def ocultar_painel(self):
        if self.window_ref is not None:
            self.window_ref.hide()

    @pyqtSlot(str)
    def executar_comando(self, cmd: str):
        global main_async_loop
        diretriz = limpar_prefixo(cmd)
        if main_async_loop is not None and not main_async_loop.is_closed():
            asyncio.run_coroutine_threadsafe(self.executar_e_emitir(diretriz), main_async_loop)

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
        msg    = router.definir_modo(modo)
        status = router.status
        self.dados_para_ui.emit(json.dumps({"resposta": msg, "ia_status": status}))
        return json.dumps({"ok": True, "modo": modo, "msg": msg})

    @pyqtSlot(result=str)
    def obter_ia_status(self) -> str:
        from engine.ia_router import router
        return json.dumps(router.status)

    @pyqtSlot(str, str)
    def salvar_configuracao(self, chave: str, valor: str):
        config.definir_valor_ui(chave, valor)
        try:
            arquivo = resolver_arquivo(chave)
            config.salvar_json(arquivo, {chave: valor})
        except Exception:
            pass

    @pyqtSlot(result=str)
    def obter_biblioteca_comandos(self) -> str:
        return json.dumps(montar_biblioteca_comandos())

    @pyqtSlot(result=str)
    def obter_configuracoes_atuais(self) -> str:
        from engine.ia_router import router
        dados = config.ler_json(config.API_DIR / CONFIG_CORE_FILE)
        return json.dumps({
            "gemini":               getattr(config, "GEMINI_API_KEY",        ""),
            "qwen":                 getattr(config, "QWEN_API_KEY",           ""),
            "openweather_api_key":  getattr(config, "OPENWEATHER_API_KEY",    ""),
            "telegram_token":       getattr(config, "TELEGRAM_TOKEN",         ""),
            "telegram_auth_token":  getattr(config, "TELEGRAM_AUTH_TOKEN",    ""),
            "spotify_id":           getattr(config, "SPOTIFY_ID",             ""),
            "spotify_sec":          getattr(config, "SPOTIFY_SECRET",         ""),
            "smartthings":          getattr(config, "SMARTTHINGS_TOKEN",      ""),
            "smartthings_tv_id":    getattr(config, "SMARTTHINGS_TV_DEVICE_ID", "") or "",
            "deepgram_api_key":     getattr(config, "DEEPGRAM_API_KEY",       ""),
            "openai_api_key":       getattr(config, "OPENAI_API_KEY",         ""),
            "openai_tts_voice":     getattr(config, "OPENAI_TTS_VOICE",       "nova"),
            "whisper_model":        getattr(config, "WHISPER_MODEL",          "small"),
            "fish_audio_api_key":   getattr(config, "FISH_AUDIO_API_KEY",     ""),
            "fish_audio_voice_id":  getattr(config, "FISH_AUDIO_VOICE_ID",    ""),
            "nome_mestre":          getattr(config, "NOME_MESTRE",            ""),
            "ia_mode":              router.status.get("modelo", "ollama"),
            "notas":                getattr(config, "notas",                  ""),
            "cidade_padrao":        dados.get("cidade_padrao", "São Paulo"),
            "voz":                  getattr(config, "voz_atual",              "pt-BR-AntonioNeural"),
            "device_index":         getattr(config, "DEVICE_INDEX",           1),
        })



    @pyqtSlot(result=str)
    def obter_tema_ativo(self) -> str:
        dados = config.ler_json(config.API_DIR / CONFIG_CORE_FILE)
        tema  = dados.get("tema", dados.get("tema_ativo", ""))
        if isinstance(tema, dict):
            return json.dumps(tema)
        return json.dumps(str(tema) if tema else "")

    @pyqtSlot(result=str)
    def obter_config_voz(self) -> str:
        try:
            from audio.voz import listar_microfones
            mics = listar_microfones()
        except Exception:
            mics = []
        return json.dumps({
            "device_index": int(getattr(config, "DEVICE_INDEX", 0) or 0),
            "microfones":   mics,
        })

    @pyqtSlot()
    def testar_voz_painel(self):
        global main_async_loop
        if main_async_loop is not None and not main_async_loop.is_closed():
            asyncio.run_coroutine_threadsafe(run_test_voice(), main_async_loop)

    @pyqtSlot()
    def interromper_voz_painel(self):
        try:
            from audio.voz import interromper_voz
            interromper_voz()
        except Exception:
            pass

    @pyqtSlot()
    def desligar_sistema(self):
        try:
            from engine.controller import get_shutdown_event
            get_shutdown_event().set()
        except Exception:
            pass
        app = QApplication.instance()
        if app is not None:
            app.quit()

    @pyqtSlot(result=str)
    def get_status(self) -> str:
        return json.dumps({"cpu": self.cpu_atual, "ram": self.ram_atual, "online": True})

    @pyqtSlot()
    def solicitar_analise_visual(self):
        global main_async_loop
        if main_async_loop is not None and not main_async_loop.is_closed():
            asyncio.run_coroutine_threadsafe(self.rotina_visao_ui(), main_async_loop)

    @pyqtSlot(str)
    def solicitar_analise_visual_com_prompt(self, prompt_usuario: str):
        global main_async_loop
        if main_async_loop is not None and not main_async_loop.is_closed():
            asyncio.run_coroutine_threadsafe(self.rotina_visao_ui(prompt_usuario), main_async_loop)

    async def rotina_visao_ui(self, prompt_personalizado: str = None):
        try:
            from vision.capture import analisar_tela, capturar_frame_base64
            prompt_final = prompt_personalizado or "Descreve o que está visível no ecrã e se há erros óbvios."
            self.dados_para_ui.emit(json.dumps({"visao_status": "A capturar o ecrã..."}))
            await asyncio.sleep(0.8)
            loop = asyncio.get_running_loop()
            b64  = await loop.run_in_executor(None, capturar_frame_base64)
            if not b64:
                self.dados_para_ui.emit(json.dumps({"visao_erro": "Falha na captura de tela."}))
                return
            self.dados_para_ui.emit(json.dumps({"visao_status": "Imagem capturada. A analisar com Qwen-VL..."}))
            analise = await analisar_tela(prompt_final)
            self.dados_para_ui.emit(json.dumps({"visao_img": b64, "visao_resultado": analise}))
        except Exception as e:
            self.dados_para_ui.emit(json.dumps({"visao_erro": str(e)}))

    @pyqtSlot(str)
    def solicitar_clima(self, cidade: str):
        if not cidade:
            dados  = config.ler_json(config.API_DIR / CONFIG_CORE_FILE)
            cidade = (getattr(config, "cidade_padrao", None) or "").strip() or dados.get("cidade_padrao", "São Paulo")
        global main_async_loop
        if main_async_loop is not None and not main_async_loop.is_closed():
            asyncio.run_coroutine_threadsafe(self.rotina_clima(cidade), main_async_loop)

    async def rotina_clima(self, cidade: str):
        try:
            from tasks.weather import obter_clima_raw
            loop         = asyncio.get_running_loop()
            resultado_str = await loop.run_in_executor(None, obter_clima_raw, cidade)
            resultado_json = json.loads(resultado_str)
            self.dados_para_ui.emit(json.dumps({"clima_dados": resultado_json, "cidade_buscada": cidade}))
        except Exception as e:
            self.dados_para_ui.emit(json.dumps({"erro": f"Clima: {e}"}))

    @pyqtSlot(result=str)
    def obter_alarmes(self) -> str:
        try:
            from tasks import alarm
            return json.dumps(alarm.carregar_alarmes())
        except Exception:
            return "[]"

    @pyqtSlot(str)
    def salvar_alarme(self, dados_json: str):
        try:
            from tasks import alarm
            alarme  = json.loads(dados_json)
            alarmes = alarm.carregar_alarmes()
            alarmes.append(alarme)
            alarm.salvar_alarmes(alarmes)
            if alarm.falar_callback and alarm.alarm_loop_ativo:
                asyncio.run_coroutine_threadsafe(
                    alarm.falar_callback("Senhor, despertador configurado."),
                    alarm.alarm_loop_ativo,
                )
        except Exception:
            pass

    @pyqtSlot(str)
    def remover_alarme(self, dados_json: str):
        try:
            from tasks import alarm
            req = json.loads(dados_json)
            alarm.remover_alarme(req.get("hora"), req.get("missao"), req.get("data"))
        except Exception:
            pass

    @pyqtSlot()
    def parar_alarme(self):
        try:
            from tasks import alarm
            alarm.parar_alarme_total()
        except Exception:
            pass

    @pyqtSlot()
    def limpar_alarmes_concluidos(self):
        try:
            from tasks import alarm
            alarm.limpar_alarmes_concluidos()
        except Exception:
            pass


class PainelCore(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("J.A.R.V.I.S ◈ MARK XXVIII")
        self.resize(1480, 750)

        try:
            app = QApplication.instance()
            if app is not None:
                app.setQuitOnLastWindowClosed(False)
        except Exception:
            pass

        try:
            self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)
        except Exception:
            pass

        self.view    = QWebEngineView()
        self.setCentralWidget(self.view)
        self.channel = QWebChannel()
        self.bridge  = JarvisBridge()
        self.bridge.bind_window(self)
        self.channel.registerObject("jarvis", self.bridge)
        self.view.page().setWebChannel(self.channel)

        caminho_html = Path(__file__).resolve().parent / "web" / "index.html"
        self.view.load(QUrl.fromLocalFile(str(caminho_html)))

        self.timer_metricas = QTimer()
        self.timer_metricas.timeout.connect(self.atualizar_hardware)
        self.timer_metricas.start(2000)

        self.timer_ia = QTimer()
        self.timer_ia.timeout.connect(self.atualizar_ia_status)
        self.timer_ia.start(15000)

        try:
            from engine.core import registrar_ui_bridge
            registrar_ui_bridge(self.bridge)
        except Exception:
            pass

        def hook_voz(on: bool, vol: float = 1.0):
            try:
                self.bridge.dados_para_ui.emit(
                    json.dumps({"voz_speaking": bool(on), "voz_vol": float(vol)})
                )
            except Exception:
                pass

        config.registrar_callback_voz_painel(hook_voz)

    def closeEvent(self, event):
        self.hide()
        event.ignore()

    def enviar_para_html(self, json_str: str):
        script = f"if(window.receberDoJarvis){{window.receberDoJarvis({json_str});}}"
        self.view.page().runJavaScript(script)

    def atualizar_hardware(self):
        try:
            cpu = psutil.cpu_percent()
            ram = psutil.virtual_memory().percent
            self.bridge.cpu_atual = cpu
            self.bridge.ram_atual = ram
            self.enviar_para_html(json.dumps({"cpu": cpu, "ram": ram}))
        except Exception:
            pass

    def atualizar_ia_status(self):
        try:
            from engine.ia_router import router
            self.enviar_para_html(json.dumps({"ia_status": router.status}))
        except Exception:
            pass


def set_loop(loop: asyncio.AbstractEventLoop):
    global main_async_loop
    main_async_loop = loop