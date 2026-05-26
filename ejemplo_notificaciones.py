"""
Ejemplo de integración de notificaciones con el modelo de Solicitud.
Copiar y adaptar según tu estructura real de BD.
"""

from notificaciones import (
    notificar_solicitud_creada,
    notificar_cambio_estado,
    notificar_respuesta_final,
    enviar_correo_prueba
)
from datetime import datetime


# ========== EJEMPLO 1: Al crear una solicitud ==========
def crear_solicitud_con_notificacion(
    nombre_solicitante: str,
    correo_solicitante: str,
    tipo_pqrs: str,
    descripcion: str,
    # ... otros campos ...
):
    """
    Crea una solicitud y envía notificación de radicación.
    """
    # Guardar en BD (pseudocódigo)
    # solicitud = Solicitud.create(...)
    numero_solicitud = "PQRS-2024-001"  # Generar número único
    fecha_creacion = datetime.now().strftime("%d/%m/%Y %H:%M")
    fecha_vencimiento = "30/06/2024"  # Calcular según tipo
    
    # Enviar notificación
    resultado = notificar_solicitud_creada(
        nombre_solicitante=nombre_solicitante,
        correo_solicitante=correo_solicitante,
        numero_solicitud=numero_solicitud,
        tipo_pqrs=tipo_pqrs,
        fecha_creacion=fecha_creacion,
        fecha_vencimiento=fecha_vencimiento,
        correos_adicionales=["admin@empresa.com"]  # Opcional: CC
    )
    
    print(f"Notificación enviada: {resultado}")
    return numero_solicitud


# ========== EJEMPLO 2: Al cambiar estado ==========
def cambiar_estado_solicitud_con_notificacion(
    numero_solicitud: str,
    nombre_solicitante: str,
    correo_solicitante: str,
    estado_anterior: str,
    estado_nuevo: str,
    observaciones: str = None
):
    """
    Cambia el estado de una solicitud y notifica al solicitante.
    """
    # Actualizar en BD (pseudocódigo)
    # solicitud.estado = estado_nuevo
    # solicitud.save()
    
    fecha_cambio = datetime.now().strftime("%d/%m/%Y %H:%M")
    
    # Enviar notificación
    resultado = notificar_cambio_estado(
        nombre_solicitante=nombre_solicitante,
        correo_solicitante=correo_solicitante,
        numero_solicitud=numero_solicitud,
        estado_anterior=estado_anterior,
        estado_nuevo=estado_nuevo,
        fecha_cambio=fecha_cambio,
        observaciones=observaciones,
        correos_adicionales=["funcionario@empresa.com"]
    )
    
    print(f"Notificación de cambio enviada: {resultado}")


# ========== EJEMPLO 3: Al enviar respuesta final ==========
def enviar_respuesta_final_con_notificacion(
    numero_solicitud: str,
    nombre_solicitante: str,
    correo_solicitante: str,
    tipo_pqrs: str,
    descripcion_respuesta: str
):
    """
    Envía la respuesta final y notifica al solicitante.
    """
    # Guardar respuesta en BD (pseudocódigo)
    # solicitud.respuesta = descripcion_respuesta
    # solicitud.fecha_respuesta = datetime.now()
    # solicitud.estado = "RESUELTA"
    # solicitud.save()
    
    fecha_respuesta = datetime.now().strftime("%d/%m/%Y")
    
    # Enviar notificación
    resultado = notificar_respuesta_final(
        nombre_solicitante=nombre_solicitante,
        correo_solicitante=correo_solicitante,
        numero_solicitud=numero_solicitud,
        tipo_pqrs=tipo_pqrs,
        fecha_respuesta=fecha_respuesta,
        descripcion_respuesta=descripcion_respuesta,
        correos_adicionales=["jefe@empresa.com"]
    )
    
    print(f"Notificación de respuesta enviada: {resultado}")


# ========== PRUEBA ==========
if __name__ == "__main__":
    # 1. Enviar correo de prueba
    print("=" * 60)
    print("PRUEBA DE CONFIGURACIÓN")
    print("=" * 60)
    resultado_prueba = enviar_correo_prueba("tucorreo@gmail.com")
    print(f"Resultado: {resultado_prueba}\n")
    
    # 2. Ejemplo: Crear solicitud
    print("=" * 60)
    print("EJEMPLO 1: CREAR SOLICITUD")
    print("=" * 60)
    crear_solicitud_con_notificacion(
        nombre_solicitante="Juan Pérez",
        correo_solicitante="juan@example.com",
        tipo_pqrs="Petición",
        descripcion="Solicito información sobre..."
    )
    print()
    
    # 3. Ejemplo: Cambiar estado
    print("=" * 60)
    print("EJEMPLO 2: CAMBIAR ESTADO")
    print("=" * 60)
    cambiar_estado_solicitud_con_notificacion(
        numero_solicitud="PQRS-2024-001",
        nombre_solicitante="Juan Pérez",
        correo_solicitante="juan@example.com",
        estado_anterior="Abierta",
        estado_nuevo="En Proceso",
        observaciones="Enviada a área responsable para análisis"
    )
    print()
    
    # 4. Ejemplo: Enviar respuesta
    print("=" * 60)
    print("EJEMPLO 3: ENVIAR RESPUESTA FINAL")
    print("=" * 60)
    enviar_respuesta_final_con_notificacion(
        numero_solicitud="PQRS-2024-001",
        nombre_solicitante="Juan Pérez",
        correo_solicitante="juan@example.com",
        tipo_pqrs="Petición",
        descripcion_respuesta="Se adjunta documento solicitado en formato PDF..."
    )
