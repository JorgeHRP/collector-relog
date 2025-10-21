import asyncio
import os
import requests
from telethon import TelegramClient, events
from flask import Flask, jsonify
from dotenv import load_dotenv
from telethon.sessions import StringSession

# ---------------------------
# CONFIGURAÇÃO
# ---------------------------
load_dotenv()

API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
SESSION_NAME = os.getenv("SESSION_NAME", "session_userbot")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").strip()

if not API_ID or not API_HASH:
    raise ValueError("❌ As variáveis API_ID e API_HASH devem estar definidas.")
try:
    API_ID = int(API_ID)
except ValueError:
    raise ValueError("❌ A variável API_ID precisa ser um número inteiro válido.")

# ---------------------------
# CLIENTE TELETHON E FLASK
# ---------------------------
client = TelegramClient(StringSession(os.getenv("SESSION_STRING")), API_ID, API_HASH)
app = Flask(__name__)

# ---------------------------
# ROTA HEALTH CHECK
# ---------------------------
@app.route("/healthz")
def health():
    return jsonify({
        "status": "running",
        "webhook": bool(WEBHOOK_URL),
        "session_exists": os.path.exists(f"{SESSION_NAME}.session")
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

        chat_data = {
            "id": getattr(chat, "id", None),
            "title": getattr(chat, "title", None),
            "is_user": chat.__class__.__name__ == "User",
            "is_group": getattr(chat, "megagroup", False),
            "is_channel": getattr(chat, "broadcast", False),
        }

        sender_data = {
            "id": getattr(sender, "id", None),
            "username": getattr(sender, "username", None),
            "first_name": getattr(sender, "first_name", None),
            "last_name": getattr(sender, "last_name", None),
            "phone": getattr(sender, "phone", None),
            "is_self": getattr(sender, "is_self", False),
        }

        photo_path = None
        try:
            if sender.photo:
                os.makedirs("static/photos", exist_ok=True)
                photo_path = f"static/photos/{sender.id}.jpg"
                await client.download_profile_photo(sender, file=photo_path)
        except Exception:
            photo_path = None

        data = {
            "message_id": msg.id,
            "text": msg.message,
            "date": msg.date.isoformat(),
            "outgoing": msg.out,
            "chat": chat_data,
            "sender": {**sender_data, "photo": photo_path},
        }

        direction = "📤 Enviado" if msg.out else "📥 Recebido"
        print(f"[{data['date']}] {direction} | {sender_data['username']} -> {data['text']}")

        if WEBHOOK_URL:
            try:
                requests.post(WEBHOOK_URL, json=data, timeout=8)
            except Exception as e:
                print("❌ Erro ao enviar webhook:", e)

    except Exception as e:
        print("⚠️ Erro no handler:", e)


# ---------------------------
# LOGIN AUTOMÁTICO (via terminal)
# ---------------------------
async def login():
    if not await client.is_user_authorized():
        print("📱 Você ainda não está logado no Telegram.")
        phone = input("👉 Digite seu número de telefone (ex: +55XXXXXXXXXX): ")
        await client.send_code_request(phone)
        code = input("🔑 Digite o código que você recebeu no Telegram: ")
        try:
            await client.sign_in(phone=phone, code=code)
            print("✅ Login realizado com sucesso! Sessão salva.")
        except Exception as e:
            print("❌ Erro ao fazer login:", e)
            exit(1)
    else:
        print("✅ Sessão existente detectada — já logado.")


# ---------------------------
# INICIALIZAÇÃO DO SISTEMA
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


if __name__ == "__main__":
    asyncio.run(start_all())
