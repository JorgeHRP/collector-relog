import asyncio
from telethon import TelegramClient, events
from flask import Flask, jsonify
import os, requests
from dotenv import load_dotenv

# ---------------------------
# CONFIGURAÇÃO
# ---------------------------
load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SESSION_NAME = os.getenv("SESSION_NAME", "session_userbot")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").strip()

client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
app = Flask(__name__)

# ---------------------------
# ROTA HEALTH CHECK
# ---------------------------
@app.route("/healthz")
def health():
    return jsonify({"status": "running", "webhook": bool(WEBHOOK_URL)}), 200


# ---------------------------
# HANDLER DE NOVAS MENSAGENS
# ---------------------------
@client.on(events.NewMessage)
async def handler(event):
    try:
        msg = event.message
        chat = await event.get_chat()
        sender = await event.get_sender()

        # ---------------------------
        # DADOS DO CHAT
        # ---------------------------
        chat_data = {
            "id": getattr(chat, "id", None),
            "title": getattr(chat, "title", None),
            "is_user": chat.__class__.__name__ == "User",
            "is_group": getattr(chat, "megagroup", False),
            "is_channel": getattr(chat, "broadcast", False),
        }

        # ---------------------------
        # DADOS DO REMETENTE
        # ---------------------------
        sender_data = {
            "id": getattr(sender, "id", None),
            "username": getattr(sender, "username", None),
            "first_name": getattr(sender, "first_name", None),
            "last_name": getattr(sender, "last_name", None),
            "phone": getattr(sender, "phone", None),
            "is_self": getattr(sender, "is_self", False),
        }

        # ---------------------------
        # FOTO DE PERFIL DO REMETENTE
        # ---------------------------
        photo_path = None
        try:
            if sender.photo:
                os.makedirs("static/photos", exist_ok=True)
                photo_path = f"static/photos/{sender.id}.jpg"
                await client.download_profile_photo(sender, file=photo_path)
        except Exception:
            photo_path = None

        # ---------------------------
        # PACOTE COMPLETO DE DADOS
        # ---------------------------
        data = {
            "message_id": msg.id,
            "text": msg.message,
            "date": msg.date.isoformat(),
            "outgoing": msg.out,
            "chat": chat_data,
            "sender": {
                **sender_data,
                "photo": photo_path,
            },
        }

        # ---------------------------
        # LOG
        # ---------------------------
        direction = "📤 Enviado" if msg.out else "📥 Recebido"
        print(f"[{data['date']}] {direction} | {sender_data['username']} -> {data['text']}")

        # ---------------------------
        # ENVIO PARA O WEBHOOK
        # ---------------------------
        if WEBHOOK_URL:
            try:
                requests.post(WEBHOOK_URL, json=data, timeout=8)
            except Exception as e:
                print("❌ Erro ao enviar webhook:", e)

    except Exception as e:
        print("⚠️ Erro no handler:", e)


# ---------------------------
# INICIALIZAÇÃO DO SISTEMA
# ---------------------------
async def start_all():
    await client.start()
    print("✅ Telethon iniciado e escutando mensagens...")

    # roda Flask e Telethon juntos com Hypercorn
    from hypercorn.asyncio import serve
    from hypercorn.config import Config

    config = Config()
    config.bind = ["0.0.0.0:5000"]
    await serve(app, config)


if __name__ == "__main__":
    asyncio.run(start_all())
