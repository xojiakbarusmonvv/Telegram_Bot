import asyncio
import os
import random
import re
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from groq import Groq
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)


# ==================================================
# SOZLAMALAR
# ==================================================
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
GROQ_API_KEY = os.environ["GROQ_API_KEY"]
MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")

client = Groq(api_key=GROQ_API_KEY)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RULES_FILE = os.path.join(BASE_DIR, "grand_mobile_qoidalari.txt")


# ==================================================
# GRAND MOBILE QOIDALARINI O'QISH
# ==================================================
try:
    with open(RULES_FILE, "r", encoding="utf-8") as file:
        RULES_TEXT = file.read()

    print(
        f"GRAND MOBILE QOIDALARI YUKLANDI: "
        f"{len(RULES_TEXT)} ta belgi"
    )

except FileNotFoundError:
    RULES_TEXT = ""
    print(f"XATOLIK: {RULES_FILE} topilmadi")


# ==================================================
# XOTIRA
# ==================================================
histories = {}
HISTORY_LIMIT = 10


# ==================================================
# QO'SHIMCHA FUNKSIYALAR
# ==================================================
FUN_FACTS = [
    "Ahtapotning uchta yuragi bor.",
    "Asalarilar raqs orqali bir-biriga oziq-ovqat joyini ko'rsatadi.",
    "Bananning botanika bo'yicha rezavor meva hisoblanishini bilarmidingiz?",
    "Yorug'lik Quyoshdan Yerga taxminan 8 daqiqada yetib keladi.",
    "Inson miyasi uxlayotganda ham ma'lumotlarni qayta ishlaydi.",
]

JOKES = [
    "Dasturchi choy ichgani bordi. Choy tugadi, lekin u hali ham 'loading...' holatida.",
    "Kompyuter nega shifokorga bordi? Chunki virus yuqtirib olgan ekan.",
    "Adminning eng sevimli gapi: 'Qoidani o'qib chiqing'.",
]

DAILY_TASKS = [
    "Bugun yangi bir narsani o'rganing va uni do'stingizga tushuntiring.",
    "10 daqiqa telefondan uzoqlashing va rejalaringizni yozib chiqing.",
    "Bugun bir kishiga foydali yordam bering.",
    "Grand Mobile'da qoidalarni buzmasdan eng yaxshi RP vaziyatni yarating.",
]

THIS_OR_THAT = [
    "Choymi yoki kofe?",
    "Telefonmi yoki kompyuter?",
    "Grand Mobile'da boylikmi yoki kuchli RP?",
    "Kinomi yoki serial?",
]

QUIZES = [
    ("O'zbekiston poytaxti qaysi shahar?", "Toshkent"),
    ("Grand Mobile'da DM nimani anglatadi?", "DeathMatch"),
    ("Yerning tabiiy yo'ldoshi nima?", "Oy"),
    ("Python'da matn chiqarish funksiyasi nima?", "print"),
]


# ==================================================
# AI SYSTEM PROMPT
# ==================================================
SYSTEM_PROMPT = """
Sen Grand Mobile admin qoidalari bo'yicha yordamchi botsan.

ENG MUHIM QOIDA:
Grand Mobile haqidagi savollarga JAVOB FAQAT foydalanuvchiga berilgan
GRAND MOBILE QOIDALARI MATNIGA asoslanishi kerak.

Qoidalardan tashqaridan ma'lumot qo'shma.
Internetdan Grand Mobile qoidasi qidirmagin.
O'z umumiy bilimingdan yangi jazo, yangi band yoki yangi qoida o'ylab topma.

Agar kerakli ma'lumot qoidalar matnida bo'lmasa:
"Bu holat yuborilgan qoidalar matnida aniq ko'rsatilmagan."
deb ayt.

Agar foydalanuvchi band raqamini so'rasa, aynan shu bandga asoslan.

Agar vaziyatli savol bo'lsa:
1. Eng mos bandni ko'rsat.
2. Band raqamini yoz.
3. Qoidani sodda tushuntir.
4. Qoidada ko'rsatilgan jazoni yoz.
5. Agar ma'lumot yetarli bo'lmasa, buni ayt.
6. Yakuniy qarorni server ma'muriyati berishini eslatish mumkin.

JAVOB USLUBI:
- O'zbek tilida yoz.
- Oddiy va tushunarli gapir.
- Foydalanuvchi xato yozsa ham ma'nosini tushun.
- Keraksiz uzun javob yozma.
- Qoidada yo'q jazoni aytma.
- Qoidada yo'q bandni o'ylab topma.
- Bir nechta band mos kelsa, ularni ko'rsat.
- Agar foydalanuvchi faqat "RP nima?" desa, qoidalar matnidagi RP ta'rifiga
  asoslanib javob ber.
- Agar qoidalar matnida faqat qisqa ta'rif bo'lsa, uni keraksiz umumiy
  tushuntirish bilan almashtirma.

Grand Mobile'ga aloqasi bo'lmagan oddiy savollarga odatiy yordamchi sifatida
javob berishing mumkin.
"""


# ==================================================
# MATNNI NORMALIZATSIYA
# ==================================================
def normalize(text: str) -> str:
    text = text.lower()

    replacements = {
        "oʻ": "o'",
        "o’": "o'",
        "gʻ": "g'",
        "g’": "g'",
        "ё": "yo",
        "қ": "q",
        "ғ": "g'",
        "ҳ": "h",
        "ў": "o'",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    return re.sub(r"[^a-z0-9'ʼ\s.-]", " ", text)


# ==================================================
# QOIDA BANDLARINI AJRATISH
# ==================================================
def rule_chunks(text: str):
    """
    1.1, 1.2, 4.1, 5.2.1 kabi bandlarni alohida ajratadi.
    """

    pattern = r"(?m)(?=^\s*\d+(?:\.\d+)+\s+)"

    chunks = re.split(pattern, text)

    result = []

    for chunk in chunks:
        chunk = chunk.strip()

        if len(chunk) >= 20:
            result.append(chunk)

    return result


RULE_CHUNKS = rule_chunks(RULES_TEXT)


# ==================================================
# ANIQ BANDNI TOPISH
# ==================================================
def find_exact_band(band: str):
    """
    Masalan:
    4.1
    5.2
    1.1.1
    """

    pattern = (
        rf"(?ms)"
        rf"^\s*{re.escape(band)}\s+"
        rf".*?"
        rf"(?=^\s*\d+(?:\.\d+)+\s+|\Z)"
    )

    match = re.search(pattern, RULES_TEXT)

    if match:
        return match.group(0).strip()

    return None


# ==================================================
# MUHIM TERMINLAR
# ==================================================
RULE_TERMS = [
    "rp",
    "ic",
    "ooc",
    "mg",
    "nonrp",
    "pg",
    "dm",
    "mass dm",
    "db",
    "sk",
    "mass sk",
    "rk",
    "tk",
    "gz",
    "rmt",
    "report",
    "mute",
    "ban",
    "warn",
    "demorgan",
    "bizwar",
    "furgon",
    "opg",
    "family war",
    "lider",
    "otgul",
    "srok",
    "fraksiya",
    "biznes",
]


# ==================================================
# MOS QOIDALARNI TOPISH
# ==================================================
def find_relevant_rules(question: str, limit: int = 8) -> str:
    if not RULES_TEXT.strip():
        return "GRAND MOBILE QOIDALARI FAYLI TOPILMADI."

    question_normalized = normalize(question)

    # ----------------------------------------------
    # 1. BAND RAQAMI QIDIRISH
    # ----------------------------------------------
    requested_bands = re.findall(
        r"\b(\d+(?:\.\d+)+)\b",
        question_normalized,
    )

    exact_results = []

    for band in requested_bands:
        found = find_exact_band(band)

        if found:
            exact_results.append(found)

    if exact_results:
        return "\n\n".join(exact_results[:limit])

    # ----------------------------------------------
    # 2. TERMINLARNI QIDIRISH
    # ----------------------------------------------
    search_words = set(
        word
        for word in question_normalized.split()
        if len(word) >= 2
    )

    scored = []

    for chunk in RULE_CHUNKS:
        chunk_normalized = normalize(chunk)

        score = 0

        # Oddiy so'z mosligi
        for word in search_words:
            if word in chunk_normalized.split():
                score += 2

        # Maxsus terminlar
        for term in RULE_TERMS:
            if term in question_normalized and term in chunk_normalized:
                score += 8

        # To'liq iboralar
        if "qaysi band" in question_normalized:
            score += 1

        if score > 0:
            scored.append((score, chunk))

    scored.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    selected = [
        chunk
        for _, chunk in scored[:limit]
    ]

    if not selected:
        return (
            "Mos keladigan aniq qoida bandi topilmadi. "
            "Savolni vaziyat bilan aniqroq yozing."
        )

    return "\n\n".join(selected)


# ==================================================
# GRAND MOBILE SAVOLINI ANIQLASH
# ==================================================
def is_grand_mobile_question(text: str) -> bool:
    normalized = normalize(text)

    keywords = [
        "grand mobile",
        "qoid",
        "admin",
        "demorgan",
        "mute",
        "ban",
        "warn",
        "rp",
        "ic",
        "ooc",
        "mg",
        "pg",
        "dm",
        "db",
        "sk",
        "rk",
        "tk",
        "gz",
        "rmt",
        "bizwar",
        "furgon",
        "opg",
        "lider",
        "fraksiya",
        "report",
        "srok",
        "otgul",
        "biznes",
        "spawn",
        "chit",
        "script",
        "autoclicker",
        "macro",
    ]

    return any(
        keyword in normalized
        for keyword in keywords
    )


# ==================================================
# START
# ==================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Salom! Men Grand Mobile qoidalari bo'yicha yordamchi botman.\n\n"
        "Savolingizni yozing.\n"
        "Masalan:\n"
        "• RP nima?\n"
        "• DM nima?\n"
        "• GZda o'q uzsa qaysi band?\n"
        "• 4.1 band nima?"
    )


# ==================================================
# QOIDALAR
# ==================================================
async def rules_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Grand Mobile qoidalari bo'yicha savolingizni yozing.\n\n"
        "Masalan:\n"
        "4.1 band nima?\n"
        "DM uchun qanday jazo bor?\n"
        "GZda o'ldirish mumkinmi?"
    )


# ==================================================
# YORDAM
# ==================================================
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Buyruqlar:\n"
        "/start — botni boshlash\n"
        "/qoidalar — Grand Mobile qoidalari\n"
        "/yordam — yordam\n"
        "/fakt — qiziqarli fakt\n"
        "/hazil — hazil\n"
        "/topshiriq — topshiriq\n"
        "/tanlov — tanlov\n"
        "/viktorina — viktorina\n\n"
        "Oddiy savolingizni ham yozishingiz mumkin."
    )


# ==================================================
# FAKT
# ==================================================
async def fact_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Qiziqarli fakt: " + random.choice(FUN_FACTS)
    )


# ==================================================
# HAZIL
# ==================================================
async def joke_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        random.choice(JOKES)
    )


# ==================================================
# TOPSHIRIQ
# ==================================================
async def task_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Bugungi topshiriq: " + random.choice(DAILY_TASKS)
    )


# ==================================================
# TANLOV
# ==================================================
async def choice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Tanlov: " + random.choice(THIS_OR_THAT)
    )


# ==================================================
# VIKTORINA
# ==================================================
async def quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    question, answer = random.choice(QUIZES)

    context.user_data["quiz_answer"] = answer.lower()

    await update.message.reply_text(
        "Mini-viktorina:\n\n"
        + question
        + "\n\nJavobingizni yozing."
    )


# ==================================================
# CHAT
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

    # ----------------------------------------------
    # VIKTORINA JAVOBI
    # ----------------------------------------------
    quiz_answer = context.user_data.pop(
        "quiz_answer",
        None,
    )

    if quiz_answer:
        if quiz_answer in text.lower():
            await update.message.reply_text(
                "To'g'ri javob! Barakalla."
            )
        else:
            await update.message.reply_text(
                f"Bu safar xato. To'g'ri javob: {quiz_answer}"
            )

        return

    # ----------------------------------------------
    # GRAND MOBILE SAVOLI
    # ----------------------------------------------
    grand_mobile = is_grand_mobile_question(text)

    # ----------------------------------------------
    # QOIDALARNI TOPISH
    # ----------------------------------------------
    relevant = find_relevant_rules(text)

    # ----------------------------------------------
    # TARIX
    # ----------------------------------------------
    if user_id not in histories:
        histories[user_id] = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            }
        ]

    histories[user_id].append(
        {
            "role": "user",
            "content": text,
        }
    )

    histories[user_id] = (
        [histories[user_id][0]]
        + histories[user_id][1:][-HISTORY_LIMIT:]
    )

    # ----------------------------------------------
    # GRAND MOBILE UCHUN QAT'IY PROMPT
    # ----------------------------------------------
    if grand_mobile:

        messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "system",
                "content": (
                    "MUHIM: Quyidagi matn Grand Mobile qoidalarining "
                    "shu savolga tegishli qismidir.\n\n"
                    "FAQAT SHU MATNGA ASOSLAN.\n"
                    "Matnda yo'q ma'lumotni qo'shma.\n"
                    "Matnda yo'q jazo yoki bandni o'ylab topma.\n\n"
                    "QOIDALAR:\n"
                    + relevant
                ),
            },
        ]

        # Grand Mobile savolida faqat so'nggi suhbat kontekstini qo'shamiz.
        messages += histories[user_id][1:][-6:]

    else:

        # Oddiy savol
        messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            }
        ]

        messages += histories[user_id][1:]

    try:

        response = await asyncio.to_thread(
            client.chat.completions.create,
            model=MODEL,
            messages=messages,
            tool_choice="none",
            reasoning_effort="low",
            temperature=0.2,
            max_completion_tokens=800,
            stream=False,
        )

        answer = (
            response.choices[0].message.content
            or "Kechirasiz, javob tayyor bo'lmadi."
        )

        histories[user_id].append(
            {
                "role": "assistant",
                "content": answer,
            }
        )

        # Telegram 4096 belgidan oshgan xabarni qabul qilmaydi.
        for i in range(0, len(answer), 4000):
            await update.message.reply_text(
                answer[i:i + 4000]
            )

    except Exception as error:

        print(
            "XATOLIK:",
            repr(error),
        )

        await update.message.reply_text(
            "Javob berishda texnik xatolik yuz berdi. "
            "Keyinroq yana urinib ko'ring."
        )


# ==================================================
# RENDER HEALTH CHECK
# ==================================================
class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):

        self.send_response(200)
        self.end_headers()

        self.wfile.write(
            b"Grand Mobile admin bot ishlayapti!"
        )

    def log_message(self, format, *args):
        pass


def start_web_server():

    port = int(
        os.environ.get(
            "PORT",
            10000,
        )
    )

    HTTPServer(
        ("0.0.0.0", port),
        HealthHandler,
    ).serve_forever()


# ==================================================
# WEB SERVER
# ==================================================
threading.Thread(
    target=start_web_server,
    daemon=True,
).start()


# ==================================================
# TELEGRAM BOT
# ==================================================
app = (
    Application
    .builder()
    .token(TELEGRAM_TOKEN)
    .build()
)

app.add_handler(
    CommandHandler(
        "start",
        start,
    )
)

app.add_handler(
    CommandHandler(
        "qoidalar",
        rules_command,
    )
)

app.add_handler(
    CommandHandler(
        "yordam",
        help_command,
    )
)

app.add_handler(
    CommandHandler(
        "fakt",
        fact_command,
    )
)

app.add_handler(
    CommandHandler(
        "hazil",
        joke_command,
    )
)

app.add_handler(
    CommandHandler(
        "topshiriq",
        task_command,
    )
)

app.add_handler(
    CommandHandler(
        "tanlov",
        choice_command,
    )
)

app.add_handler(
    CommandHandler(
        "viktorina",
        quiz_command,
    )
)

app.add_handler(
    MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        chat,
    )
)


# ==================================================
# START
# ==================================================
print("GRAND MOBILE ADMIN BOT ISHLAYAPTI!")

app.run_polling(
    drop_pending_updates=True
)
