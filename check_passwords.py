import sqlite3

conn = sqlite3.connect('reflex.db')
c = conn.cursor()
c.execute('SELECT id, email, Contraseña FROM usuario WHERE rol="funcionario"')
rows = c.fetchall()
conn.close()

for r in rows:
    print(f'ID {r[0]}: {r[1]} - Pass: {r[2][:20] if r[2] else "None"}...')