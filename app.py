# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')

import asyncio
import os
import datetime
import threading
import requests
from flask import Flask, jsonify
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from dotenv import load_dotenv

# ---------------------------
# CONFIGURAÇÃO
# ---------------------------
load_dotenv()

API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
SESSION_STRING = os.getenv("SESSION_STRING")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").strip()

if not API_ID or not API_HASH:
    raise ValueError("❌ As variáveis API_ID e API_HASH devem estar definidas.")
try:
    API_ID = int(API_ID)
except ValueError:
    raise ValueError("❌ A variável API_ID precisa ser um número inteiro válido.")

if not SESSION_STRING:
    raise ValueError("❌ A variável SESSION_STRING não foi encontrada no ambiente (.env).")

# ---------------------------
# CLIENTE TELETHON E FLASK
# ---------------------------
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
app = Flask(__name__)

# ---------------------------
# ROTA HEALTH CHECK
# ---------------------------
@app.route("/healthz")
def health():
    return jsonify({
        "status": "running",
        "webhook": bool(WEBHOOK_URL),
        "telegram_connected": client.is_connected()
    }), 200

# ---------------------------
# HANDLER DE NOVAS MENSAGENS
# ---------------------------
@client.on(events.NewMessage)
async def handler(event):
    try:
        msg = event.message
        chat = await event.get_chat()
        sender = await event.get_sender()

        # Dados úteis
        direction = "📤" if msg.out else "📥"
        time_str = datetime.datetime.now().strftime("%H:%M:%S")

        sender_name = getattr(sender, "username", None) or getattr(sender, "first_name", "Desconhecido")
        chat_title = getattr(chat, "title", None) or "Privado"
        text = msg.message or "<sem texto>"

        # Log bonitinho no console
        print(f"[{time_str}] {direction} {sender_name} → {chat_title}: {text}")

        # Envio opcional para Webhook
        if WEBHOOK_URL:
            data = {
                "message_id": msg.id,
                "text": text,
                "date": msg.date.isoformat(),
                "outgoing": msg.out,
                "chat": {
                    "id": getattr(chat, "id", None),
                    "title": chat_title,
                    "is_user": chat.__class__.__name__ == "User",
                    "is_group": getattr(chat, "megagroup", False),
                    "is_channel": getattr(chat, "broadcast", False),
                },
                "sender": {
                    "id": getattr(sender, "id", None),
                    "username": getattr(sender, "username", None),
                    "first_name": getattr(sender, "first_name", None),
                    "last_name": getattr(sender, "last_name", None),
                    "phone": getattr(sender, "phone", None),
                    "is_self": getattr(sender, "is_self", False),
                },
            }
            try:
                requests.post(WEBHOOK_URL, json=data, timeout=8)
            except Exception as e:
                print("❌ Erro ao enviar webhook:", e)

    except Exception as e:
        print("⚠️ Erro no handler:", e)

# ---------------------------
# LOGIN AUTOMÁTICO
# ---------------------------
async def login():
    if not await client.is_user_authorized():
        print("📱 Você ainda não está logado no Telegram.")
        phone = input("👉 Digite seu número de telefone (ex: +55XXXXXXXXXX): ")
        await client.send_code_request(phone)
        code = input("🔑 Digite o código que você recebeu no Telegram: ")
        try:
            await client.sign_in(phone=phone, code=code)
            print("✅ Login realizado com sucesso!")
        except Exception as e:
            print("❌ Erro ao fazer login:", e)
            exit(1)
    else:
        me = await client.get_me()
        print(f"✅ Sessão existente — logado como {me.first_name} (@{me.username})")

# ---------------------------
# INICIALIZAÇÃO COMPLETA
# ---------------------------
async def start_all():
    await client.connect()
    await login()
    print("✅ Telethon iniciado e escutando mensagens...")

    from hypercorn.asyncio import serve
    from hypercorn.config import Config
    config = Config()
    config.bind = ["0.0.0.0:5000"]
    await serve(app, config)

# ---------------------------
# DETECÇÃO AUTOMÁTICA DE MODO
# ---------------------------
def run_background(loop):
    asyncio.set_event_loop(loop)
    loop.run_until_complete(client.connect())
    loop.run_until_complete(login())
    print("✅ Telethon iniciado (modo Gunicorn).")
    loop.run_until_complete(client.run_until_disconnected())

if __name__ == "__main__":
    # Rodando manualmente (ex: python app.py)
    asyncio.run(start_all())
else:
    # Rodando via Gunicorn (ex: gunicorn app:app)
    loop = asyncio.new_event_loop()
    threading.Thread(target=run_background, args=(loop,), daemon=True).start()
