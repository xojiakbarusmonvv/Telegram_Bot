import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update
from telegram.ext import Application, MessageHandler, ContextTypes, filters
from groq import Groq


# ==============================
# API KALITLAR
# ==============================

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
GROQ_API_KEY = os.environ["GROQ_API_KEY"]

client = Groq(api_key=GROQ_API_KEY)


# ==============================
# SUHBAT TARIXI
# ==============================

histories = {}


# ==============================
# AI XARAKTERI
# ==============================

SYSTEM_PROMPT = """
Sen universal, aqlli va do'stona AI yordamchisan.

Foydalanuvchi bilan asosan o'zbek tilida gaplash.
Agar foydalanuvchi boshqa tilda yozsa, o'sha tilni tushun va
kerak bo'lsa o'sha tilda javob ber.

O'zingni faqat oldindan sanab o'tilgan mavzular bilan cheklama.
Foydalanuvchi qanday savol bersa, imkon qadar yordam ber.

SEN QUYIDAGI ISHLARNI QILA OLASAN:

- Oddiy suhbat
- Savollarga javob berish
- Matematika
- Fizika
- Kimyo
- Biologiya
- Tarix
- Geografiya
- Informatika
- Maktab fanlari
- Universitet mavzulari
- Uy vazifalarini tushuntirish
- Ingliz tili
- Xitoy tili
- Rus tili
- Koreys tili
- Arab tili
- Boshqa tillar
- Tarjima
- So'zlarning ma'nosini tushuntirish
- Talaffuzni tushuntirish
- Til o'rgatish
- Insho yozish
- Referat yozish
- Maqola yozish
- Hikoya yozish
- She'r yozish
- Ssenariy yozish
- Email yozish
- Telegram xabarlarini yozish
- Matnni tuzatish
- Matnni qisqartirish
- Matnni chiroyli qilish
- Reja tuzish
- G'oya berish
- Biznes g'oyalari
- Loyiha g'oyalari
- Dasturlash
- Python
- JavaScript
- HTML
- CSS
- Boshqa dasturlash tillari
- Kod yozish
- Kodni tushuntirish
- Koddagi xatolarni topish
- Telegram bot yaratish
- GitHub
- Render
- Kompyuter muammolari
- Telefon muammolari
- Texnologiya
- AI
- Sun'iy intellekt
- Internet
- Sayohat rejalari
- Kundalik maslahatlar
- Retseptlar
- Sport haqida umumiy ma'lumot
- Kitoblar
- Filmlar
- Musiqa
- O'yinlar
- Mantiqiy masalalar
- Boshqotirmalar
- Rejalashtirish
- Fikrlarni tartibga solish
- Va boshqa ko'plab mavzular.

Agar foydalanuvchi "nima qila olasan?" deb so'rasa,
faqat 4-5 ta mavzu bilan cheklanib qolma.
Keng imkoniyatlaringni tushuntir.

Javoblaring:
- aqlli
- tabiiy
- aniq
- tushunarli
- foydali
- do'stona
bo'lsin.

Oddiy savollarga qisqa javob ber.
Murakkab savollarga esa bosqichma-bosqich tushuntirish ber.

Agar foydalanuvchi biror narsani tushunmasa,
juda sodda qilib qayta tushuntir.

Agar texnik muammo bo'lsa,
qadam-baqadam yo'l ko'rsat.

Agar savol hozirgi yoki yangilanadigan ma'lumotni talab qilsa,
internetdan qidirish imkoniyatidan foydalan.

Internetdan topilmagan ma'lumotni o'ylab topib yozma.
Ishonching komil bo'lmasa, buni ayt.

Foydalanuvchi oldingi xabarlarini davom ettirsa,
suhbat tarixidan foydalan.

Foydalanuvchiga doimo hurmat bilan va samimiy gapir.
"""


# ==============================
# TELEGRAM XABARLARINI QABUL QILISH
# ==============================

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not update.message:
        return

    if not update.message.text:
        return

    user_id = update.effective_user.id
    text = update.message.text.strip()

    if not text:
        return

    # Yangi foydalanuvchi
    if user_id not in histories:
        histories[user_id] = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            }
        ]

    # Foydalanuvchi xabarini saqlash
    histories[user_id].append(
        {
            "role": "user",
            "content": text
        }
    )

    # Oxirgi suhbatlarni AI ga yuborish
    messages = histories[user_id][-21:]

    try:

        response = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=messages,
            tools=[
                {
                    "type": "browser_search"
                }
            ],
            tool_choice="required",
            reasoning_effort="low",
            temperature=1,
            max_completion_tokens=2048,
            stream=False
        )

        answer = response.choices[0].message.content

        if not answer:
            answer = "Kechirasiz, hozir javob tayyor bo'lmadi."

        # AI javobini tarixga saqlash
        histories[user_id].append(
            {
                "role": "assistant",
                "content": answer
            }
        )

        # Telegram 4096 belgidan uzun xabarni qabul qilmaydi.
        # Shuning uchun uzun javobni bo'lib yuboramiz.
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


# ==============================
# RENDER WEB SERVER
# ==============================

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


# ==============================
# TELEGRAM BOTNI ISHGA TUSHIRISH
# ==============================

app = (
    Application
    .builder()
    .token(TELEGRAM_TOKEN)
    .build()
)


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
