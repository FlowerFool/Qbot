import aiosqlite
from config import DB_NAME

# Функция инициализации базы данных
async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.executescript("""
        -- Пользователи
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT,
            balance REAL DEFAULT 0,
            is_subscribed INTEGER DEFAULT 0
        );

        -- Категории (курсовые, дипломы, рефераты и т.д.)
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            parent_id INTEGER
        );

        -- Работы
        CREATE TABLE IF NOT EXISTS works (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            price REAL NOT NULL,
            author_income REAL,
            category_id INTEGER,
            subcategory_id INTEGER,
            author_id INTEGER,
            preview_image_id TEXT,
            times_sold INTEGER DEFAULT 0,
            total_earnings REAL DEFAULT 0,
            status TEXT DEFAULT 'pending', -- 'pending', 'approved', 'rejected'
            FOREIGN KEY (category_id) REFERENCES categories (id),
            FOREIGN KEY (author_id) REFERENCES users (id)
        );

        -- Файлы работы
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            work_id INTEGER,
            file_id TEXT,
            file_name TEXT,
            FOREIGN KEY (work_id) REFERENCES works (id)
        );

        -- Покупки
        CREATE TABLE IF NOT EXISTS purchases (
            id TEXT PRIMARY KEY,
            work_id INTEGER,
            buyer_id INTEGER,
            amount REAL,
            status TEXT,
            payment_proof TEXT,
            FOREIGN KEY (work_id) REFERENCES works (id),
            FOREIGN KEY (buyer_id) REFERENCES users (id)
        );
        -- Транзакции
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_user INTEGER,
            to_user INTEGER,
            work_id INTEGER,
            amount REAL,
            type TEXT, -- 'purchase', 'payout', 'deposit'
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (from_user) REFERENCES users(id),
            FOREIGN KEY (to_user) REFERENCES users(id),
            FOREIGN KEY (work_id) REFERENCES works(id)
        );

        -- Выплаты авторам
        CREATE TABLE IF NOT EXISTS payouts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            status TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        );

        -- Посты (для публикации в канал, если понадобится)
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            work_id INTEGER,
            content TEXT,
            FOREIGN KEY (work_id) REFERENCES works (id)
        );

        -- Настройки нейросети
        CREATE TABLE IF NOT EXISTS ai_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ai_provider TEXT,
            model_name TEXT,
            api_key TEXT,
            api_url TEXT,
            temperature REAL,
            max_tokens INTEGER,
            is_active INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT
        );
        """)
        await db.commit()
