from aiogram import Dispatcher, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, Message
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from config import ADMIN_IDS, DB_NAME
from utils.subscription import check_subscription
from services.work_service import (
    get_categories,
    get_subcategories,
    get_works,
    delete_work,
    get_user_balance,
    save_work,
    get_author_stats,
    get_user_purchases,
    add_category,
    delete_category,
    get_pending_works,
    get_work_info,
    approve_work,
    reject_work,
    get_work_files,
    update_work_title,
    get_categories_with_subcategories,
    update_work_description
)
from database.queries import (
    get_user,
    create_purchase,
    update_balance,
    complete_purchase
)
from aiosqlite import connect

# ===== Состояния =====
class WorkForm(StatesGroup):
    category = State()
    title = State()
    description = State()
    price = State()
    preview = State()
    files = State()
    confirm = State()

class EditWorkForm(StatesGroup):
    new_title = State()
    new_description = State()

class CategoryForm(StatesGroup):
    name = State()

class DepositForm(StatesGroup):
    amount = State()

# ===== Вспомогательные функции =====
def is_admin(user_id: int):
    return user_id in ADMIN_IDS

async def add_message_id(msg, state: FSMContext):
    data = await state.get_data()
    last_msg_ids = data.get("last_msg_ids", [])
    last_msg_ids.append(msg.message_id)
    await state.update_data(last_msg_ids=last_msg_ids)

async def delete_previous_messages(callback_or_message, state: FSMContext):
    data = await state.get_data()
    last_msg_ids = data.get("last_msg_ids", [])
    bot = callback_or_message.bot
    chat_id = callback_or_message.from_user.id
    for msg_id in last_msg_ids:
        try:
            await bot.delete_message(chat_id, msg_id)
        except:
            pass
    await state.update_data(last_msg_ids=[])

async def delete_bot_messages(chat: types.Chat, msg_ids: list[int]):
    for msg_id in msg_ids:
        try:
            await chat.delete_message(msg_id)
        except:
            pass

async def go_main_from_success(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.message.delete()
    except:
        pass
    await main_menu(callback, state)

async def go_main_from_error(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.message.delete()
    except:
        pass
    await main_menu(callback, state)

async def subscribed_callback_handler(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    bot = callback.bot

    # Проверяем подписку
    is_subscribed = await check_subscription(user_id, bot)
    if is_subscribed:
        # Удаляем сообщение с кнопкой подписки
        try:
            await callback.message.delete()
        except:
            pass
        # Показываем главное меню
        await main_menu(callback, state)
    else:
        # Пользователь нажал "Я подписан", но реально не подписан
        await callback.answer("❌ Вы ещё не подписались на канал!", show_alert=True)

# ===== Меню =====
def get_main_menu(user_id: int):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📂 Каталог работ", callback_data="catalog")],
        [InlineKeyboardButton(text="➕ Разместить работу", callback_data="add_work")],
        [InlineKeyboardButton(text="🎩 Профиль", callback_data="profile_menu")]  # <- здесь
    ])
    if user_id in ADMIN_IDS:
        keyboard.inline_keyboard.append([InlineKeyboardButton(text="🪢 Настройки публикации", callback_data="ai_settings")])
        keyboard.inline_keyboard.append([InlineKeyboardButton(text="⚙️ Админ-панель", callback_data="admin_panel")])
    return keyboard

def get_profile_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Пополнить баланс", callback_data="profile_deposit")],
        [InlineKeyboardButton(text="🏦 Заявка на выплату", callback_data="profile_withdraw_request")],
        [InlineKeyboardButton(text="💰 Баланс", callback_data="profile_balance")],
        [InlineKeyboardButton(text="📝 Мои работы", callback_data="profile_works")],
        [InlineKeyboardButton(text="🛒 Мои покупки", callback_data="profile_purchases")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
    ])

# ===== Главное меню =====
async def start(message: types.Message, state: FSMContext):
    await delete_previous_messages(message, state)
    await state.clear()
    menu = get_main_menu(message.from_user.id)
    photo = FSInputFile("image/welcome.jpg")
    msg = await message.answer_photo(
        photo=photo,
        caption="📚 Здесь вы можете размещать и покупать учебные работы.\n\nВыберите действие ниже 👇",
        reply_markup=menu
    )
    await add_message_id(msg, state)

async def main_menu(callback_or_message, state: FSMContext):
    await delete_previous_messages(callback_or_message, state)
    await state.clear()
    if isinstance(callback_or_message, types.CallbackQuery):
        chat_id = callback_or_message.from_user.id
        menu = get_main_menu(chat_id)
        photo = FSInputFile("image/welcome.jpg")
        msg = await callback_or_message.message.answer_photo(
            photo=photo,
            caption="📚 Главное меню. Выберите действие ниже 👇",
            reply_markup=menu
        )
        await add_message_id(msg, state)
        await callback_or_message.answer()
    else:
        await start(callback_or_message, state)

# ===== Пополнение баланса =====
async def deposit_handler(message: Message, state: FSMContext):
    user_id = message.from_user.id

    user = await get_user(user_id)
    if not user:
        await message.answer("❌ Пользователь не найден. Сначала используйте /start")
        return

    await message.answer("💰 Введите сумму для пополнения баланса (RUB):")
    await state.set_state(DepositForm.amount)

# ===== Состояние для пополнения баланса =====
async def deposit_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите корректное число больше 0.")
        return

    user_id = message.from_user.id
    await update_balance(user_id, amount)

    # Кнопка Главное меню
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
    ])
    msg = await message.answer(f"✅ Баланс успешно пополнен на {amount} RUB.", reply_markup=keyboard)

    # Сохраняем ID сообщений
    await add_message_id(message, state)  # сообщение с суммой
    await add_message_id(msg, state)      # сообщение с ✅

# ===== Каталог =====
async def catalog_handler(callback: types.CallbackQuery, state: FSMContext):
    await delete_previous_messages(callback, state)

    categories = await get_categories_with_subcategories()

    if not categories:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]]
        )
        msg = await callback.message.answer("📂 Каталог пуст.", reply_markup=keyboard)
        await add_message_id(msg, state)
        return

    # показываем только верхние категории
    keyboard_buttons = [
        [InlineKeyboardButton(text=name, callback_data=f"category_{cat_id}_1_root")]
        for cat_id, name, subcats in categories
        if not any(sc for sc in subcats) or True  # просто все верхние
    ]

    # Главное меню
    keyboard_buttons.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    photo = FSInputFile("image/catalog.jpg")
    msg = await callback.message.answer_photo(
        photo=photo,
        caption="📂 <b>Каталог работ</b>\n\nВыберите категорию:",
        reply_markup=keyboard
    )
    await add_message_id(msg, state)
    await callback.answer()

async def category_handler(callback: types.CallbackQuery, state: FSMContext):
    await delete_previous_messages(callback, state)

    parts = callback.data.split("_")
    category_id = int(parts[1])
    page = int(parts[2]) if len(parts) > 2 else 1
    is_root = len(parts) > 3 and parts[3] == "root"

    # Получаем подкатегории
    subcategories = await get_subcategories(category_id)

    if subcategories:  # если есть подкатегории
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=sub_name, callback_data=f"category_{sub_id}_1")]
                for sub_id, sub_name in subcategories
            ] + [
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="catalog")],
            ]
        )
        msg = await callback.message.answer(f"📂 Подкатегории:", reply_markup=keyboard)
        await add_message_id(msg, state)
        await callback.answer()
        return

    # Если подкатегорий нет — показываем работы
    works = await get_works(category_id)
    if not works:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="catalog")],
                             [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]]
        )
        photo = FSInputFile("image/catalog.jpg")
        msg = await callback.message.answer_photo(
            photo=photo,
            caption="❌ В этой категории пока нет работ.",
            reply_markup=keyboard
        )
        await add_message_id(msg, state)
        return

    # Постраничный вывод — оставляем как есть
    page_size = 3
    total_pages = max((len(works) + page_size - 1) // page_size, 1)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    current_works = works[start_idx:end_idx]

    for work in current_works:
        work_id, title, description, price, author_income, cat_id, subcategory_id, author_id, preview_image_id = work
        if not preview_image_id:
            continue
        caption = f"🔹 <b>{title}</b>\n📄 {description}\n💰 Цена: {price} RUB\n"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🛒 Купить", callback_data=f"buy_work_{work_id}")]])
        msg = await callback.message.answer_photo(photo=preview_image_id, caption=caption, reply_markup=keyboard)
        await add_message_id(msg, state)

    # Навигация между страницами
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"category_{category_id}_{page-1}"))
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton(text="➡️ Вперед", callback_data=f"category_{category_id}_{page+1}"))
    nav_buttons.append(InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu"))
    nav_keyboard = InlineKeyboardMarkup(inline_keyboard=[nav_buttons])
    nav_msg = await callback.message.answer(f"📑 Страница {page} из {total_pages}", reply_markup=nav_keyboard)
    await add_message_id(nav_msg, state)
    await callback.answer()

# ===== Покупка работы =====
SERVICE_USER_ID = 1  # Сервисный аккаунт

async def buy_work_handler(callback: types.CallbackQuery):
    work_id = int(callback.data.split("_")[-1])
    buyer_id = callback.from_user.id

    # Получаем покупателя
    buyer = await get_user(buyer_id)
    if not buyer:
        await callback.answer("❌ Пользователь не найден.", show_alert=True)
        return

    # Получаем работу
    work = await get_work_info(work_id)
    if not work:
        await callback.answer("❌ Работа не найдена.", show_alert=True)
        return

    price = work['price'] if isinstance(work, dict) else work[3]
    author_id = work['author_id'] if isinstance(work, dict) else work[7]

    # Проверка баланса покупателя
    buyer_balance = buyer[2]  # balance — третий столбец
    if buyer_balance < price:
        await callback.answer("❌ Недостаточно средств на балансе.", show_alert=True)
        return

    # Создаем запись о покупке
    purchase_id = await create_purchase(work_id, buyer_id, price)

    # Распределяем оплату между автором и сервисом
    author_share = price * 0.7
    service_share = price - author_share

    async with connect(DB_NAME) as db:
        await db.execute("UPDATE users SET balance = balance + ? WHERE id=?", (author_share, author_id))
        await db.execute("UPDATE users SET balance = balance + ? WHERE id=?", (service_share, SERVICE_USER_ID))
        await db.execute("UPDATE users SET balance = balance - ? WHERE id=?", (price, buyer_id))

        # Обновляем статистику работы
        await db.execute(
            "UPDATE works SET times_sold = times_sold + 1, total_earnings = total_earnings + ? WHERE id=?",
            (price, work_id)
        )
        # Отмечаем покупку как завершённую
        await db.execute("UPDATE purchases SET status='completed' WHERE id=?", (purchase_id,))
        await db.commit()

    await callback.answer(f"✅ Покупка успешна!\n💰 Автор получил {author_share} RUB\n🛠 Сервис: {service_share} RUB", show_alert=True)

# ===== Заявка на выплату  =====
async def withdraw_request_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()  # тихо подтверждает нажатие, без всплывающего окна

# ===== Профиль =====
async def profile_handler(callback: types.CallbackQuery, state: FSMContext):
    await delete_previous_messages(callback, state)
    user_id = callback.from_user.id
    text = ""
    keyboard = None  # по умолчанию

    if callback.data == "profile_menu":
        # Главное меню профиля
        text = "🎩 Профиль. Выберите действие:"
        keyboard = get_profile_menu()

    elif callback.data == "profile_balance":
        # Показ баланса и статистики
        balance = await get_user_balance(user_id)
        stats = await get_author_stats(user_id)
        total_earnings = sum(work['author_income'] * work['times_sold'] for work in stats['works'])
        text = (
            f"💰 Ваш текущий баланс: {balance} RUB\n\n"
            f"📊 Общая статистика:\n"
            f"Всего доход от работ: {total_earnings} RUB\n"
            f"Всего продаж: {stats['total_times_sold']}\n"
        )
        keyboard = get_profile_menu()

    elif callback.data == "profile_works":
        stats = await get_author_stats(user_id)
        if not stats['works']:
            text = "❌ Пока нет размещённых работ."
            keyboard = get_profile_menu()
        else:
            text = "📝 Ваши работы:\n"
            buttons = []
            for work in stats['works']:
                text += f"🔹 {work['title']} — {work['author_income']*work['times_sold']} RUB доход\n"
                buttons.append([InlineKeyboardButton(
                    text=f"❌ Удалить '{work['title']}'",
                    callback_data=f"delete:{work['id']}"
                )])
            buttons.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")])
            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    elif callback.data == "profile_purchases":
        purchases = await get_user_purchases(user_id)
        if not purchases:
            text = "❌ У вас пока нет купленных работ."
        else:
            text = "🛒 Мои покупки:\n"
            for p in purchases:
                text += (
                    f"🔹 {p['title']}\n"
                    f"💰 Цена: {p['price']} RUB\n"
                    f"👤 Автор: {p['author_name']}\n"
                    f"💳 Оплачено: {p['amount']} RUB\n"
                    f"📌 Статус: {p['status']}\n\n"
                )
        keyboard = get_profile_menu()

    elif callback.data == "profile_withdraw_request":
        await callback.answer()
        return

    elif callback.data == "profile_deposit":
        await delete_previous_messages(callback, state)  # удаляем старые сообщения
        await callback.answer()
        msg = await callback.message.answer("💰 Введите сумму для пополнения баланса (RUB):")
        await add_message_id(msg, state)  # сохраняем ID сообщения
        await state.set_state(DepositForm.amount)
        return  # обязательно выходим, чтобы не показывать фото профиля

    if keyboard is None:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])

    photo = FSInputFile("image/profile.jpg")
    msg = await callback.message.answer_photo(photo=photo, caption=text, reply_markup=keyboard)
    await add_message_id(msg, state)
    await callback.answer()

# ===== Удаление работы =====
async def delete_work_handler(callback: types.CallbackQuery, state: FSMContext):
    if not callback.data.startswith("delete:"):
        return

    try:
        work_id = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        await callback.answer("❌ Ошибка при получении ID работы.", show_alert=True)
        return

    user_id = callback.from_user.id
    # Удаляем работу
    success = await delete_work(work_id, user_id)
    if not success:
        await callback.answer("❌ Не удалось удалить работу.", show_alert=True)
        return

    # Обновляем меню "Мои работы"
    stats = await get_author_stats(user_id)
    works = stats['works']

    if not works:
        text = "❌ Пока нет размещённых работ."
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
        ])
    else:
        text = "📝 Ваши работы:\n"
        keyboard_buttons = []
        for work in works:
            text += f"🔹 {work['title']} — {work['author_income']*work['times_sold']} RUB доход\n"
            keyboard_buttons.append([InlineKeyboardButton(
                text=f"❌ Удалить '{work['title']}'",
                callback_data=f"delete:{work['id']}"
            )])
        keyboard_buttons.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")])
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    # Редактируем сообщение с фото
    await callback.message.edit_caption(caption=text, reply_markup=keyboard)
    await callback.answer("✅ Работа удалена")

# ===== Размещение работы =====
async def add_work_start(callback: types.CallbackQuery, state: FSMContext):
    await delete_previous_messages(callback, state)
    
    categories = await get_categories()  # [(id, name, parent_id), ...]

    # Фильтруем только верхние категории (parent_id is None)
    top_categories = [(cat_id, name) for cat_id, name, parent_id in categories if parent_id is None]

    if not top_categories:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]]
        )
        msg = await callback.message.answer("❌ Категории не найдены.", reply_markup=keyboard)
        await add_message_id(msg, state)
        return

    # Формируем клавиатуру с кнопками для каждой верхней категории
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=name, callback_data=f"select_cat_{cat_id}")] 
                         for cat_id, name in top_categories]
    )
    keyboard.inline_keyboard.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")])

    photo = FSInputFile("image/become_avtor.jpg")
    msg = await callback.message.answer_photo(
        photo=photo,
        caption="📁 Выберите категорию работы:",
        reply_markup=keyboard
    )
    await add_message_id(msg, state)
    await state.set_state(WorkForm.category)
    await callback.answer()

# ===== Этапы создания работы =====
async def work_category(callback: types.CallbackQuery, state: FSMContext):
    await delete_previous_messages(callback, state)
    cat_id = int(callback.data.split("_")[-1])
    await state.update_data(category_id=cat_id)
    await state.set_state(WorkForm.title)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]])
    photo = FSInputFile("image/become_avtor.jpg")
    msg = await callback.message.answer_photo(photo=photo, caption="📝 Введите название работы:", reply_markup=keyboard)
    await add_message_id(msg, state)
    await callback.answer()

async def work_title(message: types.Message, state: FSMContext):
    await delete_previous_messages(message, state)
    await state.update_data(title=message.text)
    await state.set_state(WorkForm.description)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]])
    photo = FSInputFile("image/become_avtor.jpg")
    msg = await message.answer_photo(photo=photo, caption="📄 Введите описание работы:", reply_markup=keyboard)
    await add_message_id(msg, state)

async def work_description(message: types.Message, state: FSMContext):
    await delete_previous_messages(message, state)
    await state.update_data(description=message.text)
    await state.set_state(WorkForm.price)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]])
    photo = FSInputFile("image/become_avtor.jpg")
    msg = await message.answer_photo(photo=photo, caption="💰 Укажите цену работы:", reply_markup=keyboard)
    await add_message_id(msg, state)

async def work_price(message: types.Message, state: FSMContext):
    await delete_previous_messages(message, state)
    try:
        price = int(message.text)
    except ValueError:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]])
        msg = await message.answer("❌ Введите число.", reply_markup=keyboard)
        await add_message_id(msg, state)
        return
    await state.update_data(price=price)
    await state.set_state(WorkForm.preview)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]])
    msg = await message.answer("📸 Отправьте превью работы (фото):", reply_markup=keyboard)
    await add_message_id(msg, state)

async def work_preview(message: types.Message, state: FSMContext):
    await delete_previous_messages(message, state)
    if not message.photo:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]])
        msg = await message.answer("❌ Пожалуйста, отправьте изображение в виде фото.", reply_markup=keyboard)
        await add_message_id(msg, state)
        return
    preview_file_id = message.photo[-1].file_id
    await state.update_data(preview=preview_file_id)
    await state.set_state(WorkForm.files)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]])
    msg = await message.answer("📎 Отправьте файл работы. После одного файла работа будет автоматически отправлена на проверку.", reply_markup=keyboard)
    await add_message_id(msg, state)

async def work_files(message: types.Message, state: FSMContext):
    await delete_previous_messages(message, state)
    if not message.document:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]])
        msg = await message.answer("❌ Пожалуйста, отправьте документ.", reply_markup=keyboard)
        await add_message_id(msg, state)
        return

    data = await state.get_data()
    files = data.get("files", [])
    files.append({"file_id": message.document.file_id, "file_name": message.document.file_name})
    await state.update_data(files=files)

    work_data = {
        "title": data.get("title"),
        "description": data.get("description"),
        "price": data.get("price"),
        "category_id": data.get("category_id"),
        "subcategory_id": None,
        "preview": data.get("preview"),
        "files": [(f["file_id"], f["file_name"]) for f in files]
    }
    author_id = message.from_user.id

    try:
        await save_work(author_id, work_data)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏠 Главное меню", callback_data="go_main_from_success")]])
        msg = await message.answer("✅ Работа успешно отправлена на проверку администратору.", reply_markup=keyboard)
    except Exception as e:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏠 Главное меню", callback_data="go_main_from_error")]])
        msg = await message.answer("❌ Ошибка при сохранении работы. Попробуйте позже.", reply_markup=keyboard)
        print("Ошибка save_work:", e)

    await state.set_data({})

# ===== Регистрация хендлеров =====
def register_handlers(dp: Dispatcher):
    dp.message.register(start, Command("start"))
    dp.callback_query.register(main_menu, lambda c: c.data == "main_menu")
    dp.callback_query.register(catalog_handler, lambda c: c.data == "catalog")
    dp.callback_query.register(category_handler, lambda c: c.data.startswith("category_"))
    dp.callback_query.register(profile_handler, lambda c: c.data.startswith("profile_"))
    dp.callback_query.register(add_work_start, F.data == "add_work")
    dp.callback_query.register(buy_work_handler, lambda c: c.data.startswith("buy_work_"))
    dp.callback_query.register(work_category, lambda c: c.data.startswith("select_cat_"))
    dp.callback_query.register(go_main_from_success, F.data == "go_main_from_success")
    dp.callback_query.register(go_main_from_error, F.data == "go_main_from_error")
    dp.message.register(work_title, WorkForm.title)
    dp.message.register(work_description, WorkForm.description)
    dp.message.register(work_price, WorkForm.price)
    dp.message.register(work_preview, WorkForm.preview)
    dp.message.register(work_files, WorkForm.files)
    dp.callback_query.register(withdraw_request_handler, lambda c: c.data == "profile_withdraw_request")
    dp.callback_query.register(delete_work_handler, lambda c: c.data.startswith("delete:"))
    dp.message.register(deposit_amount, DepositForm.amount)
    dp.callback_query.register(profile_handler, lambda c: c.data.startswith("profile_"))
    dp.message.register(deposit_amount, DepositForm.amount)
    dp.callback_query.register(subscribed_callback_handler, lambda c: c.data == "subscribed")
