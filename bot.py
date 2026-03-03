import asyncio
import os
import json
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, ConversationHandler, MessageHandler, filters
from telethon import TelegramClient, errors
from telethon.tl.functions.channels import InviteToChannelRequest
from telethon.tl.functions.messages import AddChatUserRequest
from telethon.tl.types import Channel, Chat

# ======= CONFIGURAÇÕES =======
BOT_TOKEN = "7146425074:AAHf2EhXs2dO6jaiDrnl3F6qnc70Rg_GhZ0"
OWNER_ID = 8002161328
INTERVALO_ADICAO = 20

# Configuração de múltiplas contas (adicione quantas quiser)
CONTAS_CONFIG = [
    {
        "nome": "conta1",
        "api_id": 20305448,
        "api_hash": "2d9ee612f8ece128cd4bd78b2e71d01e",
        "phone": "+5522981528428"
    },
    # Adicione mais contas aqui:
    # {
    #     "nome": "conta2",
    #     "api_id": SEU_API_ID_2,
    #     "api_hash": "SEU_API_HASH_2",
    #     "phone": "+SEU_NUMERO_2"
    # },
]
# =============================

os.makedirs("sessions", exist_ok=True)

# Estados da conversação
AGUARDANDO_CONTA, AGUARDANDO_CODIGO, AGUARDANDO_SENHA = range(3)

# Dicionário para armazenar os clientes Telethon ativos
clientes = {}
conta_atual = {}  # Para rastrear qual conta está sendo logada

def apenas_dono(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != OWNER_ID:
            await update.message.reply_text("⛔ Acesso negado.")
            return
        return await func(update, context)
    return wrapper

def get_teclado_contas():
    """Retorna string com lista de contas disponíveis"""
    if not CONTAS_CONFIG:
        return "Nenhuma conta configurada."

    texto = "📱 Contas disponíveis:
"
    for i, conta in enumerate(CONTAS_CONFIG, 1):
        status = "🟢" if conta["nome"] in clientes else "🔴"
        texto += f"{i}. {status} {conta['nome']} ({conta['phone']})
"
    return texto

@apenas_dono
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Olá! Comandos disponíveis:
"
        "/contas — Ver contas configuradas e status
"
        "/login <nome_conta> — Autenticar uma conta específica
"
        "/login_todas — Autenticar todas as contas
"
        "/adicionar @origem @destino — Transferir membros usando todas as contas
"
        "/status — Ver status das contas
"
        "/parar <nome_conta> — Desconectar uma conta

"
        f"{get_teclado_contas()}"
    )

@apenas_dono
async def contas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lista todas as contas e seus status"""
    texto = "📱 **Status das Contas**

"

    for conta in CONTAS_CONFIG:
        nome = conta["nome"]
        telefone = conta["phone"]

        if nome in clientes:
            cliente = clientes[nome]
            try:
                if cliente.is_connected():
                    autenticado = await cliente.is_user_authorized()
                    status = "🟢 Conectado" if autenticado else "🟡 Conectado (não autenticado)"
                else:
                    status = "🔴 Desconectado"
            except:
                status = "🔴 Erro"
        else:
            status = "🔴 Não iniciado"

        texto += f"**{nome}** ({telefone}): {status}
"

    await update.message.reply_text(texto, parse_mode="Markdown")

@apenas_dono
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Verifica status de todas as contas"""
    await contas(update, context)

@apenas_dono
async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicia login em uma conta específica"""
    global conta_atual

    if not context.args:
        await update.message.reply_text(
            "Uso: /login <nome_conta>

"
            f"{get_teclado_contas()}"
        )
        return ConversationHandler.END

    nome_conta = context.args[0]

    # Procura a configuração da conta
    conta_config = None
    for conta in CONTAS_CONFIG:
        if conta["nome"] == nome_conta:
            conta_config = conta
            break

    if not conta_config:
        await update.message.reply_text(f"❌ Conta '{nome_conta}' não encontrada.")
        return ConversationHandler.END

    # Cria o cliente se não existir
    if nome_conta not in clientes:
        session_path = f"sessions/{nome_conta}"
        clientes[nome_conta] = TelegramClient(
            session_path, 
            conta_config["api_id"], 
            conta_config["api_hash"]
        )

    cliente = clientes[nome_conta]

    try:
        if not cliente.is_connected():
            await cliente.connect()

        autenticado = await cliente.is_user_authorized()
        if autenticado:
            await update.message.reply_text(f"✅ Conta '{nome_conta}' já está autenticada!")
            return ConversationHandler.END

        # Armazena qual conta está sendo logada
        conta_atual[update.effective_user.id] = nome_conta

        await cliente.send_code_request(conta_config["phone"])
        await update.message.reply_text(
            f"📱 Código enviado para {conta_config['phone']} (conta: {nome_conta}).
"
            "Digite o código:"
        )
        return AGUARDANDO_CODIGO

    except Exception as e:
        await update.message.reply_text(f"❌ Erro ao iniciar login: {e}")
        return ConversationHandler.END

@apenas_dono
async def receber_codigo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recebe o código de verificação"""
    user_id = update.effective_user.id

    if user_id not in conta_atual:
        await update.message.reply_text("❌ Sessão de login expirada. Use /login novamente.")
        return ConversationHandler.END

    nome_conta = conta_atual[user_id]
    cliente = clientes[nome_conta]
    conta_config = next(c for c in CONTAS_CONFIG if c["nome"] == nome_conta)

    codigo = update.message.text.strip()

    try:
        await cliente.sign_in(conta_config["phone"], codigo)
        await update.message.reply_text(f"✅ Login realizado com sucesso na conta '{nome_conta}'!")
        del conta_atual[user_id]
        return ConversationHandler.END

    except errors.SessionPasswordNeededError:
        await update.message.reply_text("🔐 Conta com 2FA. Digite a senha:")
        return AGUARDANDO_SENHA

    except Exception as e:
        await update.message.reply_text(f"❌ Erro: {e}")
        del conta_atual[user_id]
        return ConversationHandler.END

@apenas_dono
async def receber_senha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recebe a senha de 2FA"""
    user_id = update.effective_user.id

    if user_id not in conta_atual:
        await update.message.reply_text("❌ Sessão expirada.")
        return ConversationHandler.END

    nome_conta = conta_atual[user_id]
    cliente = clientes[nome_conta]

    senha = update.message.text.strip()

    try:
        await cliente.sign_in(password=senha)
        await update.message.reply_text(f"✅ Login com 2FA realizado na conta '{nome_conta}'!")
    except Exception as e:
        await update.message.reply_text(f"❌ Erro na senha: {e}")

    del conta_atual[user_id]
    return ConversationHandler.END

@apenas_dono
async def login_todas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tenta conectar todas as contas já autenticadas (sem código)"""
    resultados = []

    for conta in CONTAS_CONFIG:
        nome = conta["nome"]
        try:
            if nome not in clientes:
                session_path = f"sessions/{nome}"
                clientes[nome] = TelegramClient(
                    session_path, 
                    conta["api_id"], 
                    conta["api_hash"]
                )

            cliente = clientes[nome]
            if not cliente.is_connected():
                await cliente.connect()

            if await cliente.is_user_authorized():
                resultados.append(f"✅ {nome}: Autenticada")
            else:
                resultados.append(f"⚠️ {nome}: Não autenticada (use /login {nome})")

        except Exception as e:
            resultados.append(f"❌ {nome}: Erro - {e}")

    await update.message.reply_text("📊 Resultado:
" + "
".join(resultados))

@apenas_dono
async def parar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Desconecta uma conta específica"""
    if not context.args:
        await update.message.reply_text("Uso: /parar <nome_conta>")
        return

    nome_conta = context.args[0]

    if nome_conta not in clientes:
        await update.message.reply_text(f"❌ Conta '{nome_conta}' não está ativa.")
        return

    try:
        cliente = clientes[nome_conta]
        if cliente.is_connected():
            await cliente.disconnect()
        del clientes[nome_conta]
        await update.message.reply_text(f"✅ Conta '{nome_conta}' desconectada.")
    except Exception as e:
        await update.message.reply_text(f"❌ Erro ao desconectar: {e}")

@apenas_dono
async def adicionar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Adiciona membros usando todas as contas disponíveis (distribuição round-robin)"""

    if len(context.args) < 2:
        await update.message.reply_text("Uso: /adicionar @grupo_origem @grupo_destino")
        return

    origem_id = context.args[0]
    destino_id = context.args[1]

    # Verifica quais contas estão autenticadas
    contas_prontas = []
    for nome, cliente in clientes.items():
        try:
            if cliente.is_connected() and await cliente.is_user_authorized():
                contas_prontas.append((nome, cliente))
        except:
            pass

    if not contas_prontas:
        await update.message.reply_text("❌ Nenhuma conta autenticada. Use /login ou /login_todas primeiro.")
        return

    await update.message.reply_text(
        f"🚀 Iniciando com {len(contas_prontas)} conta(s)...
"
        f"Origem: {origem_id}
"
        f"Destino: {destino_id}"
    )

    try:
        # Usa a primeira conta para coletar membros
        cliente_principal<response clipped><NOTE>Result is longer than **10000 characters**, will be **truncated**.</NOTE>
