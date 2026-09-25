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

# Foydalanuvchining oxirgi rasmi
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

    return grand_mobile_rules[:max_chars]


# =========================================================
# SYSTEM PROMPT
# =========================================================

GENERAL_SYSTEM_PROMPT = """
Sen Telegramdagi universal AI yordamchisan.

Foydalanuvchi qaysi tilda yozsa, shu tilda javob ber.

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

Javobda:

- Qaysi qoida buzilgan
- Qoida raqami
- Jazosi
- Qisqa tushuntirish

ni ko'rsat.

Agar qoidalarda aniq javob bo'lmasa:

"Bu holat berilgan qoidalar faylida aniq ko'rsatilmagan."

deb ayt.

Qoidani o'zingcha o'ylab topma.
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
🖼 Rasm tahrirlash

mumkin.

Rasmga masalan:

👉 pastiga Xojiakbar deb yoz
👉 o'rtasiga SALOM deb yoz
👉 ustiga TEST deb yoz

Yoki mavjud ismni almashtirish:

👉 Pasidagi Xumo_Xusniddovni Xojiakbar_Usmonvv qilib tahrirla
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

            return ImageFont.truetype(
                path,
                size
            )

    return ImageFont.load_default()


# =========================================================
# ODDIY RASMGA MATN YOZISH
# =========================================================

def add_text_to_image(
    image_bytes,
    text,
    position="bottom"
):

    image = Image.open(
        io.BytesIO(image_bytes)
    ).convert("RGB")

    draw = ImageDraw.Draw(image)

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
# YANGI:
# "ESKI ISMNI YANGI ISMGA ALMASHTIR"
# BUYRUG'INI ANIQLASH
# =========================================================

def extract_replace_command(command):

    command = command.strip()

    patterns = [

        # Pasidagi Xumo_Xusniddovni Xojiakbar_Usmonvv qilib tahrirla
        r"pasidagi\s+(.+?)\s+(?:ni\s+)?(.+?)\s+qilib\s+tahrirla$",

        # Pastidagi Xumo_Xusniddovni Xojiakbar_Usmonvv qilib o'zgartir
        r"pastidagi\s+(.+?)\s+(?:ni\s+)?(.+?)\s+qilib\s+(?:o['’`]?zgartir|almashtir)$",

        # Pasidagi Xumo_Xusniddovni Xojiakbar_Usmonvv ga almashtir
        r"pasidagi\s+(.+?)\s+(.+?)\s+ga\s+almashtir$",

        # Pastidagi Xumo_Xusniddovni Xojiakbar_Usmonvv qilib yoz
        r"pastidagi\s+(.+?)\s+(.+?)\s+qilib\s+yoz$",

        # Xumo_Xusniddovni Xojiakbar_Usmonvv ga almashtir
        r"(.+?)\s+(.+?)\s+ga\s+almashtir$",

    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            command,
            re.IGNORECASE
        )

        if match:

            old_text = match.group(1).strip()
            new_text = match.group(2).strip()

            if old_text and new_text:

                return (
                    old_text,
                    new_text,
                    "bottom"
                )

    return None, None, None


# =========================================================
# ODDIY RASM BUYRUG'INI ANIQLASH
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
            r"pasiga\s+(.+?)\s+deb\s+yoz$",
            "bottom"
        ),

        (
            r"pasiga\s+(.+?)\s+yoz$",
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
# YANGI:
# ESKI YOZUV JOYIGA YANGI YOZUV QO'YISH
#
# Hozircha eski yozuvni avtomatik OCR bilan topmaydi.
# Foydalanuvchi "pasidagi" desa pastki qismdan foydalanadi.
# =========================================================

def replace_bottom_text(
    image_bytes,
    old_text,
    new_text
):

    image = Image.open(
        io.BytesIO(image_bytes)
    ).convert("RGB")

    draw = ImageDraw.Draw(image)

    width, height = image.size

    # -----------------------------------------------------
    # Yangi yozuv uchun font
    # -----------------------------------------------------

    font_size = 55

    if len(new_text) > 25:
        font_size = 45

    if len(new_text) > 40:
        font_size = 35

    font = get_font(font_size)

    # -----------------------------------------------------
    # Eski ism uzunligiga qarab taxminiy maydon
    # -----------------------------------------------------

    old_font = get_font(font_size)

    old_bbox = draw.textbbox(
        (0, 0),
        old_text,
        font=old_font
    )

    old_width = old_bbox[2] - old_bbox[0]
    old_height = old_bbox[3] - old_bbox[1]

    # Yangi yozuv markazda bo'ladi
    new_bbox = draw.textbbox(
        (0, 0),
        new_text,
        font=font,
        stroke_width=2
    )

    new_width = new_bbox[2] - new_bbox[0]
    new_height = new_bbox[3] - new_bbox[1]

    # -----------------------------------------------------
    # Pastki qismdagi yozuv joyini taxmin qilish
    # -----------------------------------------------------

    old_x = (width - old_width) // 2

    old_y = height - old_height - 45

    # Biroz kattaroq tozalash maydoni
    padding_x = 30
    padding_y = 20

    left = max(
        0,
        old_x - padding_x
    )

    top = max(
        0,
        old_y - padding_y
    )

    right = min(
        width,
        old_x + old_width + padding_x
    )

    bottom = min(
        height,
        old_y + old_height + padding_y
    )

    # -----------------------------------------------------
    # FONNI TIKLASH
    #
    # Rasmning shu joyiga yaqin fon rangidan foydalanamiz.
    # -----------------------------------------------------

    sample_y = max(
        0,
        top - 15
    )

    sample_box = image.crop(
        (
            left,
            sample_y,
            right,
            min(
                height,
                sample_y + 10
            )
        )
    )

    # O'rtacha rangni topamiz
    pixels = list(
        sample_box.getdata()
    )

    if pixels:

        avg_r = sum(
            p[0] for p in pixels
        ) // len(pixels)

        avg_g = sum(
            p[1] for p in pixels
        ) // len(pixels)

        avg_b = sum(
            p[2] for p in pixels
        ) // len(pixels)

        background = (
            avg_r,
            avg_g,
            avg_b
        )

    else:

        background = (
            255,
            255,
            255
        )

    # Tozalash
    draw.rectangle(
        (
            left,
            top,
            right,
            bottom
        ),
        fill=background
    )

    # -----------------------------------------------------
    # YANGI YOZUV
    # -----------------------------------------------------

    new_x = (
        width - new_width
    ) // 2

    new_y = (
        old_y
        + (old_height - new_height) // 2
    )

    draw.text(
        (
            new_x,
            new_y
        ),
        new_text,
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

    user_images[user_id] = bytes(
        image_bytes
    )

    # -----------------------------------------------------
    # ENG MUHIM QISM:
    # RASM BILAN BIRGA CAPTION KELGAN BO'LSA,
    # UNI HAM SAQLAYMIZ
    # -----------------------------------------------------

    caption = update.message.caption

    if caption:

        caption = caption.strip()

        # Avval almashtirish buyrug'ini tekshiramiz

        old_text, new_text, position = (
            extract_replace_command(
                caption
            )
        )

        if old_text and new_text:

            try:

                result = replace_bottom_text(
                    user_images[user_id],
                    old_text,
                    new_text
                )

                await update.message.reply_photo(
                    photo=result,
                    caption=(
                        "✅ Ism tahrirlandi!\n\n"
                        f"Eski: {old_text}\n"
                        f"Yangi: {new_text}"
                    )
                )

                del user_images[user_id]

                return

            except Exception as e:

                print(
                    "RASM ALMASHTIRISH XATOSI:",
                    e
                )

                await update.message.reply_text(
                    "❌ Ismni almashtirishda xatolik bo'ldi."
                )

                return

        # Oddiy rasm buyrug'i

        image_text, position = (
            extract_image_text(
                caption
            )
        )

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

                print(
                    "RASM XATOSI:",
                    e
                )

                await update.message.reply_text(
                    "❌ Rasmni o'zgartirishda xatolik bo'ldi."
                )

                return

    # -----------------------------------------------------
    # AGAR CAPTION YO'Q BO'LSA
    # -----------------------------------------------------

    await update.message.reply_text(
        "🖼 Rasm qabul qilindi.\n\n"
        "Endi nima qilishni yoz.\n\n"
        "Masalan:\n"
        "👉 pastiga Xojiakbar deb yoz\n"
        "👉 o'rtasiga SALOM deb yoz\n"
        "👉 ustiga TEST deb yoz\n\n"
        "Yoki:\n"
        "👉 Pasidagi Eski_Ismni Yangi_Ism qilib tahrirla"
    )


# =========================================================
# MATN XABAR
# =========================================================

async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    if not update.message.text:
        return

    user_id = update.effective_user.id

    text = update.message.text.strip()

    # -----------------------------------------------------
    # RASM BILAN ISHLASH
    # -----------------------------------------------------

    if user_id in user_images:

        # Avval ismni almashtirishni tekshiramiz

        old_text, new_text, position = (
            extract_replace_command(
                text
            )
        )

        if old_text and new_text:

            try:

                result = replace_bottom_text(
                    user_images[user_id],
                    old_text,
                    new_text
                )

                await update.message.reply_photo(
                    photo=result,
                    caption=(
                        "✅ Tayyor!\n\n"
                        f"Eski: {old_text}\n"
                        f"Yangi: {new_text}"
                    )
                )

                del user_images[user_id]

                return

            except Exception as e:

                print(
                    "RASM ALMASHTIRISH XATOSI:",
                    e
                )

                await update.message.reply_text(
                    "❌ Rasmni tahrirlashda xatolik bo'ldi."
                )

                return

        # Oddiy yozuv

        image_text, position = (
            extract_image_text(
                text
            )
        )

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

                print(
                    "RASM XATOSI:",
                    e
                )

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

        relevant_rules = find_relevant_rules(
            text
        )

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

        answer = (
            response
            .choices[0]
            .message
            .content
        )

        if not answer:

            answer = (
                "Javob olishda xatolik yuz berdi."
            )

        history.append(
            {
                "role": "assistant",
                "content": answer
            }
        )

        chat_histories[user_id] = (
            history[-10:]
        )

        await update.message.reply_text(
            answer
        )

    except Exception as e:

        print(
            "GROQ XATOSI:",
            e
        )

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
        .token(
            TELEGRAM_TOKEN
        )
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

    # RASM
    application.add_handler(
        MessageHandler(
            filters.PHOTO,
            handle_photo
        )
    )

    # MATN
    application.add_handler(
        MessageHandler(
            filters.TEXT
            & ~filters.COMMAND,
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


# =========================================================
# START
# =========================================================

if __name__ == "__main__":
    main()
