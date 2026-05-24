import sqlite3

# Hash Bcrypt real para "password_segura"
bcrypt_hash = "$2b$12$Y76f99ubvG9p9NNDSgt8re7.7mZ7mR3WvLuC9reLhN6kOitK3m7ve"
email_target = "funcionario@ejemplo.com"

try:
    conn = sqlite3.connect("reflex.db")
    cursor = conn.cursor()
    
    # Obtenemos las columnas reales
    cursor.execute("PRAGMA table_info(usuario)")
    cols = [col[1] for col in cursor.fetchall()]
    
    # Intentamos actualizar en cualquier columna que se parezca a password
    targets = ["Contraseña", "contrasena", "password", "ContraseÃ±a"]
    updated = False
    
    for t in targets:
        if t in cols:
            cursor.execute(f'UPDATE usuario SET "{t}" = ? WHERE email = ?', (bcrypt_hash, email_target))
            print(f"✅ Columna '{t}' actualizada con el hash.")
            updated = True
    
    if updated:
        conn.commit()
        print("\n🚀 PROCESO EXITOSO. Intenta loguearte de nuevo.")
    else:
        print("\n❌ No se encontró ninguna columna de contraseña conocida.")

except Exception as e:
    print(f"❌ Error: {e}")
finally:
    conn.close()
