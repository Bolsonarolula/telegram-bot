import asyncio
import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, ConversationHandler, MessageHandler, filters
from telethon import TelegramClient, errors
from telethon.tl.functions.channels import InviteToChannelRequest
from telethon.tl.functions.messages import AddChatUserRequest
from telethon.tl.types import Channel, Chat

# ======= CONFIGURAÇÕES =======
BOT_TOKEN = "7146425074:AAHf2EhXs2dO6jaiDrnl3F6qnc70Rg_GhZ0"
API_ID = 20305448
API_HASH = "2d9ee612f8ece128cd4bd78b2e71d01e"
PHONE = "+5522981528428"
OWNER_ID = 8002161328
INTERVALO_ADICAO = 20
# =============================

os.makedirs("sessions", exist_ok=True)
AGUARDANDO_CODIGO, AGUARDANDO_SENHA = range(2)

# Cliente Telethon - sem loop manual
client = TelegramClient("sessions/user_session", API_ID, API_HASH)

def apenas_dono(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != OWNER_ID:
            await update.message.reply_text("⛔ Acesso negado.")
            return
        return await func(update, context)
    return wrapper

@apenas_dono
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Olá! Comandos disponíveis:\n"
        "/login — Autenticar sua conta Telegram\n"
        "/adicionar @origem @destino — Transferir membros\n"
        "/status — Ver se está autenticado"
    )

@apenas_dono
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if client.is_connected():
            autenticado = await client.is_user_authorized()
            if autenticado:
                await update.message.reply_text("✅ Conta autenticada e pronta para uso.")
            else:
                await update.message.reply_text("❌ Conectado mas não autenticado. Use /login.")
        else:
            await update.message.reply_text("❌ Não conectado. Use /login primeiro.")
    except Exception as e:
        await update.message.reply_text(f"Erro ao verificar status: {e}")

@apenas_dono
async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not client.is_connected():
            await client.connect()
        
        autenticado = await client.is_user_authorized()
        if autenticado:
            await update.message.reply_text("✅ Você já está autenticado!")
            return ConversationHandler.END
        
        await client.send_code_request(PHONE)
        await update.message.reply_text("📱 Código enviado para o seu Telegram. Digite o código:")
        return AGUARDANDO_CODIGO
    except Exception as e:
        await update.message.reply_text(f"Erro ao iniciar login: {e}")
        return ConversationHandler.END

@apenas_dono
async def receber_codigo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    codigo = update.message.text.strip()
    try:
        await client.sign_in(PHONE, codigo)
        await update.message.reply_text("✅ Login realizado com sucesso!")
        return ConversationHandler.END
    except errors.SessionPasswordNeededError:
        await update.message.reply_text("🔐 Sua conta tem verificação em duas etapas. Digite sua senha:")
        return AGUARDANDO_SENHA
    except Exception as e:
        await update.message.reply_text(f"Erro ao confirmar código: {e}")
        return ConversationHandler.END

@apenas_dono
async def receber_senha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    senha = update.message.text.strip()
    try:
        await client.sign_in(password=senha)
        await update.message.reply_text("✅ Login realizado com sucesso!")
    except Exception as e:
        await update.message.reply_text(f"Erro ao confirmar senha: {e}")
    return ConversationHandler.END

@apenas_dono
async def adicionar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Uso correto: /adicionar @grupo_origem @grupo_destino")
        return
    
    origem_id = context.args[0]
    destino_id = context.args[1]
    
    await update.message.reply_text(f"⏳ Iniciando coleta de membros de {origem_id}...")
    
    try:
        if not client.is_connected():
            await client.connect()
        
        autenticado = await client.is_user_authorized()
        if not autenticado:
            await update.message.reply_text("❌ Não autenticado. Use /login primeiro.")
            return
        
        origem = await client.get_entity(origem_id)
        destino = await client.get_entity(destino_id)
        
        membros = []
        async for user in client.iter_participants(origem, aggressive=True):
            if not user.bot and not user.deleted:
                membros.append(user)
        
        await update.message.reply_text(f"✅ {len(membros)} membros coletados. Iniciando adição...")
        
        adicionados = 0
        erros = 0
        
        for i, user in enumerate(membros):
            try:
                if isinstance(destino, Channel):
                    await client(InviteToChannelRequest(destino, [user]))
                elif hasattr(destino, 'participants'):  # Chat
                    await client(AddChatUserRequest(destino.id, user, 10))
                
                adicionados += 1
                
                if adicionados % 5 == 0:
                    await update.message.reply_text(f"➕ {adicionados} adicionados até agora...")
                
                await asyncio.sleep(INTERVALO_ADICAO)
                
            except Exception as e:
                erros += 1
                print(f"Erro ao adicionar {user.username or user.id}: {e}")
        
        await update.message.reply_text(
            f"🏁 Concluído!\n"
            f"✅ Adicionados: {adicionados}\n"
            f"❌ Erros: {erros}"
        )
        
    except Exception as e:
        await update.message.reply_text(f"Erro: {e}")

async def post_init(application):
    """Inicializa o Telethon quando o bot inicia"""
    if not client.is_connected():
        await client.connect()
    print("Telethon conectado!")

async def post_shutdown(application):
    """Desconecta o Telethon quando o bot para"""
    if client.is_connected():
        await client.disconnect()
    print("Telethon desconectado!")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).post_shutdown(post_shutdown).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("login", login)],
        states={
            AGUARDANDO_CODIGO: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_codigo)],
            AGUARDANDO_SENHA: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_senha)],
        },
        fallbacks=[]
    )
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("adicionar", adicionar))
    app.add_handler(conv_handler)
    
    print("Bot rodando...")
    app.run_polling()

if __name__ == "__main__":
    main()