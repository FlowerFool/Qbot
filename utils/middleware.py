from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from utils.subscription import check_subscription, get_subscribe_keyboard

class SubscriptionMiddleware(BaseMiddleware):
    """
    Middleware блокирует неподписанных пользователей.
    """

    async def __call__(self, handler, event, data):
        bot = data.get("bot")
        if not bot:
            return await handler(event, data)

        user_id = None
        if isinstance(event, Message) or isinstance(event, CallbackQuery):
            user_id = event.from_user.id

        if user_id is not None:
            subscribed = await check_subscription(user_id, bot)
            if not subscribed:
                text = "❌ Чтобы пользоваться ботом, подпишитесь на канал!"
                keyboard = get_subscribe_keyboard()
                if isinstance(event, Message):
                    await event.answer(text, reply_markup=keyboard)
                elif isinstance(event, CallbackQuery):
                    await event.message.answer(text, reply_markup=keyboard)
                    await event.answer()  # закрываем всплывающее окно callback
                return  # блокируем дальнейшую обработку

        return await handler(event, data)
