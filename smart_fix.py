import sqlite3

bcrypt_hash = "$2b$12$Y76f99ubvG9p9NNDSgt8re7.7mZ7mR3WvLuC9reLhN6kOitK3m7ve"

try:
    conn = sqlite3.connect("reflex.db")
    cursor = conn.cursor()
    
    # 1. Obtener los nombres reales de las columnas
    cursor.execute("PRAGMA table_info(usuario)")
    columns = [col[1] for col in cursor.fetchall()]
    print(f"Columnas detectadas: {columns}")
    
    # 2. Buscar cual es la de la contraseña (la que no es email, id, rol, etc.)
    # Normalmente es la segunda o tercera columna
    col_pass = None
    for c_name in columns:
        if "Contras" in c_name or "password" in c_name.lower():
            col_pass = c_name
            break
            
    if col_pass:
        print(f"🎯 Columna identificada como: '{col_pass}'")
        # 3. Actualizar usando el nombre exacto que encontramos
        query = f'UPDATE usuario SET "{col_pass}" = ? WHERE email = "funcionario@ejemplo.com"'
        cursor.execute(query, (bcrypt_hash,))
        conn.commit()
        print("✅ ¡ÉXITO! Contraseña actualizada correctamente.")
    else:
        print("❌ No se encontró una columna que parezca ser la contraseña.")

except Exception as e:
    print(f"❌ Error: {e}")
finally:
    conn.close()
