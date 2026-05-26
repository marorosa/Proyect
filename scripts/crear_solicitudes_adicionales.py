#!/usr/bin/env python3
"""
Script para crear 50 solicitudes adicionales de ejemplo con temáticas muy variadas.
"""
import sqlite3
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from autenticacion.autenticacion import engine

# Solicitudes adicionales con temáticas diferentes y más variadas
SAMPLE_SOLICITUDES_ADICIONALES = [
    {
        "tipo_solicitud": "Petición",
        "asunto": "Solicito información sobre subsidios de vivienda",
        "descripcion": "¿Cuáles son los programas de subsidio de vivienda disponibles? Necesito conocer requisitos, montos y fechas de convocatoria para 2026.",
        "ubicacion": "Bogotá, Cundinamarca",
        "area_responsable": "Vivienda",
        "persona_vulnerable": "Ninguna",
    },
    {
        "tipo_solicitud": "Queja",
        "asunto": "Acoso laboral en dependencia pública",
        "descripcion": "He sido víctima de acoso laboral por parte de mi supervisor durante 6 meses. Se han presentado evidencias pero la administración no actúa.",
        "ubicacion": "Medellín, Antioquia",
        "area_responsable": "Recursos Humanos",
        "persona_vulnerable": "Ninguna",
    },
    {
        "tipo_solicitud": "Reclamo",
        "asunto": "Daño de bien público ocasionado por funcionario",
        "descripcion": "Un vehículo oficial causó daños a mi propiedad. Presenté denuncias pero no hay respuesta. Solicito indemnización.",
        "ubicacion": "Cali, Valle del Cauca",
        "area_responsable": "Juridica",
        "persona_vulnerable": "Ninguna",
    },
    {
        "tipo_solicitud": "Sugerencia",
        "asunto": "Crear programa de voluntariado comunitario",
        "descripcion": "Sugiero establecer un programa de voluntariado donde los ciudadanos puedan participar en actividades de desarrollo social.",
        "ubicacion": "Bogotá, Cundinamarca",
        "area_responsable": "Participación Ciudadana",
        "persona_vulnerable": "Ninguna",
    },
    {
        "tipo_solicitud": "Petición",
        "asunto": "Acceso a expediente médico del servicio de salud",
        "descripcion": "Solicito copia de mi expediente médico de la última atención en el hospital público para tramitar ante otra institución.",
        "ubicacion": "Bogotá, Cundinamarca",
        "area_responsable": "Salud",
        "persona_vulnerable": "Persona de la tercera edad",
    },
    {
        "tipo_solicitud": "Queja",
        "asunto": "Contaminación ambiental en sector residencial",
        "descripcion": "La fábrica vecina genera ruido y emisiones que afectan la salud de residentes. Hemos reportado pero no hay control ambiental.",
        "ubicacion": "Barranquilla, Atlántico",
        "area_responsable": "Ambiente",
        "persona_vulnerable": "Ninguna",
    },
    {
        "tipo_solicitud": "Reclamo",
        "asunto": "Error en cálculo de pensión de jubilación",
        "descripcion": "El cálculo de mi pensión está incorrecto. Según mi expediente debería recibir un monto superior. Solicito revisión urgente.",
        "ubicacion": "Bogotá, Cundinamarca",
        "area_responsable": "Pensiones",
        "persona_vulnerable": "Persona de la tercera edad",
    },
    {
        "tipo_solicitud": "Sugerencia",
        "asunto": "Implementar carril exclusivo para bicicletas",
        "descripcion": "Propongo crear un carril exclusivo para bicicletas en la avenida principal para promover movilidad sostenible.",
        "ubicacion": "Bogotá, Cundinamarca",
        "area_responsable": "Movilidad",
        "persona_vulnerable": "Ninguna",
    },
    {
        "tipo_solicitud": "Petición",
        "asunto": "Certificado de antecedentes penales",
        "descripcion": "Requiero un certificado de antecedentes penales para solicitud de empleo en el exterior. Necesito que sea expedido rápidamente.",
        "ubicacion": "Bogotá, Cundinamarca",
        "area_responsable": "Justicia",
        "persona_vulnerable": "Ninguna",
    },
    {
        "tipo_solicitud": "Queja",
        "asunto": "Falta de atención a personas con discapacidad",
        "descripcion": "Las oficinas no tienen accesibilidad para personas en silla de ruedas. Faltan rampas, ascensores y baños adaptados.",
        "ubicacion": "Bogotá, Cundinamarca",
        "area_responsable": "Inclusión",
        "persona_vulnerable": "Discapacidad Motriz",
    },
    {
        "tipo_solicitud": "Reclamo",
        "asunto": "Incumplimiento de contrato de servicios",
        "descripcion": "El contratista no ha cumplido con los compromisos. Las obras están paralizadas hace 3 meses. Exijo compensación por daño.",
        "ubicacion": "Bucaramanga, Santander",
        "area_responsable": "Contratación",
        "persona_vulnerable": "Ninguna",
    },
    {
        "tipo_solicitud": "Sugerencia",
        "asunto": "Crear escuela de formación en oficios técnicos",
        "descripcion": "Sugiero establecer una escuela pública que ofrezca formación gratuita en oficios técnicos para jóvenes sin recursos.",
        "ubicacion": "Bogotá, Cundinamarca",
        "area_responsable": "Educación",
        "persona_vulnerable": "Ninguna",
    },
    {
        "tipo_solicitud": "Petición",
        "asunto": "Información sobre programa de vivienda joven",
        "descripcion": "¿Existe programa de vivienda para jóvenes? ¿Cuál es el plazo de inscripción? Necesito información detallada.",
        "ubicacion": "Cali, Valle del Cauca",
        "area_responsable": "Vivienda",
        "persona_vulnerable": "Ninguna",
    },
    {
        "tipo_solicitud": "Queja",
        "asunto": "Represión policial desproporcionada",
        "descripcion": "Fui agredido por agentes de policía durante manifestación pacífica. Requiero investigación y medidas disciplinarias.",
        "ubicacion": "Bogotá, Cundinamarca",
        "area_responsable": "Seguridad",
        "persona_vulnerable": "Ninguna",
    },
    {
        "tipo_solicitud": "Reclamo",
        "asunto": "Corte de servicios sin previo aviso",
        "descripcion": "Cortaron el servicio de energía sin notificación previa ni oportunidad de pagar. He pagado religiosamente todos mis recibos.",
        "ubicacion": "Medellín, Antioquia",
        "area_responsable": "Servicios Públicos",
        "persona_vulnerable": "Ninguna",
    },
    {
        "tipo_solicitud": "Sugerencia",
        "asunto": "Mejorar alumbrado público en zona periférica",
        "descripcion": "Propongo aumentar el número de luminarias en la zona periférica de nuestro barrio. Actualmente hay muy poca iluminación y es inseguro.",
        "ubicacion": "Bogotá, Cundinamarca",
        "area_responsable": "Infraestructura",
        "persona_vulnerable": "Ninguna",
    },
    {
        "tipo_solicitud": "Petición",
        "asunto": "Registro de marca comercial",
        "descripcion": "Solicito información sobre el trámite para registrar mi marca comercial. ¿Cuál es el costo y los requisitos necesarios?",
        "ubicacion": "Bogotá, Cundinamarca",
        "area_responsable": "Comercio",
        "persona_vulnerable": "Ninguna",
    },
    {
        "tipo_solicitud": "Queja",
        "asunto": "Negligencia médica en atención de emergencia",
        "descripcion": "Fui atendido de manera negligente en urgencias. El diagnóstico fue errado, lo que agravó mi condición. Exijo indemnización.",
        "ubicacion": "Bogotá, Cundinamarca",
        "area_responsable": "Salud",
        "persona_vulnerable": "Ninguna",
    },
    {
        "tipo_solicitud": "Reclamo",
        "asunto": "Expulsión injusta de institución educativa",
        "descripcion": "Mi hijo fue expulsado sin debido proceso ni derecho a defensa. La decisión fue arbitraria y viola sus derechos constitucionales.",
        "ubicacion": "Bogotá, Cundinamarca",
        "area_responsable": "Educación",
        "persona_vulnerable": "Ninguna",
    },
    {
        "tipo_solicitud": "Sugerencia",
        "asunto": "Crear banco de datos de ofertas de empleo",
        "descripcion": "Sugiero crear una plataforma pública donde se publiquen ofertas de empleo disponibles para desempleados. Sería de gran utilidad.",
        "ubicacion": "Bogotá, Cundinamarca",
        "area_responsable": "Empleo",
        "persona_vulnerable": "Ninguna",
    },
    {
        "tipo_solicitud": "Petición",
        "asunto": "Autorización para cambio de nombre legal",
        "descripcion": "Solicito iniciar trámite de cambio de nombre legal. He preparado toda la documentación requerida.",
        "ubicacion": "Bogotá, Cundinamarca",
        "area_responsable": "Registraduría",
        "persona_vulnerable": "Ninguna",
    },
    {
        "tipo_solicitud": "Queja",
        "asunto": "Falta de vigilancia en zona pública",
        "descripcion": "El parque de nuestro barrio no tiene vigilancia. Constantemente hay robos y asaltos. Exijo mayor presencia de policía.",
        "ubicacion": "Bogotá, Cundinamarca",
        "area_responsable": "Seguridad",
        "persona_vulnerable": "Ninguna",
    },
    {
        "tipo_solicitud": "Reclamo",
        "asunto": "Tratamiento inadecuado en albergue para personas sin hogar",
        "descripcion": "El albergue municipal no ofrece condiciones dignas. Faltan servicios básicos y hay maltrato del personal.",
        "ubicacion": "Medellín, Antioquia",
        "area_responsable": "Bienestar Social",
        "persona_vulnerable": "Población en situación de calle",
    },
    {
        "tipo_solicitud": "Sugerencia",
        "asunto": "Ampliar cobertura de transporte público nocturno",
        "descripcion": "Propongo extender horario de transporte público hasta las 2 AM para trabajadores nocturnos.",
        "ubicacion": "Bogotá, Cundinamarca",
        "area_responsable": "Transporte",
        "persona_vulnerable": "Ninguna",
    },
    {
        "tipo_solicitud": "Petición",
        "asunto": "Consulta sobre programa de apoyo a víctimas del conflicto",
        "descripcion": "¿Cuáles son los beneficios disponibles para víctimas del conflicto armado? Necesito información sobre subsidios y reparación.",
        "ubicacion": "Bogotá, Cundinamarca",
        "area_responsable": "Víctimas",
        "persona_vulnerable": "Víctimas - Conflicto Armado",
    },
    {
        "tipo_solicitud": "Queja",
        "asunto": "Demora en expedición de carnet de identidad",
        "descripcion": "Solicité carnet hace 2 meses y no está listo. Necesito urgentemente para trabajar.",
        "ubicacion": "Cali, Valle del Cauca",
        "area_responsable": "Identificación",
        "persona_vulnerable": "Ninguna",
    },
    {
        "tipo_solicitud": "Reclamo",
        "asunto": "Sobrecobro en servicios de agua",
        "descripcion": "Mi factura del mes pasado tiene un cobro inexplicable. El consumo reportado no corresponde con mi uso real.",
        "ubicacion": "Bogotá, Cundinamarca",
        "area_responsable": "Servicios Públicos",
        "persona_vulnerable": "Persona de la tercera edad",
    },
    {
        "tipo_solicitud": "Sugerencia",
        "asunto": "Crear zonas verdes en áreas urbanas densas",
        "descripcion": "Propongo convertir lotes baldíos en parques comunitarios para mejorar calidad de vida.",
        "ubicacion": "Bogotá, Cundinamarca",
        "area_responsable": "Ambiente",
        "persona_vulnerable": "Ninguna",
    },
    {
        "tipo_solicitud": "Petición",
        "asunto": "Información sobre becas para postgrado en el exterior",
        "descripcion": "¿Existen programas de becas para estudios de postgrado en universidades extranjeras? Requisitos y plazos.",
        "ubicacion": "Bogotá, Cundinamarca",
        "area_responsable": "Educación",
        "persona_vulnerable": "Ninguna",
    },
    {
        "tipo_solicitud": "Queja",
        "asunto": "Falta de señalización vial en zona escolar",
        "descripcion": "La zona escolar no tiene suficientes señales de tránsito. Hay riesgo para los niños al cruzar la calle.",
        "ubicacion": "Medellín, Antioquia",
        "area_responsable": "Tránsito",
        "persona_vulnerable": "Primera Infancia",
    },
    {
        "tipo_solicitud": "Reclamo",
        "asunto": "Desalojo injustificado de vivienda arrendada",
        "descripcion": "El arrendador me desalojó sin seguir procedimiento legal. No me permitió recoger pertenencias.",
        "ubicacion": "Bogotá, Cundinamarca",
        "area_responsable": "Juridica",
        "persona_vulnerable": "Ninguna",
    },
    {
        "tipo_solicitud": "Sugerencia",
        "asunto": "Implementar sistema de reciclaje en instituciones públicas",
        "descripcion": "Sugiero instalar contenedores de reciclaje en todas las oficinas públicas para promover la sostenibilidad.",
        "ubicacion": "Bogotá, Cundinamarca",
        "area_responsable": "Ambiente",
        "persona_vulnerable": "Ninguna",
    },
    {
        "tipo_solicitud": "Petición",
        "asunto": "Copia de acta de matrimonio",
        "descripcion": "Necesito una copia auténtica de mi acta de matrimonio para trámites de herencia.",
        "ubicacion": "Bogotá, Cundinamarca",
        "area_responsable": "Registraduría",
        "persona_vulnerable": "Ninguna",
    },
    {
        "tipo_solicitud": "Queja",
        "asunto": "Presencia de mendigos agresivos en transporte público",
        "descripcion": "Personas en situación de calle actúan de forma agresiva en buses. Requiero mayor seguridad en transporte.",
        "ubicacion": "Bogotá, Cundinamarca",
        "area_responsable": "Seguridad",
        "persona_vulnerable": "Población en situación de calle",
    },
    {
        "tipo_solicitud": "Reclamo",
        "asunto": "Falta de cumplimiento de cita médica programada",
        "descripcion": "Llegué a mi cita a tiempo pero fue cancelada sin motivo. Necesito que se reprograme urgentemente.",
        "ubicacion": "Bogotá, Cundinamarca",
        "area_responsable": "Salud",
        "persona_vulnerable": "Persona de la tercera edad",
    },
    {
        "tipo_solicitud": "Sugerencia",
        "asunto": "Crear seminarios de educación financiera",
        "descripcion": "Propongo talleres gratuitos sobre gestión de dinero, ahorro e inversión para ciudadanos.",
        "ubicacion": "Bogotá, Cundinamarca",
        "area_responsable": "Educación",
        "persona_vulnerable": "Ninguna",
    },
    {
        "tipo_solicitud": "Petición",
        "asunto": "Información sobre cambio de residencia legal",
        "descripcion": "¿Cuál es el procedimiento para cambiar residencia legal? ¿Debo hacer trámite ante alguna autoridad?",
        "ubicacion": "Bogotá, Cundinamarca",
        "area_responsable": "Registraduría",
        "persona_vulnerable": "Ninguna",
    },
    {
        "tipo_solicitud": "Queja",
        "asunto": "Falta de atención a personas indígenas",
        "descripcion": "Los funcionarios no respetan la diversidad cultural. Hubo maltrato a ciudadano de comunidad indígena.",
        "ubicacion": "Bogotá, Cundinamarca",
        "area_responsable": "Inclusión",
        "persona_vulnerable": "Afrocolombiano",
    },
    {
        "tipo_solicitud": "Reclamo",
        "asunto": "Recorte injustificado de beneficio pensional",
        "descripcion": "Mi pensión fue disminuida sin previo aviso ni justificación. Requiero explicación y restauración.",
        "ubicacion": "Bogotá, Cundinamarca",
        "area_responsable": "Pensiones",
        "persona_vulnerable": "Persona de la tercera edad",
    },
    {
        "tipo_solicitud": "Sugerencia",
        "asunto": "Crear app móvil para trámites ciudadanos",
        "descripcion": "Propongo desarrollar aplicación para realizar trámites desde celular sin ir a ventanilla.",
        "ubicacion": "Bogotá, Cundinamarca",
        "area_responsable": "Sistemas y Tecnología",
        "persona_vulnerable": "Ninguna",
    },
    {
        "tipo_solicitud": "Petición",
        "asunto": "Solicito copia de resolución de licencia profesional",
        "descripcion": "Necesito documento que acredite mi registro profesional. Será usado para trámites en el extranjero.",
        "ubicacion": "Bogotá, Cundinamarca",
        "area_responsable": "Profesional",
        "persona_vulnerable": "Ninguna",
    },
    {
        "tipo_solicitud": "Queja",
        "asunto": "Ruido excesivo en zona residencial",
        "descripcion": "Establecimiento comercial genera ruido intolerable hasta altas horas. Afecta sueño de residentes.",
        "ubicacion": "Bogotá, Cundinamarca",
        "area_responsable": "Ambiente",
        "persona_vulnerable": "Ninguna",
    },
    {
        "tipo_solicitud": "Reclamo",
        "asunto": "Falta de medicamentos en hospital público",
        "descripcion": "El hospital no tiene medicamentos recetados. Me obligaron a comprarlos de forma privada.",
        "ubicacion": "Bogotá, Cundinamarca",
        "area_responsable": "Salud",
        "persona_vulnerable": "Ninguna",
    },
    {
        "tipo_solicitud": "Sugerencia",
        "asunto": "Ampliar centros de acopio de reciclaje",
        "descripcion": "Sugiero distribuir más puntos de recolección de materiales reciclables en la ciudad.",
        "ubicacion": "Bogotá, Cundinamarca",
        "area_responsable": "Ambiente",
        "persona_vulnerable": "Ninguna",
    },
    {
        "tipo_solicitud": "Petición",
        "asunto": "Información sobre permiso de residencia extranjera",
        "descripcion": "Soy extranjero y necesito conocer requisitos para obtener residencia permanente en el país.",
        "ubicacion": "Bogotá, Cundinamarca",
        "area_responsable": "Migraciones",
        "persona_vulnerable": "Ninguna",
    },
    {
        "tipo_solicitud": "Queja",
        "asunto": "Falta de capacitación a funcionarios públicos",
        "descripcion": "Funcionarios desconocen procedimientos básicos. Esto genera trámites erróneos y demoras.",
        "ubicacion": "Bogotá, Cundinamarca",
        "area_responsable": "Recursos Humanos",
        "persona_vulnerable": "Ninguna",
    },
    {
        "tipo_solicitud": "Reclamo",
        "asunto": "Cierre de clínica sin advertencia a pacientes",
        "descripcion": "La clínica cerró sin informar a pacientes. Perdí mis historias médicas.",
        "ubicacion": "Bogotá, Cundinamarca",
        "area_responsable": "Salud",
        "persona_vulnerable": "Ninguna",
    },
    {
        "tipo_solicitud": "Sugerencia",
        "asunto": "Establecer peluquería pública para personas adultas mayores",
        "descripcion": "Propongo crear servicio de peluquería gratuito para personas de tercera edad.",
        "ubicacion": "Bogotá, Cundinamarca",
        "area_responsable": "Bienestar Social",
        "persona_vulnerable": "Persona de la tercera edad",
    },
    {
        "tipo_solicitud": "Petición",
        "asunto": "Solicito información sobre antecedentes disciplinarios",
        "descripcion": "¿Tengo antecedentes disciplinarios en la administración pública? Necesito certificado de no hallazgo.",
        "ubicacion": "Bogotá, Cundinamarca",
        "area_responsable": "Disciplina",
        "persona_vulnerable": "Ninguna",
    },
    {
        "tipo_solicitud": "Queja",
        "asunto": "Trato discriminatorio hacia migrantes",
        "descripcion": "Funcionarios tuvieron actitud discriminatoria conmigo por mi origen extranjero. Exijo disculpas públicas.",
        "ubicacion": "Bogotá, Cundinamarca",
        "area_responsable": "Inclusión",
        "persona_vulnerable": "Ninguna",
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
    for idx, solicitud in enumerate(SAMPLE_SOLICITUDES_ADICIONALES):
        # Asociar ciudadano de forma circular
        usuario_id, email, nombres = ciudadanos[idx % len(ciudadanos)]

        # Radicado único
        radicado = f"PQRS-{datetime.now().year}-{uuid.uuid4().hex[:8]}".upper()

        # Variedad de estados
        estados = ["Radicada", "En Revisión", "Asignada", "En Proceso", "Cerrada"]
        estado = estados[idx % len(estados)]

        # Fecha variable (últimas 3 semanas)
        dias_atras = (idx % 21) + 1
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

    print(f"\n✨ Resumen: {created} solicitudes adicionales creadas de {len(SAMPLE_SOLICITUDES_ADICIONALES)}.")


if __name__ == "__main__":
    main()
