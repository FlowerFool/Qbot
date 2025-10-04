from aiogram import types, F, Dispatcher
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

async def start_user(message: types.Message):
    text = "👋 Привет! Я бот Qentacle.\nВыберите действие:"

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📂 Каталог", callback_data="menu_catalog")],
            [InlineKeyboardButton(text="➕ Разместить работу", callback_data="add_work")],
            [InlineKeyboardButton(text="💰 Баланс", callback_data="menu_balance")],
            [InlineKeyboardButton(text="🤖 AI Управление", callback_data="menu_ai")]
        ]
    )

    await message.answer(text, reply_markup=keyboard)

def register_user_handlers(dp: Dispatcher):
    dp.message.register(start_user, F.text == "/start")
