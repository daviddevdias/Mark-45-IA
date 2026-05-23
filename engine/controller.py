from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import re
import time
from collections import deque
from datetime import datetime
from typing import Any, Awaitable, Callable, Optional

import aiohttp
import config

from engine.tools import TOOL_DECLARATIONS
from vision.capture import status_monitor as info_monitor
from vision.capture import parar_monitor as desligar_monitor

log = logging.getLogger("engine.controller")

URL_LOCAL_CHAT   = "http://127.0.0.1:1234/v1/chat/completions"
URL_LOCAL_MODELS = "http://127.0.0.1:1234/v1/models"

TIMEOUT   = 60.0
MAX_HIST  = 20
MAX_TOOLS = 5
COOLDOWN  = 30.0

SYSTEM = (
    "Você é o Jarvis. Responda de forma prestativa, educada e levemente sarcástica como o assistente do Stark. "
    "Responda SEMPRE em português brasileiro. Contexto: {ctx}. "
    "REGRAS: 1. SEMPRE confirme o que fez em uma frase natural. "
    "2. Se abrir um app, diga algo como 'Sistema carregado, Senhor'. "
    "3. Use tool_calls para ações. "
    "4. Frases curtas (até 3 linhas) para resposta rápida."
)

modelo:       str   = ""
disponivel:   bool  = False
ultimo_check: float = 0.0

_SHUTDOWN_EVENT: asyncio.Event | None = None

PREFIXOS_SPOTIFY = [
    "buscar no spotify", "tocar no spotify", "procurar no spotify",
    "buscar spotify", "tocar spotify", "spotify",
    "tocar musica", "toca musica", "buscar musica",
    "colocar", "coloca", "tocar", "toca", "buscar", "busca",
    "musica", "musicas",
]
PREFIXOS_YOUTUBE = ["pesquisar no youtube", "buscar no youtube", "tocar no youtube", "youtube"]
PREFIXOS_WEB = [
    "pesquisar na web", "pesquisar no google", "buscar na web",
    "pesquisar", "pesquisa", "buscar", "busca",
]

Handler = Callable[[str], Awaitable[Optional[str]]]
ROUTES: list[tuple[tuple[str, ...], Handler]] = []

def system_msg(ctx: str):
    agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    return SYSTEM.format(ctx=f"{ctx} | Horário Atual: {agora}"[:400])

def normalizar(texto: str):
    t = re.sub(r"\s+", " ", texto.lower().strip())
    for src, dst in {
        "ã": "a", "â": "a", "á": "a", "à": "a",
        "ê": "e", "é": "e",
        "í": "i",
        "ó": "o", "ô": "o", "õ": "o",
        "ú": "u",
        "ç": "c"
    }.items():
        t = t.replace(src, dst)
    return t

def extrair_numero(texto: str) -> Optional[int]:
    m = re.search(r"\d+", texto)
    return int(m.group()) if m else None

def extrair_termo(cmd: str, prefixos: list):
    texto = cmd.strip()
    for p in sorted(prefixos, key=len, reverse=True):
        if texto.startswith(p):
            texto = texto[len(p):].strip()
            break
    return re.sub(r"^(a musica|o|a|as|os|um|uma)\s+", "", texto).strip()

def get_shutdown_event() -> asyncio.Event:
    global _SHUTDOWN_EVENT
    if _SHUTDOWN_EVENT is None:
        _SHUTDOWN_EVENT = asyncio.Event()
    return _SHUTDOWN_EVENT

async def detectar_modelo() -> bool:
    global modelo, disponivel, ultimo_check
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(URL_LOCAL_MODELS, timeout=aiohttp.ClientTimeout(total=5)) as r:
                if r.status != 200:
                    disponivel = False
                    return False
                resposta = await r.json()
                modelos = [m.get("id") for m in resposta.get("data", [])]
                if not modelos:
                    disponivel = False
                    return False
                modelo       = modelos[0]
                disponivel   = True
                ultimo_check = time.time()
                print(f"LM Studio Online! Modelo carregado: {modelo}")
                return True
    except Exception:
        disponivel = False
        return False

async def check(force: bool = False):
    if not force and disponivel and (time.time() - ultimo_check) < COOLDOWN:
        return
    await detectar_modelo()

def ligar_monitor(intervalo_s: float = 10.0, callback=None):
    from vision.capture import iniciar_monitor as iniciar_mon, MonitorConfig
    cfg = MonitorConfig(intervalo_s=intervalo_s, callback=callback)
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    try:
        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(iniciar_mon(cfg), loop)
        else:
            asyncio.run(iniciar_mon(cfg))
    except Exception as e:
        log.error("Erro ao ligar monitor: %s", e)

class Historico:
    def __init__(self):
        self.turns: deque[dict] = deque(maxlen=MAX_HIST)

    def add(self, role: str, content: Any):
        self.turns.append({"role": role, "content": content})

    def add_tool(self, call_id: str, name: str, result: str):
        self.turns.append({
            "role": "tool",
            "tool_call_id": call_id,
            "name": name,
            "content": result
        })

    def msgs(self) -> list[dict]:
        return list(self.turns)

    def pop(self):
        if self.turns:
            self.turns.pop()

    def clear(self):
        self.turns.clear()

class IARRouter:
    def __init__(self):
        self.historico = Historico()
        self.provedor  = "lmstudio"

    @property
    def status(self) -> dict:
        return {"modelo": modelo, "servidor": disponivel, "provedor": self.provedor}

    @property
    def modo_atual(self):
        return self.provedor

    def definir_modo(self, modo: str):
        if modo == "gemini":
            if not config.GEMINI_API_KEY:
                return "Chave da API do Gemini ausente no sistema."
            self.provedor = "gemini"
            return "Conexão estabelecida com os servidores do Google Gemini."
        if modo in ("openrouter", "auto"):
            if not config.QWEN_API_KEY:
                return "Chave da API externa ausente no sistema."
            self.provedor = "openrouter"
            return "Modelos externos do OpenRouter ativados com sucesso."
        self.provedor = "lmstudio"
        return f"Processamento neural local ativado via LM Studio. Modelo: {modelo or 'nenhum detectado'}."

    def resetar_conversa(self):
        self.historico.clear()
        return "Conversa resetada."

    def montar_content(self, text: str, imagem: Any) -> Any:
        if imagem is None:
            return text
        if isinstance(imagem, str) and os.path.isfile(imagem):
            try:
                with open(imagem, "rb") as f:
                    imagem = f.read()
            except Exception:
                return text
        if isinstance(imagem, bytes):
            url = f"data:image/png;base64,{base64.b64encode(imagem).decode()}"
        elif isinstance(imagem, str) and imagem.startswith("data:"):
            url = imagem
        else:
            return text
        return [
            {"type": "text", "text": text},
            {"type": "image_url", "image_url": {"url": url}}
        ]

    async def chat(self, messages: list[dict], tools: bool = True) -> dict | None:
        if self.provedor in ("gemini", "openrouter"):
            if self.provedor == "gemini":
                url     = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
                hdrs    = {"Authorization": f"Bearer {config.GEMINI_API_KEY}", "Content-Type": "application/json"}
                payload = {"model": "gemini-1.5-flash", "messages": messages, "temperature": 0.7}
            else:
                url     = "https://openrouter.ai/api/v1/chat/completions"
                hdrs    = {"Authorization": f"Bearer {config.QWEN_API_KEY}", "Content-Type": "application/json"}
                payload = {"model": config.CURRENT_MODEL, "messages": messages, "temperature": 0.7}
            if tools:
                payload["tools"] = TOOL_DECLARATIONS
            try:
                async with aiohttp.ClientSession() as s:
                    async with s.post(url, headers=hdrs, json=payload, timeout=aiohttp.ClientTimeout(total=TIMEOUT)) as r:
                        if r.status != 200:
                            return None
                        return (await r.json()).get("choices", [{}])[0].get("message")
            except Exception:
                return None

        if not modelo:
            return None

        payload = {
            "model": modelo,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 800
        }
        if tools:
            payload["tools"] = TOOL_DECLARATIONS
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(URL_LOCAL_CHAT, json=payload, timeout=aiohttp.ClientTimeout(total=TIMEOUT)) as r:
                    if r.status != 200:
                        log.error("Erro na API Local: Status %s", r.status)
                        return None
                    dados = await r.json()
                    return dados.get("choices", [{}])[0].get("message")
        except Exception as e:
            log.error("Erro de conexão com LM Studio: %s", e)
            return None

    async def dispatch(self, name: str, args: dict):
        try:
            from engine.tools_mapper import despachar
            return str(await despachar(name, args))
        except Exception as e:
            return f"Erro na ferramenta '{name}': {e}"

    async def responder(self, pergunta: str, nome: str = "Chefe", memoria: str = "", imagem: Any = None):
        if self.provedor == "lmstudio":
            await check()
            if not disponivel:
                await check(force=True)
            if not disponivel:
                return "Servidor local offline. Inicie o Local Server no LM Studio."
            if not modelo:
                return "Nenhum modelo carregado na memória. Carregue um modelo no LM Studio."

        self.historico.add("user", self.montar_content(pergunta, imagem))
        msgs = [{"role": "system", "content": system_msg(memoria)}] + self.historico.msgs()

        for _ in range(MAX_TOOLS):
            msg = await self.chat(msgs)
            if msg is None:
                return "Falha na comunicação com a IA local."

            tool_calls = msg.get("tool_calls") or []
            if not tool_calls:
                reply = (msg.get("content") or "").strip()
                if not reply or (reply.startswith("{") and reply.endswith("}")):
                    reply = "Comando processado, Senhor."
                self.historico.add("assistant", reply)
                return reply

            for tc in tool_calls:
                call_id = tc.get("id", "call_0")
                fn      = tc.get("function", {})
                raw     = fn.get("arguments", {})
                args    = json.loads(raw) if isinstance(raw, str) else (raw or {})
                result  = await self.dispatch(fn.get("name", ""), args)
                msgs.append({
                    "role": "tool",
                    "tool_call_id": call_id,
                    "name": fn.get("name"),
                    "content": result,
                })
                self.historico.add_tool(call_id, fn.get("name", ""), result)

        return "Protocolo concluído."

router = IARRouter()

async def abrir_web_direto(cmd: str):
    from engine.tools_mapper import gerenciador_browser
    cmd_lower = cmd.lower()
    if "youtube" in cmd_lower:
        gerenciador_browser({"action": "open", "url": "https://www.youtube.com"})
        return "Acessando o YouTube imediatamente."
    elif "google" in cmd_lower:
        gerenciador_browser({"action": "open", "url": "https://www.google.com"})
        return "Abrindo o Google de imediato."
    return "Comando web processado."

async def youtube_busca(cmd: str):
    from engine.tools_mapper import gerenciador_youtube
    termo = extrair_termo(cmd, PREFIXOS_YOUTUBE)
    return gerenciador_youtube({"query": termo} if termo else {})

async def silencio(cmd: str):
    from tasks.computer_control import mutar_volume
    mutar_volume()
    return "Sistema de áudio silenciado."

async def bloquear(cmd: str):
    from tasks.computer_control import bloquear_tela
    bloquear_tela()
    return "Estação bloqueada."

async def minimizar(cmd: str):
    from tasks.computer_control import minimizar_janelas
    minimizar_janelas()
    return "Janelas minimizadas."

async def fechar(cmd: str):
    from tasks.computer_control import fechar_janela_ativa
    fechar_janela_ativa()
    return "Janela encerrada."

async def screenshot(cmd: str):
    from tasks.computer_control import print_tela
    print_tela()
    return "Captura de tela realizada."

async def limpar_lixo(cmd: str):
    from tasks.computer_control import limpar_lixeira
    limpar_lixeira()
    return "Lixeira purgada."

async def trabalho(cmd: str):
    from tasks.open_app import open_app
    open_app({"app_name": "vscode"})
    open_app({"app_name": "chrome"})
    return "Modo de trabalho iniciado. Sistemas prontos."

async def tv_ligar(cmd: str):
    from tasks.smart_home import energia_tv, buscar_id_tv, diagnosticar_falha_tv
    if energia_tv(True):
        return "Televisão ligada."
    if not buscar_id_tv():
        return diagnosticar_falha_tv()
    return "A TV não respondeu ao sinal de energia."

async def tv_desligar(cmd: str):
    from tasks.smart_home import desligar_tv, buscar_id_tv, diagnosticar_falha_tv
    if desligar_tv():
        return "Televisão desligada."
    if not buscar_id_tv():
        return diagnosticar_falha_tv()
    return "Falha ao cessar energia da TV."

async def tv_volume(cmd: str):
    from tasks.smart_home import enviar_comando_tv
    nivel = extrair_numero(cmd)
    if nivel is None:
        return "Por favor, indique o nível do volume."
    nivel = max(0, min(100, nivel))
    if enviar_comando_tv("setVolume", "audioVolume", [nivel]):
        return f"Volume ajustado para {nivel} por cento."
    return "Falha no ajuste de áudio da TV."

async def tv_youtube(cmd: str):
    from tasks.smart_home import abrir_youtube_tv
    return abrir_youtube_tv()

async def musica(cmd: str):
    from tasks.spotify_manager import spotify_stark
    cmd   = re.sub(r"\s+", " ", re.sub(r"\bspotify\b", "", cmd)).strip()
    termo = extrair_termo(cmd, PREFIXOS_SPOTIFY)
    if termo:
        return spotify_stark.abrir_e_buscar(termo)
    return "Qual música devo buscar?"

async def playlist(cmd: str):
    from tasks.spotify_manager import spotify_stark
    return spotify_stark.listar_e_tocar_playlist(re.sub(r"\bplaylist\b", "", cmd).strip())

async def favoritas(cmd: str):
    from tasks.spotify_manager import spotify_stark
    return spotify_stark.tocar_minhas_favoritas()

async def pausar(cmd: str):
    from tasks.spotify_manager import spotify_stark
    return spotify_stark.controlar_reproducao("pause")

async def continuar(cmd: str):
    from tasks.spotify_manager import spotify_stark
    return spotify_stark.controlar_reproducao("play")

async def proxima(cmd: str):
    from tasks.spotify_manager import spotify_stark
    return spotify_stark.controlar_reproducao("proxima")

async def anterior(cmd: str):
    from tasks.spotify_manager import spotify_stark
    return spotify_stark.controlar_reproducao("anterior")

async def monitorar(cmd: str):
    from engine.core import ligar_monitoramento
    await ligar_monitoramento(cmd)
    return "Sentinela de tela ativada."

async def parar_monitor_cmd(cmd: str):
    from engine.core import desligar_monitoramento
    await desligar_monitoramento()
    return "Monitoramento cessado."

async def status_monitor_cmd(cmd: str):
    from engine.core import status_do_sistema
    await status_do_sistema()
    return "Status do sistema reportado."

async def olha_tela(cmd: str):
    from engine.core import analisar_tela_agora
    await analisar_tela_agora()
    return "Análise de tela concluída."

async def olha_camera(cmd: str):
    try:
        from engine.core import analisar_camera_agora
        await analisar_camera_agora()
    except AttributeError:
        pass
    return "Análise de câmera concluída."

async def alarme(cmd: str):
    from tasks.alarm import parse_alarme_voz, adicionar_alarme
    data_iso, hora, missao, _ = parse_alarme_voz(cmd)

    if not hora:
        m = re.search(r"(\d{1,2})[:h](\d{2})", cmd.replace(" e ", ":"))
        if m:
            hora = f"{int(m.group(1)):02d}:{int(m.group(2)):02d}"
        else:
            m2 = re.search(r"(\d{1,2})", cmd)
            hora = f"{int(m2.group(1)):02d}:00" if m2 else None

        if not hora:
            return "Diga a data e hora do alarme."
        missao = missao or "Alarme agendado"

    return adicionar_alarme(hora, missao, data=data_iso)

async def parar_alarme(cmd: str):
    from tasks.spotify_manager import spotify_stark
    from tasks.alarm import parar_alarme_total
    spotify_stark.controlar_reproducao("pause")
    return parar_alarme_total()

ROUTES_LEGADAS: list[tuple[tuple[str, ...], Handler]] = [
    (("abrir",    "youtube"),      abrir_web_direto),
    (("pesquisar","youtube"),      youtube_busca),
    (("pesquisar","google"),       abrir_web_direto),
    (("silencio",),                silencio),
    (("mutar",),                   silencio),
    (("bloquear",),                bloquear),
    (("lock",),                    bloquear),
    (("minimizar",),               minimizar),
    (("fechar",),                  fechar),
    (("screenshot",),              screenshot),
    (("captura",),                 screenshot),
    (("limpar", "lixeira"),        limpar_lixo),
    (("limpar",),                  limpar_lixo),
    (("trabalho",),                trabalho),
    (("ligar",    "tv"),           tv_ligar),
    (("liga",     "tv"),           tv_ligar),
    (("desligar", "tv"),           tv_desligar),
    (("desliga",  "tv"),           tv_desligar),
    (("youtube",  "tv"),           tv_youtube),
    (("youtube",  "televisao"),    tv_youtube),
    (("volume",),                  tv_volume),
    (("spotify",),                 musica),
    (("tocar",    "musica"),       musica),
    (("musica",),                  musica),
    (("playlist",),                playlist),
    (("favoritas",),               favoritas),
    (("pausar",),                  pausar),
    (("continuar",),               continuar),
    (("proxima",),                 proxima),
    (("anterior",),                anterior),
    (("monitorar","tela"),         monitorar),
    (("monitorar",),               monitorar),
    (("desligar", "monitor"),      parar_monitor_cmd),
    (("desativar","monitor"),      parar_monitor_cmd),
    (("monitor",  "status"),       status_monitor_cmd),
    (("olha",     "tela"),         olha_tela),
    (("analisa",  "tela"),         olha_tela),
    (("olha",     "camera"),       olha_camera),
    (("camera",),                  olha_camera),
    (("ver",      "camera"),       olha_camera),
    (("agendar",  "alarme"),       alarme),
    (("criar",    "alarme"),       alarme),
    (("despertar",),               alarme),
    (("parar",    "alarme"),       parar_alarme),
    (("parar",    "musica"),       parar_alarme),
    (("desligar", "alarme"),       parar_alarme),
    (("acordei",),                 parar_alarme),
]

ROUTES.extend(ROUTES_LEGADAS)

PREFIXO_MAP: dict[str, str] = {}
for route_item in ROUTES:
    for kw in route_item[0]:
        for n in range(4, len(kw) + 1):
            PREFIXO_MAP.setdefault(kw[:n], kw)

def expandir(cmd: str):
    return " ".join(PREFIXO_MAP.get(tok, tok) for tok in cmd.split())

def buscar_handler(cmd: str) -> Optional[Handler]:
    exp    = expandir(cmd)
    tokens = exp.split()
    for keywords, handler in ROUTES:
        if all(kw in tokens for kw in keywords):
            return handler
    return None

async def processar_diretriz(texto: str) -> Optional[str]:
    cmd = normalizar(texto)
    from tasks import weather as wx
    if wx.menciona_clima(cmd):
        cidade = wx.extrair_cidade_do_utterance(texto)
        if "amanh" in cmd:
            return wx.verificar_chuva_amanha(cidade)
        return wx.obter_previsao_hoje(cidade)

    handler = buscar_handler(cmd)
    if handler is None:
        return None

    try:
        return await handler(cmd)
    except Exception as e:
        return f"Erro na diretriz: {e}"