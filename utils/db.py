from flask import current_app, g
import sqlite3


def init_db(app):
    app.teardown_appcontext(close_db)
    with app.app_context():
        initialize_db()


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row

    return g.db


def close_db(e=None):
    db = g.pop('db', None)

    if db is not None:
        db.close()


def initialize_db():
    conn = get_db()
    cursor = conn.cursor()

    # Create the users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            is_admin INTEGER DEFAULT 0
        )
    ''')

    # Create the chores table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price INTEGER NOT NULL,
            bonus_price INTEGER,
            bonus_price_trigger TEXT,
            interval TEXT NOT NULL,
            work_limit INTEGER,
            UNIQUE(name)
        )
    ''')

    # Create the completed_chores table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS completed_chores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            chore_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            price INTEGER NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (chore_id) REFERENCES chores (id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS paid_weeks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER NOT NULL,
            week INTEGER NOT NULL,
            paid_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()
