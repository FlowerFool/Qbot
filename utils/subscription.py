from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import CHANNEL_ID


async def check_subscription(user_id: int, bot: Bot) -> bool:
    """
    Проверяет, подписан ли пользователь на канал.
    """
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception:
        return False


def get_subscribe_keyboard() -> InlineKeyboardMarkup:
    """
    Кнопка для подписки на канал.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
            InlineKeyboardButton(text="📢 Подписаться", url=f"https://t.me/{CHANNEL_ID.lstrip('@')}"),
            InlineKeyboardButton(text="✅ Я подписан", callback_data="subscribed")
            ]
        ]
    )
