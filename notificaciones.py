"""
Módulo de notificaciones para PQRS usando Resend.
Maneja el envío de correos para diferentes estados de solicitudes.
"""

import os
import logging
from typing import Dict, Optional, List
from datetime import datetime
from dotenv import load_dotenv
import resend

# Cargar variables de entorno
load_dotenv()

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('notificaciones.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configurar Resend
resend.api_key = os.getenv("RESEND_API_KEY")
RESEND_FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL", "onboarding@resend.dev")
EMPRESA_NOMBRE = os.getenv("EMPRESA_NOMBRE", "Sistema de PQRS")


# ========== PLANTILLAS DE CORREOS ==========

def template_solicitud_creada(
    nombre_solicitante: str,
    numero_solicitud: str,
    tipo_pqrs: str,
    fecha_creacion: str,
    fecha_vencimiento: str
) -> str:
    """Template HTML para notificar creación de solicitud"""
    return f"""
    <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; background-color: #f5f5f5; }}
                .container {{ max-width: 600px; margin: 20px auto; background: white; padding: 20px; border-radius: 8px; }}
                .header {{ background-color: #003366; color: white; padding: 15px; border-radius: 5px; text-align: center; }}
                .content {{ margin: 20px 0; }}
                .info {{ background-color: #f0f8ff; padding: 15px; border-left: 4px solid #003366; margin: 10px 0; }}
                .footer {{ color: #666; font-size: 12px; margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; }}
                .button {{ background-color: #003366; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>¡Solicitud Radicada Exitosamente!</h1>
                </div>
                
                <div class="content">
                    <p>Estimado/a <strong>{nombre_solicitante}</strong>,</p>
                    
                    <p>Su solicitud de {tipo_pqrs} ha sido radicada exitosamente en {EMPRESA_NOMBRE}.</p>
                    
                    <div class="info">
                        <p><strong>Número de Solicitud:</strong> {numero_solicitud}</p>
                        <p><strong>Tipo:</strong> {tipo_pqrs}</p>
                        <p><strong>Fecha de Radicación:</strong> {fecha_creacion}</p>
                        <p><strong>Fecha de Vencimiento:</strong> {fecha_vencimiento}</p>
                    </div>
                    
                    <p>Puede seguimiento de su solicitud usando el número de radicación anterior.</p>
                    
                    <p>Si tiene preguntas, no dude en contactarnos.</p>
                </div>
                
                <div class="footer">
                    <p>{EMPRESA_NOMBRE}</p>
                    <p>Este es un correo automatizado, por favor no responda a este mensaje.</p>
                </div>
            </div>
        </body>
    </html>
    """


def template_cambio_estado(
    nombre_solicitante: str,
    numero_solicitud: str,
    estado_anterior: str,
    estado_nuevo: str,
    fecha_cambio: str,
    observaciones: Optional[str] = None
) -> str:
    """Template HTML para notificar cambio de estado"""
    obs_html = f"<p><strong>Observaciones:</strong> {observaciones}</p>" if observaciones else ""
    
    return f"""
    <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; background-color: #f5f5f5; }}
                .container {{ max-width: 600px; margin: 20px auto; background: white; padding: 20px; border-radius: 8px; }}
                .header {{ background-color: #003366; color: white; padding: 15px; border-radius: 5px; text-align: center; }}
                .content {{ margin: 20px 0; }}
                .estado {{ background-color: #e8f5e9; padding: 15px; border-left: 4px solid #4caf50; margin: 10px 0; border-radius: 5px; }}
                .footer {{ color: #666; font-size: 12px; margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>¡Actualización de Su Solicitud!</h1>
                </div>
                
                <div class="content">
                    <p>Estimado/a <strong>{nombre_solicitante}</strong>,</p>
                    
                    <p>Su solicitud ha experimentado un cambio de estado:</p>
                    
                    <div class="estado">
                        <p><strong>Número de Solicitud:</strong> {numero_solicitud}</p>
                        <p><strong>Estado Anterior:</strong> {estado_anterior}</p>
                        <p><strong>Estado Nuevo:</strong> {estado_nuevo}</p>
                        <p><strong>Fecha de Cambio:</strong> {fecha_cambio}</p>
                        {obs_html}
                    </div>
                    
                    <p>Continuaremos actualizándole sobre el progreso de su solicitud.</p>
                </div>
                
                <div class="footer">
                    <p>{EMPRESA_NOMBRE}</p>
                    <p>Este es un correo automatizado, por favor no responda a este mensaje.</p>
                </div>
            </div>
        </body>
    </html>
    """


def template_respuesta_final(
    nombre_solicitante: str,
    numero_solicitud: str,
    tipo_pqrs: str,
    fecha_respuesta: str,
    descripcion_respuesta: str
) -> str:
    """Template HTML para notificar respuesta final"""
    return f"""
    <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; background-color: #f5f5f5; }}
                .container {{ max-width: 600px; margin: 20px auto; background: white; padding: 20px; border-radius: 8px; }}
                .header {{ background-color: #003366; color: white; padding: 15px; border-radius: 5px; text-align: center; }}
                .content {{ margin: 20px 0; }}
                .respuesta {{ background-color: #fff3e0; padding: 15px; border-left: 4px solid #ff9800; margin: 10px 0; border-radius: 5px; }}
                .footer {{ color: #666; font-size: 12px; margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>¡Respuesta a Su Solicitud!</h1>
                </div>
                
                <div class="content">
                    <p>Estimado/a <strong>{nombre_solicitante}</strong>,</p>
                    
                    <p>Nos complace informarle que su solicitud de {tipo_pqrs} ha sido procesada.</p>
                    
                    <div class="respuesta">
                        <p><strong>Número de Solicitud:</strong> {numero_solicitud}</p>
                        <p><strong>Fecha de Respuesta:</strong> {fecha_respuesta}</p>
                        <p><strong>Respuesta:</strong></p>
                        <p>{descripcion_respuesta}</p>
                    </div>
                    
                    <p>Si tiene alguna aclaración o comentario, por favor comuníquese con nosotros.</p>
                </div>
                
                <div class="footer">
                    <p>{EMPRESA_NOMBRE}</p>
                    <p>Este es un correo automatizado, por favor no responda a este mensaje.</p>
                </div>
            </div>
        </body>
    </html>
    """


# ========== FUNCIONES DE ENVÍO ==========

def enviar_correo(
    destinatarios: List[str],
    asunto: str,
    html: str,
    nombre_evento: str = "general"
) -> Dict:
    """
    Envía un correo usando Resend.
    
    Args:
        destinatarios: Lista de correos electrónicos
        asunto: Asunto del correo
        html: Contenido HTML del correo
        nombre_evento: Nombre del evento para logging
        
    Returns:
        Dict con el resultado del envío
    """
    try:
        if not destinatarios:
            logger.warning(f"[{nombre_evento}] No hay destinatarios para enviar el correo")
            return {"success": False, "error": "No destinatarios"}
        
        # Resend espera un solo destinatario en el campo 'to'
        # Si hay múltiples, enviamos a cada uno
        resultados = []
        
        for correo in destinatarios:
            try:
                respuesta = resend.Emails.send({
                    "from": RESEND_FROM_EMAIL,
                    "to": correo,
                    "subject": asunto,
                    "html": html,
                })
                
                logger.info(f"[{nombre_evento}] Correo enviado a {correo} - ID: {respuesta.get('id')}")
                resultados.append({
                    "correo": correo,
                    "exito": True,
                    "id": respuesta.get('id')
                })
            except Exception as e:
                logger.error(f"[{nombre_evento}] Error enviando a {correo}: {str(e)}")
                resultados.append({
                    "correo": correo,
                    "exito": False,
                    "error": str(e)
                })
        
        return {
            "success": True,
            "resultados": resultados,
            "total": len(resultados),
            "exitosos": sum(1 for r in resultados if r["exito"])
        }
        
    except Exception as e:
        logger.error(f"[{nombre_evento}] Error general en envío: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


def notificar_solicitud_creada(
    nombre_solicitante: str,
    correo_solicitante: str,
    numero_solicitud: str,
    tipo_pqrs: str,
    fecha_creacion: str,
    fecha_vencimiento: str,
    correos_adicionales: Optional[List[str]] = None
) -> Dict:
    """
    Notifica cuando se crea una nueva solicitud.
    """
    destinatarios = [correo_solicitante]
    if correos_adicionales:
        destinatarios.extend(correos_adicionales)
    
    html = template_solicitud_creada(
        nombre_solicitante,
        numero_solicitud,
        tipo_pqrs,
        fecha_creacion,
        fecha_vencimiento
    )
    
    return enviar_correo(
        destinatarios,
        f"Solicitud {numero_solicitud} Radicada - {EMPRESA_NOMBRE}",
        html,
        "solicitud_creada"
    )


def notificar_cambio_estado(
    nombre_solicitante: str,
    correo_solicitante: str,
    numero_solicitud: str,
    estado_anterior: str,
    estado_nuevo: str,
    fecha_cambio: str,
    observaciones: Optional[str] = None,
    correos_adicionales: Optional[List[str]] = None
) -> Dict:
    """
    Notifica cuando cambia el estado de una solicitud.
    """
    destinatarios = [correo_solicitante]
    if correos_adicionales:
        destinatarios.extend(correos_adicionales)
    
    html = template_cambio_estado(
        nombre_solicitante,
        numero_solicitud,
        estado_anterior,
        estado_nuevo,
        fecha_cambio,
        observaciones
    )
    
    return enviar_correo(
        destinatarios,
        f"Actualización Solicitud {numero_solicitud} - {estado_nuevo}",
        html,
        "cambio_estado"
    )


def notificar_respuesta_final(
    nombre_solicitante: str,
    correo_solicitante: str,
    numero_solicitud: str,
    tipo_pqrs: str,
    fecha_respuesta: str,
    descripcion_respuesta: str,
    correos_adicionales: Optional[List[str]] = None
) -> Dict:
    """
    Notifica cuando se envía la respuesta final de una solicitud.
    """
    destinatarios = [correo_solicitante]
    if correos_adicionales:
        destinatarios.extend(correos_adicionales)
    
    html = template_respuesta_final(
        nombre_solicitante,
        numero_solicitud,
        tipo_pqrs,
        fecha_respuesta,
        descripcion_respuesta
    )
    
    return enviar_correo(
        destinatarios,
        f"Respuesta a su Solicitud {numero_solicitud}",
        html,
        "respuesta_final"
    )


# ========== FUNCIÓN DE PRUEBA ==========

def enviar_correo_prueba(correo_destino: str) -> Dict:
    """
    Envía un correo de prueba para validar la configuración.
    """
    html = f"""
    <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                .container {{ max-width: 600px; margin: 20px auto; background: white; padding: 20px; border-radius: 8px; }}
                .header {{ background-color: #4caf50; color: white; padding: 15px; border-radius: 5px; text-align: center; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>¡Correo de Prueba! 🚀</h1>
                </div>
                <p>Si recibes este correo, Resend está configurado correctamente.</p>
                <p>Timestamp: {datetime.now().isoformat()}</p>
            </div>
        </body>
    </html>
    """
    
    return enviar_correo(
        [correo_destino],
        "Correo de Prueba - PQRS",
        html,
        "prueba"
    )


if __name__ == "__main__":
    # Prueba rápida
    print("Módulo de notificaciones cargado correctamente.")
    print(f"API Key configurada: {bool(resend.api_key)}")
    print(f"Email desde: {RESEND_FROM_EMAIL}")
