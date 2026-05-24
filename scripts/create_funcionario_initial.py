#!/usr/bin/env python3
"""
Script para crear un funcionario inicial en la base de datos.
Ejecuta este script para crear un usuario administrador por defecto.
"""

import sqlite3
import bcrypt
from datetime import datetime


def create_initial_funcionario():
    # Datos del funcionario inicial
    email = "admin@empresa.com"
    password = "admin123"  # Cambia esta contraseña en producción
    nombres = "Administrador"
    apellidos = "Sistema"
    tipo_identificacion = "CC"
    numero_identificacion = "1234567890"
    telefono = "3001234567"
    direccion = "Calle Principal 123"
    departamento = "Antioquia"
    ciudad = "Medellín"

    # Hash de la contraseña
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    # Conectar a la base de datos
    conn = sqlite3.connect("reflex.db")
    cur = conn.cursor()

    try:
        # Verificar si ya existe el usuario
        cur.execute("SELECT id FROM usuario WHERE email = ?", (email,))
        if cur.fetchone():
            print(f"ADVERTENCIA: El usuario {email} ya existe. No se creo nada.")
            return

        # Insertar el nuevo funcionario
        cur.execute(
            """
            INSERT INTO usuario (
                email, Contraseña, rol, is_active, Fecha_de_creacion,
                tipo_identificacion, numero_identificacion, nombres, apellidos,
                genero, direccion, telefono, departamento, ciudad
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                email,
                hashed,
                "funcionario",
                1,
                datetime.now().isoformat(),
                tipo_identificacion,
                numero_identificacion,
                nombres,
                apellidos,
                None,  # género
                direccion,
                telefono,
                departamento,
                ciudad,
            ),
        )
        conn.commit()
        print("EXITO: Funcionario inicial creado correctamente!")
        print(f"Email: {email}")
        print(f"Contrasena: {password}")
        print("Recuerda cambiar la contrasena despues del primer inicio de sesion.")
        print("Puedes iniciar sesion en /login")

    except sqlite3.Error as e:
        print(f"❌ Error en la base de datos: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    create_initial_funcionario()