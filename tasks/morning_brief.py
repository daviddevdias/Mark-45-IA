from __future__ import annotations

import config
from tasks.news import noticias_para_fala

async def gerar_briefing(ativo: bool | None = None) -> str:
    if ativo is None:
        ativo = getattr(config, "BRIEFING_AUTO", True)
    if not ativo:
        return "Briefing desativado nas configurações."

    partes = ["Bom dia, Senhor. Aqui está seu briefing matinal."]

    clima = getattr(config, "cidade_padrao", "")
    if clima:
        try:
            from tasks.monitor import status_clima
            info = status_clima(clima)
            if info:
                partes.append(f"Clima em {clima}: {info}.")
        except:
            pass

    news_ativo = getattr(config, "NEWS_ATIVO", True)
    if news_ativo:
        try:
            noticias = await noticias_para_fala(3)
            if noticias:
                partes.append(noticias)
        except:
            pass

    cal_ativo = getattr(config, "CALENDAR_ATIVO", False)
    if cal_ativo:
        try:
            from datetime import date
            from tasks.calendar_integration import eventos_para_fala
            ev = eventos_para_fala(date.today().isoformat())
            if ev:
                partes.append(ev)
        except:
            pass

    email_ativo = getattr(config, "EMAIL_ATIVO", False)
    if email_ativo:
        try:
            from tasks.email_checker import emails_para_fala
            emails = await emails_para_fala(3)
            if emails:
                partes.append(emails)
        except:
            pass

    return ". ".join(partes)
