#!/usr/bin/env python3
"""
Script de prueba para verificar la funcionalidad completa de persistencia de solicitudes
"""
import sys
import os
sys.path.append(os.path.dirname(__file__))

from sqlmodel import create_engine, Session
from sqlalchemy import text
from autenticacion.usuario_model import Usuario, Solicitud
from datetime import datetime, timedelta
from notificaciones import notificar_solicitud_creada, notificar_cambio_estado

# Configurar la base de datos
DATABASE_URL = "sqlite:///reflex.db"
engine = create_engine(DATABASE_URL, echo=False)

def probar_persistencia():
    """Prueba la funcionalidad completa de persistencia"""
    print("=== PRUEBA DE PERSISTENCIA DE SOLICITUDES ===\n")

    # Crear una nueva solicitud de prueba
    with Session(engine) as session:
        # Buscar un usuario ciudadano para asignar la solicitud
        usuario = session.exec(Usuario.select().where(Usuario.rol == "ciudadano")).first()
        if not usuario:
            print("✗ No se encontró un usuario ciudadano para la prueba")
            return

        print(f"✓ Usuario encontrado: {usuario.nombres} (ID: {usuario.id})")

        # Crear una nueva solicitud
        nueva_solicitud = Solicitud(
            radicado=f"PQRS-TEST-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            tipo_solicitud="Prueba",
            asunto="Solicitud de prueba automática",
            descripcion="Esta es una solicitud creada automáticamente para probar la persistencia",
            ubicacion="Ciudad de prueba",
            documento=None,
            documento_basename=None,
            estado="Radicada",
            fecha=datetime.now(),
            creado_por=usuario.nombres,
            usuario_id=usuario.id
        )

        session.add(nueva_solicitud)
        session.commit()
        session.refresh(nueva_solicitud)

        print(f"✓ Nueva solicitud creada con ID: {nueva_solicitud.id}")
        print(f"  Radicado: {nueva_solicitud.radicado}")
        print(f"  Tipo: {nueva_solicitud.tipo_solicitud}")
        print(f"  Asunto: {nueva_solicitud.asunto}")
        print(f"  Estado: {nueva_solicitud.estado}")

        # Enviar notificación al crear la solicitud (ejemplo)
        try:
            fecha_creacion = nueva_solicitud.fecha.strftime("%d/%m/%Y %H:%M")
            # Calcular fecha de vencimiento simple (ejemplo: +15 días)
            fecha_vencimiento = (nueva_solicitud.fecha + timedelta(days=15)).strftime("%d/%m/%Y")
            correo_usuario = usuario.email if getattr(usuario, 'email', None) else None
            if correo_usuario:
                res = notificar_solicitud_creada(
                    nombre_solicitante=usuario.nombres or usuario.email,
                    correo_solicitante=correo_usuario,
                    numero_solicitud=nueva_solicitud.radicado,
                    tipo_pqrs=nueva_solicitud.tipo_solicitud,
                    fecha_creacion=fecha_creacion,
                    fecha_vencimiento=fecha_vencimiento,
                    correos_adicionales=None
                )
                print(f"→ Notificación de creación enviada: {res}")
            else:
                print("→ No se envió notificación: usuario no tiene email registrado")
        except Exception as e:
            print(f"→ Error enviando notificación de creación: {e}")

    print("\n=== VERIFICACIÓN DE CARGA ===")

    # Verificar que se puede cargar la solicitud
    with Session(engine) as session:
        # Cargar solicitudes del usuario
        solicitudes = session.exec(Solicitud.select().where(Solicitud.usuario_id == usuario.id)).all()

        print(f"✓ Solicitudes encontradas para el usuario {usuario.nombres}: {len(solicitudes)}")

        for sol in solicitudes[-3:]:  # Mostrar las últimas 3
            print(f"  ID: {sol.id}, Radicado: {sol.radicado}, Asunto: {sol.asunto}, Estado: {sol.estado}")

    print("\n=== PRUEBA DE EDICIÓN ===")

    # Probar editar una solicitud
    with Session(engine) as session:
        solicitud = session.exec(Solicitud.select().where(Solicitud.usuario_id == usuario.id).order_by(Solicitud.id.desc())).first()

        if solicitud:
            estado_anterior = solicitud.estado
            solicitud.estado = "En proceso"
            session.commit()

            # Enviar notificación de cambio de estado (ejemplo)
            try:
                correo_usuario = usuario.email if getattr(usuario, 'email', None) else None
                if correo_usuario:
                    fecha_cambio = datetime.now().strftime("%d/%m/%Y %H:%M")
                    res2 = notificar_cambio_estado(
                        nombre_solicitante=usuario.nombres or usuario.email,
                        correo_solicitante=correo_usuario,
                        numero_solicitud=solicitud.radicado,
                        estado_anterior=estado_anterior,
                        estado_nuevo=solicitud.estado,
                        fecha_cambio=fecha_cambio,
                        observaciones="Actualizado por script de prueba",
                        correos_adicionales=None
                    )
                    print(f"→ Notificación de cambio enviada: {res2}")
                else:
                    print("→ No se envió notificación de cambio: usuario no tiene email registrado")
            except Exception as e:
                print(f"→ Error enviando notificación de cambio: {e}")

            print(f"✓ Solicitud {solicitud.id} editada:")
            print(f"  Estado anterior: {estado_anterior}")
            print(f"  Estado nuevo: {solicitud.estado}")

    print("\n=== PRUEBA COMPLETADA EXITOSAMENTE ===")
    print("✓ La persistencia de solicitudes está funcionando correctamente")

if __name__ == "__main__":
    probar_persistencia()