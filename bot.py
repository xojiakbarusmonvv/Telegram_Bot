import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update
from telegram.ext import Application, MessageHandler, ContextTypes, filters
from groq import Groq


# =========================
# API KEYLAR
# =========================

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
GROQ_API_KEY = os.environ["GROQ_API_KEY"]

client = Groq(api_key=GROQ_API_KEY)


# =========================
# FOYDALANUVCHI TARIXI
# =========================

histories = {}


# =========================
# BOTNING XARAKTERI
# =========================

SYSTEM_PROMPT = """
Sen Telegramdagi aqlli AI yordamchisan.

Foydalanuvchi bilan asosan o‘zbek tilida gaplash.
Foydalanuvchi qaysi tilda savol bersa, kerak bo‘lsa o‘sha tilda javob ber.

Javoblaring:
- tabiiy
- tushunarli
- foydali
- aniq
- keraksiz darajada uzun bo‘lmagan
bo‘lsin.

Oddiy suhbatda samimiy gaplash.

Matematika, tarjima, dasturlash, texnologiya,
Xitoy tili, ingliz tili, o‘qish, umumiy bilim,
kundalik savollar va boshqa mavzularda yordam ber.

Agar savolga javob berish uchun hozirgi yoki yangilangan
ma'lumot kerak bo‘lsa, internetdan qidirish imkoniyatidan foydalan.

Internetdan topilgan ma'lumotni o‘zing to‘qib chiqarmagin.
Agar ma'lumot noaniq bo‘lsa, buni foydalanuvchiga ayt.

Foydalanuvchi oldingi gaplarini davom ettirsa,
suhbat tarixidan foydalan.

Foydalanuvchiga yordam berishda hurmatli va do‘stona bo‘l.
"""


# =========================
# TELEGRAM XABARINI QABUL QILISH
# =========================

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not update.message or not update.message.text:
        return

    user_id = update.effective_user.id
    text = update.message.text.strip()

    if not text:
        return

    # Yangi foydalanuvchi uchun tarix yaratish
    if user_id not in histories:
        histories[user_id] = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            }
        ]

    # Foydalanuvchi savolini tarixga qo‘shish
    histories[user_id].append(
        {
            "role": "user",
            "content": text
        }
    )

    # Juda ko‘p tarix yig‘ilib ketmasligi uchun
    # oxirgi suhbatlarni yuboramiz
    messages = histories[user_id][-21:]

    try:

        response = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=messages,

            # Internetdan qidirish imkoniyati
            tools=[
                {
                    "type": "browser_search"
                }
            ],

            # Browser searchdan foydalanishga ruxsat
            tool_choice="required",

            # Javob tezroq bo‘lishi uchun
            reasoning_effort="low",

            temperature=1,
            max_completion_tokens=2048,
            stream=False
        )

        answer = response.choices[0].message.content

        if not answer:
            answer = "Kechirasiz, hozir javob tayyor bo‘lmadi."

        # AI javobini tarixga saqlash
        histories[user_id].append(
            {
                "role": "assistant",
                "content": answer
            }
        )

        # Telegram xabar uzunligi cheklangan.
        # Juda uzun javob bo‘lsa bo‘lib yuboramiz.
        max_length = 4000

        for i in range(0, len(answer), max_length):
            await update.message.reply_text(
                answer[i:i + max_length]
            )

    except Exception as e:

        print("XATOLIK:", repr(e))

        await update.message.reply_text(
            "Kechirasiz, hozir javob berishda muammo bo‘ldi. "
            "Birozdan keyin yana urinib ko‘ring."
        )


# =========================
# RENDER UCHUN WEB SERVER
# =========================

class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(
            b"Telegram bot ishlayapti!"
        )

    def log_message(self, format, *args):
        pass


def start_web_server():

    port = int(
        os.environ.get("PORT", 10000)
    )

    server = HTTPServer(
        ("0.0.0.0", port),
        HealthHandler
    )

    server.serve_forever()


# Web serverni alohida ishga tushirish
threading.Thread(
    target=start_web_server,
    daemon=True
).start()


# =========================
# TELEGRAM BOT
# =========================

app = (
    Application
    .builder()
    .token(TELEGRAM_TOKEN)
    .build()
)


# Oddiy text xabarlarni qabul qilish
app.add_handler(
    MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        chat
    )
)


print("BOT ISHLAYAPTI!")

app.run_polling()
