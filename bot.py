import os
import re
import io

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
# GRAND MOBILE QOIDALARI
# =========================================================

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
    print("OGOHLANTIRISH: grand_mobile_qoidalari.txt topilmadi")


# =========================================================
# CHAT TARIXI
# =========================================================

chat_histories = {}

MAX_HISTORY = 12


# =========================================================
# RASM SAQLASH
# =========================================================

user_images = {}


# =========================================================
# GRAND MOBILE KALIT SO'ZLARI
# =========================================================

GRAND_MOBILE_KEYWORDS = [
    "grand mobile",
    "grandmobile",
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
    "mute",
    "ban",
    "gz",
    "green zone",
    "yashil zona",
    "lider",
    "leader",
    "admin",
    "adminka",
    "tashkilot",
    "fam",
    "oila",
    "server",
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


# =========================================================
# QOIDALARDAN KERAKLI QISMNI TOPISH
# =========================================================

def find_relevant_rules(question: str, max_chars: int = 12000) -> str:

    if not grand_mobile_rules:
        return ""

    question_lower = question.lower()

    # Aniq band raqami
    numbers = re.findall(
        r"\b\d+\.\d+(?:\.\d+)?\b",
        question_lower
    )

    if numbers:

        selected = []

        for number in numbers:

            pattern = re.compile(
                rf"(?im)^\s*{re.escape(number)}\b.*?"
                rf"(?=^\s*\d+\.\d+(?:\.\d+)?\b|\Z)",
                re.S
            )

            matches = pattern.findall(grand_mobile_rules)

            for match in matches:
                selected.append(match.strip())

        if selected:

            result = "\n\n".join(selected)

            return result[:max_chars]

    # So'zlar bo'yicha qidirish
    words = re.findall(
        r"[a-zA-Zа-яА-ЯёЁ0-9]+",
        question_lower
    )

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
            scored.append(
                (score, chunk.strip())
            )

    scored.sort(
        key=lambda x: x[0],
        reverse=True
    )

    selected_chunks = []

    for score, chunk in scored[:8]:
        selected_chunks.append(chunk)

    if selected_chunks:

        result = "\n\n".join(selected_chunks)

        return result[:max_chars]

    return grand_mobile_rules[:max_chars]


# =========================================================
# SISTEMA PROMPT
# =========================================================

GENERAL_SYSTEM_PROMPT = """
Sen universal aqlli Telegram yordamchisisan.

Foydalanuvchi bilan tabiiy, tushunarli va foydali suhbat qil.

Qoidalar:

1. Savolga to'g'ridan-to'g'ri javob ber.
2. Keraksiz uzun gaplar yozma.
3. Foydalanuvchi qaysi tilda yozsa, o'sha tilda javob ber.
4. O'zbekcha savollarga sodda o'zbekcha javob ber.
5. Ruscha savollarga ruscha javob ber.
6. Inglizcha savollarga inglizcha javob ber.
7. Matematika, tarix, texnologiya, dasturlash, tarjima,
   kundalik savollar va boshqa mavzularda yordam ber.
8. Bilmagan narsangni uydirma.
9. Oldingi suhbat kontekstini hisobga ol.
10. Tabiiy va odamga o'xshab javob ber.
"""


GRAND_MOBILE_SYSTEM_PROMPT = """
Agar foydalanuvchi Grand Mobile haqida so'rasa,
berilgan GRAND MOBILE QOIDALARI asosida javob ber.

MUHIM:

- Berilgan qoidalar asosiy manba.
- Qoidalarda yo'q narsani o'ylab topma.
- Jazo turini o'zgartirma.
- WARN, BAN, MUTE, DEMORGAN kabi jazolarni
  qoidada ko'rsatilganidek yoz.
- Agar band raqami bo'lsa, bandni ko'rsat.
- Javobni sodda tushuntir.
- Faqat kerakli qoidani ko'rsat.
"""


# =========================================================
# START
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = update.effective_user

    name = (
        user.first_name
        if user
        else "do'stim"
    )

    await update.message.reply_text(
        f"Salom, {name}! 👋\n\n"
        "Men universal AI botman 🤖\n\n"
        "Men quyidagilarda yordam bera olaman:\n\n"
        "🎮 Grand Mobile qoidalari\n"
        "🤖 Oddiy AI savollar\n"
        "📚 O'qish\n"
        "💻 Dasturlash\n"
        "🌍 Tarjima\n"
        "🧮 Matematika\n"
        "📸 Oddiy rasm tahrirlash\n\n"
        "Savolingni yoki rasmingni yuboraver!"
    )


# =========================================================
# RESET
# =========================================================

async def reset(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    chat_id = update.effective_chat.id

    chat_histories[chat_id] = []

    await update.message.reply_text(
        "🧹 Suhbat tarixi tozalandi."
    )


# =========================================================
# RASM QABUL QILISH
# =========================================================

async def handle_photo(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    photo = update.message.photo

    if not photo:
        return

    chat_id = update.effective_chat.id

    try:

        # Eng katta o'lchamdagi rasm
        file = await photo[-1].get_file()

        image_bytes = await file.download_as_bytearray()

        user_images[chat_id] = bytes(image_bytes)

        await update.message.reply_text(
            "📸 Rasmni oldim!\n\n"
            "Endi nima qilishimni yoz.\n\n"
            "Masalan:\n"
            "• Rasmga Xojiakbar deb yoz\n"
            "• Pastiga Xumo_Xusniddinov deb yoz\n"
            "• O'rtasiga TEST deb yoz\n\n"
            "⚠️ Hozircha bepul tahrirlashda "
            "asosan yozuv qo'shish funksiyasi ishlaydi."
        )

    except Exception as e:

        print(
            "RASM QABUL QILISH XATOSI:",
            repr(e)
        )

        await update.message.reply_text(
            "❌ Rasmni olishda xatolik bo'ldi."
        )


# =========================================================
# FONT TOPISH
# =========================================================

def get_font(size: int):

    possible_fonts = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]

    for font_path in possible_fonts:

        if os.path.exists(font_path):

            try:
                return ImageFont.truetype(
                    font_path,
                    size
                )
            except:
                pass

    return ImageFont.load_default()


# =========================================================
# RASMGA YOZUV QO'SHISH
# =========================================================

def add_text_to_image(
    image_bytes: bytes,
    text: str
):

    image = Image.open(
        io.BytesIO(image_bytes)
    ).convert("RGB")

    draw = ImageDraw.Draw(image)

    width, height = image.size

    # Rasmga mos font
    font_size = max(
        20,
        min(width, height) // 15
    )

    font = get_font(font_size)

    # Matn o'lchami
    bbox = draw.textbbox(
        (0, 0),
        text,
        font=font,
        stroke_width=2
    )

    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    # Pastki markaz
    x = (width - text_width) // 2
    y = height - text_height - 40

    # Qora kontur + oq yozuv
    draw.text(
        (x, y),
        text,
        font=font,
        fill="white",
        stroke_width=3,
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
# RASM TAHRIRLASH BUYRUG'INI ANIQLASH
# =========================================================

def extract_image_text(command: str):

    text = command.strip()

    patterns = [
        r"r\w*\s+ga\s+(.+?)\s+(?:deb\s+)?yoz",
        r"pastiga\s+(.+?)\s+(?:deb\s+)?yoz",
        r"o['’`]?rtasiga\s+(.+?)\s+(?:deb\s+)?yoz",
        r"ustiga\s+(.+?)\s+(?:deb\s+)?yoz",
        r"(.+?)\s+deb\s+yoz",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE
        )

        if match:

            result = match.group(1).strip()

            if result:
                return result

    return None


# =========================================================
# MATNLI XABAR
# =========================================================

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

    # =====================================================
    # AGAR OLDIN RASM YUBORILGAN BO'LSA
    # =====================================================

    if chat_id in user_images:

        image_text = extract_image_text(
            user_text
        )

        if image_text:

            try:

                result_image = add_text_to_image(
                    user_images[chat_id],
                    image_text
                )

                await update.message.reply_photo(
                    photo=result_image,
                    caption=(
                        f"✅ Tayyor!\n"
                        f"Qo'shilgan yozuv: {image_text}"
                    )
                )

                # Rasmni o'chirib qo'yamiz
                del user_images[chat_id]

                return

            except Exception as e:

                print(
                    "RASM TAHRIR XATOSI:",
                    repr(e)
                )

                await update.message.reply_text(
                    "❌ Rasmni tahrirlashda xatolik bo'ldi."
                )

                return

    # =====================================================
    # CHAT TARIXI
    # =====================================================

    if chat_id not in chat_histories:

        chat_histories[chat_id] = []

    # =====================================================
    # GRAND MOBILE
    # =====================================================

    grand_question = is_grand_mobile_question(
        user_text
    )

    if grand_question:

        relevant_rules = find_relevant_rules(
            user_text
        )

        system_prompt = (
            GENERAL_SYSTEM_PROMPT
            + "\n\n"
            + GRAND_MOBILE_SYSTEM_PROMPT
            + "\n\n"
            + "GRAND MOBILE QOIDALARIDAN MA'LUMOT:\n"
            + relevant_rules
        )

    else:

        system_prompt = GENERAL_SYSTEM_PROMPT

    # =====================================================
    # GROQ MESSAGES
    # =====================================================

    messages = [
        {
            "role": "system",
            "content": system_prompt
        }
    ]

    messages.extend(
        chat_histories[chat_id][-MAX_HISTORY:]
    )

    messages.append(
        {
            "role": "user",
            "content": user_text
        }
    )

    # =====================================================
    # GROQ
    # =====================================================

    try:

        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=0.4,
            max_tokens=1200
        )

        answer = response.choices[0].message.content

        if not answer:

            answer = (
                "Kechirasiz, hozir javob "
                "bera olmadim."
            )

        # =================================================
        # TARIX
        # =================================================

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

        if len(chat_histories[chat_id]) > MAX_HISTORY * 2:

            chat_histories[chat_id] = (
                chat_histories[chat_id]
                [-MAX_HISTORY * 2:]
            )

        # =================================================
        # TELEGRAM LIMIT
        # =================================================

        if len(answer) <= 4000:

            await update.message.reply_text(
                answer
            )

        else:

            for i in range(
                0,
                len(answer),
                4000
            ):

                await update.message.reply_text(
                    answer[i:i + 4000]
                )

    except Exception as e:

        print(
            "AI XATOLIK:",
            repr(e)
        )

        await update.message.reply_text(
            "⚠️ AI javobida xatolik yuz berdi."
        )


# =========================================================
# MAIN
# =========================================================

def main():

    print(
        "UNIVERSAL AI + RASM BOT ISHGA TUSHYAPTI..."
    )

    if grand_mobile_rules:

        print(
            "Grand Mobile qoidalari tayyor."
        )

    else:

        print(
            "Grand Mobile qoidalari topilmadi."
        )

    app = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .build()
    )

    # START
    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    # RESET
    app.add_handler(
        CommandHandler(
            "reset",
            reset
        )
    )

    # RASM
    app.add_handler(
        MessageHandler(
            filters.PHOTO,
            handle_photo
        )
    )

    # MATN
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message
        )
    )

    print(
        "UNIVERSAL AI + RASM BOT ISHLAYAPTI!"
    )

    app.run_polling(
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
