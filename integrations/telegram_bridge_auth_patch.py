import asyncio
import config
from telegram import Update, BotCommand
from telegram.ext import (
    Application, 
    CommandHandler, 
    ContextTypes, 
    MessageHandler, 
    filters
)
# Importações dos seus motores de negócio
from engine.controller import processar_diretriz
from engine.ia_router import router
from tasks.alarm import gerenciador_alarmes
from tasks.weather import obter_previsao_hoje
from audio.voz import falar, interromper_voz
from integrations.telegram_auth import requer_autorizacao

# Configurações globais
TOKEN = getattr(config, "TELEGRAM_TOKEN", "")
NOME_USUARIO = "David"
app = None

# --- FUNÇÕES DE SUPORTE ---

def get_cidade_padrao() -> str:
    """Retorna a cidade configurada sem depender de storage externo."""
    return getattr(config, "cidade_padrao", "São Paulo")

async def responder_e_falar(update: Update, texto: str):
    """Envia resposta ao Telegram e executa a fala no servidor."""
    if not texto:
        return
    await update.message.reply_text(str(texto))
    # Executa a voz de forma assíncrona para não travar o bot
    asyncio.create_task(falar(str(texto)))

# --- HANDLERS DE COMANDOS ---

@requer_autorizacao
async def cmd_jarvis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = " ".join(context.args)
    if not texto:
        return await update.message.reply_text("Uso: /jarvis <comando>")
    
    # Prioriza o controller, se não, envia para a IA
    resultado = await processar_diretriz(texto) or await router.responder(texto, nome=NOME_USUARIO)
    await responder_e_falar(update, resultado)

@requer_autorizacao
async def cmd_texto_livre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text
    if not texto: return
    
    resultado = await processar_diretriz(texto) or await router.responder(texto, nome=NOME_USUARIO)
    await responder_e_falar(update, resultado)

@requer_autorizacao
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from engine.ia_router import disponivel, modelo
    status_msg = (
        f"J.A.R.V.I.S — SISTEMAS ATIVOS\n"
        f"Ollama: {'online' if disponivel else 'offline'}\n"
        f"Modelo: {modelo or 'nenhum'}"
    )
    await update.message.reply_text(status_msg)

@requer_autorizacao
async def cmd_clima(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cidade = " ".join(context.args).strip() or get_cidade_padrao()
    resultado = await asyncio.to_thread(obter_previsao_hoje, cidade)
    await responder_e_falar(update, resultado)

@requer_autorizacao
async def cmd_alarme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        return await update.message.reply_text("Uso: /alarme HH:MM <descricao>")
    
    hora = context.args[0]
    desc = " ".join(context.args[1:])
    resultado = gerenciador_alarmes.adicionar_alarme(hora, desc)
    await responder_e_falar(update, resultado)

@requer_autorizacao
async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    interromper_voz()
    await update.message.reply_text("Voz interrompida.")

@requer_autorizacao
async def cmd_ajuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "Comandos disponíveis:\n"
        "/jarvis - Comando geral\n"
        "/status - Verificar sistemas\n"
        "/clima - Previsão do tempo\n"
        "/alarme - Adicionar alarme\n"
        "/stop - Parar voz"
    )
    await update.message.reply_text(help_text)

# --- CONFIGURAÇÃO DO APP ---

async def configurar_comandos(application: Application):
    comandos = [
        ("jarvis", "Comando"), ("status", "Status"), ("clima", "Clima"),
        ("alarme", "Criar alarme"), ("stop", "Parar voz"), ("ajuda", "Ajuda")
    ]
    await application.bot.set_my_commands([BotCommand(n, d) for n, d in comandos])

def iniciar_telegram():
    global app
    if not TOKEN:
        print("Erro: TELEGRAM_TOKEN não encontrado.")
        return

    # Inicia a aplicação
    app = Application.builder().token(TOKEN).post_init(configurar_comandos).build()
    
    # Registra os handlers
    app.add_handler(CommandHandler("jarvis", cmd_jarvis))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("clima", cmd_clima))
    app.add_handler(CommandHandler("alarme", cmd_alarme))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("ajuda", cmd_ajuda))
    
    # Handler para mensagens de texto sem comando
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, cmd_texto_livre))
    
    print("Bot do Telegram iniciado com sucesso.")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    iniciar_telegram()