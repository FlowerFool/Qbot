import os
import asyncio
import logging
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from config import API_TOKEN
from database.db import init_db
from handlers import combined_handlers, admin_handlers, ai_handlers, payment_handlers
from utils.middleware import SubscriptionMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===== Startup / Shutdown =====
async def on_startup():
    await init_db()
    logger.info("✅ Бот запущен!")

async def on_shutdown(bot: Bot):
    await bot.session.close()
    logger.info("🛑 Бот остановлен.")

# ===== Main =====
async def main():
    bot = Bot(
        token=API_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Подключаем middleware отдельно для сообщений и callback
    dp.message.middleware(SubscriptionMiddleware())
    dp.callback_query.middleware(SubscriptionMiddleware())

    # Регистрация хендлеров
    combined_handlers.register_handlers(dp)
    admin_handlers.register_admin_handlers(dp)
    ai_handlers.register_handlers(dp)
    payment_handlers.register_handlers(dp)

    await on_startup()

    # Поллинг
    while True:
        try:
            logger.info("▶️ Запуск поллинга...")
            await dp.start_polling(bot)
        except asyncio.CancelledError:
            logger.info("⚠️ Поллинг был отменён.")
            break
        except KeyboardInterrupt:
            logger.info("🛑 Остановка бота по Ctrl+C")
            break
        except Exception as e:
            logger.error(f"❌ Ошибка сети: {e}")
            await asyncio.sleep(5)
            logger.info("♻️ Перезапуск бота...")
        finally:
            await on_shutdown(bot)
            break

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен вручную")
