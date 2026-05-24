import sqlite3
import sys

try:
    from passlib.context import CryptContext
    # Configuramos el motor de encriptación
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    # Generamos el código secreto (Hash)
    hashed_password = pwd_context.hash("password_segura")
    
    conn = sqlite3.connect("reflex.db")
    c = conn.cursor()
    
    # Actualizamos el registro del funcionario con el Hash generado
    # Nota: Usamos el nombre de columna 'ContraseÃ±a' que detectamos en tu DB
    c.execute('UPDATE usuario SET "ContraseÃ±a" = ? WHERE email = "funcionario@ejemplo.com"', (hashed_password,))
    
    if c.rowcount > 0:
        conn.commit()
        print("\n✅ EXITO: Contraseña encriptada y guardada en la base de datos.")
        print(f"Nuevo valor (Hash): {hashed_password[:30]}...")
    else:
        print("\n⚠️ No se encontró al usuario 'funcionario@ejemplo.com' para actualizar.")

    conn.close()

except ImportError:
    print("\n❌ ERROR: Sigue sin detectarse 'passlib'. Intenta ejecutar: python -m pip install \"passlib[bcrypt]\"")
except Exception as e:
    print(f"\n❌ ERROR inesperado: {e}")
