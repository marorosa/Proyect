#!/usr/bin/env python3
"""
Script para crear varios ciudadanos de ejemplo en la base de datos reflex.db.
"""
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from autenticacion.autenticacion import engine, tiene_password

SAMPLE_USUARIOS = [
    {
        "email": "juan.perez@ejemplo.com",
        "password": "C1udadano!",
        "nombres": "Juan",
        "apellidos": "Pérez",
        "tipo_identificacion": "Cédula de ciudadanía",
        "numero_identificacion": "1020304050",
        "sexo": "Masculino",
        "direccion": "Calle 12 #34-56",
        "telefono": "3101234567",
        "departamento": "Cundinamarca",
        "ciudad": "Bogotá",
        "etnia": "Ninguna",
        "persona_vulnerable": "Ninguna",
        "acepta_notificaciones": True,
        "acepta_politica_datos": True,
    },
    {
        "email": "ana.martinez@ejemplo.com",
        "password": "Segura2026$",
        "nombres": "Ana",
        "apellidos": "Martínez",
        "tipo_identificacion": "Cédula de ciudadanía",
        "numero_identificacion": "1547382910",
        "sexo": "Femenino",
        "direccion": "Carrera 45 #67-89",
        "telefono": "3129876543",
        "departamento": "Antioquia",
        "ciudad": "Medellín",
        "etnia": "Afrocolombiano",
        "persona_vulnerable": "Primera Infancia",
        "acepta_notificaciones": True,
        "acepta_politica_datos": True,
    },
    {
        "email": "carlos.ramirez@ejemplo.com",
        "password": "PqrS@2026",
        "nombres": "Carlos",
        "apellidos": "Ramírez",
        "tipo_identificacion": "Cédula de ciudadanía",
        "numero_identificacion": "2030405060",
        "sexo": "Masculino",
        "direccion": "Avenida 20 #15-23",
        "telefono": "3145556677",
        "departamento": "Valle del Cauca",
        "ciudad": "Cali",
        "etnia": "Ninguna",
        "persona_vulnerable": "No brinda información",
        "acepta_notificaciones": True,
        "acepta_politica_datos": True,
    },
    {
        "email": "andrea.gomez@ejemplo.com",
        "password": "Seguridad#1",
        "nombres": "Andrea",
        "apellidos": "Gómez",
        "tipo_identificacion": "Cédula de ciudadanía",
        "numero_identificacion": "1837364554",
        "sexo": "Femenino",
        "direccion": "Diagonal 58 #12-34",
        "telefono": "3172233445",
        "departamento": "Santander",
        "ciudad": "Bucaramanga",
        "etnia": "Ninguna",
        "persona_vulnerable": "Veteranos Fuerza Pública",
        "acepta_notificaciones": True,
        "acepta_politica_datos": True,
    },
    {
        "email": "maria.lopez@ejemplo.com",
        "password": "Pqrs2026$",
        "nombres": "María",
        "apellidos": "López",
        "tipo_identificacion": "Cédula de ciudadanía",
        "numero_identificacion": "1122334455",
        "sexo": "Otro",
        "direccion": "Transversal 7 #89-10",
        "telefono": "3109988776",
        "departamento": "Bolívar",
        "ciudad": "Cartagena",
        "etnia": "Raizal",
        "persona_vulnerable": "Víctimas - Conflicto Armado",
        "acepta_notificaciones": True,
        "acepta_politica_datos": True,
    },
    {
        "email": "hinolopez6@gmail.com",
        "password": "Hino2026!",
        "nombres": "Hino",
        "apellidos": "López",
        "tipo_identificacion": "Cédula de ciudadanía",
        "numero_identificacion": "1234567890",
        "sexo": "Otro",
        "direccion": "Calle Falsa 123",
        "telefono": "3111234567",
        "departamento": "Cundinamarca",
        "ciudad": "Bogotá",
        "etnia": "Ninguna",
        "persona_vulnerable": "Ninguna",
        "acepta_notificaciones": True,
        "acepta_politica_datos": True,
    },
]

INSERT_SQL = """
INSERT INTO usuario (
    email,
    Contraseña,
    rol,
    is_active,
    Fecha_de_creacion,
    tipo_identificacion,
    numero_identificacion,
    nombres,
    apellidos,
    genero,
    direccion,
    telefono,
    departamento,
    ciudad,
    etnia,
    persona_vulnerable,
    acepta_notificaciones,
    acepta_politica_datos
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def main() -> None:
    db_path = Path(engine.url.database)
    if not db_path.exists():
        print(f"ERROR: no se encuentra la base de datos en {db_path}")
        return

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    created = 0
    skipped = 0

    for usuario in SAMPLE_USUARIOS:
        cursor.execute("SELECT id FROM usuario WHERE email = ?", (usuario["email"],))
        if cursor.fetchone():
            print(f"⚠️ Usuario ya existente: {usuario['email']}")
            skipped += 1
            continue

        cursor.execute(
            INSERT_SQL,
            (
                usuario["email"],
                tiene_password(usuario["password"]),
                "ciudadano",
                1,
                datetime.now(),
                usuario["tipo_identificacion"],
                usuario["numero_identificacion"],
                usuario["nombres"],
                usuario["apellidos"],
                usuario["sexo"],
                usuario["direccion"],
                usuario["telefono"],
                usuario["departamento"],
                usuario["ciudad"],
                usuario["etnia"],
                usuario["persona_vulnerable"],
                int(usuario["acepta_notificaciones"]),
                int(usuario["acepta_politica_datos"]),
            ),
        )
        created += 1
        print(f"✅ Usuario creado: {usuario['email']}")

    conn.commit()
    conn.close()

    print(f"\nResumen: {created} usuarios creados, {skipped} saltados.")


if __name__ == "__main__":
    main()
