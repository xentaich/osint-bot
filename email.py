import os
import re
import aiohttp
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from dotenv import load_dotenv

# Загрузка конфига
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
HIBP_API_KEY = os.getenv("HIBP_API_KEY")

# Настройка логов
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- Валидация ---
def is_phone(phone: str) -> bool:
    return re.match(r"^\+?[0-9\s\-]{10,15}$", phone) is not None

def is_ip(ip: str) -> bool:
    try:
        socket.inet_aton(ip)
        return True
    except socket.error:
        return False

def is_email(email: str) -> bool:
    return re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email) is not None

# --- API-запросы ---
async def check_phone(phone: str) -> dict:
    url = f"https://htmlweb.ru/geo/api.php?json&telcod={phone}"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, timeout=10) as resp:
                data = await resp.json()
                return {
                    "country": data.get("country", {}).get("name", "N/A"),
                    "operator": data.get("0", {}).get("oper", "N/A"),
                    "valid": "Да" if data.get("0", {}).get("mobile") else "Нет"
                }
        except Exception as e:
            logger.error(f"Phone API error: {e}")
            return {"error": "API error"}

async def check_ip(ip: str) -> dict:
    url = f"http://ip-api.com/json/{ip}"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, timeout=10) as resp:
                data = await resp.json()
                return {
                    "country": data.get("country", "N/A"),
                    "city": data.get("city", "N/A"),
                    "isp": data.get("isp", "N/A")
                }
        except Exception as e:
            logger.error(f"IP API error: {e}")
            return {"error": "API error"}

async def check_email(email: str) -> dict:
    # Проверка утечек через Have I Been Pwned
    headers = {"hibp-api-key": HIBP_API_KEY}
    url = f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}"
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    breaches = await resp.json()
                    return {
                        "breaches": [b["Name"] for b in breaches][:5],
                        "count": len(breaches)
                    }
                return {"breaches": [], "count": 0}
        except Exception as e:
            logger.error(f"Email API error: {e}")
            return {"error": "API error"}

# --- Клавиатуры ---
def get_phone_kb(phone: str) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="WhatsApp", url=f"https://wa.me/{phone}")],
        [InlineKeyboardButton(text="Telegram", url=f"tg://resolve?phone={phone}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# --- Обработчики ---
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "🔍 OSINT Bot\n\n"
        "Отправьте:\n"
        "- Номер телефона (+79123456789)\n"
        "- IP-адрес\n"
        "- Email для проверки"
    )

@dp.message(F.text)
async def handle_query(message: types.Message):
    query = message.text.strip()
    
    if is_phone(query):
        # Проверка телефона
        data = await check_phone(query)
        if "error" in data:
            await message.answer("⚠️ Ошибка проверки")
            return
            
        text = (
            f"📱 Номер: {query}\n"
            f"🌍 Страна: {data['country']}\n"
            f"📶 Оператор: {data['operator']}\n"
            f"✅ Валидность: {data['valid']}"
        )
        await message.answer(text, reply_markup=get_phone_kb(query))
        
    elif is_ip(query):
        # Проверка IP
        data = await check_ip(query)
        if "error" in data:
            await message.answer("⚠️ Ошибка проверки")
            return
            
        text = (
            f"🖥️ IP: {query}\n"
            f"🌍 Страна: {data['country']}\n"
            f"🏙️ Город: {data['city']}\n"
            f"📶 Провайдер: {data['isp']}"
        )
        await message.answer(text)
        
    elif is_email(query):
        # Проверка email
        data = await check_email(query)
        if "error" in data:
            await message.answer("⚠️ Ошибка проверки")
            return
            
        text = f"📧 Email: {query}\n"
        if data["count"] > 0:
            text += f"⚠️ Найден в {data['count']} утечках:\n"
            text += "\n".join(f"├ {b}" for b in data["breaches"])
        else:
            text += "✅ Не найден в известных утечках"
        await message.answer(text)
        
    else:
        await message.answer("❌ Неверный формат ввода")

# --- Запуск ---
if __name__ == "__main__":
    dp.run_polling(bot)