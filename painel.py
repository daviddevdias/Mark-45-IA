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


def set_loop(loop):
    global main_async_loop
    main_async_loop = loop


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
    except Exception as e:
        print(f"Erro ao carregar ROUTES: {e}")

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
    except Exception as e:
        print(f"Erro ao carregar TOOL_DECLARATIONS: {e}")

    biblioteca.extend(
        [
            {
                "cmd": "CONFIRMAR AJUDA",
                "cat": "CONFIRMAÇÃO",
                "desc": "Confirmação longa.",
                "passos": ["pedido aceito"],
                "handler": "confirm",
                "icon": "✓",
                "poder": "◆",
            },
            {
                "cmd": "NEGAR AJUDA",
                "cat": "CONFIRMAÇÃO",
                "desc": "Recusa longa.",
                "passos": ["negar"],
                "handler": "deny",
                "icon": "✗",
                "poder": "◆",
            },
        ]
    )

    return biblioteca


async def run_test_voice():
    from audio.voz import falar

    await falar("Painel JARVIS operacional.")


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
        return json.dumps({"status": "ok"})

    @pyqtSlot(result=str)
    def obter_comandos(self) -> str:
        try:
            cmds = montar_biblioteca_comandos()
            return json.dumps(cmds)
        except Exception as e:
            return json.dumps({"erro": str(e)})

    @pyqtSlot(result=str)
    def obter_configuracoes_atuais(self) -> str:
        try:
            return json.dumps(
                {
                    "nome_mestre": getattr(config, "NOME_MESTRE", ""),
                    "cidade_padrao": getattr(config, "cidade_padrao", ""),
                    "gemini": getattr(config, "GEMINI_API_KEY", ""),
                    "qwen": getattr(config, "QWEN_API_KEY", ""),
                    "voz": getattr(config, "voz_atual", "pt-BR-AntonioNeural"),
                    "voz_atual": getattr(config, "voz_atual", "pt-BR-AntonioNeural"),
                    "openweather_api_key": getattr(config, "OPENWEATHER_API_KEY", ""),
                    "spotify_id": getattr(config, "SPOTIFY_ID", ""),
                    "spotify_sec": getattr(config, "SPOTIFY_SECRET", ""),
                    "smartthings": getattr(config, "SMARTTHINGS_TOKEN", ""),
                    "telegram_token": getattr(config, "TELEGRAM_TOKEN", ""),
                    "telegram_auth_token": getattr(config, "TELEGRAM_AUTH_TOKEN", ""),
                    "deepgram_api_key": "",
                    "whisper_model": getattr(config, "WHISPER_MODEL", "small"),
                    "tema_ativo": getattr(config, "tema_ativo", "LARANJA_MESA"),
                }
            )
        except Exception as e:
            return json.dumps({"erro": str(e)})

    @pyqtSlot(str)
    def salvar_configuracao(self, chave: str, valor: str):
        try:
            config.definir_valor_ui(chave, valor)
            arquivo = resolver_arquivo(chave)
            from pathlib import Path

            caminho = config.API_DIR / arquivo
            dados = config.ler_json(caminho) if caminho.exists() else {}
            dados[chave] = valor
            caminho.write_text(
                json.dumps(dados, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except Exception as e:
            print(f"Erro ao salvar {chave}: {e}")

    @pyqtSlot(result=str)
    def obter_alarmes(self) -> str:
        try:
            from tasks.alarm import gerenciador_alarmes

            alarmes = gerenciador_alarmes._carregar_alarmes()
            return json.dumps(alarmes)
        except Exception as e:
            return json.dumps({"erro": str(e)})

    @pyqtSlot(str)
    def salvar_alarme(self, dados_json: str):
        try:
            from tasks.alarm import gerenciador_alarmes

            a = json.loads(dados_json)
            gerenciador_alarmes.adicionar_alarme(
                hora=a.get("hora", ""),
                missao=a.get("missao", "Alarme"),
                repetir=a.get("repetir", False),
                data=a.get("data", None),
                dias_semana=a.get("dias_semana", None),
            )
        except Exception as e:
            print(f"Erro salvar alarme: {e}")

    @pyqtSlot(str)
    def remover_alarme(self, dados_json: str):
        try:
            from tasks.alarm import gerenciador_alarmes

            a = json.loads(dados_json)
            gerenciador_alarmes.remover_alarme(
                hora=a.get("hora", ""),
                missao=a.get("missao", ""),
                data=a.get("data", None),
            )
        except Exception as e:
            print(f"Erro remover alarme: {e}")

    @pyqtSlot()
    def limpar_alarmes_concluidos(self):
        try:
            from tasks.alarm import gerenciador_alarmes

            gerenciador_alarmes.limpar_alarmes_concluidos()
        except Exception as e:
            print(f"Erro limpar alarmes: {e}")

    @pyqtSlot(str)
    def solicitar_clima(self, cidade: str):
        try:
            from tasks.weather import obter_previsao_hoje, obter_clima_raw
            import asyncio

            loop = asyncio.get_event_loop()
            resultado = asyncio.run_coroutine_threadsafe(
                self._buscar_clima(cidade), main_async_loop
            )
        except Exception as e:
            self.dados_para_ui.emit(json.dumps({"erro": str(e)}))

    async def _buscar_clima(self, cidade: str):
        try:
            from tasks.weather import obter_previsao_hoje, obter_clima_raw

            dados = obter_clima_raw(cidade)
            self.dados_para_ui.emit(
                json.dumps({"clima_dados": json.loads(dados), "cidade_buscada": cidade})
            )
        except Exception as e:
            self.dados_para_ui.emit(json.dumps({"erro": str(e)}))

    @pyqtSlot(result=str)
    def obter_ia_status(self) -> str:
        try:
            from engine.ia_router import router, disponivel, modelo

            return json.dumps(router.status)
        except Exception as e:
            return json.dumps({"modelo": "", "servidor": False, "erro": str(e)})

    @pyqtSlot()
    def testar_voz_painel(self):
        try:
            from audio.voz import falar
            import asyncio

            if main_async_loop and not main_async_loop.is_closed():
                asyncio.run_coroutine_threadsafe(
                    falar("Painel operacional."), main_async_loop
                )
        except Exception as e:
            print(f"Erro teste voz: {e}")


class PainelCore(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Jarvis Control Panel")
        self.voz_ativa = False
        self.bridge = JarvisBridge()
        self.bridge.bind_window(self)

        self.web = QWebEngineView()
        self.setCentralWidget(self.web)

        channel = QWebChannel()
        channel.registerObject("bridge", self.bridge)
        self.web.page().setWebChannel(channel)

        web_path = QUrl.fromLocalFile(str(config.BASE_DIR / "web" / "index.html"))
        self.web.setUrl(web_path)

        config.registrar_callback_voz_painel(self.on_voice_change)

        self.timer_stats = QTimer()
        self.timer_stats.timeout.connect(self.atualizar_stats)
        self.timer_stats.start(1000)

    def on_voice_change(self, on: bool, vol: float = 1.0):
        self.voz_ativa = on
        self.bridge.dados_para_ui.emit(json.dumps({"voz_speaking": on, "voz_vol": vol}))

    def atualizar_stats(self):
        dados = {"voz_speaking": self.voz_ativa}
        try:
            from tasks.monitor import status_hardware

            hw = status_hardware()
            dados.update(
                {
                    "cpu": hw["cpu_percent"],
                    "ram": hw["ram_percent"],
                    "bateria": hw["bateria_percent"],
                    "disco": hw["disco_percent"],
                    "temp": hw["temp_cpu"],
                    "uptime": hw["uptime"],
                    "processos": hw["processos"],
                    "internet": hw["internet"],
                }
            )
        except:
            self.bridge.cpu_atual = psutil.cpu_percent(interval=None)
            self.bridge.ram_atual = psutil.virtual_memory().percent
            dados.update({"cpu": self.bridge.cpu_atual, "ram": self.bridge.ram_atual})
        self.bridge.dados_para_ui.emit(json.dumps(dados))
