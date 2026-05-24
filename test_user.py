import sqlite3
import datetime

new_email = "test@admin.com"
password_plana = "12345" # Usaremos algo simple para probar

try:
    conn = sqlite3.connect("reflex.db")
    c = conn.cursor()
    
    # Insertamos un usuario nuevo desde cero con valores básicos
    # Usamos la columna "Contraseña" que confirmamos que existe
    c.execute('''
        INSERT INTO usuario (email, "Contraseña", rol, is_active, nombres) 
        VALUES (?, ?, ?, ?, ?)
    ''', (new_email, password_plana, "funcionario", 1, "Usuario Test"))
    
    conn.commit()
    print(f"\n✅ USUARIO DE PRUEBA CREADO")
    print(f"Email: {new_email}")
    print(f"Password: {password_plana}")
    conn.close()
except Exception as e:
    print(f"❌ Error al crear: {e}")
