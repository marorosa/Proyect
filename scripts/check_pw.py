import sys
import sqlite3
import bcrypt

if len(sys.argv) != 3:
    print("Uso: python scripts/check_pw.py email password")
    sys.exit(1)

email = sys.argv[1]
password = sys.argv[2]

conn = sqlite3.connect('reflex.db')
cur = conn.cursor()
cur.execute('SELECT Contraseña FROM usuario WHERE email = ?', (email,))
row = cur.fetchone()
if not row:
    print('Usuario no encontrado:', email)
    sys.exit(1)

hashed = row[0]
match = bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
print(f'Password match for {email}:', match)
conn.close()
