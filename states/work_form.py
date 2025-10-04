from aiogram.fsm.state import StatesGroup, State

class WorkForm(StatesGroup):
    title = State()
    description = State()
    price = State()
    category = State()
    preview_image = State()
    files = State()
    requisites = State()
    confirm = State()
