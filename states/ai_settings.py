from aiogram.fsm.state import StatesGroup, State

class AdminActions(StatesGroup):
    ai_settings_provider = State()
    ai_settings_model = State()
    ai_settings_api_key = State()
    ai_settings_api_url = State()
    ai_settings_temperature = State()
    ai_settings_max_tokens = State()
    ai_test_generation = State()
