import sqlite3
import bcrypt

conn = sqlite3.connect('reflex.db')
c = conn.cursor()

# Obtener todos los usuarios
c.execute('SELECT id, email, Contraseña FROM usuario')
rows = c.fetchall()

for user_id, email, password in rows:
    if not password.startswith('$2b$'):  # No es hash bcrypt
        print(f'Actualizando contraseña para {email}')
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        c.execute('UPDATE usuario SET Contraseña = ? WHERE id = ?', (hashed, user_id))

conn.commit()
conn.close()
print('Contraseñas actualizadas.')