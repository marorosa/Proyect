import sqlite3

try:
    conn = sqlite3.connect("reflex.db")
    c = conn.cursor()
    
    # Buscamos al usuario por email
    c.execute('SELECT email, "Contraseña", is_active, rol FROM usuario WHERE email="funcionario@ejemplo.com"')
    user = c.fetchone()
    
    print("\n--- REVISIÓN DE USUARIO EN DB ---")
    if user:
        print(f"📧 Email: {user[0]}")
        print(f"🔑 Password en DB: {user[1]}")
        print(f"✅ Activo: {user[2]}")
        print(f"👤 Rol: {user[3]}")
    else:
        print("❌ ERROR: El usuario 'funcionario@ejemplo.com' NO EXISTE en la base de datos.")
    
    conn.close()
except Exception as e:
    print(f"❌ Error al consultar: {e}")
