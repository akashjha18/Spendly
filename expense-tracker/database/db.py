import sqlite3

def get_db():
    """Returns a SQLite connection with row_factory and foreign keys enabled."""
    conn = sqlite3.connect('expenses.db')
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn

def init_db():
    """Creates all tables using CREATE TABLE IF NOT EXISTS."""
    db = get_db()
    db.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            avatar TEXT DEFAULT 'avatars/avatar1.svg'
        )
    ''')
    db.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            color TEXT DEFAULT '#007bff'
        )
    ''')
    db.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            category_id INTEGER,
            amount REAL NOT NULL,
            description TEXT,
            date TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (category_id) REFERENCES categories (id)
        )
    ''')
    db.execute('''
        CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            category_id INTEGER,
            amount REAL NOT NULL,
            period TEXT NOT NULL DEFAULT 'monthly',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (category_id) REFERENCES categories (id)
        )
    ''')
    # Add category_id column if it doesn't exist (for migration)
    try:
        db.execute("ALTER TABLE expenses ADD COLUMN category_id INTEGER REFERENCES categories (id)")
    except sqlite3.OperationalError:
        pass  # Column already exists
    try:
        db.execute("ALTER TABLE budgets ADD COLUMN period TEXT DEFAULT 'monthly'")
    except sqlite3.OperationalError:
        pass  # Column already exists
    try:
        db.execute("ALTER TABLE users ADD COLUMN avatar TEXT DEFAULT 'avatars/avatar1.svg'")
    except sqlite3.OperationalError:
        pass  # Column already exists
    db.commit()
    db.close()

def seed_db():
    """Inserts sample data for development."""
    db = get_db()
    # Insert sample categories
    categories = [
        ('Food & Dining', '#28a745'),
        ('Transportation', '#007bff'),
        ('Entertainment', '#ffc107'),
        ('Shopping', '#dc3545'),
        ('Bills & Utilities', '#6c757d'),
        ('Healthcare', '#17a2b8'),
        ('Other', '#6f42c1')
    ]
    for name, color in categories:
        db.execute("INSERT OR IGNORE INTO categories (name, color) VALUES (?, ?)", (name, color))
    
    # Insert sample user (password is 'demo')
    db.execute("INSERT OR IGNORE INTO users (name, email, password_hash) VALUES (?, ?, ?)", ('Demo User', 'demo@example.com', 'scrypt:32768:8:1$tFUsPHBdICTtnZCh$56635345c3441fd6b1371b9e65cacac357b00c597328fc2cfae13edbea3cd03dac8230197ae959df754cd41076e095ec982de406aa769f20eb69d45fc25f844b'))
    user_id = db.execute("SELECT id FROM users WHERE email = ?", ('demo@example.com',)).fetchone()['id']
    
    # Get category IDs
    food_id = db.execute("SELECT id FROM categories WHERE name = ?", ('Food & Dining',)).fetchone()['id']
    transport_id = db.execute("SELECT id FROM categories WHERE name = ?", ('Transportation',)).fetchone()['id']
    
    # Insert sample expenses
    db.execute("INSERT OR IGNORE INTO expenses (user_id, category_id, amount, description, date) VALUES (?, ?, ?, ?, ?)", (user_id, food_id, 50.0, 'Coffee', '2023-10-01'))
    db.execute("INSERT OR IGNORE INTO expenses (user_id, category_id, amount, description, date) VALUES (?, ?, ?, ?, ?)", (user_id, transport_id, 20.0, 'Bus ticket', '2023-10-02'))
    
    # Insert sample budgets
    db.execute("INSERT OR IGNORE INTO budgets (user_id, category_id, amount, period) VALUES (?, ?, ?, ?)", (user_id, None, 1500.0, 'monthly'))
    db.execute("INSERT OR IGNORE INTO budgets (user_id, category_id, amount, period) VALUES (?, ?, ?, ?)", (user_id, food_id, 500.0, 'monthly'))
    db.commit()
    db.close()
