import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from groq import Groq


# ==================================================
# API KALITLARI
# ==================================================

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
GROQ_API_KEY = os.environ["GROQ_API_KEY"]

client = Groq(api_key=GROQ_API_KEY)


# ==================================================
# SUHBAT TARIXI
# ==================================================

histories = {}


# ==================================================
# AI XARAKTERI
# ==================================================

SYSTEM_PROMPT = """
Sen universal, aqlli va do'stona AI yordamchisan.

Foydalanuvchi bilan asosan o'zbek tilida gaplash.
Agar foydalanuvchi boshqa tilda yozsa, o'sha tilda javob ber.

Foydalanuvchi qanday savol bersa, imkon qadar yordam ber.
O'zingni faqat oldindan sanab o'tilgan mavzular bilan cheklama.

Sen quyidagilarda yordam bera olasan:

- Oddiy suhbat
- Savollarga javob
- Matematika
- Fizika
- Kimyo
- Biologiya
- Tarix
- Geografiya
- Informatika
- Maktab va universitet fanlari
- Uy vazifalarini tushuntirish
- Ingliz tili
- Xitoy tili
- Rus tili
- Koreys tili
- Arab tili
- Boshqa tillar
- Tarjima
- So'z ma'nosi
- Talaffuz
- Grammatika
- Til o'rgatish
- Insho
- Referat
- Maqola
- Hikoya
- She'r
- Ssenariy
- Email
- Telegram xabarlari
- Matnni tuzatish
- Matnni qisqartirish
- Matnni chiroyli qilish
- Reja tuzish
- G'oya berish
- Biznes g'oyalari
- Dasturlash
- Python
- JavaScript
- HTML
- CSS
- Telegram bot
- GitHub
- Render
- Kompyuter muammolari
- Telefon muammolari
- Internet muammolari
- Texnologiya
- AI
- Sayohat
- Retseptlar
- Sport
- Kitoblar
- Filmlar
- Musiqa
- O'yinlar
- Mantiqiy masalalar
- Va boshqa ko'plab mavzular.

Agar foydalanuvchi biror narsani tushunmasa,
juda sodda qilib qayta tushuntir.

Texnik muammolarda qadam-baqadam yo'l ko'rsat.

Agar savol hozirgi yoki yangilanadigan ma'lumotni talab qilsa,
internet qidiruvidan foydalan.

Internetdan topilmagan ma'lumotni o'ylab topma.
Ishonching komil bo'lmasa, buni ayt.

Foydalanuvchining oldingi xabarlaridan foydalanib,
suhbatni davom ettir.

Javoblaring tabiiy, aniq, foydali va do'stona bo'lsin.

Oddiy savollarga qisqa javob ber.
Murakkab savollarga bosqichma-bosqich javob ber.
"""


# ==================================================
# /START BUYRUG'I
# ==================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "Salom! 👋\n\n"
        "Men sizga turli mavzularda yordam bera oladigan AI botman.\n\n"
        "Savolingizni yozing — boshlaymiz! 🤖"
    )


# ==================================================
# TELEGRAM XABARLARI
# ==================================================

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not update.message:
        return

    if not update.message.text:
        return

    user_id = update.effective_user.id
    text = update.message.text.strip()

    if not text:
        return

    # Yangi foydalanuvchi uchun tarix
    if user_id not in histories:
        histories[user_id] = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            }
        ]

    # Foydalanuvchi xabarini saqlash
    histories[user_id].append(
        {
            "role": "user",
            "content": text,
        }
    )

    # Oxirgi suhbatlarni yuborish
    messages = histories[user_id][-21:]

    try:

        response = client.chat.completions.create(
            model="openai/gpt-oss-20b",

            messages=messages,

            # Internet qidiruvi mavjud
            tools=[
                {
                    "type": "browser_search"
                }
            ],

            # MUHIM:
            # required emas, auto bo'lishi kerak.
            # AI kerak bo'lsa internetdan qidiradi.
            # Oddiy savollarda esa qidirmaydi.
            tool_choice="auto",

            reasoning_effort="low",

            temperature=1,

            max_completion_tokens=2048,

            stream=False,
        )

        answer = response.choices[0].message.content

        if not answer:
            answer = "Kechirasiz, hozir javob tayyor bo'lmadi."

        # AI javobini tarixga saqlash
        histories[user_id].append(
            {
                "role": "assistant",
                "content": answer,
            }
        )

        # Telegram 4096 belgidan uzun xabarni qabul qilmaydi
        max_length = 4000

        for i in range(0, len(answer), max_length):

            await update.message.reply_text(
                answer[i:i + max_length]
            )

    except Exception as e:

        print("XATOLIK:", repr(e))

        await update.message.reply_text(
            "Kechirasiz, hozir javob berishda muammo bo'ldi. "
            "Birozdan keyin yana urinib ko'ring."
        )


# ==================================================
# RENDER WEB SERVER
# ==================================================

class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):

        self.send_response(200)
        self.end_headers()

        self.wfile.write(
            b"Telegram AI bot ishlayapti!"
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


# Render uchun web server
threading.Thread(
    target=start_web_server,
    daemon=True
).start()


# ==================================================
# TELEGRAM BOTNI ISHGA TUSHIRISH
# ==================================================

app = (
    Application
    .builder()
    .token(TELEGRAM_TOKEN)
    .build()
)


# /start
app.add_handler(
    CommandHandler(
        "start",
        start
    )
)


# Oddiy xabarlar
app.add_handler(
    MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        chat
    )
)


print("================================")
print("BOT ISHLAYAPTI!")
print("AI + INTERNET SEARCH")
print("================================")


app.run_polling()
