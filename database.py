"""
Database connection manager for SQLite.
Provides helper functions for safe, parameterized queries with %s to ? conversion for backward compatibility.
Auto-initializes the database from schema.sql if the database file does not exist.
"""
import sqlite3
import os
from datetime import datetime, date
from config import Config


# Custom parsers for sqlite3 to parse date/datetime columns automatically
def parse_datetime(val):
    val_str = val.decode('utf-8')
    try:
        return datetime.strptime(val_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        try:
            return datetime.fromisoformat(val_str)
        except ValueError:
            return val_str


def parse_date(val):
    val_str = val.decode('utf-8')
    try:
        return datetime.strptime(val_str, "%Y-%m-%d").date()
    except ValueError:
        return val_str


# Register the custom converters
sqlite3.register_converter("DATETIME", parse_datetime)
sqlite3.register_converter("DATE", parse_date)


def convert_query(query):
    """Automatically convert %s placeholders to SQLite's ? placeholders."""
    if not isinstance(query, str):
        return query
    return query.replace('%s', '?')


def get_connection():
    """Create and return a new SQLite connection with foreign keys and type detection enabled."""
    conn = sqlite3.connect(
        Config.DATABASE_PATH,
        check_same_thread=False,
        detect_types=sqlite3.PARSE_DECLTYPES
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn



def ensure_user_reset_columns():
    """Add password-reset fields for older databases created before the forgot-password feature."""
    conn = get_connection()
    try:
        cols = conn.execute("PRAGMA table_info(users)").fetchall()
        existing = {col['name'] for col in cols}

        if 'reset_token' not in existing:
            conn.execute("ALTER TABLE users ADD COLUMN reset_token VARCHAR(255) DEFAULT NULL")
        if 'reset_token_expires' not in existing:
            conn.execute("ALTER TABLE users ADD COLUMN reset_token_expires DATETIME DEFAULT NULL")
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Initialize the database from schema.sql if the database file does not exist."""
    db_exists = os.path.exists(Config.DATABASE_PATH)
    if not db_exists:
        db_dir = os.path.dirname(Config.DATABASE_PATH)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        print("[DB] Database file not found. Creating and initializing SQLite database...")
        conn = get_connection()
        try:
            schema_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'schema.sql')
            if os.path.exists(schema_path):
                with open(schema_path, 'r', encoding='utf-8') as f:
                    schema_sql = f.read()
                # Execute the schema script (multiple statements)
                conn.executescript(schema_sql)
                conn.commit()
                print("[DB] Database successfully initialized with schema.sql.")
            else:
                print("[DB] [WARNING] schema.sql not found! Cannot initialize database schema.")
        except Exception as e:
            print(f"[DB] [ERROR] Error initializing database: {e}")
            raise e
        finally:
            conn.close()

        # Auto-seed the database with default admin, officer, and categories
        try:
            from seed import seed
            seed()
        except Exception as se:
            print(f"[DB] [WARNING] Could not auto-seed database: {se}")

    ensure_user_reset_columns()


def fetch_one(query, params=None):
    """Execute a query and return a single row as a dictionary."""
    query_converted = convert_query(query)
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query_converted, params or ())
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def fetch_all(query, params=None):
    """Execute a query and return all rows as a list of dictionaries."""
    query_converted = convert_query(query)
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query_converted, params or ())
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def execute(query, params=None):
    """Execute an INSERT / UPDATE / DELETE and return the lastrowid."""
    query_converted = convert_query(query)
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query_converted, params or ())
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def execute_many(query, params_list):
    """Execute a batch of INSERT / UPDATE / DELETE statements."""
    query_converted = convert_query(query)
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.executemany(query_converted, params_list)
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def execute_with_rowcount(query, params=None):
    """Execute a query and return the number of affected rows."""
    query_converted = convert_query(query)
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query_converted, params or ())
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


# Automatically initialize the database on import
init_db()
