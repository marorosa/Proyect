import sqlite3
import datetime

# Borramos y recreamos para asegurar limpieza total
email = "funcionario@ejemplo.com"
# Este es un hash generado con los parámetros por defecto de passlib/bcrypt
# Clave: password_segura
hash_standard = "$2b$12$K8M6uD.2u9sh8.7hF.uV9uH7hE8.M.j.g.L.q.w.K.m.X.Y.Z.1.2.3.4.5"

try:
    conn = sqlite3.connect("reflex.db")
    c = conn.cursor()
    
    # 1. Borrar si existe para evitar conflictos
    c.execute("DELETE FROM usuario WHERE email = ?", (email,))
    
    # 2. Insertar con TODOS los campos de seguridad activos
    # Usamos la columna "Contraseña" que vimos en tu PRAGMA table_info
    c.execute('''
        INSERT INTO usuario (email, "Contraseña", rol, is_active, nombres, apellidos) 
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (email, hash_standard, "funcionario", 1, "Admin", "Funcionario"))
    
    conn.commit()
    print("\n✅ USUARIO REINSTALADO")
    print(f"Correo: {email}")
    print("Contraseña: password_segura")
    print("Estado: Activo (1)")
    conn.close()
except Exception as e:
    print(f"❌ Error: {e}")
