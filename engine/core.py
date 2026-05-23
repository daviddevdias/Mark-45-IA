from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional, Dict

from audio.voz import falar
from engine.controller import processar_diretriz
from engine.ia_router import detectar_modelo, desligar_monitor, info_monitor, router
from storage.memory_manager import get_nome, load_memory, process_memory_logic
from tasks.alarm import alarme_ativo, parar_alarme_total

from vision.capture import (
    MonitorConfig, ResultadoAnalise, capturar_frame_base64, chamar_qwen,
    estado as vision_estado, gerar_dica_profunda, iniciar_monitor,
    parar_monitor, parse, SYSTEM_RAPIDO
)

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

ALERTAS: Dict[str, str] = {
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
        self._bridge = None

    def registrar(self, bridge: Any):
        self._bridge = bridge

    def emitir(self, dados: dict):
        if self._bridge:
            try:
                self._bridge.dados_para_ui.emit(json.dumps(dados))
            except Exception as e:
                logging.error(f"Erro ao emitir para UI: {e}")

class MonitorState:

    def __init__(self):
        self.aguardando_confirmacao: bool = False
        self.ultima_analise_obj: Optional[ResultadoAnalise] = None
        self.ultima_sugestao: float = 0.0
        self._lock = threading.Lock()

    @property
    def aguardando(self) -> bool:
        with self._lock:
            return self.aguardando_confirmacao

    @aguardando.setter
    def aguardando(self, valor: bool):
        with self._lock:
            self.aguardando_confirmacao = valor

class SystemOrchestrator:

    def __init__(self, ui_manager: UIBridgeManager, state: MonitorState):
        self.ui = ui_manager
        self.state = state

    @staticmethod
    def construir_contexto():
        nome = get_nome()
        mem = load_memory()

        try:
            from tasks.weather import get_cidade_painel
            cidade = get_cidade_painel()
        except (ImportError, AttributeError):
            cidade = "Desconhecida"

        ctx = f"Mestre: {nome}. Cidade padrão (clima): {cidade}."
        if isinstance(mem, dict) and "preferences" in mem:
            ctx += f" Pref: {mem['preferences']}."
        return ctx

    async def inicializar_ia(self):
        await detectar_modelo()

    def registrar_telemetria(self, tipo: str, comando: str, modulo: str, ts_inicio: float):
        duracao = time.time() - ts_inicio
        logging.info(f"[TELEMETRIA] {tipo} | Modulo: {modulo} | Duracao: {duracao:.3f}s | Cmd: '{comando}'")

        try:
            from storage.observability import registrar_acao
            registrar_acao(
                tipo=tipo,
                modulo=modulo,
                descricao=comando[:200],
                sucesso=True
            )
        except ImportError:
            pass
        except Exception as e:
            logging.debug(f"Aviso: Não foi possível gravar telemetria no banco: {e}")

    async def analisar_tela_agora(self):
        await falar("Iniciando análise da tela.")

        img = await asyncio.get_running_loop().run_in_executor(None, capturar_frame_base64)
        if not img:
            await falar("Não consegui capturar a tela.")
            return

        raw = await chamar_qwen(SYSTEM_RAPIDO, "Analise esta tela. Há erros ou situações relevantes?", img, 150)
        resultado = parse(raw, img)

        self.ui.emitir({
            "visao_img": img, 
            "visao_resultado": resultado.resumo,
            "monitor_evento": {
                "ok": resultado.ok, "tipo": resultado.tipo,
                "resumo": resultado.resumo, "problema": resultado.problema,
                "sugestao_rapida": resultado.sugestao_rapida,
                "timestamp": time.time()
            }
        })

        if not resultado.ok:
            dica = await gerar_dica_profunda(img, resultado.problema, resultado.tipo)
            resultado.dica_profunda = dica
            self.ui.emitir({"monitor_dica": dica, "monitor_tipo": resultado.tipo})
            logging.info(f"[VISÃO]: {resultado.resumo} | [DICA]: {dica}")
            await falar(f"{resultado.resumo}. {resultado.sugestao_rapida}")
        else:
            logging.info(f"[VISÃO]: {resultado.resumo}")
            await falar(resultado.resumo)

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
        await falar(f"Monitoramento suspenso. {stats.get('total_problemas', 0)} problema(s) registrados.")

    async def status_do_sistema(self):
        s = info_monitor()
        if s.get("rodando"):
            msg = f"Operacional. {s.get('chamadas_api', 0)} consultas, {s.get('total_problemas', 0)} problema(s)."
        else:
            msg = "Sistema em repouso."
        await falar(msg)

    async def loop_monitoramento(self, resultado: Any):
        if not isinstance(resultado, ResultadoAnalise) or self.state.aguardando:
            return

        agora = time.time()
        self.ui.emitir({
            "monitor_evento": {
                "ok": resultado.ok, "tipo": resultado.tipo,
                "resumo": resultado.resumo, "problema": resultado.problema,
                "sugestao_rapida": resultado.sugestao_rapida, "timestamp": agora,
            }
        })

        if resultado.ok:
            self.ui.emitir({"monitor_ultimo_ok": resultado.resumo})
            return

        if (agora - self.state.ultima_sugestao) < 45.0:
            return

        self.state.ultima_analise_obj = resultado
        self.state.aguardando = True
        self.state.ultima_sugestao = agora

        alerta = ALERTAS.get(resultado.tipo, "Detectei algo incomum na tela.")

        if resultado.dica_profunda:
            self.ui.emitir({
                "monitor_dica": resultado.dica_profunda, "monitor_tipo": resultado.tipo,
                "monitor_alerta": alerta, "aguardando_confirmacao": True
            })
            logging.info(f"[MONITOR]: {alerta} | [DICA]: {resultado.dica_profunda}")
            await falar(f"{alerta} {resultado.sugestao_rapida}. Quer análise completa?")
        else:
            self.ui.emitir({
                "monitor_alerta": alerta, "monitor_tipo": resultado.tipo,
                "aguardando_confirmacao": True
            })
            logging.info(f"[MONITOR]: {alerta} — {resultado.problema}")
            await falar(f"{alerta} Quer que eu analise?")

    async def processar_comando(self, comando: str, imagem_monitor: Optional[Any] = None) -> Optional[str]:
        if not comando.strip() and not imagem_monitor:
            return None

        ts_inicio = time.time()
        cmd_lower = comando.lower().strip()

        if alarme_ativo and any(p in cmd_lower for p in ("parar", "desligar", "acordei", "chega", "ok")):
            msg = parar_alarme_total()
            await falar(msg)
            return msg

        if self.state.aguardando:
            aceitar = ("pedido aceito", "pode ajudar", "pode analisar", "pode resolver", "pode continuar", "aceito")
            recusar = ("dispensa ajuda", "não precisa", "nao precisa", "ignora", "agora não", "cancelar")

            if any(p in cmd_lower for p in aceitar):
                self.state.aguardando = False
                obj = self.state.ultima_analise_obj

                if obj and getattr(obj, 'img_b64', None):
                    dica = await gerar_dica_profunda(obj.img_b64, obj.problema, obj.tipo)
                else:
                    problema_atual = obj.problema if obj else 'problema na tela'
                    dica = await router.responder(
                        f"Sugira solução para: {problema_atual}",
                        memoria=self.construir_contexto(),
                    )

                tipo_obj = obj.tipo if obj else "erro"
                self.ui.emitir({"monitor_dica": dica, "monitor_tipo": tipo_obj})
                logging.info(f"[SOLUÇÃO]: {dica}")
                await falar(dica)
                return dica

            if any(p in cmd_lower for p in recusar):
                self.state.aguardando = False
                msg = "Entendido. Monitoramento continua."
                await falar(msg)
                return msg

            msg = "Ainda aguardo confirmação. Diga 'pode ajudar' ou 'dispensa ajuda'."
            await falar(msg)
            return msg

        resultado_local = await processar_diretriz(comando)
        if resultado_local is not None:
            if resultado_local:
                logging.info(f"[LOCAL]: {resultado_local}")
                await falar(resultado_local)
                self.registrar_telemetria("comando_local", comando, "controller", ts_inicio)
            return resultado_local

        resposta_ia = await router.responder(
            pergunta=comando, nome=get_nome(), memoria=self.construir_contexto(), imagem=imagem_monitor
        )

        if resposta_ia:
            logging.info(f"[IA]: {resposta_ia}")
            await falar(resposta_ia)
            asyncio.create_task(process_memory_logic(comando, resposta_ia))
            self.registrar_telemetria("comando_ia", comando, "ia_router", ts_inicio)

        return resposta_ia or None

ui_manager = UIBridgeManager()
monitor_state = MonitorState()
orchestrator = SystemOrchestrator(ui_manager, monitor_state)
inicializar_ia = orchestrator.inicializar_ia

registrar_ui_bridge     = ui_manager.registrar
processar_comando       = orchestrator.processar_comando

ligar_monitoramento     = orchestrator.ligar_monitoramento
desligar_monitoramento  = orchestrator.desligar_monitoramento
status_do_sistema       = orchestrator.status_do_sistema
analisar_tela_agora     = orchestrator.analisar_tela_agora