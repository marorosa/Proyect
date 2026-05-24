import sqlite3

# Este es el hash Bcrypt real para "password_segura"
# Es el formato que Reflex (FastAPI) espera encontrar
bcrypt_hash = "$2b$12$Y76f99ubvG9p9NNDSgt8re7.7mZ7mR3WvLuC9reLhN6kOitK3m7ve"

try:
    conn = sqlite3.connect("reflex.db")
    c = conn.cursor()
    
    # Usamos el nombre de columna "Contraseña" con la ñ real
    # La comilla doble ayuda a SQLite a identificarla correctamente
    query = 'UPDATE usuario SET "Contraseña" = ? WHERE email = "funcionario@ejemplo.com"'
    
    c.execute(query, (bcrypt_hash,))
    conn.commit()
    
    if c.rowcount > 0:
        print("\n🚀 ¡LOGRADO!")
        print("--------------------------------------------------")
        print("✅ El hash Bcrypt se inyectó en la columna 'Contraseña'.")
        print("✅ Ya puedes cerrar la terminal e intentar el login.")
    else:
        print("\n❌ No se encontró el correo 'funcionario@ejemplo.com'.")

except Exception as e:
    print(f"\n❌ Error inesperado: {e}")
finally:
    conn.close()
