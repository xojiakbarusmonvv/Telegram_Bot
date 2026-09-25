import os
import re
import io
import threading

from flask import Flask
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from groq import Groq
from PIL import Image, ImageDraw, ImageFont


# =========================================================
# SOZLAMALAR
# =========================================================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

MODEL = "openai/gpt-oss-20b"

if not TELEGRAM_TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN topilmadi!")

if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY topilmadi!")

client = Groq(api_key=GROQ_API_KEY)


# =========================================================
# RENDER PORT
# =========================================================

web_app = Flask(__name__)


@web_app.route("/")
def home():
    return "Telegram bot ishlayapti!"


def run_web():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port)


threading.Thread(target=run_web, daemon=True).start()


# =========================================================
# GRAND MOBILE QOIDALARI
# =========================================================

RULES_FILE = "grand_mobile_qoidalari.txt"

grand_mobile_rules = ""

try:
    with open(RULES_FILE, "r", encoding="utf-8") as f:
        grand_mobile_rules = f.read()

    print(
        f"GRAND MOBILE QOIDALARI YUKLANDI: "
        f"{len(grand_mobile_rules)} ta belgi"
    )

except Exception as e:
    print("QOIDALAR FAYLI XATOSI:", e)
    grand_mobile_rules = ""


# =========================================================
# XOTIRA
# =========================================================

chat_histories = {}

# Har bir foydalanuvchining oxirgi rasmi
user_images = {}


# =========================================================
# GRAND MOBILE ANIQLASH
# =========================================================

GRAND_MOBILE_KEYWORDS = [
    "grand mobile",
    "grandmobile",
    "rp",
    "mg",
    "dm",
    "pg",
    "db",
    "sk",
    "rk",
    "tk",
    "nonrp",
    "warn",
    "demorgan",
    "mute",
    "ban",
    "gz",
    "green zone",
    "yashil zona",
    "qoid",
    "qoida",
    "admin",
    "arz",
    "shikoyat",
    "complaint",
    "o'ldirish",
    "öldirish",
    "otish",
    "tarang",
]


def is_grand_mobile_question(text):
    text_lower = text.lower()

    for keyword in GRAND_MOBILE_KEYWORDS:
        if keyword in text_lower:
            return True

    return False


# =========================================================
# RELEVANT QOIDANI TOPISH
# =========================================================

def find_relevant_rules(question, max_chars=14000):
    if not grand_mobile_rules:
        return ""

    words = re.findall(
        r"[a-zA-Zа-яА-ЯёЁ0-9']+",
        question.lower()
    )

    lines = grand_mobile_rules.splitlines()

    scored = []

    for line in lines:
        line_lower = line.lower()

        score = 0

        for word in words:
            if len(word) >= 2 and word in line_lower:
                score += 1

        if score > 0:
            scored.append((score, line))

    scored.sort(
        key=lambda x: x[0],
        reverse=True
    )

    selected = []

    total = 0

    for score, line in scored:
        if total + len(line) > max_chars:
            break

        selected.append(line)
        total += len(line) + 1

    if selected:
        return "\n".join(selected)

    # Agar mos qator topilmasa, qoidalarning boshidan beramiz
    return grand_mobile_rules[:max_chars]


# =========================================================
# SYSTEM PROMPT
# =========================================================

GENERAL_SYSTEM_PROMPT = """
Sen Telegramdagi universal AI yordamchisan.

Foydalanuvchi qaysi tilda yozsa, shu tilda javob ber.

Asosiy qoidalar:

1. O'zbekcha savolga o'zbekcha javob ber.
2. Ruscha savolga ruscha javob ber.
3. Inglizcha savolga inglizcha javob ber.
4. Oddiy suhbat qila ol.
5. Matematika masalalarini yech.
6. Tarjima qil.
7. Tarix, geografiya, texnologiya, dasturlash va boshqa mavzularda yordam ber.
8. Javoblarni tushunarli va amaliy qil.
9. Agar aniq bilmasang, uydirma ma'lumot bermagin.
10. Foydalanuvchi qisqa savol bersa, keraksiz uzun javob bermagin.
"""


GRAND_MOBILE_SYSTEM_PROMPT = """
Sen Grand Mobile server qoidalari bo'yicha yordamchisan.

Foydalanuvchi savoliga faqat berilgan Grand Mobile qoidalariga
asoslanib javob ber.

Javobda quyidagilarni aniq ko'rsatishga harakat qil:

- Qaysi qoida buzilgan
- Qoida raqami, agar mavjud bo'lsa
- Jazosi
- Qisqa tushuntirish

Agar qoidalarda aniq javob bo'lmasa:

"Bu holat berilgan qoidalar faylida aniq ko'rsatilmagan."

deb ayt.

Qoidani o'zingcha o'ylab topma.

Agar foydalanuvchi RP, MG, DM, PG, DB, SK, RK, TK,
NonRP kabi terminlardan foydalansa, ularning qoidalar faylidagi
ma'nosidan foydalan.
"""


# =========================================================
# START
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = """
🤖 Salom!

Men Universal AI Telegram botman.

Men bilan:

💬 Oddiy suhbat
🧠 AI savollar
📚 Grand Mobile qoidalari
➗ Matematika
🌍 Tarjima
💻 Dasturlash
📖 Umumiy bilim
🖼 Rasmga matn qo‘shish

kabi ishlarni qilishing mumkin.

Grand Mobile bo‘yicha:
👉 RP nima?
👉 DM jazosi qancha?
👉 GZ qoidasi qanday?

deb so‘rashing mumkin.

Rasm yuborsang, unga nima yozish kerakligini ayt.
Masalan:

"pastiga Xojiakbar deb yoz"
"o'rtasiga Salom deb yoz"
"ustiga TEST deb yoz"
"""

    await update.message.reply_text(text)


# =========================================================
# RESET
# =========================================================

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    chat_histories[user_id] = []

    await update.message.reply_text(
        "🧹 Suhbat xotirasi tozalandi."
    )


# =========================================================
# FONT
# =========================================================

def get_font(size=50):

    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    ]

    for path in font_paths:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)

    return ImageFont.load_default()


# =========================================================
# RASMGA MATN YOZISH
# =========================================================

def add_text_to_image(image_bytes, text, position="bottom"):

    image = Image.open(
        io.BytesIO(image_bytes)
    ).convert("RGB")

    draw = ImageDraw.Draw(image)

    # Matn juda uzun bo'lsa kichraytiramiz
    font_size = 60

    if len(text) > 25:
        font_size = 45

    if len(text) > 40:
        font_size = 35

    font = get_font(font_size)

    bbox = draw.textbbox(
        (0, 0),
        text,
        font=font,
        stroke_width=2
    )

    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    image_width, image_height = image.size

    x = (image_width - text_width) // 2

    if position == "top":
        y = 30

    elif position == "middle":
        y = (image_height - text_height) // 2

    else:
        y = image_height - text_height - 40

    # Qora kontur + oq yozuv
    draw.text(
        (x, y),
        text,
        font=font,
        fill="white",
        stroke_width=4,
        stroke_fill="black"
    )

    output = io.BytesIO()

    image.save(
        output,
        format="JPEG",
        quality=95
    )

    output.seek(0)

    return output


# =========================================================
# RASM BUYRUG'INI ANIQLASH
# =========================================================

def extract_image_text(command):

    command = command.strip()

    patterns = [

        (
            r"pastiga\s+(.+?)\s+deb\s+yoz$",
            "bottom"
        ),

        (
            r"pastiga\s+(.+?)\s+yoz$",
            "bottom"
        ),

        (
            r"tagiga\s+(.+?)\s+deb\s+yoz$",
            "bottom"
        ),

        (
            r"tagiga\s+(.+?)\s+yoz$",
            "bottom"
        ),

        (
            r"o['’`]?rtasiga\s+(.+?)\s+deb\s+yoz$",
            "middle"
        ),

        (
            r"o['’`]?rtasiga\s+(.+?)\s+yoz$",
            "middle"
        ),

        (
            r"markaziga\s+(.+?)\s+deb\s+yoz$",
            "middle"
        ),

        (
            r"ustiga\s+(.+?)\s+deb\s+yoz$",
            "top"
        ),

        (
            r"ustiga\s+(.+?)\s+yoz$",
            "top"
        ),

        (
            r"(.+?)\s+deb\s+yoz$",
            "bottom"
        ),
    ]

    for pattern, position in patterns:

        match = re.search(
            pattern,
            command,
            re.IGNORECASE
        )

        if match:

            text = match.group(1).strip()

            if text:
                return text, position

    return None, None


# =========================================================
# RASM QABUL QILISH
# =========================================================

async def handle_photo(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user_id = update.effective_user.id

    photo = update.message.photo[-1]

    telegram_file = await context.bot.get_file(
        photo.file_id
    )

    image_bytes = await telegram_file.download_as_bytearray()

    user_images[user_id] = bytes(image_bytes)

    await update.message.reply_text(
        "🖼 Rasm qabul qilindi.\n\n"
        "Endi rasmga nima qilishni yoz.\n\n"
        "Masalan:\n"
        "👉 pastiga Xojiakbar deb yoz\n"
        "👉 o'rtasiga SALOM deb yoz\n"
        "👉 ustiga TEST deb yoz"
    )


# =========================================================
# MATN XABAR
# =========================================================

async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message or not update.message.text:
        return

    user_id = update.effective_user.id
    text = update.message.text.strip()

    # -----------------------------------------------------
    # RASM BUYRUG'I
    # -----------------------------------------------------

    if user_id in user_images:

        image_text, position = extract_image_text(text)

        if image_text:

            try:

                result = add_text_to_image(
                    user_images[user_id],
                    image_text,
                    position
                )

                await update.message.reply_photo(
                    photo=result,
                    caption="✅ Tayyor!"
                )

                del user_images[user_id]

                return

            except Exception as e:

                print("RASM XATOSI:", e)

                await update.message.reply_text(
                    "❌ Rasmni o'zgartirishda xatolik bo'ldi."
                )

                return

    # -----------------------------------------------------
    # CHAT TARIXI
    # -----------------------------------------------------

    if user_id not in chat_histories:
        chat_histories[user_id] = []

    history = chat_histories[user_id]

    # -----------------------------------------------------
    # GRAND MOBILE
    # -----------------------------------------------------

    if is_grand_mobile_question(text):

        relevant_rules = find_relevant_rules(text)

        system_prompt = (
            GRAND_MOBILE_SYSTEM_PROMPT
            + "\n\nGRAND MOBILE QOIDALARI:\n"
            + relevant_rules
        )

    else:

        system_prompt = GENERAL_SYSTEM_PROMPT

    history.append(
        {
            "role": "user",
            "content": text
        }
    )

    # Oxirgi 10 ta xabarni saqlaymiz
    history = history[-10:]

    messages = [
        {
            "role": "system",
            "content": system_prompt
        }
    ]

    messages.extend(history)

    # -----------------------------------------------------
    # GROQ
    # -----------------------------------------------------

    try:

        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=0.4,
            max_tokens=1200
        )

        answer = response.choices[0].message.content

        if not answer:
            answer = "Javob olishda xatolik yuz berdi."

        history.append(
            {
                "role": "assistant",
                "content": answer
            }
        )

        chat_histories[user_id] = history[-10:]

        await update.message.reply_text(
            answer
        )

    except Exception as e:

        print("GROQ XATOSI:", e)

        await update.message.reply_text(
            "❌ AI bilan bog‘lanishda xatolik yuz berdi."
        )


# =========================================================
# ERROR
# =========================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE
):

    print(
        "BOT ERROR:",
        context.error
    )


# =========================================================
# BOT
# =========================================================

def main():

    print(
        "UNIVERSAL AI + RASM BOT ISHGA TUSHYAPTI..."
    )

    application = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .build()
    )

    application.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    application.add_handler(
        CommandHandler(
            "reset",
            reset
        )
    )

    application.add_handler(
        MessageHandler(
            filters.PHOTO,
            handle_photo
        )
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message
        )
    )

    application.add_error_handler(
        error_handler
    )

    print(
        "UNIVERSAL AI + RASM BOT ISHLAYAPTI!"
    )

    application.run_polling(
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
