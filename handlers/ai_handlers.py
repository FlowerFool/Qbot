from aiogram import types, Router, Dispatcher
from aiogram.fsm.context import FSMContext
from states.ai_settings import AdminActions
from database.queries import save_ai_settings, get_ai_settings

router = Router()

def register_handlers(dp: Dispatcher):
    dp.include_router(router)

# Здесь можно добавить полноценные FSM обработчики для настройки AI
