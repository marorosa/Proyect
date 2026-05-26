#!/usr/bin/env python3
"""
Script para crear 20 solicitudes de ejemplo en la base de datos reflex.db.
"""
import sqlite3
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from autenticacion.autenticacion import engine

# Solicitudes de ejemplo con variedad de tipos y estados
SAMPLE_SOLICITUDES = [
    {
        "tipo_solicitud": "Petición",
        "asunto": "Solicito información sobre trámite de licencia de conducción",
        "descripcion": "Requiero conocer los pasos, requisitos y tiempo estimado para obtener mi licencia de conducción categoría B.",
        "ubicacion": "Bogotá, Cundinamarca",
        "area_responsable": "Licencias y Trámites",
        "persona_vulnerable": "Ninguna",
    },
    {
        "tipo_solicitud": "Queja",
        "asunto": "Mal trato recibido en ventanilla",
        "descripcion": "El pasado martes 20 de mayo recibí un trato irrespetuoso del servidor público en la ventanilla 3. El funcionario fue grosero y no atendió mis inquietudes adecuadamente.",
        "ubicacion": "Medellín, Antioquia",
        "area_responsable": "Atención al Ciudadano",
        "persona_vulnerable": "Ninguna",
    },
    {
        "tipo_solicitud": "Reclamo",
        "asunto": "No he recibido respuesta a solicitud anterior",
        "descripcion": "Hace más de dos meses presenté una solicitud sobre certificado de residencia y hasta ahora no me dan respuesta. Solicito que se acelere el trámite.",
        "ubicacion": "Cali, Valle del Cauca",
        "area_responsable": "Gestión Administrativa",
        "persona_vulnerable": "Víctimas - Conflicto Armado",
    },
    {
        "tipo_solicitud": "Sugerencia",
        "asunto": "Mejorar horarios de atención al público",
        "descripcion": "Sugiero ampliar el horario de atención hasta las 18:00 los jueves y viernes para ciudadanos que trabajan. Esto facilitaría el acceso a los servicios.",
        "ubicacion": "Bucaramanga, Santander",
        "area_responsable": "Planeación",
        "persona_vulnerable": "Ninguna",
    },
    {
        "tipo_solicitud": "Petición",
        "asunto": "Solicito copia de documento de identidad",
        "descripcion": "Necesito una copia auténtica de mi cédula de ciudadanía expedida en la ciudad de Bogotá para trámites de seguridad social.",
        "ubicacion": "Bogotá, Cundinamarca",
        "area_responsable": "Servicios Administrativos",
        "persona_vulnerable": "Ninguna",
    },
    {
        "tipo_solicitud": "Queja",
        "asunto": "Plataforma con fallas técnicas frecuentes",
        "descripcion": "La plataforma de PQRS se cae constantemente. No puedo enviar mis solicitudes porque el sistema no responde. Esto es muy frustrante.",
        "ubicacion": "Cartagena, Bolívar",
        "area_responsable": "Sistemas y Tecnología",
        "persona_vulnerable": "Ninguna",
    },
    {
        "tipo_solicitud": "Reclamo",
        "asunto": "Cobro indebido en factura de servicios",
        "descripcion": "La factura del mes anterior me muestra cobros duplicados. Requiero una revisión inmediata y corrección de los montos facturados.",
        "ubicacion": "Bogotá, Cundinamarca",
        "area_responsable": "Tesorería",
        "persona_vulnerable": "Persona de la tercera edad",
    },
    {
        "tipo_solicitud": "Sugerencia",
        "asunto": "Implementar atención por chat en línea",
        "descripcion": "Propongo que se implemente un servicio de chat en vivo para que los ciudadanos puedan resolver dudas rápidamente sin tener que hacer fila.",
        "ubicacion": "Bogotá, Cundinamarca",
        "area_responsable": "Atención al Ciudadano",
        "persona_vulnerable": "Ninguna",
    },
    {
        "tipo_solicitud": "Petición",
        "asunto": "Acceso a registros públicos",
        "descripcion": "Solicito acceso a los registros públicos de adjudicaciones de contratos del semestre anterior para propósitos de investigación académica.",
        "ubicacion": "Bogotá, Cundinamarca",
        "area_responsable": "Transparencia",
        "persona_vulnerable": "Ninguna",
    },
    {
        "tipo_solicitud": "Queja",
        "asunto": "Información errónea suministrada",
        "descripcion": "Un servidor me informó incorrectamente sobre los requisitos para un trámite, lo que me hizo perder tiempo y dinero. Requiero que se investigue y se corrija esto.",
        "ubicacion": "Medellín, Antioquia",
        "area_responsable": "Gestión Administrativa",
        "persona_vulnerable": "Ninguna",
    },
    {
        "tipo_solicitud": "Reclamo",
        "asunto": "Demora excesiva en entrega de documento",
        "descripcion": "Solicité un certificado hace 30 días y me informaron que está listo hace una semana, pero al ir por él no está disponible. Esto es inconcebible.",
        "ubicacion": "Cali, Valle del Cauca",
        "area_responsable": "Servicios Administrativos",
        "persona_vulnerable": "Primera Infancia",
    },
    {
        "tipo_solicitud": "Sugerencia",
        "asunto": "Crear punto de atención en zona rural",
        "descripcion": "Los habitantes de la zona rural deben desplazarse largas distancias. Sugiero crear un punto de atención descentralizado en la vereda El Carmen.",
        "ubicacion": "Cundinamarca",
        "area_responsable": "Planeación",
        "persona_vulnerable": "Ninguna",
    },
    {
        "tipo_solicitud": "Petición",
        "asunto": "Solicito información sobre becas educativas",
        "descripcion": "Requiero conocer las opciones de becas disponibles para estudiantes de pregrado en mi región, requisitos y fechas de convocatoria.",
        "ubicacion": "Bogotá, Cundinamarca",
        "area_responsable": "Educación",
        "persona_vulnerable": "Ninguna",
    },
    {
        "tipo_solicitud": "Queja",
        "asunto": "Falta de señalización en oficinas",
        "descripcion": "Las oficinas no tienen señalización clara. Es muy difícil saber dónde ir para cada trámite. Hay confusión permanente entre los ciudadanos.",
        "ubicacion": "Bucaramanga, Santander",
        "area_responsable": "Infraestructura",
        "persona_vulnerable": "Ninguna",
    },
    {
        "tipo_solicitud": "Reclamo",
        "asunto": "No se respetaron mis derechos como ciudadano",
        "descripcion": "Fue violado mi derecho de petición. No recibí respuesta oportuna a mi solicitud anterior y se venció el término de ley sin que se diera trámite.",
        "ubicacion": "Cartagena, Bolívar",
        "area_responsable": "Derechos Humanos",
        "persona_vulnerable": "Afrocolombiano",
    },
    {
        "tipo_solicitud": "Sugerencia",
        "asunto": "Implementar cita previa en línea",
        "descripcion": "Sugiero permitir que los ciudadanos agenden cita previa desde la plataforma para evitar esperas prolongadas en las oficinas.",
        "ubicacion": "Bogotá, Cundinamarca",
        "area_responsable": "Atención al Ciudadano",
        "persona_vulnerable": "Ninguna",
    },
    {
        "tipo_solicitud": "Petición",
        "asunto": "Solicito estado de mi solicitud PQRS",
        "descripcion": "¿Cuál es el estado actual de mi solicitud con radicado PQRS-2026-00123? Hace una semana que no tengo noticias al respecto.",
        "ubicacion": "Bogotá, Cundinamarca",
        "area_responsable": "Gestión de Solicitudes",
        "persona_vulnerable": "Ninguna",
    },
    {
        "tipo_solicitud": "Queja",
        "asunto": "Celular dañado en traslado de documentos",
        "descripcion": "Mientras esperaba ser atendido en la fila, un servidor me golpeó accidentalmente el celular causándome daño material. Requiero compensación.",
        "ubicacion": "Medellín, Antioquia",
        "area_responsable": "Atención al Ciudadano",
        "persona_vulnerable": "Ninguna",
    },
    {
        "tipo_solicitud": "Reclamo",
        "asunto": "Trato discriminatorio recibido",
        "descripcion": "Siento que fui discriminado por mi orientación sexual durante la atención en ventanilla. El funcionario fue agresivo y negó el servicio sin justificación.",
        "ubicacion": "Bogotá, Cundinamarca",
        "area_responsable": "Derechos Humanos",
        "persona_vulnerable": "Ninguna",
    },
    {
        "tipo_solicitud": "Sugerencia",
        "asunto": "Crear guías visuales en idioma de señas",
        "descripcion": "Sugiero desarrollar guías visuales en lenguaje de señas colombiano para mejorar la accesibilidad de personas sordas en los trámites.",
        "ubicacion": "Bogotá, Cundinamarca",
        "area_responsable": "Inclusión",
        "persona_vulnerable": "Discapacidad Auditiva",
    },
]


def main() -> None:
    db_path = Path(engine.url.database)
    if not db_path.exists():
        print(f"ERROR: no se encuentra la base de datos en {db_path}")
        return

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Obtener ciudadanos existentes para asociar solicitudes
    cursor.execute("SELECT id, email, nombres FROM usuario WHERE rol='ciudadano' LIMIT 10")
    ciudadanos = cursor.fetchall()

    if not ciudadanos:
        print("⚠️ No hay ciudadanos en la base de datos. Crea ciudadanos primero.")
        conn.close()
        return

    created = 0
    for idx, solicitud in enumerate(SAMPLE_SOLICITUDES):
        # Asociar ciudadano de forma circular
        usuario_id, email, nombres = ciudadanos[idx % len(ciudadanos)]

        # Radicado único
        radicado = f"PQRS-{datetime.now().year}-{uuid.uuid4().hex[:8]}".upper()

        # Variedad de estados
        estados = ["Radicada", "En Revisión", "Asignada", "En Proceso"]
        estado = estados[idx % len(estados)]

        # Fecha variable (últimas 2 semanas)
        dias_atras = (idx % 14) + 1
        fecha = (datetime.now() - timedelta(days=dias_atras)).isoformat()

        try:
            cursor.execute(
                """
                INSERT INTO solicitud (
                    radicado, tipo_solicitud, asunto, descripcion, ubicacion, 
                    documento, documento_basename, area_responsable, persona_vulnerable,
                    estado, fecha, creado_por, usuario_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    radicado,
                    solicitud["tipo_solicitud"],
                    solicitud["asunto"],
                    solicitud["descripcion"],
                    solicitud["ubicacion"],
                    None,  # documento
                    None,  # documento_basename
                    solicitud["area_responsable"],
                    solicitud["persona_vulnerable"],
                    estado,
                    fecha,
                    email,
                    usuario_id,
                ),
            )
            created += 1
            print(f"✅ Solicitud {idx + 1} creada: {radicado} - {solicitud['tipo_solicitud']} ({estado})")
        except sqlite3.Error as e:
            print(f"❌ Error creando solicitud {idx + 1}: {e}")

    conn.commit()
    conn.close()

    print(f"\n✨ Resumen: {created} solicitudes creadas de {len(SAMPLE_SOLICITUDES)}.")


if __name__ == "__main__":
    main()
