import sqlite3
from datetime import datetime

# Credenciales
email = "funcionario@ejemplo.com"
# Hash Bcrypt para "password_segura"
bcrypt_hash = "$2b$12$Y76f99ubvG9p9NNDSgt8re7.7mZ7mR3WvLuC9reLhN6kOitK3m7ve"
fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

try:
    conn = sqlite3.connect("reflex.db")
    c = conn.cursor()
    
    # Limpiamos intentos fallidos anteriores
    c.execute("DELETE FROM usuario WHERE email = ?", (email,))
    
    # Insertamos con TODOS los campos que tu DB exige
    query = '''
        INSERT INTO usuario (
            email, "Contraseña", rol, is_active, Fecha_de_creacion, 
            nombres, apellidos, tipo_identificacion, numero_identificacion
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    '''
    valores = (
        email, bcrypt_hash, "funcionario", 1, fecha_actual,
        "Admin", "Sistema", "CC", "123456789"
    )
    
    c.execute(query, valores)
    conn.commit()
    
    print("\n✅ USUARIO CREADO CON ÉXITO")
    print(f"Fecha de registro: {fecha_actual}")
    print("------------------------------------------")
    print(f"Usuario: {email}")
    print("Clave: password_segura")
    print("------------------------------------------")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
finally:
    conn.close()
