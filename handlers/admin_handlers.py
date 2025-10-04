from aiogram import Dispatcher, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from config import ADMIN_IDS, CHANNEL_ID
from services.work_service import (
    add_category, get_categories, delete_category, get_pending_works, get_work_info,
    approve_work, reject_work, get_work_files, update_work_title, update_work_description,
    get_users_count, get_works_count, get_payout_requests, get_total_users_count,
    get_category_sales_count, update_work_category, admin_delete_work
)
from handlers.combined_handlers import get_main_menu, add_message_id, delete_previous_messages
from database import queries

# ===== FSM =====
class CategoryForm(StatesGroup):
    parent_id = State()
    name = State()

class EditWorkForm(StatesGroup):
    new_title = State()
    new_description = State()

class EditPreviewForm(StatesGroup):
    waiting_for_photo = State()

# ===== Проверка админа =====
def is_admin(user_id: int):
    return user_id in ADMIN_IDS

# ===== Вспомогательная функция удаления сообщений =====
async def delete_bot_messages(chat: types.Chat, msg_ids: list[int]):
    for msg_id in msg_ids:
        try:
            await chat.delete_message(msg_id)
        except:
            pass
            
# ===== Удаление success-сообщения =====
async def delete_success_message(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    success_msg_id = data.get("success_msg_id")
    if success_msg_id:
        try:
            await callback.message.chat.delete_message(success_msg_id)
        except:
            pass
        await state.update_data(success_msg_id=None)

# ===== Админ-панель =====
async def admin_panel_handler(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    await delete_success_message(callback, state)
    await delete_previous_messages(callback, state)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📂 Категории", callback_data="admin_categories")],
        [InlineKeyboardButton(text="📝 Проверка работ", callback_data="admin_pending_works")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="🦧 Заявки на выплату", callback_data="admin_payouts")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="to_main_menu")]
    ])
    photo = FSInputFile("image/admin.jpg")
    msg = await callback.message.answer_photo(photo=photo, caption="⚙️ <b>Админ-панель</b>", reply_markup=keyboard)
    await state.update_data(last_msg_ids=[msg.message_id])

# ===== Работа с категориями =====
async def admin_categories_handler(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    await delete_success_message(callback, state)
    await delete_previous_messages(callback, state)

    categories = await get_categories()
    keyboard_buttons = []

    # Разделяем категории и подкатегории
    main_categories = [c for c in categories if c[2] is None]
    subcategories = [c for c in categories if c[2] is not None]

    for cat_id, cat_name, _ in main_categories:
        # Добавляем основную категорию
        keyboard_buttons.append([
            InlineKeyboardButton(text=f"❌ {cat_name}", callback_data=f"delete_category_{cat_id}")
        ])

        # Находим подкатегории этой категории
        for sub_id, sub_name, parent_id in subcategories:
            if parent_id == cat_id:
                keyboard_buttons.append([
                    InlineKeyboardButton(text=f"   ↳ {sub_name}", callback_data=f"delete_category_{sub_id}")
                ])

    # Кнопки управления
    keyboard_buttons.append([InlineKeyboardButton(text="➕ Добавить категорию / подкатегорию", callback_data="add_category")])
    keyboard_buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_panel")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    msg = await callback.message.answer("📂 Список категорий и подкатегорий:", reply_markup=keyboard)
    await state.update_data(last_msg_ids=[msg.message_id])

async def delete_category_handler(callback: types.CallbackQuery, state: FSMContext):
    await delete_success_message(callback, state)
    cat_id = int(callback.data.split("_")[-1])
    await delete_category(cat_id)
    await admin_categories_handler(callback, state)

# ===== Добавление категории =====
async def add_category_start(callback: types.CallbackQuery, state: FSMContext):
    await delete_success_message(callback, state)

    categories = await get_categories()
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Без родителя", callback_data="parent_none")]
        ] + [
            [InlineKeyboardButton(text=name, callback_data=f"parent_{cat_id}")]
            for cat_id, name, parent_id in categories if parent_id is None
        ]
    )
    keyboard.inline_keyboard.append([InlineKeyboardButton(text=name, callback_data=f"parent_{cat_id}")])

    msg = await callback.message.answer("Выберите родительскую категорию (или 'Без родителя'):", reply_markup=keyboard)
    await state.update_data(temp_msg_id=msg.message_id)
    await state.set_state(CategoryForm.parent_id)

async def add_category_parent(callback: types.CallbackQuery, state: FSMContext):
    await delete_success_message(callback, state)

    parent_id = None if callback.data == "parent_none" else int(callback.data.split("_")[1])
    await state.update_data(parent_id=parent_id)

    msg = await callback.message.answer("Введите название новой категории / подкатегории:")
    data = await state.get_data()
    temp_msg_id = data.get("temp_msg_id")
    if temp_msg_id:
        try:
            await callback.message.chat.delete_message(temp_msg_id)
        except:
            pass
    await state.update_data(temp_msg_id=msg.message_id)
    await state.set_state(CategoryForm.name)

async def add_category_save(message: types.Message, state: FSMContext):
    data = await state.get_data()
    parent_id = data.get("parent_id")
    name = message.text.strip()
    await add_category(name, parent_id)

    temp_msg_id = data.get("temp_msg_id")
    if temp_msg_id:
        try:
            await message.chat.delete_message(temp_msg_id)
        except:
            pass

    last_msg_ids = data.get("last_msg_ids", [])
    await delete_bot_messages(message.chat, last_msg_ids)

    msg = await message.answer("✅ Категория / подкатегория успешно добавлена.")
    await state.update_data(last_msg_ids=[msg.message_id], success_msg_id=msg.message_id)
    await state.clear()

    fake_callback = types.CallbackQuery(id="0", from_user=message.from_user, chat_instance="0", message=message, data="admin_categories")
    await admin_categories_handler(fake_callback, state)

# ===== Модерация работ =====
async def admin_pending_works(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    await delete_success_message(callback, state)
    await delete_previous_messages(callback, state)

    works = await get_pending_works()
    if not works:
        msg = await callback.message.answer(
            "❌ Нет работ на проверку",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏠 Главное меню", callback_data="to_main_menu")]])
        )
        await state.update_data(last_msg_ids=[msg.message_id])
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for work_id, title, author_id in works:
        keyboard.inline_keyboard.append([InlineKeyboardButton(text=f"{title}", callback_data=f"review_{work_id}")])
    keyboard.inline_keyboard.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data="to_main_menu")])

    msg = await callback.message.answer("📝 Работы на проверку:", reply_markup=keyboard)
    await state.update_data(last_msg_ids=[msg.message_id])

# ===== Кнопки категорий =====
def generate_all_category_buttons(categories: list[tuple], work_id: int) -> InlineKeyboardMarkup:
    buttons = []

    # Разделяем категории
    main_categories = [c for c in categories if c[2] is None]
    subcategories = [c for c in categories if c[2] is not None]

    for cat_id, cat_name, _ in main_categories:
        # Основная категория
        buttons.append([
            InlineKeyboardButton(
                text=f"{cat_name}",
                callback_data=f"set_category_{work_id}_{cat_id}"
            )
        ])

        # Подкатегории этой категории
        for sub_id, sub_name, parent_id in subcategories:
            if parent_id == cat_id:
                buttons.append([
                    InlineKeyboardButton(
                        text=f"   ↳ {sub_name}",
                        callback_data=f"set_category_{work_id}_{sub_id}"
                    )
                ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ===== Работа с конкретной работой =====
async def review_work(callback: types.CallbackQuery, state: FSMContext, page: int = 0, work_id: int | None = None):
    await delete_previous_messages(callback, state)

    if work_id is None:
        try:
            work_id = int(callback.data.split("_")[-1])
        except:
            await callback.answer("❌ Ошибка данных, попробуйте снова", show_alert=True)
            return

    work_info = await get_work_info(work_id)
    if not work_info:
        await callback.answer("❌ Работа не найдена", show_alert=True)
        return

    _, title, description, price, _, _, _, author_id, preview_image_id, _, _, status = work_info
    admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Удалить работу", callback_data=f"admin_delete_{work_id}")],
        [InlineKeyboardButton(text="✏️ Изменить название", callback_data=f"edit_title_{work_id}")],
        [InlineKeyboardButton(text="📝 Изменить описание", callback_data=f"edit_description_{work_id}")],
         [InlineKeyboardButton(text="🖼 Изменить превью", callback_data=f"edit_preview:{work_id}")],
        [InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_{work_id}")],
        [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{work_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="go_back_pending")]
    ])

    caption_text = f"🔹 <b>{title}</b>\n📄 {description}\n💰 Цена: {price} RUB\nСтатус: {status}"

    try:
        if preview_image_id:
            if preview_image_id.startswith(("AgAC", "BQAC")):
                msg = await callback.message.answer_photo(photo=preview_image_id, caption=caption_text, reply_markup=admin_keyboard)
            else:
                photo = FSInputFile(preview_image_id)
                msg = await callback.message.answer_photo(photo=photo, caption=caption_text, reply_markup=admin_keyboard)
        else:
            photo = FSInputFile("image/catalog.jpg")
            msg = await callback.message.answer_photo(photo=photo, caption=caption_text, reply_markup=admin_keyboard)
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка при отправке превью: {e}")
        return

    await state.update_data(last_msg_ids=[msg.message_id])

    try:
        files = await get_work_files(work_id)
        for file_id, _ in files:
            if file_id.startswith(("AgAC", "BQAC")):
                file_msg = await callback.message.answer_document(file_id)
                last_ids = (await state.get_data()).get("last_msg_ids", [])
                last_ids.append(file_msg.message_id)
                await state.update_data(last_msg_ids=last_ids)
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка при отправке файлов работы: {e}")

    categories = await get_categories()
    category_keyboard = generate_all_category_buttons(categories, work_id)
    try:
        category_msg = await callback.message.answer("📂 Выберите категорию для работы:", reply_markup=category_keyboard)
        last_ids = (await state.get_data()).get("last_msg_ids", [])
        last_ids.append(category_msg.message_id)
        await state.update_data(last_msg_ids=last_ids)
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка при отправке клавиатуры категорий: {e}")

# ===== Обработчик перехода по страницам категорий =====
async def category_page_handler(callback: types.CallbackQuery, state: FSMContext):
    try:
        parts = callback.data.split("_")
        work_id = int(parts[2])
        page = int(parts[3])
    except Exception:
        await callback.answer("❌ Ошибка данных, попробуйте снова", show_alert=True)
        return
    await review_work(callback, state, page=page, work_id=work_id)

# ===== Подкатегории =====
async def show_subcategories(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    work_id, category_id = int(parts[2]), int(parts[3])
    categories = await get_categories()
    subcategories = [cat for cat in categories if cat[2] == category_id]

    buttons = [[InlineKeyboardButton(text=f"↳ {sub_name}", callback_data=f"set_category_{work_id}_{sub_id}")] for sub_id, sub_name, _ in subcategories]
    buttons.append([InlineKeyboardButton(text="⬅️ Назад к категориям", callback_data=f"review_{work_id}")])
    buttons += [
        [InlineKeyboardButton(text="✏️ Изменить название", callback_data=f"edit_title_{work_id}")],
        [InlineKeyboardButton(text="📝 Изменить описание", callback_data=f"edit_description_{work_id}")],
        [InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_{work_id}")],
        [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{work_id}")]
    ]
    await callback.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

# ===== Назначение категории =====
async def set_work_category(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    work_id, category_id = int(parts[2]), int(parts[3])
    await update_work_category(work_id, category_id)
    await callback.answer("✅ Категория успешно назначена")

# ===== Редактирование работы =====
async def start_edit_title(callback: types.CallbackQuery, state: FSMContext):
    work_id = int(callback.data.split("_")[-1])
    await state.update_data(work_id=work_id)
    msg = await callback.message.answer("✏️ Введите новое название для работы:")
    last_ids = (await state.get_data()).get("last_msg_ids", [])
    last_ids.append(msg.message_id)
    await state.update_data(last_msg_ids=last_ids)
    await state.set_state(EditWorkForm.new_title)

async def save_new_title(message: types.Message, state: FSMContext):
    data = await state.get_data()
    work_id = data.get("work_id")
    await update_work_title(work_id, message.text.strip())
    await delete_bot_messages(message.chat, data.get("last_msg_ids", []))
    await state.clear()
    fake_callback = types.CallbackQuery(id="0", from_user=message.from_user, chat_instance="0", message=message, data=f"review_{work_id}")
    await review_work(fake_callback, state)

async def start_edit_description(callback: types.CallbackQuery, state: FSMContext):
    work_id = int(callback.data.split("_")[-1])
    await state.update_data(work_id=work_id)
    msg = await callback.message.answer("📝 Введите новое описание работы:")
    last_ids = (await state.get_data()).get("last_msg_ids", [])
    last_ids.append(msg.message_id)
    await state.update_data(last_msg_ids=last_ids)
    await state.set_state(EditWorkForm.new_description)

async def save_new_description(message: types.Message, state: FSMContext):
    data = await state.get_data()
    work_id = data.get("work_id")
    await update_work_description(work_id, message.text.strip())
    await delete_bot_messages(message.chat, data.get("last_msg_ids", []))
    await state.clear()
    fake_callback = types.CallbackQuery(id="0", from_user=message.from_user, chat_instance="0", message=message, data=f"review_{work_id}")
    await review_work(fake_callback, state)

from config import CHANNEL_ID  # импортируем из конфига

from config import CHANNEL_ID  # импортируем из конфига

# ===== Одобрение / отклонение =====
async def approve_work_handler(callback: types.CallbackQuery, state: FSMContext):
    work_id = int(callback.data.split("_")[-1])
    work_info = await get_work_info(work_id)
    if not work_info:
        await callback.answer("❌ Работа не найдена", show_alert=True)
        return

    # Берём только нужные поля
    title = work_info[1]
    description = work_info[2]
    price = work_info[3]
    photo_file_id = work_info[8]

    # Одобряем работу
    await approve_work(work_id)

    # Формируем текст для канала
    channel_text = f"🔹 {title}\n📄 {description}\n💰 Цена: {price} RUB"

    # Отправляем в канал с фото
    try:
        if photo_file_id:
            await callback.message.bot.send_photo(chat_id=CHANNEL_ID, photo=photo_file_id, caption=channel_text)
        else:
            await callback.message.bot.send_message(chat_id=CHANNEL_ID, text=channel_text)
    except Exception as e:
        print(f"Ошибка при отправке в канал: {e}")

    await callback.answer("✅ Работа одобрена")
    await admin_pending_works(callback, state)

async def reject_work_handler(callback: types.CallbackQuery, state: FSMContext):
    work_id = int(callback.data.split("_")[-1])
    work_info = await get_work_info(work_id)
    if not work_info:
        await callback.answer("❌ Работа не найдена", show_alert=True)
        return
    _, title, *_ , author_id, _, _ = work_info
    await reject_work(work_id)
    try: await callback.message.bot.send_message(author_id, f"❌ Ваша работа '{title}' отклонена администратором.")
    except: pass
    last_ids = (await state.get_data()).get("last_msg_ids", [])
    await delete_bot_messages(callback.message.chat, last_ids)
    await state.update_data(last_msg_ids=[])
    await callback.answer("❌ Работа отклонена")
    await admin_pending_works(callback, state)

# Кнопка для вызова изменения картинки
async def ask_change_preview(callback: types.CallbackQuery, state: FSMContext):
    work_id = int(callback.data.split(":")[1])
    await state.update_data(work_id=work_id)
    await state.set_state(EditPreviewForm.waiting_for_photo)

    # Удаляем предыдущие сообщения, чтобы не оставалось "старых"
    last_msg_ids = (await state.get_data()).get("last_msg_ids", [])
    await delete_bot_messages(callback.message.chat, last_msg_ids)
    
    msg = await callback.message.answer("📸 Отправьте новое превью (фото) для этой работы.")
    await state.update_data(last_msg_ids=[msg.message_id])

# Приём новой картинки
async def change_preview(message: types.Message, state: FSMContext):
    if not message.photo:
        await message.answer("❌ Пожалуйста, отправьте фото.")
        return

    data = await state.get_data()
    work_id = data.get("work_id")

    new_preview_id = message.photo[-1].file_id
    await queries.update_work_preview(work_id, new_preview_id)

    # Удаляем все предыдущие сообщения
    last_msg_ids = data.get("last_msg_ids", [])
    await delete_bot_messages(message.chat, last_msg_ids)

    await state.clear()  # очищаем состояние после изменения

    # Показываем обновлённое меню работы с новым превью
    fake_callback = types.CallbackQuery(
        id="0",
        from_user=message.from_user,
        chat_instance="0",
        message=message,
        data=f"review_{work_id}"
    )
    await review_work(fake_callback, state)

# ===== Прочее =====
async def go_back_to_pending(callback: types.CallbackQuery, state: FSMContext):
    last_ids = (await state.get_data()).get("last_msg_ids", [])
    await delete_bot_messages(callback.message.chat, last_ids)
    await state.update_data(last_msg_ids=[])
    await admin_pending_works(callback, state)

async def go_to_main_menu(callback: types.CallbackQuery, state: FSMContext):
    await delete_previous_messages(callback, state)
    menu = get_main_menu(callback.from_user.id)
    photo = FSInputFile("image/welcome.jpg")
    msg = await callback.message.answer_photo(photo=photo, caption="📚 Главное меню. Выберите действие ниже 👇", reply_markup=menu)
    await add_message_id(msg, state)
    await callback.answer()

async def admin_stats_handler(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await delete_previous_messages(callback, state)
    categories = await get_categories()
    text = "📊 <b>Статистика по категориям</b>\n\n"
    for cat_id, cat_name, _ in categories:
        users_count = await get_users_count(cat_id)
        works_count = await get_works_count(cat_id)
        sales_count = await get_category_sales_count(cat_id)
        text += f"📂 <b>{cat_name}</b>\n 👥 Пользователи: {users_count}\n 📝 Всего работ: {works_count}\n 🛒 Куплено работ: {sales_count}\n\n"
    text += f"👤 <b>Всего пользователей бота:</b> {await get_total_users_count()}\n"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_panel")]])
    msg = await callback.message.answer(text, reply_markup=keyboard)
    await state.update_data(last_msg_ids=[msg.message_id])

async def admin_payouts_handler(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await delete_previous_messages(callback, state)
    requests = await get_payout_requests()
    if not requests:
        msg = await callback.message.answer("❌ Нет заявок на выплату", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_panel")]]))
        await state.update_data(last_msg_ids=[msg.message_id])
        return
    text = "💰 <b>Заявки на выплату</b>\n\n"
    for user_id, amount in requests: text += f"🔹 Пользователь: {user_id} | Сумма: {amount} RUB\n"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_panel")]])
    msg = await callback.message.answer(text, reply_markup=keyboard)
    await state.update_data(last_msg_ids=[msg.message_id])

async def admin_delete_work_handler(callback: types.CallbackQuery, state: FSMContext):
    work_id = int(callback.data.split("_")[-1])
    
    data = await state.get_data()
    last_msg_ids = data.get("last_msg_ids", [])
    await admin_delete_work(work_id)
    await delete_bot_messages(callback.message.chat, last_msg_ids)
    msg = await callback.message.answer("✅ Работа успешно удалена.")


    await state.update_data(last_msg_ids=[msg.message_id], success_msg_id=msg.message_id)
    fake_callback = types.CallbackQuery(
        id="0", from_user=callback.from_user, chat_instance="0",
        message=callback.message, data="admin_pending_works"
    )
    await admin_pending_works(fake_callback, state)

# ===== Регистрация обработчиков =====
def register_admin_handlers(dp: Dispatcher):
    dp.callback_query.register(ask_change_preview, lambda c: c.data.startswith("edit_preview:"))
    dp.message.register(change_preview, EditPreviewForm.waiting_for_photo)
    dp.callback_query.register(admin_delete_work_handler, F.data.startswith("admin_delete_"))
    dp.callback_query.register(admin_panel_handler, F.data == "admin_panel")
    dp.callback_query.register(admin_pending_works, F.data == "admin_pending_works")
    dp.callback_query.register(review_work, F.data.startswith("review_"))
    dp.callback_query.register(set_work_category, F.data.startswith("set_category_"))
    dp.callback_query.register(start_edit_title, F.data.startswith("edit_title_"))
    dp.message.register(save_new_title, EditWorkForm.new_title)
    dp.callback_query.register(start_edit_description, F.data.startswith("edit_description_"))
    dp.message.register(save_new_description, EditWorkForm.new_description)
    dp.callback_query.register(category_page_handler, F.data.startswith("category_page_"))
    dp.callback_query.register(approve_work_handler, F.data.startswith("approve_"))
    dp.callback_query.register(reject_work_handler, F.data.startswith("reject_"))
    dp.callback_query.register(go_back_to_pending, F.data == "go_back_pending")
    dp.callback_query.register(go_to_main_menu, F.data == "to_main_menu")
    dp.callback_query.register(admin_categories_handler, F.data == "admin_categories")
    dp.callback_query.register(delete_category_handler, F.data.startswith("delete_category_"))
    dp.callback_query.register(add_category_start, F.data == "add_category")
    dp.message.register(add_category_save, CategoryForm.name)
    dp.callback_query.register(add_category_parent, F.data.startswith("parent_"))
    dp.callback_query.register(admin_stats_handler, F.data == "admin_stats")
    dp.callback_query.register(admin_payouts_handler, F.data == "admin_payouts")
    dp.callback_query.register(show_subcategories, F.data.startswith("show_subcats_"))
