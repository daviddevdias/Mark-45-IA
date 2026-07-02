import asyncio
import json
import queue
import threading
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
    "email_imap_host",
    "email_user",
    "email_pass",
    "calendar_ics_path",
    "news_ativo",
    "calendar_ativo",
    "email_ativo",
    "briefing_auto",
    "pomodoro_padrao",
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


from PyQt6.QtWebEngineCore import QWebEnginePage


class DebugWebEnginePage(QWebEnginePage):
    

    def javaScriptConsoleMessage(self, level, message, line, source):
        print(f"[JS console] {source}:{line} — {message}")


class JarvisBridge(QObject):

    dados_para_ui = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.cpu_atual = 0.0
        self.ram_atual = 0.0
        self.window_ref = None
        self._logs: list[dict] = []
        self._lm_online = False

    def bind_window(self, w: QMainWindow):
        self.window_ref = w

    def adicionar_log(self, tipo: str, msg: str):
        self._logs.append({"tipo": tipo, "msg": msg})
        if len(self._logs) > 100:
            self._logs = self._logs[-100:]

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

            self.adicionar_log("comando", f"Processando: {diretriz}")
            texto = await processar_comando(diretriz)
            if texto:
                self.dados_para_ui.emit(json.dumps({"resposta": texto}))
                self.adicionar_log("info", f"Resposta: {texto[:60]}")
        except Exception as e:
            self.adicionar_log("erro", f"Erro: {e}")
            self.dados_para_ui.emit(json.dumps({"erro": str(e)}))

    @pyqtSlot(str, result=str)
    def alternar_ia(self, modo: str) -> str:
        from engine.ia_router import router

        msg = router.definir_modo(modo)
        self.adicionar_log("sistema", f"Modo IA: {modo}")
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
                    "email_imap_host": getattr(config, "EMAIL_IMAP_HOST", ""),
                    "email_user": getattr(config, "EMAIL_USER", ""),
                    "email_pass": getattr(config, "EMAIL_PASS", ""),
                    "calendar_ics_path": getattr(config, "CALENDAR_ICS_PATH", ""),
                    "news_ativo": getattr(config, "NEWS_ATIVO", True),
                    "calendar_ativo": getattr(config, "CALENDAR_ATIVO", False),
                    "email_ativo": getattr(config, "EMAIL_ATIVO", False),
                    "briefing_auto": getattr(config, "BRIEFING_AUTO", True),
                    "pomodoro_padrao": getattr(config, "POMODORO_PADRAO", 25),
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

    @pyqtSlot(str, result=str)
    def obter_eventos_por_data(self, data: str) -> str:
        try:
            from tasks.calendar_integration import obter_eventos
            eventos = obter_eventos(data)
            return json.dumps(eventos)
        except Exception as e:
            return json.dumps({"erro": str(e)})

    @pyqtSlot(result=str)
    def obter_emails(self) -> str:
        try:
            from tasks.email_checker import verificar_email
            import asyncio
            if main_async_loop and not main_async_loop.is_closed():
                fut = asyncio.run_coroutine_threadsafe(
                    verificar_email(10), main_async_loop
                )
                emails = fut.result(timeout=15)
                return json.dumps(emails)
            return json.dumps([])
        except Exception as e:
            return json.dumps({"erro": str(e)})

    @pyqtSlot(str)
    def alternar_sentinela(self, acao: str):
        if self.window_ref and hasattr(self.window_ref, '_sentinela_ativado'):
            self.window_ref._sentinela_ativado = (acao == "ativar")
            status = "ativado" if self.window_ref._sentinela_ativado else "desativado"
            self.adicionar_log("sistema", f"Sentinela {status} pelo painel.")

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
        self.resize(1360, 768)
        self.voz_ativa = False
        self.bridge = JarvisBridge()
        self.bridge.bind_window(self)
        self._sentinela_cache = {}
        self._sentinela_queue = queue.Queue(maxsize=1)
        self._sentinela_ativado = False

        self.web = QWebEngineView()
        self.setCentralWidget(self.web)

        self._page = DebugWebEnginePage(self.web)
        self.web.setPage(self._page)

        from PyQt6.QtWebEngineCore import QWebEngineSettings
        settings = self.web.page().settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)

        channel = QWebChannel()
        channel.registerObject("bridge", self.bridge)
        self.web.page().setWebChannel(channel)

        web_path = QUrl.fromLocalFile(str(config.BASE_DIR / "web" / "index.html"))
        self.web.setUrl(web_path)

        QTimer.singleShot(1500, lambda: self.web.page().runJavaScript(
            "console.log('[PYTHON] Injeção direta OK'); adicionarLog('info', 'Backend→JS funcional.');"
            "receberDoBackend({temp:42,cpu:50,ram:50,bateria:80,disco:60,uptime:'TESTE',internet:true,lm_status:true});"
        ))

        config.registrar_callback_voz_painel(self.on_voice_change)

        self.timer_stats = QTimer()
        self.timer_stats.timeout.connect(self.atualizar_stats)
        self.timer_stats.start(1000)

        self.timer_sentinela = QTimer()
        self.timer_sentinela.timeout.connect(self._coletar_sentinela)
        self.timer_sentinela.start(1000)

        self._sentinela_thread = threading.Thread(target=self._loop_sentinela, daemon=True)
        self._sentinela_thread.start()

    def _loop_sentinela(self):
        import time
        while True:
            time.sleep(15)
            try:
                from tasks.sentinela import coletar_tudo
                dados = coletar_tudo()
                try:
                    self._sentinela_queue.get_nowait()
                except queue.Empty:
                    pass
                self._sentinela_queue.put_nowait(dados)
            except:
                pass

    def _coletar_sentinela(self):
        try:
            self._sentinela_cache = self._sentinela_queue.get_nowait()
        except queue.Empty:
            pass

    def on_voice_change(self, on: bool, vol: float = 1.0):
        self.voz_ativa = on
        self.bridge.dados_para_ui.emit(json.dumps({"voz_speaking": on, "voz_vol": vol}))

    def atualizar_stats(self):
        dados = {"voz_speaking": self.voz_ativa}
        if not hasattr(self, '_sem_bateria'):
            try:
                bat = psutil.sensors_battery()
                self._sem_bateria = (bat is None)
            except:
                self._sem_bateria = True
        if self._sem_bateria:
            dados["bateria_ausente"] = True
        try:
            from tasks.monitor import status_hardware
            hw = status_hardware()
            dados.update({
                "cpu": hw["cpu_percent"],
                "ram": hw["ram_percent"],
                "bateria": hw["bateria_percent"],
                "disco": hw["disco_percent"],
                "temp": hw["temp_cpu"],
                "uptime": hw["uptime"],
                "processos": hw["processos"],
                "internet": hw["internet"],
                "gpu": hw.get("gpu_percent", 0),
                "gpu_temp": hw.get("gpu_temp", 0),
                "gpu_mem": hw.get("gpu_mem", 0),
                "gpu_nome": hw.get("gpu_nome", ""),
            })
        except:
            self.bridge.cpu_atual = psutil.cpu_percent(interval=None)
            self.bridge.ram_atual = psutil.virtual_memory().percent
            from datetime import datetime
            start = getattr(self, "_start_time", datetime.now())
            if not hasattr(self, "_start_time"):
                self._start_time = start
            delta = datetime.now() - start
            dias = delta.days
            horas = delta.seconds // 3600
            minutos = (delta.seconds % 3600) // 60
            dados.update({
                "cpu": self.bridge.cpu_atual,
                "ram": self.bridge.ram_atual,
                "uptime": f"{dias}d {horas}h {minutos}m",
                "internet": True,
                "temp": 0,
                "processos": 0,
                "gpu": 0,
                "gpu_temp": 0,
                "gpu_mem": 0,
                "gpu_nome": "",
            })

        try:
            from engine.controller import disponivel as _lm
            lm_ok = bool(_lm)
            if lm_ok != self.bridge._lm_online:
                self.bridge._lm_online = lm_ok
                if lm_ok:
                    self.bridge.adicionar_log("ok", "LM Studio online.")
                else:
                    self.bridge.adicionar_log("erro", "LM Studio offline.")
                    self.bridge._logs.append({"tipo": "erro", "msg": "LM Studio sem operação — sistema fora de trabalho."})
            dados["lm_status"] = lm_ok

            if self._sentinela_ativado and self._sentinela_cache:
                dados["sentinela"] = self._sentinela_cache

            if self.bridge._logs:
                dados["logs"] = list(self.bridge._logs)
                self.bridge._logs.clear()

            dados_json = json.dumps(dados)
            self.bridge.dados_para_ui.emit(dados_json)
        except Exception as e:
            print(f"Erro atualizar_stats: {e}")
            self.bridge.dados_para_ui.emit(json.dumps(dados))