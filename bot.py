import os
import re
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from groq import Groq
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters


# ==================================================
# SOZLAMALAR
# ==================================================
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
GROQ_API_KEY = os.environ["GROQ_API_KEY"]
MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")

client = Groq(api_key=GROQ_API_KEY)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RULES_FILE = os.path.join(BASE_DIR, "grand_mobile_qoidalari.txt")

try:
    with open(RULES_FILE, "r", encoding="utf-8") as file:
        RULES_TEXT = file.read()
except FileNotFoundError:
    RULES_TEXT = ""
    print(f"OGOHLANTIRISH: {RULES_FILE} topilmadi")

histories = {}


# ==================================================
# FAQAT GRAND MOBILE ADMINLIK REJIMI
# ==================================================
SYSTEM_PROMPT = """
Sen faqat GRAND MOBILE o'yini bo'yicha adminlik va server qoidalari maslahatchisisan.
Boshqa o'yinlar, umumiy AI yordamchisi, dasturlash, matematika, siyosat, tibbiyot,
retsept, tarjima yoki boshqa mavzulardagi savollarga javob bermaysan. Muloyim tarzda:
'Men faqat Grand Mobile adminligi va server qoidalari bo'yicha javob beraman' deb ayt.

Asosiy manba — foydalanuvchi xabariga qo'shib berilgan GRAND MOBILE qoidalar matni.
Javobni faqat shu manbaga tayangan holda ber. Bandni o'ylab topma va jazo muddatini
manbada yo'q bo'lsa taxmin qilma.

Foydalanuvchi vaziyatli savol bersa:
1) vaziyat qaysi qoidabuzarlikka o'xshashini ayt;
2) aniq band raqami va band nomini ko'rsat;
3) banddagi taqiqni sodda tilda tushuntir;
4) manbada ko'rsatilgan jazoni aynan yoz;
5) agar faktlar yetarli bo'lmasa, aniqlashtiruvchi savol ber;
6) yakuniy jazo qarorini server ma'muriyati/kuratori berishini eslat.

Agar bir nechta band mos kelsa, eng mos bandni birinchi ko'rsatib, qolgan ehtimoliy
bandlarni ham sanab o't. IC/OOC, RP, GZ, DM, DB, SK, RK, MG, PG kabi atamalarni
kerak bo'lsa qisqacha izohla.

Javoblar o'zbek tilida, qisqa, aniq va hurmatli bo'lsin. Ma'muriyat nomidan yakuniy
hukm chiqarmaysan; faqat qoidani tushuntirasan.
"""


def normalize(text: str) -> str:
    text = text.lower().replace("oʻ", "o'").replace("gʻ", "g'")
    return re.sub(r"[^a-z0-9'ʼ\s-]", " ", text)


def rule_chunks(text: str):
    chunks = re.split(r"(?=\n\s*(?:\d+(?:\.\d+)*|[IVX]+\.)\s+)", text)
    return [chunk.strip() for chunk in chunks if len(chunk.strip()) > 40]


RULE_CHUNKS = rule_chunks(RULES_TEXT)


def find_relevant_rules(question: str, limit: int = 8) -> str:
    """Savolga eng yaqin bandlarni keyword qidiruvi bilan topadi."""
    normalized_question = normalize(question)
    words = {word for word in normalized_question.split() if len(word) >= 3}
    scored = []

    for chunk in RULE_CHUNKS:
        normalized_chunk = normalize(chunk)
        score = sum(1 for word in words if word in normalized_chunk)
        for term in ("dm", "gz", "rmt", "rp", "mg", "pg", "db", "sk", "rk", "mute", "ban", "report", "admin"):
            if re.search(rf"\b{re.escape(term)}\b", normalized_question) and re.search(rf"\b{re.escape(term)}\b", normalized_chunk):
                score += 4
        if score:
            scored.append((score, chunk))

    scored.sort(key=lambda item: item[0], reverse=True)
    selected = [chunk for _, chunk in scored[:limit]]
    if not selected:
        return "Mos band topilmadi. Savolni Grand Mobile vaziyati va joyi bilan aniqroq yozing."
    return "\n\n--- MOS QOIDA BANDI ---\n".join(selected)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Salom! Men faqat Grand Mobile adminligi va server qoidalari bo'yicha botman.\n\n"
        "Vaziyatni yozing: masalan, 'GZda o'q uzsa qaysi band?' yoki /qoidalar buyrug'idan foydalaning."
    )


async def rules_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Grand Mobile qoidalari bo'yicha savolingizni vaziyat bilan yozing.\n"
        "Masalan: 'O'yinchi reportni flood qilsa qaysi band va jazo?'"
    )


async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user_id = update.effective_user.id
    text = update.message.text.strip()
    if not text:
        return

    relevant = find_relevant_rules(text)
    if user_id not in histories:
        histories[user_id] = [{"role": "system", "content": SYSTEM_PROMPT}]

    histories[user_id].append({"role": "user", "content": text})
    messages = [histories[user_id][0], {
        "role": "system",
        "content": "Savolga tegishli qoidalar matni:\n" + relevant,
    }] + histories[user_id][-10:]

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=0.2,
            max_completion_tokens=1200,
            stream=False,
        )
        answer = response.choices[0].message.content or "Kechirasiz, javob tayyor bo'lmadi."
        histories[user_id].append({"role": "assistant", "content": answer})

        for i in range(0, len(answer), 4000):
            await update.message.reply_text(answer[i:i + 4000])
    except Exception as error:
        print("XATOLIK:", repr(error))
        await update.message.reply_text(
            "Javob berishda texnik xatolik yuz berdi. Keyinroq yana urinib ko'ring."
        )


# ==================================================
# RENDER HEALTH CHECK
# ==================================================
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Grand Mobile admin bot ishlayapti!")

    def log_message(self, format, *args):
        pass


def start_web_server():
    port = int(os.environ.get("PORT", 10000))
    HTTPServer(("0.0.0.0", port), HealthHandler).serve_forever()


threading.Thread(target=start_web_server, daemon=True).start()

app = Application.builder().token(TELEGRAM_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("qoidalar", rules_command))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))

print("GRAND MOBILE ADMIN BOT ISHLAYAPTI!")
app.run_polling()
