import os
import json
import asyncio
import hashlib
import re
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Set
import logging
import requests
import google.generativeai as genai
from telegram import Bot, Update
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import Application, CommandHandler, ContextTypes
import sys

# Константы
TELEGRAM_TOKEN = "7933377403:AAG5k7ryxq45aH5RrPGb1ipuoSpVq--vxpw"
NEWS_API_KEY = "e680b2dfdf70401298769475d956616c"
GOOGLE_API_KEY = "AIzaSyCWY3dZdLLjSlui28rqAw9A6NwkSUA0mQw"
NEWS_API_EVERYTHING_URL = "https://newsapi.org/v2/everything"
NEWS_API_TOP_HEADLINES_URL = "https://newsapi.org/v2/top-headlines"

# Настройка логгера
logger = logging.getLogger(__name__)

# Configure Gemini AI
genai.configure(api_key=GOOGLE_API_KEY)

def load_config():
    """Load bot configuration"""
    try:
        if os.path.exists("bot_config.json"):
            with open("bot_config.json", "r", encoding="utf-8") as f:
                return json.load(f)
        return {"channels": {}, "post_history": []}
    except Exception as e:
        logger.error(f"Ошибка загрузки конфигурации: {str(e)}")
        return {"channels": {}, "post_history": []}

def save_config(config):
    """Save bot configuration"""
    try:
        with open("bot_config.json", "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logger.error(f"Ошибка сохранения конфигурации: {str(e)}")

class ApiUsageStats:
    def __init__(self):
        self.stats = {
            'newsapi': {'calls': 0, 'last_reset': datetime.now()},
            'gemini': {'calls': 0, 'last_reset': datetime.now()},
            'telegram': {'calls': 0, 'last_reset': datetime.now()}
        }
        
    def increment(self, api_name):
        """Increment API usage counter"""
        if api_name in self.stats:
            self.stats[api_name]['calls'] += 1
            
    def get_stats(self):
        """Get current API usage statistics"""
        current_time = datetime.now()
        stats_data = {}
        
        for api, data in self.stats.items():
            time_diff = current_time - data['last_reset']
            calls_per_hour = data['calls'] / (time_diff.total_seconds() / 3600) if time_diff.total_seconds() > 0 else 0
            
            stats_data[api] = {
                'total_calls': data['calls'],
                'calls_per_hour': round(calls_per_hour, 2),
                'running_since': data['last_reset'].strftime('%Y-%m-%d %H:%M:%S')
            }
            
        return stats_data
    
    def reset(self):
        """Reset all counters"""
        for api in self.stats:
            self.stats[api]['calls'] = 0
            self.stats[api]['last_reset'] = datetime.now()

class NewsManager:
    def __init__(self):
        self.posted_news_hashes: Set[str] = set()  # Хеши опубликованных новостей
        self.channel_post_times: Dict[str, List[datetime]] = defaultdict(list)  # Время постов по каналам
        self.news_cache: Dict[str, List[dict]] = defaultdict(list)  # Кэш новостей по каналам
        
        # Загружаем историю публикаций
        config = load_config()
        for post in config.get("post_history", []):
            try:
                if "title" in post and "url" in post:
                    news_hash = self._calculate_news_hash(post["title"], post["url"])
                    self.posted_news_hashes.add(news_hash)
                    if "timestamp" in post and "channel" in post:
                        post_time = datetime.fromisoformat(post["timestamp"])
                        self.channel_post_times[post["channel"]].append(post_time)
            except KeyError:
                continue  # Пропускаем некорректные записи
            except Exception as e:
                logger.error(f"Ошибка при загрузке истории постов: {str(e)}")

    def _calculate_news_hash(self, title: str, url: str) -> str:
        """Создает уникальный хеш для новости"""
        return hashlib.md5(f"{title}{url}".encode()).hexdigest()
    
    def can_post_news(self, channel_name: str, channel_config: dict) -> bool:
        """Проверяет, можно ли публиковать новости в канал"""
        # Проверяем активность канала
        if not channel_config.get('active', True):
            return False

        # В тестовом режиме пропускаем все остальные проверки
        return True
    
    def mark_news_posted(self, channel_name: str, news_item: dict):
        """Отмечает новость как опубликованную"""
        if "title" in news_item and "url" in news_item:
            news_hash = self._calculate_news_hash(news_item["title"], news_item["url"])
            self.posted_news_hashes.add(news_hash)
            self.channel_post_times[channel_name].append(datetime.now())
            
            # Очищаем старые записи
            week_ago = datetime.now() - timedelta(days=7)
            self.channel_post_times[channel_name] = [
                t for t in self.channel_post_times[channel_name] 
                if t > week_ago
            ]

# Глобальные объекты
bot = None
api_stats = ApiUsageStats()
news_manager = NewsManager()

async def init_bot():
    """Initialize the bot and set up command handlers"""
    try:
        global bot
        application = Application.builder().token(TELEGRAM_TOKEN).build()
        bot = application.bot

        # Добавляем обработчики команд
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("status", status_command))
        application.add_handler(CommandHandler("post", manual_post))

        # Настраиваем планировщик задач
        application.job_queue.run_repeating(scheduled_news_check, interval=60, first=10)
        
        logger.info("Bot initialized successfully")
        
        # Запускаем бота
        await application.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        logger.error(f"Ошибка при инициализации бота: {str(e)}")
        raise

def fetch_news(channel_name, channel_config):
    """Получение новостей для канала"""
    logger.info(f"Получение новостей для канала {channel_name} (ID: {channel_config['channel_id']})")
    
    try:
        # Базовые параметры для everything endpoint
        params = {
            'apiKey': NEWS_API_KEY,
            'pageSize': channel_config.get('page_size', 20),
            'language': 'ru',
            'sortBy': 'publishedAt'
        }
        
        logger.info(f"Базовые параметры запроса: {params}")
        
        # Добавляем поисковый запрос
        query = channel_config.get('query')
        if not query:
            query = 'новости OR технологии OR наука'
        params['q'] = query
        logger.info(f"Добавлен поисковый запрос: {query}")
        
        # Добавляем источники если есть
        if channel_config.get('sources'):
            params['sources'] = channel_config['sources']
            logger.info(f"Добавлены источники: {channel_config['sources']}")
            
        # Делаем запрос
        logger.info(f"Отправка запроса к NewsAPI с параметрами: {params}")
        response = requests.get(NEWS_API_EVERYTHING_URL, params=params)
        api_stats.increment('newsapi')
        
        logger.info(f"Получен ответ от API. Статус: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            logger.info(f"Ответ API: {data}")
            if data['status'] == 'ok' and data['articles']:
                logger.info(f"Получено {len(data['articles'])} новостей")
                return data['articles']
            else:
                error_msg = data.get('message', 'Нет сообщения')
                logger.warning(f"API вернул статус {data['status']}. Сообщение: {error_msg}")
                if 'message' in data:
                    logger.error(f"Подробная ошибка от API: {data['message']}")
        else:
            logger.error(f"API вернул статус {response.status_code}. Тело ответа: {response.text}")
                
        logger.warning(f"Нет новостей для канала {channel_name}")
        return None
        
    except Exception as e:
        logger.error(f"Ошибка при получении новостей: {str(e)}", exc_info=True)
        return None

def generate_post(news_item, channel_config):
    """Generate a unique post using Gemini AI based on news and channel specifics"""
    logger.info("Генерация контента с помощью Gemini AI")
    
    try:
        # Получаем системный промпт канала или используем стандартный
        system_prompt = channel_config.get('system_prompt', """
        Ты - профессиональный редактор новостного Telegram-канала. 
        Твоя задача - создавать краткие, информативные и вовлекающие посты.
        Используй современный разговорный стиль, добавляй эмодзи и хэштеги.
        """).strip()
        
        # Создаем промпт для генерации
        prompt = f"""
        {system_prompt}
        
        Создай пост для Telegram на основе этой новости:
        
        TITLE: {news_item['title']}
        DESCRIPTION: {news_item['description']}
        
        ТРЕБОВАНИЯ:
        1. Максимум 300 символов
        2. Используй живой, разговорный стиль
        3. Добавь 1-2 эмодзи в начале для привлечения внимания
        4. В конце добавь 1-2 релевантных хештега
        5. Добавь призыв к действию
        6. Не повторяй заголовок дословно
        7. Пиши на русском языке
        """
        
        # Генерируем контент
        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content(prompt)
        api_stats.increment('gemini')
        
        # Получаем текст из response
        content = ""
        for part in response.parts:
            content += part.text
        
        if not content:
            raise ValueError("Пустой ответ от Gemini AI")
            
        # Добавляем ссылку на источник
        content += f"\n\nПодробнее: {news_item['url']}"
            
        return content
        
    except Exception as e:
        logger.error(f"Ошибка при генерации поста: {str(e)}")
        return None

async def send_to_channel(channel_id: str, message: str, news_item: dict):
    """Отправка сообщения в Telegram канал с обработкой ошибок"""
    global bot
    try:
        if bot is None:
            logger.error("Бот не инициализирован")
            return False
            
        await bot.send_message(
            chat_id=channel_id,
            text=message,
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True
        )
        logger.info(f"Сообщение успешно отправлено в канал {channel_id}")
        return True
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения в канал {channel_id}: {str(e)}", exc_info=True)
        return False

async def process_news():
    """Обработка новостей для всех каналов"""
    logger.info("Начало обработки новостей для каналов")
    config = load_config()
    
    for channel_name, channel_info in config["channels"].items():
        if not channel_info.get('active', True):
            logger.info(f"Канал {channel_name} неактивен, пропускаем")
            continue
            
        if not news_manager.can_post_news(channel_name, channel_info):
            logger.info(f"Пропускаем публикацию для канала {channel_name} - неподходящее время")
            continue
        
        logger.info(f"Получение новостей для канала {channel_name}")
        news_data = fetch_news(channel_name, channel_info)
        
        if not news_data:
            logger.info(f"Нет новостей для канала {channel_name}")
            continue
            
        # Публикуем новость
        for news_item in news_data:
            if "title" not in news_item or "url" not in news_item:
                continue
                
            news_hash = news_manager._calculate_news_hash(news_item["title"], news_item["url"])
            if news_hash in news_manager.posted_news_hashes:
                continue
                
            logger.info("Генерация контента с помощью Gemini AI")
            post_content = generate_post(news_item, channel_info)
            if not post_content:
                continue
                
            success = await send_to_channel(channel_info['channel_id'], post_content, news_item)
            if success:
                news_manager.mark_news_posted(channel_name, news_item)
                logger.info(f"Успешно опубликована новость в канал {channel_name}")
                
                # Обновляем историю постов
                config["post_history"].append({
                    "channel": channel_name,
                    "timestamp": datetime.now().isoformat(),
                    "title": news_item["title"],
                    "url": news_item["url"]
                })
                save_config(config)
                break  # Публикуем только одну новость за раз
            else:
                logger.warning(f"Не удалось опубликовать новость в канал {channel_name}")
    
    logger.info("Завершение обработки новостей для каналов")

async def scheduled_news_check(context: ContextTypes.DEFAULT_TYPE):
    """Периодическая проверка и публикация новостей"""
    try:
        logger.info("Запуск периодической проверки новостей")
        await process_news()
        logger.info("Периодическая проверка новостей завершена")
    except Exception as e:
        logger.error(f"Ошибка при периодической проверке: {str(e)}", exc_info=True)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    await update.message.reply_text(
        "Привет! Я бот для публикации новостей в Telegram-каналы. "
        "Используйте /status для просмотра статуса каналов и /post для ручной публикации."
    )

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /status"""
    config = load_config()
    status_text = "📊 Статус каналов:\n\n"
    
    for channel_name, info in config["channels"].items():
        active_status = "✅" if info.get('active', True) else "❌"
        categories = ", ".join(info.get('categories', ['общие']))
        posts_today = len([
            t for t in news_manager.channel_post_times[channel_name]
            if (datetime.now() - t).total_seconds() < 24 * 3600
        ])
        
        status_text += (
            f"📌 {channel_name} ({info['channel_id']})\n"
            f"Статус: {active_status}\n"
            f"Категории: {categories}\n"
            f"Постов за сегодня: {posts_today}/{info.get('max_posts_per_day', 10)}\n\n"
        )
    
    # Добавляем статистику API
    stats = api_stats.get_stats()
    status_text += "\n📈 Статистика API:\n"
    for api, data in stats.items():
        status_text += f"{api}: {data['total_calls']} вызовов ({data['calls_per_hour']}/час)\n"
    
    await update.message.reply_text(status_text)

async def manual_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /post для ручной публикации"""
    await update.message.reply_text("🔄 Запуск ручной публикации новостей...")
    
    try:
        await process_news()
        await update.message.reply_text("✅ Ручная публикация новостей завершена!")
    except Exception as e:
        error_message = f"❌ Ошибка при публикации: {str(e)}"
        logger.error(error_message)
        await update.message.reply_text(error_message)

def run_bot():
    """Run the bot"""
    try:
        # Создаем папку для логов, если её нет
        if not os.path.exists('logs'):
            os.makedirs('logs')
            
        # Настраиваем логирование
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs/bot.log', 'w', encoding='utf-8'),
                logging.StreamHandler()  # Добавляем вывод в консоль
            ]
        )
        
        logger.info("Starting bot...")
        
        asyncio.run(init_bot())
        
    except Exception as e:
        logger.error(f"Критическая ошибка при запуске бота: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    run_bot()
