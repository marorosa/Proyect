import sqlite3

conn = sqlite3.connect('reflex.db')
cur = conn.cursor()
try:
    cur.execute('SELECT id, email, is_active FROM usuario')
    rows = cur.fetchall()
    print('USUARIOS:', rows)
except Exception as e:
    print('ERROR:', e)
finally:
    conn.close()
