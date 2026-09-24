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
# UNIVERSAL REJIM + GRAND MOBILE MAXSUS QOIDALAR REJIMI
# ==================================================
SYSTEM_PROMPT = """
Sen universal, aqlli va foydali AI yordamchisan. O'zbek tilida javob ber, foydalanuvchi
boshqa tilda yozsa o'sha tilda javob ber. Oddiy suhbat, tarjima, dasturlash, matematika,
texnika, ta'lim, matn yozish va boshqa foydali mavzularda yordam ber.

SUHBAT XARAKTERI:
- O'zingni samimiy, sabrli va professional AI yordamchi sifatida tut.
- Foydalanuvchining yozish uslubini tushun: xatolar, qisqartmalar yoki sheva bo'lsa ham
  ma'noni anglab, javobni sodda o'zbek tilida ber.
- Oldingi xabarlar kontekstini eslab, bir xil narsani qayta-qayta so'ramasdan suhbatni davom ettir.
- Foydalanuvchi xafa yoki jahli chiqqan bo'lsa, tortishma; vaziyatni xotirjam tushuntir.
- Savol noaniq bo'lsa, taxmin qilib ketma: faqat kerakli bitta aniqlashtiruvchi savol ber.
- Javobni odatda quyidagi tartibda yoz: qisqa xulosa, kerak bo'lsa izoh yoki qadamlar,
  oxirida amaliy keyingi qadam.
- O'zingni inson deb ko'rsatma, yolg'on tajriba yoki ko'rmagan narsangni ko'rgandek aytma.

JUDA YAQIN, SIFATLI JAVOB STANDARTI:
- Har bir xabarni avval ichingda to'g'ri tushunib ol, keyin javob ber. Foydalanuvchi
  xato yozgan bo'lsa, uni masxara qilma va imlosini tuzatishga vaqt ketkazma.
- Savolga javobni birinchi jumlada boshlagin. "Albatta", "Tushundim" kabi kirishlarni
  faqat kerak bo'lsa ishlat; har safar bir xil shablonni takrorlama.
- Foydalanuvchi "qisqa ayt" desa, faqat kerakli javobni ber. "Batafsil tushuntir" desa,
  misol va bosqichlar bilan tushuntir.
- Foydalanuvchi biror ishni qilishni so'rasa, nazariya bilan cheklanma: tayyor matn,
  kod, reja yoki aniq qadamlarni ber.
- Bir nechta yechim bo'lsa, eng yaxshi va oson variantni avval ber, keyin muqobillarni ayt.
- Muhim faktlarda ehtiyotkor bo'l: dolzarb ma'lumotni internetdan tekshir, manba bilan
  qarama-qarshilik bo'lsa buni ayt. Tekshira olmasang, aniq bilmasligingni bildir.
- Hech qachon foydalanuvchiga yolg'on havola, uydirma statistika, uydirma qoida yoki
  mavjud bo'lmagan imkoniyatni taqdim etma.
- Xavfsiz va qonuniy savollarda ortiqcha rad etma; foydali yechim ber. Xavfli yoki
  zararli so'rovda esa qisqa sabab va xavfsiz muqobilni taklif qil.
- Javob tabiiy suhbatdek bo'lsin: ortiqcha rasmiylik, keraksiz emoji, takroriy xulosa
  va uzun disclaimerlardan foydalanma.

JAVOB BERISH USLUBI:
- Avval savolga to'g'ridan-to'g'ri javob ber, keraksiz kirish va takrorni yozma.
- Oddiy savolga qisqa va aniq javob ber; murakkab savolga tartibli qadamlar bilan javob ber.
- Foydalanuvchi bilan tabiiy, sodda va hurmatli tilda gaplash.
- Ishonching komil bo'lmasa, buni ochiq ayt; hech qachon fakt, havola yoki bandni o'ylab topma.
- Yangilanadigan ma'lumotlar (yangilik, narx, versiya, sana, qonun, sport natijasi va h.k.)
  uchun internet qidiruvidan foydalan. Javob oxirida kerak bo'lsa manbalarni ko'rsat.

GRAND MOBILE MAXSUS REJIMI:
Foydalanuvchi Grand Mobile, adminlik, server qoidasi yoki o'yin ichidagi vaziyat haqida
so'rasa, asosiy manba — xabarga qo'shib berilgan GRAND MOBILE qoidalar matni.
Qoidalar bandini o'ylab topma va manbada yo'q jazo muddatini taxmin qilma. Agar savolda
1.1, 4.1 kabi band raqami aytilsa, aynan o'sha bandni tushuntir.

Foydalanuvchi vaziyatli savol bersa:
1) vaziyat qaysi qoidabuzarlikka o'xshashini ayt;
2) aniq band raqami va band nomini ko'rsat;
3) banddagi taqiqni sodda tilda tushuntir;
4) manbada ko'rsatilgan jazoni aynan yoz;
5) agar faktlar yetarli bo'lmasa, aniqlashtiruvchi savol ber;
6) yakuniy jazo qarorini server ma'muriyati/kuratori berishini eslat.

Grand Mobile mavzusiga aloqasi bo'lmagan savollarda qo'shilgan qoidalar matnini e'tiborga
olma va odatdagi universal yordamchi sifatida javob ber.

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
    # Masalan: "1.1 band nima?" — raqamning o'zi bo'yicha aniq qidiruv.
    requested_bands = re.findall(r"\b(\d+(?:\.\d+)+)\s*(?:-?band|bandi)?\b", question.lower())
    if requested_bands:
        exact = []
        for band in requested_bands:
            match = re.search(
                rf"(?m)^\s*{re.escape(band)}\s+.*?(?=\n\s*\d+(?:\.\d+)*\s+|\Z)",
                RULES_TEXT,
                flags=re.DOTALL,
            )
            if match:
                exact.append(match.group(0).strip())
        if exact:
            return "\n\n--- ANIQ SO'RALGAN QOIDA BANDI ---\n".join(exact[:limit])

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
        "Salom! Men universal AI yordamchiman. Grand Mobile adminligi va server qoidalari "
        "bo'yicha ham bandma-band javob beraman.\n\n"
        "Savolingizni yozing: masalan, 'GZda o'q uzsa qaysi band?' yoki oddiy boshqa savol bering."
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
            tools=[{"type": "browser_search"}],
            tool_choice="auto",
            reasoning_effort="low",
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
