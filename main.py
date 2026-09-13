import sys
sys.stdout.reconfigure(line_buffering=True)

import os
import asyncio
import io
import traceback
import base64
import re
from PIL import Image, ImageDraw, ImageFont
from aiogram import Bot, Dispatcher, F, types
from groq import Groq

TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

bot = Bot(token=TOKEN)
dp = Dispatcher()
client = Groq(api_key=GROQ_API_KEY)

def clean_latex(text: str) -> str:
    while r'\frac' in text:
        text = re.sub(r'\\frac\{([^}]*)\}\{([^}]*)\}', r'(\1) / (\2)', text)
        text = re.sub(r'\\frac\s*([a-zA-Z0-9]+)\s*([a-zA-Z0-9]+)', r'(\1) / (\2)', text)
        break

    text = re.sub(r'\\sqrt\{([^}]+)\}', r'√(\1)', text)
    text = re.sub(r'\\sqrt\s*([a-zA-Z0-9])', r'√\1', text)

    text = (
        text.replace(r"\longrightarrow", " ⟶ ")
            .replace(r"\longleftarrow", " ⟵ ")
            .replace(r"\rightarrow", " → ")
            .replace(r"\leftarrow", " ← ")
            .replace(r"\to", " → ")
            .replace(r"\implies", " ⟹ ")
            .replace(r"\iff", " ⟺ ")
            .replace("###", "")
            .replace("**", "")
            .replace("*", "")
            .replace("#", "")
            .replace(r"\notin", " ∉ ")
            .replace(r"\in", " ∈ ")
            .replace(r"\approx", " ≈ ")
            .replace(r"\le", " ≤ ")
            .replace(r"\leq", " ≤ ")
            .replace(r"\ge", " ≥ ")
            .replace(r"\geq", " ≥ ")
            .replace(r"\neq", " ≠ ")
            .replace(r"\pm", " ± ")
            .replace(r"\mp", " ∓ ")
            .replace(r"\infty", " ∞ ")
            .replace(r"\sum", " ∑ ")
            .replace(r"\int", " ∫ ")
            .replace(r"\partial", " ∂ ")
            .replace(r"\emptyset", " ∅ ")
            .replace(r"\mathbf", "")
            .replace(r"\quad", "   ")
            .replace(r"\cdot", " · ")
            .replace(r"\times", " × ")
            .replace(r"\div", " ÷ ")
            .replace(r"^\circ", "°")
            .replace(r"\text", "")
            .replace("$", "")
    )
    return text

def create_solution_images(text: str) -> list[io.BytesIO]:
    cleaned_text = clean_latex(text)
    max_width_chars = 45
    lines = []
    for raw_line in cleaned_text.split("\n"):
        while len(raw_line) > max_width_chars:
            lines.append(raw_line[:max_width_chars])
            raw_line = raw_line[max_width_chars:]
        lines.append(raw_line)

    if not lines:
        lines = ["Решение пусто"]

    # Увеличили количество строк на странице, чтобы помещалось больше информации
    lines_per_page = 30
    pages_lines = [lines[i:i + lines_per_page] for i in range(0, len(lines), lines_per_page)]
    
    images_output = []
    total_pages = len(pages_lines)

    font_path = "/app/fonts/Roboto-Regular.ttf"
    font_bold_path = "/app/fonts/Roboto-Bold.ttf"

    try:
        font = ImageFont.truetype(font_path, 20)
        title_font = ImageFont.truetype(font_bold_path, 24)
    except Exception as e:
        print(f"Ошибка загрузки шрифтов: {e}. Используем стандартный шрифт.")
        font = ImageFont.load_default()
        title_font = font

    for page_idx, page_lines in enumerate(pages_lines, 1):
        width = 850
        line_height = 36
        header_height = 90
        padding = 45
        total_height = header_height + (len(page_lines) * line_height) + padding
        height = max(total_height, 450)

        image = Image.new("RGB", (width, height), color=(240, 242, 245))
        draw = ImageDraw.Draw(image)

        draw.rectangle([(0, 0), (width, 80)], fill=(33, 150, 243))
        
        if total_pages > 1:
            title_text = f"📝 РЕШЕНИЕ (Часть {page_idx} из {total_pages})"
        else:
            title_text = f"📝 РЕШЕНИЕ ЗАДАЧИ"
            
        draw.text((30, 25), title_text, fill=(255, 255, 255), font=title_font)

        margin_x, current_y = 35, 110
        for line in page_lines:
            draw.text((margin_x, current_y), line, fill=(30, 30, 30), font=font)
            current_y += line_height

        output = io.BytesIO()
        image.save(output, format="PNG")
        output.seek(0)
        images_output.append(output)

    return images_output

def encode_image_to_base64(image_path: str) -> str:
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    wait_msg = await message.answer("⏳ Анализирую задачу через Groq и оформляю подробное решение...")
    img_path = None
    try:
        photo = message.photo[-1]
        file_info = await bot.get_file(photo.file_id)
        img_path = f"temp_{message.from_user.id}.jpg"
        await bot.download_file(file_info.file_path, destination=img_path)

        base64_image = encode_image_to_base64(img_path)

        chat_completion = client.chat.completions.create(
            model="qwen/qwen3.6-27b",
            messages=[
                {
                    "role": "system",
                    "content": "Ты — эксперт-репетитор по математике и точным наукам. Пиши подробный ход решения и объяснения на русском языке, доводи решение до окончательного ответа."
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text", 
                            "text": "Реши эту задачу полностью, расписав все шаги, выкладки и итоговый ответ на русском языке."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            temperature=0.3,
            max_tokens=4096  # Увеличили лимит токенов генерации в 4 раза, чтобы решение не обрывалось
        )

        response_text = chat_completion.choices[0].message.content

        try:
            await bot.delete_message(chat_id=message.chat.id, message_id=wait_msg.message_id)
        except:
            pass

        photo_bytes_list = create_solution_images(response_text)

        if len(photo_bytes_list) == 1:
            await message.answer_photo(
                photo=types.BufferedInputFile(photo_bytes_list[0].read(), filename="solution.png"),
                caption="✅ Готово! Вот подробный разбор задачи."
            )
        else:
            media = [
                types.InputMediaPhoto(
                    media=types.BufferedInputFile(b.read(), filename=f"solution_{i+1}.png"),
                    caption="✅ Готово! Вот подробный разбор (несколько страниц)." if i == 0 else ""
                )
                for i, b in enumerate(photo_bytes_list)
            ]
            await message.answer_media_group(media=media)

    except Exception as e:
        traceback.print_exc()
        try:
            await bot.delete_message(chat_id=message.chat.id, message_id=wait_msg.message_id)
        except:
            pass
        await message.answer(f"❌ Произошла ошибка при генерации решения: {e}")
    finally:
        if img_path and os.path.exists(img_path):
            try:
                os.remove(img_path)
            except:
                pass

@dp.message(F.text)
async def handle_text(message: types.Message):
    await message.answer("📸 Пожалуйста, отправь мне картинку с задачей!")

async def main():
    print("Бот успешно запущен на базе Groq и готов к работе!")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
