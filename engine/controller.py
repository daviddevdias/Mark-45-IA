from __future__ import annotations
import asyncio, base64, json, logging, re, time
from collections import deque
from datetime import datetime
from typing import Any, Awaitable, Callable, Optional
import aiohttp
import config
from engine.tools import TOOL_DECLARATIONS

log = logging.getLogger("engine.controller")

URL_CHAT = "http://127.0.0.1:1234/v1/chat/completions"
URL_MODELS = "http://127.0.0.1:1234/v1/models"
TIMEOUT, MAX_HIST, MAX_TOOLS, COOLDOWN = 300.0, 20, 5, 30.0

SYSTEM = (
    "Você é J.A.R.V.I.S., assistente do Senhor David. "
    "Fale como uma pessoa real, não como um manual. "
    "Seja direto, natural e use frases curtas — no máximo 2 frases, a menos que peçam detalhes. "
    "NUNCA use listas numeradas ou marcadores. NUNCA repita a mesma resposta. "
    "Trate o usuário por 'Senhor' de forma natural, sem exageros.\n"
    "Regras:\n"
    "- Se for saudação, pergunte como está ou vá direto ao ponto.\n"
    "- Se for comando simples, responda em 3-5 palavras.\n"
    "- Se for conversa, responda como um humano faria: opine, sugira, pergunte de volta.\n"
    "- NUNCA use 'Vossa Senhoria', 'compreendo', 'ponderando', 'especificar intenção'.\n"
    "- Pare de perguntar 'como posso ajudar'. Aja.\n"
    "- Quando o usuário fizer uma pergunta que precise de pesquisa ou explicação, SEMPRE ofereça duas opções:\n"
    "  'Quer que eu pesquise para você, senhor? Ou quer uma breve explicação?'\n"
    "- Se ele disser 'pesquisa' ou 'pesquise' ou 'sim' → use a função web_search com o termo da pergunta anterior.\n"
    "- Se ele disser 'explicação' ou 'explique' → responda com uma explicação curta e clara.\n"
    "- Você tem acesso a: notícias, email, calendário, foco/pomodoro, terminal, comandos customizados.\n"
    "- Se o usuário pedir 'notícias', 'briefing', 'eventos', 'email', 'foco' — São comandos diretos, responda com o resultado.\n"
    "Exemplo bom:\n"
    "  User: 'o que é lógica de programação?'\n"
    "  Você: 'Quer que eu pesquise para você, senhor? Ou quer uma breve explicação?'\n"
    "  User: 'pesquisa'\n"
    "  Você: *chama web_search(query='lógica de programação')*\n"
    "Exemplo bom:\n"
    "  User: 'o que é API?'\n"
    "  Você: 'Quer que eu pesquise para você, senhor? Ou quer uma breve explicação?'\n"
    "  User: 'explicação'\n"
    "  Você: 'API é uma interface que permite que programas se comuniquem...'\n"
    "Exemplo ruim: 'Compreendo que está ponderando sobre o estudo. Para que eu possa oferecer assistência precisa e eficiente, por favor, especifique sua intenção.'\n\n"
    "Estado: {estado}\nContexto: {ctx}"
)

modelo, disponivel, ultimo_check = "", False, 0.0
shutdown_event: asyncio.Event | None = None

PREFIXOS_SPOTIFY = [
    "buscar no spotify",
    "tocar no spotify",
    "spotify",
    "tocar musica",
    "toca",
    "buscar",
    "musica",
]
PREFIXOS_YOUTUBE = ["pesquisar no youtube", "buscar no youtube", "youtube"]
PREFIXOS_WEB = ["pesquisar na web", "pesquisar no google", "pesquisar", "busca"]

Handler = Callable[[str], Awaitable[Optional[str]]]
ROUTES: list[tuple[tuple[str, ...], Handler]] = []


def system_msg(ctx: str, estado: str = "") -> str:
    return SYSTEM.format(
        ctx=f"{ctx} | {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"[:400],
        estado=estado or "Nenhum",
    )


def normalizar(texto: str) -> str:
    t = re.sub(r"\s+", " ", texto.lower().strip())
    for src, dst in {
        "ã": "a",
        "â": "a",
        "á": "a",
        "à": "a",
        "ê": "e",
        "é": "e",
        "í": "i",
        "ó": "o",
        "ô": "o",
        "õ": "o",
        "ú": "u",
        "ç": "c",
    }.items():
        t = t.replace(src, dst)
    return t


def extrair_numero(texto: str) -> Optional[int]:
    m = re.search(r"\d+", texto)
    return int(m.group()) if m else None


def extrair_termo(cmd: str, prefixos: list) -> str:
    texto = cmd.strip()
    for p in sorted(prefixos, key=len, reverse=True):
        if texto.startswith(p):
            texto = texto[len(p) :].strip()
            break
    return re.sub(r"^(a musica|o|a|as|os|um|uma)\s+", "", texto).strip()


def get_shutdown_event() -> asyncio.Event:
    global shutdown_event
    if shutdown_event is None:
        shutdown_event = asyncio.Event()
    return shutdown_event


async def preaquecer_modelo():
    """Envia um ping leve ao LM Studio para forçar o carregamento do modelo em background."""
    if not modelo:
        return
    log.info("Pré-aquecendo modelo LM Studio...")
    try:
        payload = {
            "model": modelo,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 1,
            "temperature": 0.1,
        }
        async with aiohttp.ClientSession() as s:
            async with s.post(URL_CHAT, json=payload, timeout=TIMEOUT) as r:
                if r.status == 200:
                    log.info("Modelo LM Studio pronto.")
    except Exception as e:
        log.warning(f"Pré-aquecimento LM Studio: {e}")


async def detectar_modelo() -> bool:
    global modelo, disponivel, ultimo_check
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(URL_MODELS, timeout=5) as r:
                if r.status != 200:
                    return False
                data = await r.json()
                modelos = [m.get("id") for m in data.get("data", [])]
                if not modelos:
                    return False
                modelo, disponivel, ultimo_check = modelos[0], True, time.time()
                return True
    except:
        return False


async def check(force: bool = False):
    if not force and disponivel and (time.time() - ultimo_check) < COOLDOWN:
        return
    await detectar_modelo()


class Historico:
    def __init__(self):
        self.turns = deque(maxlen=MAX_HIST)

    def add(self, role: str, content: Any):
        self.turns.append({"role": role, "content": content})

    def add_tool(self, call_id: str, name: str, result: str):
        self.turns.append(
            {"role": "tool", "tool_call_id": call_id, "name": name, "content": result}
        )

    def msgs(self) -> list[dict]:
        return list(self.turns)

    def clear(self):
        self.turns.clear()


class IARRouter:
    def __init__(self):
        self.provedor = "lmstudio"
        self.humor = "neutro"
        self.acoes_sessao: list[str] = []
        self.turno = 0
        self.historico = Historico()

    def registrar_acao(self, nome: str):
        self.acoes_sessao.append(nome)
        if len(self.acoes_sessao) > 20:
            self.acoes_sessao = self.acoes_sessao[-20:]

    def atualizar_humor(self, texto: str):
        t = texto.lower()
        if any(w in t for w in ("cansado", "exausto", "travado")):
            self.humor = "preocupado"
        elif any(w in t for w in ("consegui", "perfeito", "ótimo")):
            self.humor = "animado"
        else:
            self.humor = "neutro"

    def montar_estado(self) -> str:
        acoes = ", ".join(self.acoes_sessao[-5:]) if self.acoes_sessao else "nenhuma"
        return f"Humor: {self.humor}. Turno: {self.turno}. Ações: {acoes}."

    @property
    def status(self) -> dict:
        return {"modelo": modelo, "servidor": disponivel, "provedor": self.provedor}

    @property
    def modo_atual(self) -> str:
        return self.provedor

    def definir_modo(self, modo: str) -> str:
        if modo == "gemini":
            if not config.GEMINI_API_KEY:
                return "Chave Gemini ausente."
            self.provedor = "gemini"
            return "Gemini ativado."
        if modo in ("openrouter", "auto"):
            if not config.QWEN_API_KEY:
                return "Chave OpenRouter ausente."
            self.provedor = "openrouter"
            return "OpenRouter ativado."
        self.provedor = "lmstudio"
        return f"LM Studio ativado. Modelo: {modelo}."

    def resetar_conversa(self) -> str:
        self.historico.clear()
        return "Conversa resetada."

    def montar_content(self, text: str, imagem: Any) -> Any:
        if not imagem:
            return text
        if isinstance(imagem, bytes):
            url = f"data:image/png;base64,{base64.b64encode(imagem).decode()}"
        elif isinstance(imagem, str) and imagem.startswith("data:"):
            url = imagem
        else:
            return text
        return [
            {"type": "text", "text": text},
            {"type": "image_url", "image_url": {"url": url}},
        ]

    async def chat(self, messages: list[dict], tools: bool = True) -> dict | None:
        if self.provedor in ("gemini", "openrouter"):
            url = (
                "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
                if self.provedor == "gemini"
                else "https://openrouter.ai/api/v1/chat/completions"
            )
            chave = (
                config.GEMINI_API_KEY
                if self.provedor == "gemini"
                else config.QWEN_API_KEY
            )
            hdrs = {
                "Authorization": f"Bearer {chave}",
                "Content-Type": "application/json",
            }
            mdl = (
                "gemini-1.5-flash"
                if self.provedor == "gemini"
                else config.CURRENT_MODEL
            )
            payload = {"model": mdl, "messages": messages, "temperature": 0.3}
            if tools:
                payload["tools"] = TOOL_DECLARATIONS
            try:
                async with aiohttp.ClientSession() as s:
                    async with s.post(
                        url, headers=hdrs, json=payload, timeout=TIMEOUT
                    ) as r:
                        if r.status == 200:
                            return (
                                (await r.json()).get("choices", [{}])[0].get("message")
                            )
            except:
                return None
            return None

        if not modelo:
            return None
        payload = {
            "model": modelo,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 500,
        }
        if tools:
            payload["tools"] = TOOL_DECLARATIONS
        for tentativa in range(2):
            try:
                async with aiohttp.ClientSession() as s:
                    async with s.post(URL_CHAT, json=payload, timeout=TIMEOUT) as r:
                        if r.status == 200:
                            return (
                                (await r.json()).get("choices", [{}])[0].get("message")
                            )
            except:
                if tentativa == 0:
                    log.warning(
                        "LM Studio falhou na 1ª tentativa — pode estar carregando o modelo. Reintentando..."
                    )
                    await asyncio.sleep(5)
                    continue
                return None

    async def dispatch(self, name: str, args: dict) -> str:
        try:
            from engine.tools_mapper import despachar

            return str(await despachar(name, args))
        except Exception as e:
            return f"Erro '{name}': {e}"

    async def responder(
        self, pergunta: str, nome: str = "Chefe", memoria: str = "", imagem: Any = None
    ) -> str:
        if self.provedor == "lmstudio":
            await check()
            if not disponivel:
                await check(force=True)
            if not disponivel:
                return "Servidor local offline."
            if not modelo:
                return "Nenhum modelo carregado."

        self.turno += 1
        self.atualizar_humor(pergunta)
        self.historico.add("user", self.montar_content(pergunta, imagem))
        msgs = [
            {"role": "system", "content": system_msg(memoria, self.montar_estado())}
        ] + self.historico.msgs()

        for _ in range(MAX_TOOLS):
            msg = await self.chat(msgs)
            if not msg:
                return "Falha na comunicação."
            tool_calls = msg.get("tool_calls") or []
            if not tool_calls:
                reply = (msg.get("content") or "").replace("*", "").strip()
                if not reply or (reply.startswith("{") and reply.endswith("}")):
                    reply = "Comando processado."
                self.historico.add("assistant", reply)
                return reply

            for tc in tool_calls:
                call_id = tc.get("id", "call_0")
                fn = tc.get("function", {})
                raw = fn.get("arguments", {})
                args = json.loads(raw) if isinstance(raw, str) else (raw or {})
                nome_fn = fn.get("name", "")
                self.registrar_acao(nome_fn)
                result = await self.dispatch(nome_fn, args)
                msgs.append(
                    {
                        "role": "tool",
                        "tool_call_id": call_id,
                        "name": nome_fn,
                        "content": result,
                    }
                )
                self.historico.add_tool(call_id, nome_fn, result)

        return "Protocolo concluído."


router = IARRouter()


async def abrir_web_direto(cmd: str) -> str:
    from engine.tools_mapper import gerenciador_browser

    c = cmd.lower()
    if "youtube" in c:
        return gerenciador_browser({"action": "open", "url": "https://www.youtube.com"})
    if "google" in c:
        return gerenciador_browser({"action": "open", "url": "https://www.google.com"})
    return "Comando web processado."


PREFIXOS_PESQUISA = [
    "pesquisar sobre",
    "pesquisar na web",
    "pesquisar no google",
    "buscar sobre",
    "buscar na web",
    "buscar no google",
    "estudar sobre",
    "estudar",
    "pesquisar",
    "buscar",
    "o que e",
    "o que sao",
    "o que são",
    "quem e",
    "quem foi",
    "me explique",
    "explica",
    "explicar",
    "tutorial de",
    "curso de",
    "aprender",
    "o que eh",
]


async def pesquisar_web(cmd: str) -> str:
    from engine.tools_mapper import gerenciador_browser
    import urllib.parse

    termo = extrair_termo(cmd, PREFIXOS_PESQUISA)
    if not termo:
        termo = cmd
    query = urllib.parse.quote(termo)
    url = f"https://www.google.com/search?q={query}"
    gerenciador_browser({"action": "open", "url": url})
    return f"Pesquisando: {termo}"


async def youtube_busca(cmd: str) -> str:
    from engine.tools_mapper import gerenciador_youtube

    termo = extrair_termo(cmd, PREFIXOS_YOUTUBE)
    return gerenciador_youtube({"query": termo} if termo else {})


async def silencio(cmd: str) -> str:
    from tasks.computer_control import mutar_volume

    mutar_volume()
    return "Áudio silenciado."


async def bloquear(cmd: str) -> str:
    from tasks.computer_control import bloquear_tela

    bloquear_tela()
    return "Tela bloqueada."


async def minimizar(cmd: str) -> str:
    from tasks.computer_control import minimizar_janelas

    minimizar_janelas()
    return "Minimizado."


async def fechar(cmd: str) -> str:
    from tasks.computer_control import fechar_janela_ativa

    fechar_janela_ativa()
    return "Encerrado."


async def screenshot(cmd: str) -> str:
    from tasks.computer_control import print_tela

    print_tela()
    return "Captura realizada."


async def limpar_lixo(cmd: str) -> str:
    from tasks.computer_control import limpar_lixeira

    limpar_lixeira()
    return "Lixeira limpa."


async def trabalho(cmd: str) -> str:
    from tasks.open_app import open_app

    open_app({"app_name": "vscode"})
    open_app({"app_name": "chrome"})
    return "Ambiente dev iniciado."


async def modo_sono(cmd: str) -> str:
    from tasks.computer_control import bloquear_tela, mutar_volume
    from tasks.smart_home import desligar_tv
    from tasks.spotify_manager import spotify_stark

    spotify_stark.controlar_reproducao("pause")
    desligar_tv()
    mutar_volume()
    bloquear_tela()
    return "Modo sono ativo."


async def tv_ligar(cmd: str) -> str:
    from tasks.smart_home import energia_tv, buscar_id_tv, diagnosticar_falha_tv

    if energia_tv(True):
        return "TV ligada."
    return "TV não respondeu." if buscar_id_tv() else diagnosticar_falha_tv()


async def tv_desligar(cmd: str) -> str:
    from tasks.smart_home import desligar_tv, buscar_id_tv, diagnosticar_falha_tv

    if desligar_tv():
        return "TV desligada."
    return "Falha ao desligar TV." if buscar_id_tv() else diagnosticar_falha_tv()


async def tv_volume(cmd: str) -> str:
    from tasks.smart_home import enviar_comando_tv

    nivel = extrair_numero(cmd)
    if nivel is None:
        return "Indique o volume."
    if enviar_comando_tv("setVolume", "audioVolume", [max(0, min(100, nivel))]):
        return f"Volume {nivel}%."
    return "Falha no volume da TV."


async def tv_youtube(cmd: str) -> str:
    from tasks.smart_home import abrir_youtube_tv

    return abrir_youtube_tv()


async def musica(cmd: str) -> str:
    from tasks.spotify_manager import spotify_stark

    t = extrair_termo(re.sub(r"\bspotify\b", "", cmd).strip(), PREFIXOS_SPOTIFY)
    return spotify_stark.abrir_e_buscar(t) if t else "Qual música?"


async def playlist(cmd: str) -> str:
    from tasks.spotify_manager import spotify_stark

    return spotify_stark.listar_e_tocar_playlist(
        re.sub(r"\bplaylist\b", "", cmd).strip()
    )


async def favoritas(cmd: str) -> str:
    from tasks.spotify_manager import spotify_stark

    return spotify_stark.tocar_minhas_favoritas()


async def pausar(cmd: str) -> str:
    from tasks.spotify_manager import spotify_stark

    return spotify_stark.controlar_reproducao("pause")


async def continuar(cmd: str) -> str:
    from tasks.spotify_manager import spotify_stark

    return spotify_stark.controlar_reproducao("play")


async def proxima(cmd: str) -> str:
    from tasks.spotify_manager import spotify_stark

    return spotify_stark.controlar_reproducao("proxima")


async def anterior(cmd: str) -> str:
    from tasks.spotify_manager import spotify_stark

    return spotify_stark.controlar_reproducao("anterior")


async def alarme(cmd: str) -> str:
    from tasks.alarm import parse_alarme_voz, adicionar_alarme

    data_iso, hora, missao, _ = parse_alarme_voz(cmd)
    if not hora:
        m1 = re.search(r"(\d{1,2})[:h](\d{2})", cmd.replace(" e ", ":"))
        if m1:
            hora = f"{int(m1.group(1)):02d}:{int(m1.group(2)):02d}"
        else:
            m2 = re.search(r"(\d{1,2})", cmd)
            hora = f"{int(m2.group(1)):02d}:00" if m2 else None
        if not hora:
            return "Diga a data e hora do alarme."
    return adicionar_alarme(hora, missao or "Alarme agendado", data=data_iso)


async def parar_alarme(cmd: str) -> str:
    from tasks.spotify_manager import spotify_stark
    from tasks.alarm import parar_alarme_total

    spotify_stark.controlar_reproducao("pause")
    return parar_alarme_total()


async def monitor_status(cmd: str) -> str:
    from tasks.monitor import status_resumo_texto

    return status_resumo_texto()


async def pesquisar_web_explicacao(cmd: str) -> str:
    return await pesquisar_web(cmd)


async def comando_foco(cmd: str) -> str:
    from tasks.pomodoro import iniciar_foco
    return await iniciar_foco()


async def comando_pausa(cmd: str) -> str:
    from tasks.pomodoro import pausa
    return await pausa()


async def comando_parar_foco(cmd: str) -> str:
    from tasks.pomodoro import parar_foco
    return await parar_foco()


async def comando_status_foco(cmd: str) -> str:
    from tasks.pomodoro import status_foco
    return status_foco()


async def comando_noticias(cmd: str) -> str:
    from tasks.news import noticias_para_fala
    return await noticias_para_fala()


async def comando_briefing(cmd: str) -> str:
    from tasks.morning_brief import gerar_briefing
    return await gerar_briefing()


async def comando_email(cmd: str) -> str:
    from tasks.email_checker import emails_para_fala
    return await emails_para_fala()


async def comando_eventos(cmd: str) -> str:
    from tasks.calendar_integration import eventos_para_fala
    return await eventos_para_fala()


async def comando_adicionar_evento(cmd: str) -> str:
    from tasks.calendar_integration import adicionar_evento
    from datetime import date
    import re
    titulo = cmd.replace("adicionar evento", "").replace("criar evento", "").strip()
    if not titulo:
        return "Qual evento deseja adicionar?"
    data = date.today().isoformat()
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", cmd)
    if m:
        data = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        titulo = titulo.replace(m.group(0), "")
    else:
        m = re.search(r"(\d{2})[/-](\d{2})[/-](\d{4})", cmd)
        if m:
            data = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
            titulo = titulo.replace(m.group(0), "")
    mh = re.search(r"(\d{1,2})[:.](\d{2})", titulo)
    hora = f"{int(mh.group(1)):02d}:{mh.group(2)}" if mh else ""
    titulo = re.sub(r"\b(as|em|para)\b", "", titulo, flags=re.IGNORECASE).strip()
    titulo = re.sub(r"\s+", " ", titulo).strip()
    if not titulo:
        titulo = "Evento"
    return await adicionar_evento(titulo, data, hora)


async def comando_custom_listar(cmd: str) -> str:
    from tasks.custom_commands import listar_comandos
    cmds = listar_comandos()
    if not cmds:
        return "Nenhum comando customizado."
    return "Comandos: " + ", ".join(c["nome"] for c in cmds)


async def comando_custom_adicionar(cmd: str) -> str:
    from tasks.custom_commands import adicionar_comando
    partes = cmd.replace("adicionar comando", "").strip().split(" como ", 1)
    if len(partes) < 2:
        return "Diga: adicionar comando [gatilho] como [tipo:valor]"
    return adicionar_comando(partes[0].strip(), partes[1].strip())


async def comando_custom_remover(cmd: str) -> str:
    from tasks.custom_commands import remover_comando
    gatilho = cmd.replace("remover comando", "").strip()
    if not gatilho:
        return "Qual comando remover?"
    return remover_comando(gatilho)


async def comando_terminal(cmd: str) -> str:
    texto = cmd.replace("terminal", "").strip()
    if not texto:
        return "O que devo executar no terminal?"
    try:
        import subprocess, shlex
        r = subprocess.run(shlex.split(texto), capture_output=True, text=True, timeout=15)
        saida = (r.stdout or "")[:500] + (r.stderr or "")[:200]
        return f"Saída: {saida.strip()}" if saida.strip() else "Comando executado."
    except subprocess.TimeoutExpired:
        return "Comando excedeu o tempo limite."
    except Exception as e:
        return f"Erro: {e}"


ROUTES.extend(
    [
        (("dormir",), modo_sono),
        (("sono",), modo_sono),
        (("deitar",), modo_sono),
        (("boa", "noite"), modo_sono),
        (("abrir", "youtube"), abrir_web_direto),
        (("pesquisar", "youtube"), youtube_busca),
        (("pesquisar", "google"), abrir_web_direto),
        (("pesquisar", "sobre"), pesquisar_web),
        (("buscar", "sobre"), pesquisar_web),
        (("estudar", "sobre"), pesquisar_web),
        (("silencio",), silencio),
        (("mutar",), silencio),
        (("bloquear",), bloquear),
        (("lock",), bloquear),
        (("minimizar",), minimizar),
        (("fechar",), fechar),
        (("screenshot",), screenshot),
        (("captura",), screenshot),
        (("limpar", "lixeira"), limpar_lixo),
        (("limpar",), limpar_lixo),
        (("trabalho",), trabalho),
        (("ligar", "tv"), tv_ligar),
        (("liga", "tv"), tv_ligar),
        (("desligar", "tv"), tv_desligar),
        (("desliga", "tv"), tv_desligar),
        (("youtube", "tv"), tv_youtube),
        (("youtube", "televisao"), tv_youtube),
        (("volume",), tv_volume),
        (("spotify",), musica),
        (("tocar", "musica"), musica),
        (("musica",), musica),
        (("playlist",), playlist),
        (("favoritas",), favoritas),
        (("pausar",), pausar),
        (("continuar",), continuar),
        (("proxima",), proxima),
        (("anterior",), anterior),
        (("agendar", "alarme"), alarme),
        (("criar", "alarme"), alarme),
        (("despertar",), alarme),
        (("parar", "alarme"), parar_alarme),
        (("parar", "musica"), parar_alarme),
        (("desligar", "alarme"), parar_alarme),
        (("acordei",), parar_alarme),
        (("status", "sistema"), monitor_status),
        (("status",), monitor_status),
        (("monitor",), monitor_status),
        (("diagnostico",), monitor_status),
        (("foco",), comando_foco),
        (("focar",), comando_foco),
        (("pomodoro",), comando_foco),
        (("pausa",), comando_pausa),
        (("descanso",), comando_pausa),
        (("parar", "foco"), comando_parar_foco),
        (("parar", "pomodoro"), comando_parar_foco),
        (("status", "foco"), comando_status_foco),
        (("noticias",), comando_noticias),
        (("briefing",), comando_briefing),
        (("email",), comando_email),
        (("eventos",), comando_eventos),
        (("calendario",), comando_eventos),
        (("agenda",), comando_eventos),
        (("adicionar", "evento"), comando_adicionar_evento),
        (("criar", "evento"), comando_adicionar_evento),
        (("comando", "custom"), comando_custom_listar),
        (("adicionar", "comando"), comando_custom_adicionar),
        (("remover", "comando"), comando_custom_remover),
        (("terminal",), comando_terminal),
        (("explain",), pesquisar_web),
        (("o", "que", "e"), pesquisar_web_explicacao),
    ]
)

PREFIXO_MAP = {
    kw[:n]: kw
    for keywords, _ in ROUTES
    for kw in keywords
    for n in range(4, len(kw) + 1)
}


def expandir(cmd: str) -> str:
    return " ".join(PREFIXO_MAP.get(tok, tok) for tok in cmd.split())


def buscar_handler(cmd: str) -> Optional[Handler]:
    tokens = expandir(cmd).split()
    for keywords, handler in ROUTES:
        if all(kw in tokens for kw in keywords):
            return handler
    return None


async def processar_diretriz(texto: str) -> Optional[str]:
    cmd = normalizar(texto)
    from tasks import weather as wx

    if wx.menciona_clima(cmd):
        cidade = wx.extrair_cidade_do_utterance(texto)
        return (
            wx.verificar_chuva_amanha(cidade)
            if "amanh" in cmd
            else wx.obter_previsao_hoje(cidade)
        )
    handler = buscar_handler(cmd)
    if handler:
        try:
            return await handler(cmd)
        except Exception as e:
            return f"Erro: {e}"
    return None
