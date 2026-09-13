import os
import traceback
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from google import genai
from PIL import Image, ImageDraw, ImageFont
import io

TELEGRAM_TOKEN = "8547033865:AAGwsj1l2veNYbFIyFV8DTibbmI5uXCfs_c"

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# Инициализация клиента Gemini (подставь свой рабочий ключ)
import os
from google import genai

# Получаем ключ из защищенной переменной окружения хостинга
API_KEY = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=API_KEY)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "Привет! Отправь мне фотографию с задачей, и я пришлю тебе красивую картинку с подробным решением."
    )


def create_solution_image(text: str) -> io.BytesIO:
    """Динамически создает картинку достаточной высоты для полного текста решения."""

    # Очищаем текст от LaTeX-тегов
    cleaned_text = (
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
        .replace(r"\quad", "   ")
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
    # Подготавливаем разбиение на строки
    max_width_chars = 60
    lines = []
    for raw_line in cleaned_text.split("\n"):
        while len(raw_line) > max_width_chars:
            lines.append(raw_line[:max_width_chars])
            raw_line = raw_line[max_width_chars:]
        lines.append(raw_line)

    # Вычисляем необходимую высоту картинки в зависимости от количества строк
    width = 800
    line_height = 30
    header_height = 90
    padding = 40
    total_height = header_height + (len(lines) * line_height) + padding

    # Минимальная высота, если текст короткий
    height = max(total_height, 400)

    image = Image.new("RGB", (width, height), color=(240, 242, 245))
    draw = ImageDraw.Draw(image)

    try:
        font = ImageFont.truetype("arial.ttf", 20)
        title_font = ImageFont.truetype("arialbd.ttf", 24)
    except:
        font = ImageFont.load_default()
        title_font = font

    # Рисуем шапку
    draw.rectangle([(0, 0), (width, 80)], fill=(33, 150, 243))
    draw.text((30, 25), "📝 ПОЛНОЕ РЕШЕНИЕ ВСЕХ ЗАДАНИЙ", fill=(255, 255, 255), font=title_font)

    # Выводим все строки текста
    margin_x, current_y = 30, 110
    for line in lines:
        draw.text((margin_x, current_y), line, fill=(30, 30, 30), font=font)
        current_y += line_height

    output = io.BytesIO()
    image.save(output, format="PNG")
    output.seek(0)
    return output


    # Пытаемся загрузить стандартный шрифт Windows, если нет — используем дефолтный
    try:
        font = ImageFont.truetype("arial.ttf", 20)
        title_font = ImageFont.truetype("arialbd.ttf", 24)
    except:
        font = ImageFont.load_default()
        title_font = font

    # Рисуем шапку
    draw.rectangle([(0, 0), (width, 80)], fill=(33, 150, 243))
    draw.text((30, 25), "📝 РЕШЕНИЕ ЗАДАЧИ", fill=(255, 255, 255), font=title_font)

    # Форматируем и выводим текст по строкам
    margin_x, margin_y = 30, 110
    max_width_chars = 65

    lines = text.split("\n")
    current_y = margin_y

    for line in lines:
        # Простой перенос длинных строк
        while len(line) > max_width_chars:
            part = line[:max_width_chars]
            draw.text((margin_x, current_y), part, fill=(30, 30, 30), font=font)
            line = line[max_width_chars:]
            current_y += 30

        draw.text((margin_x, current_y), line, fill=(30, 30, 30), font=font)
        current_y += 30
        if current_y > height - 50:
            break  # Ограничение по высоте холста

    # Сохраняем в байтовый буфер без записи на диск
    output = io.BytesIO()
    image.save(output, format="PNG")
    output.seek(0)
    return output


@dp.message(F.photo)
async def handle_photo(message: types.Message):
    wait_msg = await message.answer("⏳ Анализирую задачу и оформляю решение в виде картинки...")
    img_path = None

    try:
        photo = message.photo[-1]
        file_info = await bot.get_file(photo.file_id)
        img_path = f"temp_{message.from_user.id}.jpg"
        await bot.download_file(file_info.file_path, destination=img_path)

        img = Image.open(img_path)

        # Запрос к нейросети за решением (используем стабильную модель)
        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=[img, "Реши эту академическую задачу подробно, понятно и структурировано кратко."]
        )

        # Удаляем сообщение о загрузке
        try:
            await bot.delete_message(chat_id=message.chat.id, message_id=wait_msg.message_id)
        except:
            pass

        # Создаем картинку с текстом решения и отправляем её пользователю
        photo_bytes = create_solution_image(response.text)
        await message.answer_photo(
            photo=types.BufferedInputFile(photo_bytes.read(), filename="solution.png"),
            caption="✅ Готово! Вот подробный разбор."
        )

    except Exception as e:
        print("--- ТЕХНИЧЕСКАЯ ОШИБКА ---")
        traceback.print_exc()
        try:
            await bot.delete_message(chat_id=message.chat.id, message_id=wait_msg.message_id)
        except:
            pass
        await message.answer("❌ Произошла ошибка при генерации изображения с решением.")

    finally:
        if img_path and os.path.exists(img_path):
            try:
                os.remove(img_path)
            except:
                pass


async def main():
    print("Бот успешно запущен и готов генерировать картинки-решения!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
    import os
    import asyncio
    from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

def run_server():
    server = HTTPServer(('0.0.0.0', 10000), SimpleHandler)
    server.serve_forever()

# Запускаем сервер в фоновом потоке
Thread(target=run_server, daemon=True).start()

    # ------------------------------------------------------------

   # Строка должна начинаться прямо от левого края:
async def main():
    # весь код внутри функции сдвинут внутрь на 4 пробела
    await dp.start_polling(bot)
        # ... твой запуск бота
        pass


    if __name__ == "__main__":
        asyncio.run(main())
