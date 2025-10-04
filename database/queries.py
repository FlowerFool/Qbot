import aiosqlite
from config import DB_NAME

# -------------------- Users --------------------
async def get_user(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT * FROM users WHERE id=?", (user_id,))
        return await cursor.fetchone()

async def add_user(user_id: int, username: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO users(id, username) VALUES(?,?)", (user_id, username))
        await db.commit()

async def update_balance(user_id: int, amount: float):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET balance = balance + ? WHERE id=?", (amount, user_id))
        await db.commit()

# -------------------- Categories --------------------
async def get_category_info(category_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT id, name, parent_id FROM categories WHERE id=?", (category_id,))
        return await cursor.fetchone()

async def get_categories(parent_id=None):
    async with aiosqlite.connect(DB_NAME) as db:
        if parent_id:
            cursor = await db.execute("SELECT id, name FROM categories WHERE parent_id=?", (parent_id,))
        else:
            cursor = await db.execute("SELECT id, name FROM categories WHERE parent_id IS NULL")
        return await cursor.fetchall()

# -------------------- Works --------------------
async def get_works(category_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT * FROM works WHERE category_id=? OR subcategory_id=?", (category_id, category_id))
        return await cursor.fetchall()

async def get_work_info(work_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT * FROM works WHERE id=?", (work_id,))
        return await cursor.fetchone()

async def update_work_preview(work_id: int, new_preview_id: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE works SET preview_image_id=? WHERE id=?",
            (new_preview_id, work_id)
        )
        await db.commit()

# -------------------- Files --------------------
async def get_work_files(work_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT file_id, file_name FROM files WHERE work_id=?", (work_id,))
        return await cursor.fetchall()

# -------------------- Purchases --------------------
async def create_purchase(work_id, buyer_id, amount):
    import uuid
    purchase_id = str(uuid.uuid4())
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT INTO purchases(id, work_id, buyer_id, amount, status) VALUES(?,?,?,?,?)",
                         (purchase_id, work_id, buyer_id, amount, 'pending'))
        await db.commit()
    return purchase_id

async def get_purchase_info(purchase_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT * FROM purchases WHERE id=?", (purchase_id,))
        return await cursor.fetchone()

async def update_purchase_status(purchase_id, status, proof=None):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE purchases SET status=?, payment_proof=? WHERE id=?", (status, proof, purchase_id))
        await db.commit()

# -------------------- AI Settings --------------------
async def get_ai_settings():
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT * FROM ai_settings ORDER BY id DESC LIMIT 1")
        return await cursor.fetchone()

async def save_ai_settings(provider, model, api_key, api_url, temperature, max_tokens, is_active):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
        INSERT INTO ai_settings(ai_provider, model_name, api_key, api_url, temperature, max_tokens, is_active)
        VALUES(?,?,?,?,?,?,?)""", (provider, model, api_key, api_url, temperature, max_tokens, int(is_active)))
        await db.commit()

async def reset_ai_settings():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM ai_settings")
        await db.commit()

# -------------------- Transactions --------------------
async def complete_purchase(purchase_id, service_user_id=1, author_percent=0.7):
    """
    Завершение покупки: распределение оплаты между автором и сервисом.
    Работа остаётся доступной для других покупателей.
    """
    async with aiosqlite.connect(DB_NAME) as db:
        # Получаем информацию о покупке
        cursor = await db.execute("SELECT work_id, buyer_id, amount FROM purchases WHERE id=?", (purchase_id,))
        purchase = await cursor.fetchone()
        if not purchase:
            return False
        
        work_id, buyer_id, amount = purchase
        
        # Получаем автора работы
        cursor = await db.execute("SELECT author_id FROM works WHERE id=?", (work_id,))
        author = await cursor.fetchone()
        if not author:
            return False
        author_id = author[0]
        
        # Рассчитываем доли
        author_share = amount * author_percent
        service_share = amount - author_share
        
        # Обновляем балансы
        await db.execute("UPDATE users SET balance = balance + ? WHERE id=?", (author_share, author_id))
        await db.execute("UPDATE users SET balance = balance + ? WHERE id=?", (service_share, service_user_id))
        await db.execute("UPDATE users SET balance = balance - ? WHERE id=?", (amount, buyer_id))
        
        # Обновляем purchase
        await db.execute("UPDATE purchases SET status='completed' WHERE id=?", (purchase_id,))
        
        # Увеличиваем количество продаж и доходы у работы
        await db.execute("UPDATE works SET times_sold = times_sold + 1, total_earnings = total_earnings + ? WHERE id=?", (amount, work_id))
        
        # Добавляем транзакции
        await db.execute("INSERT INTO transactions(from_user, to_user, work_id, amount, type) VALUES(?,?,?,?,?)",
                         (buyer_id, author_id, work_id, author_share, 'purchase'))
        await db.execute("INSERT INTO transactions(from_user, to_user, work_id, amount, type) VALUES(?,?,?,?,?)",
                         (buyer_id, service_user_id, work_id, service_share, 'purchase'))
        
        await db.commit()
        return True