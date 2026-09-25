import os
import re
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from groq import Groq


# =========================
# SOZLAMALAR
# =========================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

MODEL = "openai/gpt-oss-20b"

if not TELEGRAM_TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN topilmadi!")

if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY topilmadi!")

client = Groq(api_key=GROQ_API_KEY)


# =========================
# GRAND MOBILE QOIDALARINI YUKLASH
# =========================

RULES_FILE = "grand_mobile_qoidalari.txt"

grand_mobile_rules = ""

if os.path.exists(RULES_FILE):
    with open(RULES_FILE, "r", encoding="utf-8") as f:
        grand_mobile_rules = f.read()

    print(
        f"GRAND MOBILE QOIDALARI YUKLANDI: "
        f"{len(grand_mobile_rules)} ta belgi"
    )
else:
    print(f"OGOHLANTIRISH: {RULES_FILE} topilmadi")


# =========================
# SUHBAT TARIXI
# =========================

chat_histories = {}

MAX_HISTORY = 12


# =========================
# GRAND MOBILE EKANINI ANIQLASH
# =========================

GRAND_MOBILE_KEYWORDS = [
    "grand mobile",
    "grandmobile",
    "gm",
    "rp",
    "ooc",
    "ic",
    "mg",
    "nonrp",
    "non-rp",
    "pg",
    "dm",
    "mass dm",
    "db",
    "sk",
    "mass sk",
    "rk",
    "tk",
    "warn",
    "demorgan",
    "demorgan",
    "mute",
    "ban",
    "gzs",
    "gz",
    "green zone",
    "yashil zona",
    "yashil zona",
    "lider",
    "leader",
    "admin",
    "adminka",
    "tashkilot",
    "fam",
    "oila",
    "server",
    "serverda",
    "sanksiya",
    "jazo",
    "qoidasi",
    "qoidalar",
    "band",
    "4.1",
    "4.2",
    "4.3",
    "4.4",
    "4.5",
    "4.6",
    "4.7",
    "4.8",
    "5.1",
    "5.2",
    "5.3",
    "5.4",
    "5.5",
    "5.6",
    "5.7",
    "5.8",
    "5.9",
]


def is_grand_mobile_question(text: str) -> bool:
    text_lower = text.lower()

    for keyword in GRAND_MOBILE_KEYWORDS:
        if keyword in text_lower:
            return True

    return False


# =========================
# QOIDADAN KERAKLI JOYNI TOPISH
# =========================

def find_relevant_rules(question: str, max_chars: int = 12000) -> str:

    if not grand_mobile_rules:
        return ""

    question_lower = question.lower()

    # Agar aniq band raqami so'ralgan bo'lsa
    numbers = re.findall(r"\b\d+\.\d+(?:\.\d+)?\b", question_lower)

    if numbers:
        selected = []

        for number in numbers:
            pattern = re.compile(
                rf"(?im)^\s*{re.escape(number)}\b.*?(?=^\s*\d+\.\d+(?:\.\d+)?\b|\Z)",
                re.S
            )

            matches = pattern.findall(grand_mobile_rules)

            for match in matches:
                selected.append(match.strip())

        if selected:
            result = "\n\n".join(selected)

            if len(result) > max_chars:
                result = result[:max_chars]

            return result

    # Muhim kalit so'zlar
    words = re.findall(r"[a-zA-Zа-яА-ЯёЁ0-9]+", question_lower)

    # Qoidalarni bo'laklarga ajratish
    chunks = re.split(
        r"(?=^\s*(?:\d+\.\d+(?:\.\d+)?|[IVXLC]+\.)\s*)",
        grand_mobile_rules,
        flags=re.MULTILINE
    )

    scored = []

    for chunk in chunks:
        chunk_lower = chunk.lower()

        if not chunk.strip():
            continue

        score = 0

        for word in words:
            if len(word) < 2:
                continue

            if word in chunk_lower:
                score += 1

        if score > 0:
            scored.append((score, chunk.strip()))

    scored.sort(key=lambda x: x[0], reverse=True)

    selected_chunks = []

    for score, chunk in scored[:8]:
        selected_chunks.append(chunk)

    if selected_chunks:
        result = "\n\n".join(selected_chunks)

        if len(result) > max_chars:
            result = result[:max_chars]

        return result

    # Hech narsa topilmasa, qoidalarning bosh qismini berish
    return grand_mobile_rules[:max_chars]


# =========================
# SISTEMA PROMPT
# =========================

GENERAL_SYSTEM_PROMPT = """
Sen universal aqlli Telegram yordamchisisan.

Foydalanuvchi bilan tabiiy, tushunarli va foydali suhbat qil.

Asosiy qoidalar:

1. Savolga to'g'ridan-to'g'ri javob ber.
2. Keraksiz uzun gaplar yozma.
3. Foydalanuvchi qaysi tilda yozsa, odatda o'sha tilda javob ber.
4. O'zbekcha savollarga sodda va tushunarli o'zbekcha javob ber.
5. Ruscha savollarga ruscha javob ber.
6. Inglizcha savollarga inglizcha javob ber.
7. Matematika, tarix, geografiya, texnologiya, dasturlash, tarjima, kundalik savollar va boshqa mavzularda yordam ber.
8. Agar aniq bilmasang, bilmasligingni ayt. Uydirma fakt yaratma.
9. Foydalanuvchining oldingi xabarlaridan suhbat kontekstini hisobga ol.
10. Javoblarni odamga o'xshab tabiiy yoz.
11. Juda rasmiy yoki robotga o'xshash bo'lma.
"""


GRAND_MOBILE_SYSTEM_PROMPT = """
Sen Grand Mobile bo'yicha yordamchi ham bo'la olasan.

Agar foydalanuvchi Grand Mobile qoidalari haqida so'rasa,
javobni berilgan GRAND MOBILE QOIDALARI asosida tayyorla.

MUHIM:

- Berilgan qoidalar asosiy manba hisoblanadi.
- Qoidalarda yo'q narsani aniq qoida sifatida o'ylab topma.
- Agar kerakli qoida berilgan ma'lumotlarda topilmasa,
  "bu ma'lumot men olgan qoidalar ichida topilmadi" deb ayt.
- Jazo turini o'zingcha o'zgartirma.
- WARN, BAN, MUTE, DEMORGAN kabi jazolarni aynan qoidalarda ko'rsatilganidek yoz.
- Agar band raqami mavjud bo'lsa, band raqamini ko'rsat.
- Javobni foydalanuvchi tushunadigan sodda tilda yoz.
- Foydalanuvchi faqat "RP nima?" kabi qisqa savol bersa,
  keraksiz butun qoidalar kitobini chiqarma.
- Faqat savolga tegishli qoidani tushuntir.
"""


# =========================
# /START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    name = user.first_name if user else "do'stim"

    await update.message.reply_text(
        f"Salom, {name}! 👋\n\n"
        "Men universal AI botman 🤖\n\n"
        "Menga istalgan savolingni berishing mumkin:\n"
        "• 🎮 Grand Mobile qoidalari\n"
        "• 📚 O'qish\n"
        "• 💻 Dasturlash\n"
        "• 🌍 Tarjima\n"
        "• 🧮 Matematika\n"
        "• ❓ Oddiy savollar\n"
        "• 💬 Oddiy suhbat\n\n"
        "Savolingni yozaver!"
    )


# =========================
# /RESET
# =========================

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):

    chat_id = update.effective_chat.id

    chat_histories[chat_id] = []

    await update.message.reply_text(
        "🧹 Suhbat tarixi tozalandi."
    )


# =========================
# XABARGA JAVOB
# =========================

async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    user_text = update.message.text

    if not user_text:
        return

    chat_id = update.effective_chat.id

    # Tarix mavjud bo'lmasa yaratamiz
    if chat_id not in chat_histories:
        chat_histories[chat_id] = []

    # =========================
    # GRAND MOBILE TEKSHIRUVI
    # =========================

    grand_question = is_grand_mobile_question(user_text)

    if grand_question:

        relevant_rules = find_relevant_rules(user_text)

        system_prompt = (
            GENERAL_SYSTEM_PROMPT
            + "\n\n"
            + GRAND_MOBILE_SYSTEM_PROMPT
            + "\n\n"
            + "GRAND MOBILE QOIDALARIDAN TOPILGAN MA'LUMOT:\n"
            + relevant_rules
        )

    else:

        system_prompt = GENERAL_SYSTEM_PROMPT

    # =========================
    # CHAT TARIXI
    # =========================

    messages = [
        {
            "role": "system",
            "content": system_prompt
        }
    ]

    # Oldingi suhbat
    messages.extend(chat_histories[chat_id][-MAX_HISTORY:])

    # Hozirgi savol
    messages.append(
        {
            "role": "user",
            "content": user_text
        }
    )

    # =========================
    # GROQ
    # =========================

    try:

        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=0.4,
            max_tokens=1200
        )

        answer = response.choices[0].message.content

        if not answer:
            answer = "Kechirasiz, hozir javob bera olmadim."

        # =========================
        # TARIXGA SAQLASH
        # =========================

        chat_histories[chat_id].append(
            {
                "role": "user",
                "content": user_text
            }
        )

        chat_histories[chat_id].append(
            {
                "role": "assistant",
                "content": answer
            }
        )

        # Juda kattalashib ketmasligi uchun
        if len(chat_histories[chat_id]) > MAX_HISTORY * 2:
            chat_histories[chat_id] = (
                chat_histories[chat_id][-MAX_HISTORY * 2:]
            )

        # Telegram 4096 belgidan katta xabarni bo'ladi
        if len(answer) <= 4000:

            await update.message.reply_text(answer)

        else:

            for i in range(0, len(answer), 4000):
                await update.message.reply_text(
                    answer[i:i + 4000]
                )

    except Exception as e:

        print("XATOLIK:", repr(e))

        await update.message.reply_text(
            "⚠️ Hozir javob berishda xatolik yuz berdi. "
            "Birozdan keyin yana urinib ko'r."
        )


# =========================
# BOTNI ISHGA TUSHIRISH
# =========================

def main():

    print("UNIVERSAL AI BOT ISHGA TUSHYAPTI...")

    if grand_mobile_rules:
        print("Grand Mobile qoidalari tayyor.")
    else:
        print("Grand Mobile qoidalari fayli topilmadi.")

    app = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .build()
    )

    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        CommandHandler("reset", reset)
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message
        )
    )

    print("UNIVERSAL AI BOT ISHLAYAPTI!")

    app.run_polling(
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
