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
            password_hash TEXT NOT NULL
        )
    ''')
    db.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            description TEXT,
            date TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    db.commit()
    db.close()

def seed_db():
    """Inserts sample data for development."""
    db = get_db()
    # Insert sample user (password is 'demo')
    db.execute("INSERT OR IGNORE INTO users (name, email, password_hash) VALUES (?, ?, ?)", ('Demo User', 'demo@example.com', 'scrypt:32768:8:1$tFUsPHBdICTtnZCh$56635345c3441fd6b1371b9e65cacac357b00c597328fc2cfae13edbea3cd03dac8230197ae959df754cd41076e095ec982de406aa769f20eb69d45fc25f844b'))
    user_id = db.execute("SELECT id FROM users WHERE email = ?", ('demo@example.com',)).fetchone()['id']
    # Insert sample expenses
    db.execute("INSERT OR IGNORE INTO expenses (user_id, amount, description, date) VALUES (?, ?, ?, ?)", (user_id, 50.0, 'Coffee', '2023-10-01'))
    db.execute("INSERT OR IGNORE INTO expenses (user_id, amount, description, date) VALUES (?, ?, ?, ?)", (user_id, 20.0, 'Bus ticket', '2023-10-02'))
    db.commit()
    db.close()
