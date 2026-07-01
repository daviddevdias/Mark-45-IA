from __future__ import annotations
import asyncio, logging, time

log = logging.getLogger("pomodoro")

foco_ativo = False
fim_foco: float = 0
tipo_foco = ""
falar_callback = None

def registrar_falar_cb(cb):
    global falar_callback
    falar_callback = cb

def falar_voz(texto: str):
    if falar_callback:
        try:
            falar_callback(texto)
        except:
            pass

async def iniciar_foco(minutos: int = 25) -> str:
    global foco_ativo, fim_foco, tipo_foco
    if foco_ativo:
        restante = int(fim_foco - time.time())
        return f"Já está em foco. Faltam {restante // 60}m{restante % 60}s."
    foco_ativo = True
    fim_foco = time.time() + minutos * 60
    tipo_foco = "foco"
    log.info(f"Foco iniciado por {minutos}min")
    asyncio.create_task(timer_foco(minutos))
    return f"Foco iniciado por {minutos} minutos."

async def timer_foco(minutos: int):
    global foco_ativo
    try:
        await asyncio.sleep(minutos * 60)
        if foco_ativo:
            foco_ativo = False
            falar_voz("Tempo encerrado. Faça uma pausa de 5 minutos.")
    except asyncio.CancelledError:
        pass

async def pausa(minutos: int = 5) -> str:
    global foco_ativo, fim_foco, tipo_foco
    foco_ativo = True
    fim_foco = time.time() + minutos * 60
    tipo_foco = "descanso"
    asyncio.create_task(timer_foco(minutos))
    return f"Pausa de {minutos} minutos."

async def parar_foco() -> str:
    global foco_ativo
    if not foco_ativo:
        return "Nenhum foco ativo."
    foco_ativo = False
    return f"{tipo_foco.capitalize()} interrompido."

def status_foco() -> str:
    if not foco_ativo:
        return "Nenhum foco ativo."
    restante = int(fim_foco - time.time())
    if restante <= 0:
        return "Tempo encerrado."
    return f"{tipo_foco.capitalize()} — faltam {restante // 60}m{restante % 60}s."
