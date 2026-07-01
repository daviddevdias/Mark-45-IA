from __future__ import annotations
import asyncio, random, re, time

import aiohttp

cache_noticias: dict[str, tuple[float, list[dict]]] = {}
tempo_cache = 1800

FEEDS = [
    ("folha", "https://feeds.folha.uol.com.br/emcimadahora/rss.xml"),
    ("g1", "https://g1.globo.com/rss/g1/"),
    ("bbc", "https://feeds.bbci.co.uk/news/rss.xml"),
]

async def parsear_rss(session: aiohttp.ClientSession, label: str, url: str) -> list[dict]:
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
            if r.status != 200:
                return []
            text = await r.text()
            titles = re.findall(r"<title>(.*?)</title>", text, re.DOTALL)
            items = []
            for t in titles:
                t = t.strip()
                if t and len(t) > 10 and "<![" not in t:
                    items.append({"fonte": label, "titulo": t})
            return items[:5]
    except:
        return []

async def buscar_noticias(limite: int = 5) -> list[str]:
    agora = time.time()
    cache = cache_noticias.get("noticias")
    if cache and (agora - cache[0]) < tempo_cache:
        return [n["titulo"] for n in cache[1][:limite]]

    async with aiohttp.ClientSession() as s:
        tasks = [parsear_rss(s, label, url) for label, url in FEEDS]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    todas = []
    for r in results:
        if isinstance(r, list):
            todas.extend(r)

    random.shuffle(todas)
    cache_noticias["noticias"] = (time.time(), todas)
    return [n["titulo"] for n in todas[:limite]]

async def noticias_para_fala(limite: int = 3) -> str:
    try:
        noticias = await buscar_noticias(limite)
        if not noticias:
            return "Nenhuma notícia encontrada no momento."
        return "Notícias: " + " | ".join(f"{i+1}. {n}" for i, n in enumerate(noticias))
    except Exception:
        return "Não foi possível buscar notícias agora."
