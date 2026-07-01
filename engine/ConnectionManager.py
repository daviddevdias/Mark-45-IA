import aiohttp
import logging
import asyncio

log = logging.getLogger("jarvis.lm_manager")


class LMManager:
    def __init__(self, url="http://127.0.0.1:1234/v1"):
        self.url = url
        self.is_online = False
        self.modelos_disponiveis: list[str] = []
        self._task: asyncio.Task | None = None

    async def check_connection(self) -> bool:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.url}/models", timeout=3) as response:
                    if response.status == 200:
                        data = await response.json()
                        self.modelos_disponiveis = [
                            m.get("id") for m in data.get("data", []) if m.get("id")
                        ]
                        self.is_online = bool(self.modelos_disponiveis)
                        return self.is_online
                    self.is_online = False
                    return False
        except Exception:
            self.is_online = False
            return False

    async def monitor_loop(self, interval: float = 30.0):
        while True:
            await self.check_connection()
            if self.is_online:
                log.info(
                    f"LM Studio online — modelos: {', '.join(self.modelos_disponiveis[:3])}"
                )
            await asyncio.sleep(interval)

    def iniciar_monitoramento(self, loop: asyncio.AbstractEventLoop | None = None):
        if self._task and not self._task.done():
            return
        target_loop = loop or asyncio.get_event_loop()
        self._task = target_loop.create_task(self.monitor_loop())

    def parar_monitoramento(self):
        if self._task and not self._task.done():
            self._task.cancel()


lm_manager = LMManager()
