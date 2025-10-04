from aiogram import types, F, Router, Dispatcher
import re
from config import ADMIN_IDS
from database.queries import get_purchase_info, update_purchase_status, get_work_info, get_work_files, update_balance
from aiogram.types import Message
from aiogram import Bot

router = Router()

def register_handlers(dp: Dispatcher):
    dp.include_router(router)

# Обработка SMS уведомлений о платежах (код 900)
@router.message(F.text.contains("900"))
async def process_payment_sms(message: Message, bot: Bot):
    if message.from_user.id != ADMIN_IDS and not message.forward_from:
        return
    purchase_id_match = re.search(r'[A-Fa-f0-9]{8}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{12}', message.text)
    if not purchase_id_match:
        return
    purchase_id = purchase_id_match.group(0)
    purchase_info = await get_purchase_info(purchase_id)
    if not purchase_info:
        await message.answer("❌ Покупка с указанным ID не найдена.")
        return
    purchase_id, work_id, buyer_id, amount, status, payment_proof = purchase_info
    if status == 'completed':
        await message.answer("✅ Эта покупка уже была обработана ранее.")
        return
    await update_purchase_status(purchase_id, 'completed', message.text)
    work_info = await get_work_info(work_id)
    if work_info:
        work_id, title, description, price, author_income, category, subcategory, username, user_id, preview_image_id, times_sold, total_earnings = work_info
        await update_balance(user_id, author_income)
        files = await get_work_files(work_id)
        for file_id, file_name in files:
            await bot.send_document(buyer_id, file_id, caption=f"📎 {file_name}")
        await bot.send_message(buyer_id, f"✅ Оплата получена! Работа \"{title}\" теперь доступна для вас.")
        await bot.send_message(user_id, f"✅ Ваша работа \"{title}\" была продана за {price} руб. На ваш баланс зачислено {author_income} руб.")
    await message.answer(f"✅ Покупка {purchase_id} обработана. Файлы отправлены покупателю.")
