import sqlite3
import sys

try:
    from passlib.context import CryptContext
    # Configuración de seguridad
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    hashed_password = pwd_context.hash("password_segura")
    
    conn = sqlite3.connect("reflex.db")
    c = conn.cursor()
    
    # Actualizamos el valor 'ContraseÃ±a' (que estaba mal) por el HASH real
    # Usamos el nombre de columna exacto detectado en tu archivo .db
    c.execute('UPDATE usuario SET "ContraseÃ±a" = ? WHERE email = "funcionario@ejemplo.com"', (hashed_password,))
    
    conn.commit()
    print("\n✅ EXITO: Contraseña encriptada y guardada.")
    print(f"Hash generado: {hashed_password[:30]}...")
    conn.close()

except ImportError:
    print("\n❌ ERROR: No se pudo importar passlib. Asegúrate de ejecutar: pip install \"passlib[bcrypt]\"")
except Exception as e:
    print(f"\n❌ ERROR inesperado: {e}")
