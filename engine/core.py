from __future__ import annotations
import logging, time
from typing import Optional
from audio.voz import falar
from engine.controller import processar_diretriz
from engine.ia_router import detectar_modelo, router
from tasks.alarm import gerenciador_alarmes

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s: %(message)s"
)

for _nome_ruidoso in ("faster_whisper", "httpx", "huggingface_hub", "urllib3", "filelock"):
    logging.getLogger(_nome_ruidoso).setLevel(logging.WARNING)

RESPOSTAS_CURTAS = {
    "ok": "Ok.",
    "feito": "Feito.",
    "abrir": "Abrindo.",
    "abre": "Abrindo.",
    "buscar": "Pesquisando.",
    "pesquisar": "Pesquisando.",
    "pesquisa": "Pesquisando.",
    "tocar": "Tocando.",
    "toca": "Tocando.",
    "parar": "Parando.",
    "para": "Parando.",
    "fechar": "Fechando.",
    "fecha": "Fechando.",
    "ligar": "Ligando.",
    "liga": "Ligando.",
    "desligar": "Desligando.",
    "desliga": "Desligando.",
    "criar": "Criando.",
    "cria": "Criando.",
    "enviar": "Enviando.",
    "envia": "Enviando.",
    "salvar": "Salvando.",
    "salva": "Salvando.",
    "copiar": "Copiando.",
    "copia": "Copiando.",
    "mover": "Movendo.",
    "move": "Movendo.",
    "deletar": "Deletando.",
    "deleta": "Deletando.",
    "limpar": "Limpando.",
    "limpa": "Limpando.",
    "atualizar": "Atualizando.",
    "atualiza": "Atualizando.",
    "reiniciar": "Reiniciando.",
    "reinicia": "Reiniciando.",
    "instalar": "Instalando.",
    "instala": "Instalando.",
}

_memoria_sessao: list[dict] = []
_MAX_MEMORIA = 50


def registrar_memoria(tipo: str, conteudo: str):
    _memoria_sessao.append({"tipo": tipo, "conteudo": conteudo, "ts": time.time()})
    if len(_memoria_sessao) > _MAX_MEMORIA:
        _memoria_sessao.pop(0)


def contexto_memoria() -> str:
    if not _memoria_sessao:
        return ""
    recentes = _memoria_sessao[-10:]
    linhas = [f"{m['tipo']}: {m['conteudo']}" for m in recentes]
    return " | ".join(linhas)


class SystemOrchestrator:
    def __init__(self):
        pass

    async def inicializar_servicos(self):
        logging.info("Inicializando motores de IA...")
        await detectar_modelo()
        logging.info("Serviços prontos.")

    def registrar_telemetria(
        self, tipo: str, comando: str, modulo: str, ts_inicio: float
    ):
        duracao = time.time() - ts_inicio
        logging.info(
            f"[TELEMETRIA] {tipo} | Modulo: {modulo} | {duracao:.3f}s | Cmd: '{comando}'"
        )

    def _resposta_curta(self, cmd: str) -> str | None:
        primeira = cmd.strip().split()[0].lower() if cmd.strip() else ""
        return RESPOSTAS_CURTAS.get(primeira)

    async def processar_comando(self, comando: str) -> Optional[str]:
        if not comando.strip():
            return None

        ts = time.time()
        cmd_lower = comando.lower().strip()

        if gerenciador_alarmes.alarme_ativo and any(
            p in cmd_lower for p in ("parar", "desligar", "ok")
        ):
            msg = gerenciador_alarmes.parar_alarme_total()
            await falar(msg)
            return msg

        from tasks.answer_cache import buscar, armazenar

        cache = buscar(comando)
        if cache:
            await falar(cache)
            self.registrar_telemetria("comando_cache", comando, "cache", ts)
            return cache

        registrar_memoria("comando", comando)

        curta = self._resposta_curta(comando)

        resultado_local = await processar_diretriz(comando)
        if resultado_local is not None:
            self.registrar_telemetria("comando_local", comando, "controller", ts)
            fala = curta if curta else resultado_local
            registrar_memoria("resposta", fala)
            await falar(fala)
            return resultado_local

        ctx = contexto_memoria()
        resposta_ia = await router.responder(pergunta=comando, memoria=ctx)
        if resposta_ia:
            armazenar(comando, resposta_ia)
            registrar_memoria("resposta", resposta_ia[:200])
            await falar(resposta_ia)
            self.registrar_telemetria("comando_ia", comando, "ia_router", ts)
            return resposta_ia

        return None


orchestrator = SystemOrchestrator()

inicializar_ia = orchestrator.inicializar_servicos
processar_comando = orchestrator.processar_comando