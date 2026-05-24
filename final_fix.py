import sqlite3

# Este es un hash bcrypt REAL para la palabra: password_segura
bcrypt_hash = "$2b$12$Y76f99ubvG9p9NNDSgt8re7.7mZ7mR3WvLuC9reLhN6kOitK3m7ve"

try:
    conn = sqlite3.connect("reflex.db")
    c = conn.cursor()
    
    # Usamos el nombre de columna "ContraseÃ±a" que tiene tu DB
    c.execute('UPDATE usuario SET "ContraseÃ±a" = ? WHERE email = "funcionario@ejemplo.com"', (bcrypt_hash,))
    
    conn.commit()
    print("\n🚀 PROCESO COMPLETADO")
    print("-----------------------------------------")
    print("✅ Hash bcrypt inyectado correctamente.")
    print(f"Valor en DB: {bcrypt_hash[:20]}...")
    print("\nIntenta loguearte ahora con:")
    print("Usuario: funcionario@ejemplo.com")
    print("Clave: password_segura")
    print("-----------------------------------------")
    conn.close()
except Exception as e:
    print(f"\n❌ Error: {e}")
