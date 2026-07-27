import sqlite3

DB_NAME = "database.db"


def get_connection():
    return sqlite3.connect(DB_NAME)


def create_tables():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS employees (
        codigo TEXT PRIMARY KEY,
        nome TEXT NOT NULL,
        email TEXT NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        id INTEGER PRIMARY KEY,
        api_token TEXT
    )
    """)

    conn.commit()
    conn.close()


# =========================
# EMPLOYEES
# =========================

def save_employee(codigo, nome, email):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT OR REPLACE INTO employees (codigo, nome, email)
    VALUES (?, ?, ?)
    """, (codigo, nome, email))

    conn.commit()
    conn.close()


def get_employee_by_codigo(codigo):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT codigo, nome, email FROM employees WHERE codigo = ?", (codigo,))
    result = cursor.fetchone()
    conn.close()
    return result


def get_all_employees():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT codigo, nome, email FROM employees")
    results = cursor.fetchall()
    conn.close()
    return results


# =========================
# TOKEN
# =========================

def save_token(token):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM settings")
    cursor.execute("INSERT INTO settings (id, api_token) VALUES (1, ?)", (token,))

    conn.commit()
    conn.close()


def get_token():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT api_token FROM settings WHERE id = 1")
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None