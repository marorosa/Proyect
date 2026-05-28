"""
test_email.py
Script de prueba para enviar un correo usando la función enviar_correo_notificacion.
"""

import os
import sys
# Asegúrate de que la raíz del proyecto esté en el PYTHONPATH
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from autenticacion.autenticacion import enviar_correo_notificacion

def main():
    destinatario = "hinolopez6@gmail.com"
    asunto = "📧 Prueba de envío SMTP"
    cuerpo = """\
Hola,

Este es un correo de prueba enviado desde la aplicación PQRS usando SMTP.

Saludos,
Equipo de Pruebas
"""
    exito = enviar_correo_notificacion(destinatario, asunto, cuerpo)
    if exito:
        print("✅ Envío exitoso")
    else:
        print("❌ Envío falló")

if __name__ == "__main__":
    main()
