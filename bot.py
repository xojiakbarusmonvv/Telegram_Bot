import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update
from telegram.ext import Application, MessageHandler, ContextTypes, filters
from groq import Groq


TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
GROQ_API_KEY = os.environ["GROQ_API_KEY"]

client = Groq(api_key=GROQ_API_KEY)

histories = {}

SYSTEM_PROMPT = """
Sen aqlli Telegram AI yordamchisisan.
Foydalanuvchi bilan doimo o‘zbek tilida gaplash.
Savolga mos, tabiiy va tushunarli javob ber.
Matematika, uy vazifasi, tarjima, texnologiya va boshqa
mavzularda yordam ber.
Oddiy suhbatda samimiy gaplash.
Keraksiz uzun javob bermagin.
"""


async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if user_id not in histories:
        histories[user_id] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]

    histories[user_id].append({
        "role": "user",
        "content": text
    })

    messages = histories[user_id][-21:]

    try:
        response = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=messages
        )

        answer = response.choices[0].message.content

        if not answer:
            answer = "Kechirasiz, javob tayyor bo‘lmadi."

        histories[user_id].append({
            "role": "assistant",
            "content": answer
        })

        await update.message.reply_text(answer)

    except Exception as e:
        print("XATOLIK:", e)
        await update.message.reply_text(
            "Kechirasiz, hozir javob berishda muammo bo‘ldi."
        )


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Telegram bot ishlayapti!")

    def log_message(self, format, *args):
        pass


def start_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    server.serve_forever()


threading.Thread(target=start_web_server, daemon=True).start()

app = Application.builder().token(TELEGRAM_TOKEN).build()

app.add_handler(
    MessageHandler(filters.TEXT & ~filters.COMMAND, chat)
)

print("BOTIMIZ_ISHLAYAPTI!")

app.run_polling()
