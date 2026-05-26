"""
Script rápido para probar la configuración de Resend
"""

import os
from dotenv import load_dotenv
from notificaciones import enviar_correo_prueba

# Cargar variables de entorno
load_dotenv()

# Mostrar configuración
print("=" * 60)
print("VERIFICANDO CONFIGURACIÓN DE RESEND")
print("=" * 60)

api_key = os.getenv("RESEND_API_KEY")
from_email = os.getenv("RESEND_FROM_EMAIL")

print(f"✓ API Key presente: {bool(api_key)}")
print(f"✓ Email From: {from_email}")

if not api_key:
    print("❌ ERROR: No hay API_KEY configurada en .env")
    exit(1)

# Pedir email destino
print("\n" + "=" * 60)
correo_destino = input("¿A qué correo deseas enviar la prueba?: ").strip()

if not correo_destino or "@" not in correo_destino:
    print("❌ Email inválido")
    exit(1)

# Enviar prueba
print(f"\n📧 Enviando prueba a {correo_destino}...")
print("-" * 60)

resultado = enviar_correo_prueba(correo_destino)

print(f"\nResultado: {resultado}")

if resultado.get("success"):
    print("✅ ¡Correo enviado exitosamente!")
    print(f"   Revisa tu bandeja: {correo_destino}")
else:
    print(f"❌ Error: {resultado.get('error')}")

print("=" * 60)
