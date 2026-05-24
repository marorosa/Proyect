import sqlite3
import hashlib

# Usaremos un hash SHA256 que es compatible con muchos sistemas básicos
# Si tu Reflex usa bcrypt, inyectaremos el hash manual después.
password_plana = "password_segura"
hash_obj = hashlib.sha256(password_plana.encode())
hashed_password = hash_obj.hexdigest()

try:
    conn = sqlite3.connect("reflex.db")
    c = conn.cursor()
    
    # IMPORTANTE: Usamos "Contraseña" con la ñ real entre comillas dobles
    query = 'UPDATE usuario SET "Contraseña" = ? WHERE email = "funcionario@ejemplo.com"'
    c.execute(query, (hashed_password,))
    
    if c.rowcount > 0:
        conn.commit()
        print("\n✅ EXITO: La columna 'Contraseña' ha sido actualizada.")
        print(f"Hash inyectado: {hashed_password[:20]}...")
    else:
        print("\n❌ Error: No se encontró al usuario 'funcionario@ejemplo.com'.")

except Exception as e:
    print(f"\n❌ Error al acceder a la columna: {e}")
finally:
    conn.close()
