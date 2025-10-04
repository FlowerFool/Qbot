from aiogram.fsm.context import FSMContext

async def cancel_work_if_active(state: FSMContext):
    """
    Сбрасывает FSM для размещения работы, если она активна
    """
    current = await state.get_state()
    if current is not None and current.startswith("WorkForm"):
        await state.clear()
