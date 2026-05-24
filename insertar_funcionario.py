import sqlite3
from datetime import datetime

try:
    conn = sqlite3.connect("reflex.db")
    c = conn.cursor()
    
    # Nombres de columna corregidos segun el esquema real de la DB
    query = """
    INSERT INTO usuario (
        email, "Contraseña", rol, is_active, "Fecha_de_creacion", 
        tipo_identificacion, numero_identificacion, nombres, apellidos, 
        genero, direccion, telefono, departamento, ciudad
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    
    # Datos del nuevo funcionario
    datos = (
        "funcionario@ejemplo.com", 
        "password_segura", 
        "funcionario", 
        1, 
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "CC", 
        "12345678", 
        "Nombre", 
        "Apellido", 
        "Masculino", 
        "Calle Falsa 123", 
        "3001234567", 
        "Cundinamarca", 
        "Bogotá"
    )
    
    c.execute(query, datos)
    conn.commit()
    print("✅ Funcionario creado exitosamente con la columna 'Contraseña'.")

except sqlite3.IntegrityError:
    print("⚠️ El usuario ya existe en la base de datos.")
except Exception as e:
    print(f"❌ Error: {e}")
finally:
    conn.close()
