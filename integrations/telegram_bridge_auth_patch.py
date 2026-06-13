import asyncio, re, config
from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from engine.controller import processar_diretriz
from engine.ia_router import router
from storage.memory_manager import get_nome
from tasks.alarm import gerenciador_alarmes
from tasks.weather import obter_previsao_hoje, verificar_chuva_amanha
from audio.voz import falar, interromper_voz
from integrations.telegram_auth import requer_autorizacao

TOKEN = getattr(config, "TELEGRAM_TOKEN", "")
app = None
monitorando = False


def nome() -> str:
    return get_nome() or "Chefe"


def cidade_padrao() -> str:
    try:
        g = (getattr(config, "cidade_padrao", None) or "").strip()
        if g:
            return g
        return (config.ler_json(config.API_DIR / "config_core.json").get("cidade_padrao") or "São Paulo").strip() or "São Paulo"
    except:
        return "São Paulo"


async def responder_e_falar(update: Update, texto: str):
    if not texto:
        return
    await update.message.reply_text(str(texto))
    asyncio.create_task(falar(str(texto)))


@requer_autorizacao
async def cmd_jarvis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = " ".join(context.args)
    if not texto:
        return await update.message.reply_text("Use: /jarvis <comando>")
    await responder_e_falar(update, await processar_diretriz(texto) or await router.responder(texto, nome=nome()))


@requer_autorizacao
async def cmd_texto_livre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text
    if not texto:
        return
    await responder_e_falar(update, await processar_diretriz(texto) or await router.responder(texto, nome=nome()))


@requer_autorizacao
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from engine.ia_router import disponivel, modelo
    await update.message.reply_text(
        f"J.A.R.V.I.S — SISTEMAS ATIVOS\n"
        f"Ollama: {'online' if disponivel else 'offline'}\n"
        f"Modelo: {modelo or 'nenhum'}\n"
        f"Monitor: {'ativo' if monitorando else 'inativo'}"
    )


@requer_autorizacao
async def cmd_clima(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cidade = " ".join(context.args).strip() or cidade_padrao()
    await responder_e_falar(update, await asyncio.get_event_loop().run_in_executor(None, obter_previsao_hoje, cidade))


@requer_autorizacao
async def cmd_clima_amanha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cidade = " ".join(context.args).strip() or cidade_padrao()
    await responder_e_falar(update, await asyncio.get_event_loop().run_in_executor(None, verificar_chuva_amanha, cidade))


@requer_autorizacao
async def cmd_alarme_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        return await update.message.reply_text("Use: /alarme HH:MM desc ou YYYY-MM-DD HH:MM desc")
    args, data_arg = list(context.args), None
    if len(args) >= 3 and re.match(r"^\d{4}-\d{2}-\d{2}$", args[0]):
        data_arg = args.pop(0)
    await responder_e_falar(update, gerenciador_alarmes.adicionar_alarme(args[0], " ".join(args[1:]), data=data_arg))


@requer_autorizacao
async def cmd_alarme_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    alarmes = gerenciador_alarmes.listar_alarmes()
    if not alarmes:
        return await update.message.reply_text("Nenhum alarme ativo.")
    await update.message.reply_text(
        "Alarmes ativos:\n" + "\n".join(f"• {a.get('data') or '-'} {a['hora']} — {a['missao']}" for a in alarmes)
    )


@requer_autorizacao
async def cmd_alarme_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        return await update.message.reply_text("Use: /remover HH:MM descricao")
    await responder_e_falar(update, gerenciador_alarmes.remover_alarme(context.args[0], " ".join(context.args[1:])))


@requer_autorizacao
async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    interromper_voz()
    await update.message.reply_text("Voz interrompida.")


@requer_autorizacao
async def cmd_spotify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    termo = " ".join(context.args).strip()
    if not termo:
        return await update.message.reply_text("Use: /spotify <musica ou artista>")
    await responder_e_falar(update, await processar_diretriz(f"spotify {termo}") or "Comando Spotify enviado.")


@requer_autorizacao
async def cmd_pausar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await responder_e_falar(update, await processar_diretriz("pausar") or "Música pausada.")


@requer_autorizacao
async def cmd_continuar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await responder_e_falar(update, await processar_diretriz("continuar") or "Reprodução retomada.")


@requer_autorizacao
async def cmd_proxima(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await responder_e_falar(update, await processar_diretriz("proxima") or "Próxima faixa.")


@requer_autorizacao
async def cmd_youtube(update: Update, context: ContextTypes.DEFAULT_TYPE):
    termo = " ".join(context.args).strip()
    if not termo:
        return await update.message.reply_text("Use: /youtube <busca>")
    await responder_e_falar(update, await processar_diretriz(f"youtube {termo}") or "Abrindo YouTube.")


@requer_autorizacao
async def cmd_monitorar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global monitorando
    intervalo = max(5, int(context.args[0])) if context.args and context.args[0].isdigit() else 10
    monitorando = True
    await responder_e_falar(update, await processar_diretriz(f"monitorar tela {intervalo}") or f"Monitoramento ativo. Intervalo: {intervalo}s.")


@requer_autorizacao
async def cmd_parar_monitor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global monitorando
    monitorando = False
    await responder_e_falar(update, await processar_diretriz("desligar monitoramento") or "Monitoramento desativado.")


@requer_autorizacao
async def cmd_tela(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Capturando e analisando a tela...")
    await responder_e_falar(update, await processar_diretriz("olha tela") or "Análise concluída.")


@requer_autorizacao
async def cmd_abrir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    app_nome = " ".join(context.args).strip()
    if not app_nome:
        return await update.message.reply_text("Use: /abrir <nome do app>")
    res = await processar_diretriz(f"abrir {app_nome}")
    if not res:
        from tasks.open_app import open_app
        res = open_app({"app_name": app_nome}) or f"Abrindo {app_nome}."
    await responder_e_falar(update, res)


@requer_autorizacao
async def cmd_bloquear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await responder_e_falar(update, await processar_diretriz("bloquear") or "Tela bloqueada.")


@requer_autorizacao
async def cmd_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await responder_e_falar(update, await processar_diretriz("screenshot") or "Screenshot capturado.")


@requer_autorizacao
async def cmd_tv_ligar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await responder_e_falar(update, await processar_diretriz("ligar tv") or "Ligando TV.")


@requer_autorizacao
async def cmd_tv_desligar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await responder_e_falar(update, await processar_diretriz("desligar tv") or "Desligando TV.")


@requer_autorizacao
async def cmd_volume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or not context.args[0].isdigit():
        return await update.message.reply_text("Use: /volume <0-100>")
    await responder_e_falar(update, await processar_diretriz(f"volume {context.args[0]}") or f"Volume ajustado para {context.args[0]}.")


@requer_autorizacao
async def cmd_trabalho(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await responder_e_falar(update, await processar_diretriz("trabalho") or "Modo trabalho ativado.")


@requer_autorizacao
async def cmd_ia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    modo = " ".join(context.args).strip().lower()
    if modo not in ("ollama", "gemini", "auto"):
        return await update.message.reply_text("Use: /ia ollama | gemini | auto")
    await responder_e_falar(update, router.definir_modo(modo))


@requer_autorizacao
async def cmd_ajuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Comandos: /jarvis /status /stop /clima /amanha /alarme /listar /remover "
        "/spotify /pausar /continuar /proxima /youtube /abrir /bloquear /screenshot "
        "/trabalho /volume /tvligar /tvdesligar /tela /monitorar /pararmonitor /ia"
    )


async def configurar_comandos(application: Application):
    comandos = [
        ("jarvis", "Comando"), ("status", "Status"), ("clima", "Clima"), ("amanha", "Amanhã"),
        ("alarme", "Criar alarme HH:MM desc"), ("listar", "Listar alarmes"), ("remover", "Remover alarme"),
        ("spotify", "Tocar no Spotify"), ("pausar", "Pausar música"), ("continuar", "Continuar música"),
        ("proxima", "Próxima faixa"), ("youtube", "Tocar no YouTube"), ("abrir", "Abrir aplicativo"),
        ("bloquear", "Bloquear tela"), ("screenshot", "Capturar tela"), ("tela", "Analisar tela"),
        ("monitorar", "Monitoramento contínuo"), ("pararmonitor", "Parar monitoramento"),
        ("tvligar", "Ligar TV"), ("tvdesligar", "Desligar TV"), ("volume", "Ajustar volume"),
        ("trabalho", "Modo trabalho"), ("ia", "Trocar modelo IA"), ("stop", "Parar voz"), ("ajuda", "Lista de comandos"),
    ]
    await application.bot.set_my_commands([BotCommand(n, d) for n, d in comandos])


async def erro_telegram(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass


def iniciar_telegram():
    global app
    if not TOKEN:
        return
    asyncio.set_event_loop(asyncio.new_event_loop())
    app = Application.builder().token(TOKEN).post_init(configurar_comandos).build()
    handlers = [
        ("jarvis", cmd_jarvis), ("status", cmd_status), ("clima", cmd_clima), ("amanha", cmd_clima_amanha),
        ("stop", cmd_stop), ("ajuda", cmd_ajuda), ("alarme", cmd_alarme_add), ("listar", cmd_alarme_list),
        ("remover", cmd_alarme_remove), ("spotify", cmd_spotify), ("pausar", cmd_pausar),
        ("continuar", cmd_continuar), ("proxima", cmd_proxima), ("youtube", cmd_youtube),
        ("abrir", cmd_abrir), ("bloquear", cmd_bloquear), ("screenshot", cmd_screenshot),
        ("trabalho", cmd_trabalho), ("volume", cmd_volume), ("tvligar", cmd_tv_ligar),
        ("tvdesligar", cmd_tv_desligar), ("tela", cmd_tela), ("monitorar", cmd_monitorar),
        ("pararmonitor", cmd_parar_monitor), ("ia", cmd_ia),
    ]
    for cmd, fn in handlers:
        app.add_handler(CommandHandler(cmd, fn))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, cmd_texto_livre))
    app.add_error_handler(erro_telegram)
    try:
        app.run_polling(drop_pending_updates=True, close_loop=True)
    except:
        pass
