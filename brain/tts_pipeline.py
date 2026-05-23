from __future__ import annotations

import asyncio
import logging
import re
from typing import AsyncIterator, Callable

log = logging.getLogger("jarvis.tts")

SEPARADORES = re.compile(r"(?<=[.!?;:])\s+|(?<=,)\s{2,}")
MIN_CHUNK   = 20

def segmentar(texto: str) -> list[str]:
    partes    = SEPARADORES.split(texto.strip())
    resultado: list[str] = []
    acumulado = ""
    for parte in partes:
        parte = parte.strip()
        if not parte:
            continue

        acumulado = (acumulado + " " + parte).strip() if acumulado else parte
        if len(acumulado) >= MIN_CHUNK:
            resultado.append(acumulado)
            acumulado = ""

    if acumulado:
        resultado.append(acumulado)

    return resultado or [texto]

class FilaTTS:

    def __init__(self):
        self.fila:    asyncio.Queue[str | None] = asyncio.Queue(maxsize=20)
        self.rodando: bool                      = False
        self.task:    asyncio.Task | None       = None
        self.falar:   Callable | None           = None

    def registrar_falar(self, fn: Callable):
        self.falar = fn

    async def iniciar(self):
        if self.rodando:
            return

        self.rodando = True
        self.task    = asyncio.create_task(self.consumidor())

    def limpar_fila(self):
        while not self.fila.empty():
            try:
                self.fila.get_nowait()
                self.fila.task_done()
            except asyncio.QueueEmpty:
                break

    async def parar(self, forcar: bool = False):
        self.rodando = False
        if forcar:
            self.limpar_fila()

        await self.fila.put(None)
        if self.task:
            try:
                await asyncio.wait_for(self.task, timeout=1.5)
            except (asyncio.TimeoutError, Exception):
                self.task.cancel()

    async def enfileirar(self, texto: str):
        for seg in segmentar(texto):
            if not self.rodando:
                break

            await self.fila.put(seg)

    async def consumidor(self):
        while self.rodando:
            try:
                item = await asyncio.wait_for(self.fila.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue
            except Exception as exc:
                log.error("TTS fila erro: %s", exc)
                continue

            if item is None:
                break

            if self.falar:
                try:
                    await self.falar(item)
                except Exception as exc:
                    log.error("TTS síntese erro (segmento=%r): %s", item[:40], exc)

            self.fila.task_done()

async def falar_streaming(gerador: AsyncIterator[str], falar_fn: Callable) -> str:
    fila_tts.registrar_falar(falar_fn)
    if not fila_tts.rodando:
        await fila_tts.iniciar()

    buffer     = ""
    texto_full = ""
    async for token in gerador:
        buffer     += token
        texto_full += token
        if any(buffer.endswith(s) for s in (".", "!", "?", ";", ":")):
            seg = buffer.strip()
            if len(seg) >= MIN_CHUNK:
                await fila_tts.enfileirar(seg)
                buffer = ""

    if buffer.strip():
        await fila_tts.enfileirar(buffer.strip())

    return texto_full

fila_tts = FilaTTS()