import sqlite3
import hashlib

# Creamos un hash SHA256 de la contraseña
# Nota: Algunos sistemas Reflex usan bcrypt, pero intentaremos este 
# para ver si tu lógica de auth lo acepta o al menos para cambiar el texto plano.
password_plana = "password_segura"
hash_obj = hashlib.sha256(password_plana.encode())
hashed_password = hash_obj.hexdigest()

try:
    conn = sqlite3.connect("reflex.db")
    c = conn.cursor()
    
    # Nombre de columna exacto según tu DB: "ContraseÃ±a"
    c.execute('UPDATE usuario SET "ContraseÃ±a" = ? WHERE email = "funcionario@ejemplo.com"', (hashed_password,))
    
    conn.commit()
    print("\n✅ EXITO: Contraseña actualizada con SHA256 (sin librerías externas).")
    print(f"Hash guardado: {hashed_password[:30]}...")
    conn.close()
except Exception as e:
    print(f"\n❌ ERROR: {e}")
