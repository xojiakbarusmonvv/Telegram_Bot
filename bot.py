from telegram import Update
from telegram.ext import Application, MessageHandler, ContextTypes, filters
from groq import Groq

TELEGRAM_TOKEN = "8899959377:AAH7pjr7P--f2ZU1U53XRx856B6n3aRvGiE"
GROQ_API_KEY = "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"

client = Groq(api_key=GROQ_API_KEY)

# Har bir odam uchun alohida suhbat
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

    # Oxirgi suhbatlarni yuboramiz
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


app = Application.builder().token(TELEGRAM_TOKEN).build()

app.add_handler(
    MessageHandler(filters.TEXT & ~filters.COMMAND, chat)
)

print("BOT ISHLAYAPTI!")
app.run_polling()