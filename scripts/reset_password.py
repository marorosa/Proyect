import sys
import sqlite3
import bcrypt

if len(sys.argv) != 3:
    print("Uso: python scripts/reset_password.py user@example.com NewPassword123!")
    sys.exit(1)

email = sys.argv[1]
new_pw = sys.argv[2]

hashed = bcrypt.hashpw(new_pw.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

conn = sqlite3.connect('reflex.db')
cur = conn.cursor()
cur.execute('SELECT id FROM usuario WHERE email = ?', (email,))
row = cur.fetchone()
if not row:
    print('Usuario no encontrado:', email)
    conn.close()
    sys.exit(1)

cur.execute('UPDATE usuario SET Contraseña = ? WHERE email = ?', (hashed, email))
conn.commit()
conn.close()
print(f'Contraseña actualizada para {email}')
