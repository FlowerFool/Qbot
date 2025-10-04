import aiosqlite
import asyncio
from aiogram import Bot
from aiogram.types import FSInputFile
from config import DB_PATH, CHANNEL_ID, DB_NAME

# ===== Инициализация базы (PRAGMA WAL и foreign keys) =====
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute("PRAGMA foreign_keys=ON;")
        await db.commit()

# ===== Получение списка категорий =====
async def get_categories():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT id, name, parent_id FROM categories")
        return await cursor.fetchall()

# ===== Получение категорий с вложенными подкатегориями =====
async def get_categories_with_subcategories():
    categories = await get_categories()  # [(id, name, parent_id)]
    
    # Словарь: parent_id -> список подкатегорий
    subcats_dict = {}
    for cat_id, name, parent_id in categories:
        if parent_id:
            subcats_dict.setdefault(parent_id, []).append((cat_id, name))
    
    # Список только верхних категорий с вложенными подкатегориями
    result = []
    for cat_id, name, parent_id in categories:
        if parent_id is None:
            subs = subcats_dict.get(cat_id, [])
            result.append((cat_id, name, subs))  # (id, name, [подкатегории])
    return result

# ===== Добавление категории =====
async def add_category(name: str, parent_id: int = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO categories (name, parent_id) VALUES (?, ?)",
            (name, parent_id)
        )
        await db.commit()

# ===== Удаление категории =====
async def delete_category(category_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        await db.commit()

# ===== Получение списка работ по категории =====
async def get_works(category_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT id, title, description, price, author_income, category_id, subcategory_id, author_id, preview_image_id
            FROM works 
            WHERE (category_id = ? OR subcategory_id = ?) AND status='approved' AND is_deleted = 0
            ORDER BY id DESC
        """, (category_id, category_id))
        return await cursor.fetchall()
    
# ===== Получение информации о работе =====
async def get_work_info(work_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT id, title, description, price, author_income, category_id, subcategory_id, author_id, preview_image_id, times_sold, total_earnings, status
            FROM works 
            WHERE id = ? AND is_deleted = 0
        """, (work_id,))
        return await cursor.fetchone()

# ===== Получение файлов работы =====
async def get_work_files(work_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT file_id, file_name FROM files WHERE work_id = ?", (work_id,))
        return await cursor.fetchall()

# ===== Сохранение работы =====
async def save_work(author_id: int, data: dict):
    retries = 5
    for attempt in range(retries):
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                cursor = await db.execute("""
                    INSERT INTO works 
                    (title, description, price, author_income, category_id, subcategory_id, author_id, preview_image_id, times_sold, total_earnings, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    data['title'],
                    data['description'],
                    data['price'],
                    round(data['price'] * 0.8, 2),
                    data.get('category_id'),
                    data.get('subcategory_id'),
                    author_id,
                    data.get('preview'),
                    0,
                    0,
                    'pending'
                ))
                work_id = cursor.lastrowid

                for file_id, file_name in data.get('files', []):
                    await db.execute(
                        "INSERT INTO files (work_id, file_id, file_name) VALUES (?, ?, ?)",
                        (work_id, file_id, file_name)
                    )

                await db.commit()
                return work_id

        except aiosqlite.OperationalError as e:
            if "database is locked" in str(e) and attempt < retries - 1:
                await asyncio.sleep(0.1)
                continue
            else:
                raise

# ===== Получение баланса пользователя =====
async def get_user_balance(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT balance FROM users WHERE id = ?", (user_id,))
        row = await cursor.fetchone()
        if row:
            return row[0]
        else:
            await db.execute("INSERT INTO users (id, balance) VALUES (?, ?)", (user_id, 0))
            await db.commit()
            return 0

# ===== Получение статистики автора =====
async def get_author_stats(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("""
            SELECT id, title, author_income, times_sold 
            FROM works 
            WHERE author_id=? AND is_deleted = 0
        """, (user_id,))
        rows = await cursor.fetchall()
        works = [{"id": r[0], "title": r[1], "author_income": r[2], "times_sold": r[3]} for r in rows]
        total_times_sold = sum(r[3] for r in rows)
        return {"works": works, "total_times_sold": total_times_sold}

# ===== Модерация работ =====
async def get_pending_works():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT id, title, author_id FROM works WHERE status='pending' AND is_deleted = 0 ORDER BY id DESC")
        return await cursor.fetchall()

async def approve_work(work_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE works SET status='approved' WHERE id = ?", (work_id,))
        await db.commit()

async def reject_work(work_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE works SET status='rejected' WHERE id = ?", (work_id,))
        await db.commit()

# ===== Обновление полей работы =====
async def update_work_title(work_id: int, new_title: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE works SET title = ? WHERE id = ?", (new_title, work_id))
        await db.commit()

async def update_work_description(work_id: int, new_description: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE works SET description = ? WHERE id = ?", (new_description, work_id))
        await db.commit()
# ===== Статистика =====
async def get_users_count(category_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT COUNT(DISTINCT author_id) FROM works WHERE category_id = ?
        """, (category_id,))
        row = await cursor.fetchone()
        return row[0] if row else 0

async def get_works_count(category_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT COUNT(*) FROM works WHERE category_id = ?
        """, (category_id,))
        row = await cursor.fetchone()
        return row[0] if row else 0

# ===== Заявки на выплату =====
async def get_payout_requests() -> list[tuple[int, int]]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT user_id, amount FROM payouts WHERE status='pending'
        """)
        rows = await cursor.fetchall()
        return rows

# ===== Получение купленных работ пользователя =====
async def get_user_purchases(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT w.id, w.title, w.price, w.author_id, u.username AS author_name, p.amount, p.status
            FROM purchases p
            JOIN works w ON w.id = p.work_id
            LEFT JOIN users u ON u.id = w.author_id
            WHERE p.buyer_id = ?
            ORDER BY p.id DESC
        """, (user_id,))
        rows = await cursor.fetchall()
        return [
            {
                "work_id": row[0],
                "title": row[1],
                "price": row[2],
                "author_id": row[3],
                "author_name": row[4] if row[4] else "Неизвестно",
                "amount": row[5],
                "status": row[6]
            }
            for row in rows
        ]

# ===== Получение всех пользователей =====
async def get_all_users():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT id, username, balance FROM users")
        users = await cursor.fetchall()
        return users

async def get_total_users_count() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM users")
        row = await cursor.fetchone()
        return row[0] if row else 0

# ===== Подсчёт количества продаж по категории =====
async def get_category_sales_count(category_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT SUM(times_sold) FROM works WHERE category_id = ?
        """, (category_id,))
        row = await cursor.fetchone()
        return row[0] if row and row[0] is not None else 0

# ===== Получение работ конкретного пользователя =====
async def get_user_works(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT id, title, status 
            FROM works 
            WHERE author_id = ? AND is_deleted = 0
            ORDER BY id DESC
        """, (user_id,))
        rows = await cursor.fetchall()
        return [{"work_id": r[0], "title": r[1], "status": r[2]} for r in rows]

# ===== Удаление работы =====
async def delete_work(work_id: int, user_id: int) -> bool:
    import aiosqlite
    from config import DB_NAME

    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT id FROM works WHERE id=? AND author_id=?", (work_id, user_id)
        )
        work = await cursor.fetchone()
        if not work:
            return False
        await db.execute("DELETE FROM works WHERE id=?", (work_id,))
        await db.commit()
        return True


# ===== Логическое удаление работы =====
async def admin_delete_work(work_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        # Удаляем файлы работы
        await db.execute("DELETE FROM files WHERE work_id = ?", (work_id,))
        # Удаляем саму работу
        await db.execute("DELETE FROM works WHERE id = ?", (work_id,))
        await db.commit()
        return True

# ===== Получение подкатегорий =====
async def get_subcategories(parent_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT id, name FROM categories WHERE parent_id = ?", (parent_id,))
        return await cursor.fetchall()

# ===== Обновление категории работы =====
async def update_work_category(work_id: int, category_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT parent_id FROM categories WHERE id=?", (category_id,))
        row = await cursor.fetchone()
        if row and row[0]:  # Если есть родитель
            await db.execute("UPDATE works SET subcategory_id=? WHERE id=?", (category_id, work_id))
        else:
            await db.execute("UPDATE works SET category_id=?, subcategory_id=NULL WHERE id=?", (category_id, work_id))
        await db.commit()

#===== Публикация работы в канал =====
async def post_work_to_channel(bot: Bot, work_info: dict, files: list[tuple]):
    """
    Публикует работу в канал.
    work_info: {
        "title": str,
        "description": str,
        "preview_image_id": str | None
    }
    files: [(file_id, file_name), ...] 
    """
    caption = f"🔹 <b>{work_info['title']}</b>\n📄 {work_info['description']}"

    # Отправка превью
    if work_info.get('preview_image_id'):
        try:
            await bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=work_info['preview_image_id'],
                caption=caption
            )
        except:
            await bot.send_message(chat_id=CHANNEL_ID, text=caption)
    else:
        await bot.send_message(chat_id=CHANNEL_ID, text=caption)

    # Отправка файлов
    for file_id, file_name in files:
        try:
            await bot.send_document(chat_id=CHANNEL_ID, document=file_id, caption=file_name)
        except:
            pass