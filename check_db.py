import sqlite3
try:
    conn = sqlite3.connect("reflex.db")
    c = conn.cursor()
    # Buscamos usando el nombre de columna exacto que tiene tu archivo
    c.execute('SELECT email, "ContraseÃ±a" FROM usuario WHERE email="funcionario@ejemplo.com"')
    res = c.fetchone()
    if res:
        print(f"\n✅ USUARIO ENCONTRADO")
        print(f"Email: {res[0]}")
        print(f"Contraseña en DB: {res[1]}")
        
        if res[1].startswith("$2b$"):
            print("\n💡 EL HASH ES CORRECTO: La contraseña está encriptada con bcrypt.")
            print("Ya deberías poder loguearte con 'password_segura'.")
        else:
            print("\n⚠️ ADVERTENCIA: La contraseña está en texto plano.")
            print("El login de Reflex FALLARÁ hasta que la encriptes.")
    else:
        print("❌ No se encontró el usuario 'funcionario@ejemplo.com'")
except Exception as e:
    print(f"❌ Error: {e}")
finally:
    conn.close()
