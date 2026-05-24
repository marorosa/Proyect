import sqlite3
try:
    from passlib.context import CryptContext
    # Configuracion estandar de seguridad para Reflex/FastAPI
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    hashed_password = pwd_context.hash("password_segura")
    
    conn = sqlite3.connect("reflex.db")
    c = conn.cursor()
    
    # Corregimos el valor: ponemos el HASH en lugar del texto plano
    c.execute('UPDATE usuario SET "ContraseÃ±a" = ? WHERE email = "funcionario@ejemplo.com"', (hashed_password,))
    
    conn.commit()
    print("\n✅ EXITO: Contraseña encriptada correctamente.")
    print(f"Nuevo valor guardado (Hash): {hashed_password[:30]}...")
    
except ImportError:
    print("\n❌ Error: No tienes 'passlib' instalado. Ejecuta: pip install \"passlib[bcrypt]\"")
except Exception as e:
    print(f"\n❌ Error: {e}")
finally:
    conn.close()
