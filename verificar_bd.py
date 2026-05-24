#!/usr/bin/env python3
"""
Script para verificar que las tablas de la base de datos se crearon correctamente
"""
import sys
import os
sys.path.append(os.path.dirname(__file__))

from sqlmodel import create_engine, inspect
from sqlalchemy import text
from autenticacion.usuario_model import Usuario, Solicitud

# Configurar la base de datos
DATABASE_URL = "sqlite:///reflex.db"
engine = create_engine(DATABASE_URL, echo=False)

def verificar_tablas():
    """Verifica que las tablas existen y muestra su estructura"""
    inspector = inspect(engine)

    print("=== VERIFICACIÓN DE TABLAS EN LA BASE DE DATOS ===\n")

    # Verificar tabla Usuario
    if inspector.has_table("usuario"):
        print("✓ Tabla 'usuario' existe")
        columns = inspector.get_columns("usuario")
        print("  Columnas:")
        for col in columns:
            print(f"    - {col['name']}: {col['type']} {'(PK)' if col.get('primary_key') else ''}")
    else:
        print("✗ Tabla 'usuario' NO existe")

    print()

    # Verificar tabla Solicitud
    if inspector.has_table("solicitud"):
        print("✓ Tabla 'solicitud' existe")
        columns = inspector.get_columns("solicitud")
        print("  Columnas:")
        for col in columns:
            print(f"    - {col['name']}: {col['type']} {'(PK)' if col.get('primary_key') else ''}")
    else:
        print("✗ Tabla 'solicitud' NO existe")

    print("\n=== DATOS EN LAS TABLAS ===")

    # Mostrar datos de Usuario
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM usuario"))
        count = result.fetchone()[0]
        print(f"Usuarios registrados: {count}")

        if count > 0:
            result = conn.execute(text("SELECT id, nombres, email, rol FROM usuario LIMIT 5"))
            rows = result.fetchall()
            print("Primeros usuarios:")
            for row in rows:
                print(f"  ID: {row[0]}, Nombre: {row[1]}, Correo: {row[2]}, Tipo: {row[3]}")

    print()

    # Mostrar datos de Solicitud
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM solicitud"))
        count = result.fetchone()[0]
        print(f"Solicitudes registradas: {count}")

        if count > 0:
            result = conn.execute(text("SELECT id, radicado, tipo_solicitud, asunto, estado, fecha FROM solicitud LIMIT 5"))
            rows = result.fetchall()
            print("Primeras solicitudes:")
            for row in rows:
                print(f"  ID: {row[0]}, Radicado: {row[1]}, Tipo: {row[2]}, Asunto: {row[3]}, Estado: {row[4]}, Fecha: {row[5]}")

if __name__ == "__main__":
    verificar_tablas()