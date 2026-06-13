from __future__ import annotations
import asyncio, json, logging, threading, time
from typing import Any, Optional
from audio.voz import falar
from engine.controller import processar_diretriz
from engine.ia_router import detectar_modelo, desligar_monitor, info_monitor, router
from storage.memory_manager import get_nome, load_memory, process_memory_logic
from tasks.alarm import gerenciador_alarmes
from vision.capture import (
    MonitorConfig,
    ResultadoAnalise,
    capturar_frame_base64,
    chamar_qwen,
    estado as vision_estado,
    iniciar_monitor,
    parar_monitor,
    parse,
    SYSTEM_RAPIDO,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

ALERTAS = {
    "erro": "Detectei um erro na tela.",
    "crash": "Parece ter ocorrido um crash.",
    "travado": "Algo parece travado.",
    "aviso": "Há um aviso importante na tela.",
    "instalacao": "Instalação em andamento.",
    "compilacao": "Compilação em andamento.",
    "terminal": "Atividade no terminal.",
    "codigo": "Possível problema no código.",
}


class UIBridgeManager:
    def __init__(self):
        self.bridge = None

    def registrar(self, bridge: Any):
        self.bridge = bridge

    def emitir(self, dados: dict):
        if self.bridge:
            try:
                self.bridge.dados_para_ui.emit(json.dumps(dados))
            except Exception as e:
                logging.error(f"Erro ao emitir para UI: {e}")


class MonitorState:
    def __init__(self):
        self.aguardando_confirmacao = False
        self.ultima_analise_obj = None
        self.ultima_sugestao = 0.0
        self.lock = threading.Lock()

    @property
    def aguardando(self) -> bool:
        with self.lock:
            return self.aguardando_confirmacao

    @aguardando.setter
    def aguardando(self, valor: bool):
        with self.lock:
            self.aguardando_confirmacao = valor


class SystemOrchestrator:
    def __init__(self, ui_manager: UIBridgeManager, state: MonitorState):
        self.ui = ui_manager
        self.state = state

    @staticmethod
    def construir_contexto() -> str:
        mem = load_memory()
        try:
            from tasks.weather import get_cidade_painel
            cidade = get_cidade_painel()
        except:
            cidade = "Desconhecida"
        ctx = f"Mestre: {get_nome()}. Cidade padrão: {cidade}."
        if isinstance(mem, dict) and "preferences" in mem:
            ctx += f" Pref: {mem['preferences']}."
        return ctx

    async def inicializar_ia(self):
        await detectar_modelo()

    def registrar_telemetria(self, tipo: str, comando: str, modulo: str, ts_inicio: float):
        logging.info(f"[TELEMETRIA] {tipo} | Modulo: {modulo} | Duracao: {time.time() - ts_inicio:.3f}s | Cmd: '{comando}'")
        try:
            from storage.observability import registrar_acao
            registrar_acao(tipo=tipo, modulo=modulo, descricao=comando[:200], sucesso=True)
        except:
            pass

    async def analisar_tela_agora(self):
        await falar("Iniciando análise.")
        img = await asyncio.get_running_loop().run_in_executor(None, capturar_frame_base64)
        if not img:
            return await falar("Não consegui capturar a tela.")
        raw = await chamar_qwen(SYSTEM_RAPIDO, "Analise esta tela. Há erros ou situações relevantes?", img, 150)
        res = parse(raw, img)
        self.ui.emitir({
            "visao_img": img,
            "visao_resultado": res.resumo,
            "monitor_evento": {
                "ok": res.ok, "tipo": res.tipo, "resumo": res.resumo,
                "problema": res.problema, "sugestao_rapida": res.sugestao_rapida,
                "timestamp": time.time(),
            },
        })
        if not res.ok:
            res.dica_profunda = await router.responder(
                f"Analise este problema e dê uma solução técnica rápida: {res.problema}",
                memoria=self.construir_contexto(),
                imagem=img,
            )
            self.ui.emitir({"monitor_dica": res.dica_profunda, "monitor_tipo": res.tipo})
            await falar(f"{res.resumo}. {res.sugestao_rapida}")
        else:
            await falar(res.resumo)

    async def ligar_monitoramento(self, comando: str):
        if vision_estado.rodando:
            parar_monitor()
            await asyncio.sleep(0.5)
        intervalo = max(5.0, float(next((t for t in comando.split() if t.isdigit()), "8")))
        await iniciar_monitor(MonitorConfig(
            intervalo_s=intervalo,
            apenas_mudancas=True,
            gerar_dica_auto=True,
            cooldown_s=45.0,
            callback=self.loop_monitoramento,
        ))
        self.ui.emitir({"monitor_status": "ativo", "monitor_intervalo": int(intervalo)})
        await falar(f"Monitoramento ativo. Intervalo de {int(intervalo)} segundos.")

    async def desligar_monitoramento(self):
        self.state.aguardando = False
        stats = desligar_monitor()
        self.ui.emitir({"monitor_status": "inativo", "monitor_stats": stats})
        await falar(f"Monitoramento suspenso. {stats.get('total_problemas', 0)} problemas.")

    async def status_do_sistema(self):
        s = info_monitor()
        msg = (
            f"Operacional. {s.get('chamadas_api', 0)} consultas, {s.get('total_problemas', 0)} problemas."
            if s.get("rodando")
            else "Sistema em repouso."
        )
        await falar(msg)

    async def loop_monitoramento(self, resultado: Any):
        if not isinstance(resultado, ResultadoAnalise) or self.state.aguardando:
            return
        agora = time.time()
        self.ui.emitir({
            "monitor_evento": {
                "ok": resultado.ok, "tipo": resultado.tipo, "resumo": resultado.resumo,
                "problema": resultado.problema, "sugestao_rapida": resultado.sugestao_rapida,
                "timestamp": agora,
            }
        })
        if resultado.ok:
            return self.ui.emitir({"monitor_ultimo_ok": resultado.resumo})
        if (agora - self.state.ultima_sugestao) < 45.0:
            return

        self.state.ultima_analise_obj = resultado
        self.state.aguardando = True
        self.state.ultima_sugestao = agora

        alerta = ALERTAS.get(resultado.tipo, "Algo incomum na tela.")
        dica = await router.responder(
            f"Como resolver rapidamente: {resultado.problema}",
            memoria=self.construir_contexto(),
            imagem=resultado.img_b64 if hasattr(resultado, "img_b64") else None,
        )
        resultado.dica_profunda = dica

        if dica:
            self.ui.emitir({
                "monitor_dica": dica, "monitor_tipo": resultado.tipo,
                "monitor_alerta": alerta, "aguardando_confirmacao": True,
            })
            await falar(f"{alerta} {resultado.sugestao_rapida}. Quer análise completa?")
        else:
            self.ui.emitir({"monitor_alerta": alerta, "monitor_tipo": resultado.tipo, "aguardando_confirmacao": True})
            await falar(f"{alerta} Quer que eu analise?")

    async def processar_comando(self, comando: str, imagem_monitor: Optional[Any] = None) -> Optional[str]:
        if not comando.strip() and not imagem_monitor:
            return None

        ts = time.time()
        cmd_lower = comando.lower().strip()

        if gerenciador_alarmes.alarme_ativo and any(p in cmd_lower for p in ("parar", "desligar", "acordei", "chega", "ok")):
            msg = gerenciador_alarmes.parar_alarme_total()
            await falar(msg)
            return msg

        if self.state.aguardando:
            confirmacoes = ("pedido aceito", "pode ajudar", "pode analisar", "pode resolver", "pode continuar", "aceito")
            cancelamentos = ("dispensa ajuda", "não precisa", "nao precisa", "ignora", "agora não", "cancelar")

            if any(p in cmd_lower for p in confirmacoes):
                self.state.aguardando = False
                obj = self.state.ultima_analise_obj
                dica = await router.responder(
                    f"Sugira solução técnica e prática para: {obj.problema if obj else 'problema'}",
                    memoria=self.construir_contexto(),
                    imagem=obj.img_b64 if obj and getattr(obj, "img_b64", None) else None,
                )
                self.ui.emitir({"monitor_dica": dica, "monitor_tipo": obj.tipo if obj else "erro"})
                await falar(dica)
                return dica

            if any(p in cmd_lower for p in cancelamentos):
                self.state.aguardando = False
                await falar("Entendido.")
                return "Entendido."

            msg = "Aguardando confirmação. Diga 'pode ajudar' ou 'dispensa ajuda'."
            await falar(msg)
            return msg

        resultado_local = await processar_diretriz(comando)
        if resultado_local is not None:
            if resultado_local:
                await falar(resultado_local)
                self.registrar_telemetria("comando_local", comando, "controller", ts)
            return resultado_local

        resposta_ia = await router.responder(
            pergunta=comando,
            nome=get_nome(),
            memoria=self.construir_contexto(),
            imagem=imagem_monitor,
        )
        if resposta_ia:
            await falar(resposta_ia)
            asyncio.create_task(process_memory_logic(comando, resposta_ia))
            self.registrar_telemetria("comando_ia", comando, "ia_router", ts)
        return resposta_ia or None


ui_manager = UIBridgeManager()
monitor_state = MonitorState()
orchestrator = SystemOrchestrator(ui_manager, monitor_state)

inicializar_ia = orchestrator.inicializar_ia
registrar_ui_bridge = ui_manager.registrar
processar_comando = orchestrator.processar_comando
ligar_monitoramento = orchestrator.ligar_monitoramento
desligar_monitoramento = orchestrator.desligar_monitoramento
status_do_sistema = orchestrator.status_do_sistema
analisar_tela_agora = orchestrator.analisar_tela_agora
