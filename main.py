import sys
sys.stdout.reconfigure(line_buffering=True)

import os
import asyncio
import io
import traceback
import re
from PIL import Image, ImageDraw, ImageFont
from aiogram import Bot, Dispatcher, F, types
from google import genai

TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

bot = Bot(token=TOKEN)
dp = Dispatcher()
client = genai.Client(api_key=GEMINI_API_KEY)

def clean_latex(text: str) -> str:
    # Заменяем квадратные корни на понятный текст
    text = re.sub(r'\\sqrt\{([^}]+)\}', r'√(\1)', text)
    text = re.sub(r'\\sqrt\s*([a-zA-Z0-9])', r'√\1', text)
    
    # Расширенная очистка LaTeX и разметки
    text = (
        text.replace("###", "")
            .replace("**", "")
            .replace("*", "")
            .replace("#", "")
            .replace(r"\notin", " не принадлежит ")
            .replace(r"\in", " принадлежит ")
            .replace(r"\rightarrow", "→")
            .replace(r"\to", "→")
            .replace(r"\sqrt", "√")
            .replace(r"\approx", "≈")
            .replace(r"\le", "≤")
            .replace(r"\leq", "≤")
            .replace(r"\mathbf", "")
            .replace(r"\quad", "    ")
            .replace(r"\left(", "(")
            .replace(r"\right)", ")")
            .replace(r"\left[", "[")
            .replace(r"\right]", "]")
            .replace(r"\left\{", "{")
            .replace(r"\right\}", "}")
            .replace(r"\frac", "")
            .replace(r"{", "(")
            .replace(r"}", ")")
            .replace(r"\cdot", "·")
            .replace(r"^\circ", "°")
            .replace(r"\text", "")
            .replace("$", "")
    )
    return text

def create_solution_image(text: str) -> io.BytesIO:
    cleaned_text = clean_latex(text)
    max_width_chars = 60
    lines = []
    for raw_line in cleaned_text.split("\n"):
        while len(raw_line) > max_width_chars:
            lines.append(raw_line[:max_width_chars])
            raw_line = raw_line[max_width_chars:]
        lines.append(raw_line)

    width = 800
    line_height = 30
    header_height = 90
    padding = 40
    total_height = header_height + (len(lines) * line_height) + padding
    height = max(total_height, 400)

    image = Image.new("RGB", (width, height), color=(240, 242, 245))
    draw = ImageDraw.Draw(image)

    try:
        font = ImageFont.truetype("arial.ttf", 20)
        title_font = ImageFont.truetype("arialbd.ttf", 24)
    except:
        font = ImageFont.load_default()
        title_font = font

    draw.rectangle([(0, 0), (width, 80)], fill=(33, 150, 243))
    draw.text((30, 25), "📝 РЕШЕНИЕ ЗАДАЧИ", fill=(255, 255, 255), font=title_font)

    margin_x, current_y = 30, 110
    for line in lines:
        draw.text((margin_x, current_y), line, fill=(30, 30, 30), font=font)
        current_y += line_height
        if current_y > height - 50:
            break

    output = io.BytesIO()
    image.save(output, format="PNG")
    output.seek(0)
    return output

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    wait_msg = await message.answer("⏳ Анализирую задачу и оформляю решение...")
    img_path = None
    try:
        photo = message.photo[-1]
        file_info = await bot.get_file(photo.file_id)
        img_path = f"temp_{message.from_user.id}.jpg"
        await bot.download_file(file_info.file_path, destination=img_path)

        img = Image.open(img_path)
        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=[img, "Реши эту академическую задачу подробно, понятно и структурировано."]
        )

        try:
            await bot.delete_message(chat_id=message.chat.id, message_id=wait_msg.message_id)
        except:
            pass

        photo_bytes = create_solution_image(response.text)
        await message.answer_photo(
            photo=types.BufferedInputFile(photo_bytes.read(), filename="solution.png"),
            caption="✅ Готово! Вот подробный разбор."
        )
    except Exception as e:
        traceback.print_exc()
        try:
            await bot.delete_message(chat_id=message.chat.id, message_id=wait_msg.message_id)
        except:
            pass
        await message.answer("❌ Произошла ошибка при генерации.")
    finally:
        if img_path and os.path.exists(img_path):
            try:
                os.remove(img_path)
            except:
                pass

@dp.message(F.text)
async def handle_text(message: types.Message):
    await message.answer("📸 Отправь мне картинку с задачей!")

async def main():
    print("Бот запущен!")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
