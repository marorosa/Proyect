"""Sistema de Gestión de PQRS para Empresas Públicas - Sprint 1: Registro de Ciudadanos"""
import re
from datetime import datetime, date, timedelta
import random
import bcrypt
import base64
import json
import uuid
import os
from pathlib import Path
from urllib.parse import quote
import reflex as rx
from .usuario_model import Usuario, Solicitud
from sqlmodel import select, SQLModel, create_engine, text, Session
from rxconfig import config
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from starlette.staticfiles import StaticFiles
from dotenv import load_dotenv
from reflex.components import recharts as rc

# Carpeta donde se guardarán los archivos subidos por los usuarios
BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "assets" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
from typing import Any

# Almacenamiento temporal para descargas (limpieza automática después de acceso)
TEMP_DOWNLOADS = {}

# Cargar variables de entorno
load_dotenv()
# Ruta para configuración de correo almacenada por la app (opcional)
EMAIL_CONFIG_PATH = BASE_DIR / "email_config.json"


def load_email_config() -> dict:
    """Carga configuración de correo desde `email_config.json` si existe y
    aplica valores a `os.environ` cuando sea apropiado.
    """
    try:
        if EMAIL_CONFIG_PATH.exists():
            with open(EMAIL_CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            # Aplicar solo si no están en env ya (permite override por .env)
            for k, v in cfg.items():
                if v is None:
                    continue
                os.environ.setdefault(k, str(v))
            return cfg
    except Exception as e:
        print("No se pudo cargar email_config.json:", e)
    return {}


def save_email_config(cfg: dict) -> None:
    try:
        with open(EMAIL_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f)
        # Also ensure it's available in current process env for immediate use
        for k, v in cfg.items():
            if v is None:
                continue
            os.environ[k] = str(v)
    except Exception as e:
        print("No se pudo guardar email_config.json:", e)


# Load persisted email config on startup (if any)
_EMAIL_CONFIG_CACHE = load_email_config()
DEFAULT_DATABASE_PATH = BASE_DIR / "reflex.db"
DEFAULT_DATABASE_URL = f"sqlite:///{DEFAULT_DATABASE_PATH.as_posix()}"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
engine = create_engine(DATABASE_URL, echo=False)
SQLModel.metadata.create_all(engine)

# Asegura que las columnas necesarias existan en la tabla usuario
with engine.connect() as conn:
    result = conn.execute(text("PRAGMA table_info('usuario')"))
    columnas = [row[1] for row in result]
    if 'etnia' not in columnas:
        conn.execute(text("ALTER TABLE usuario ADD COLUMN etnia TEXT"))
    if 'persona_vulnerable' not in columnas:
        conn.execute(text("ALTER TABLE usuario ADD COLUMN persona_vulnerable TEXT"))
    conn.commit()

# Asegura que la columna persona_vulnerable exista en la tabla solicitud cuando se añada al modelo
with engine.connect() as conn:
    result = conn.execute(text("PRAGMA table_info('solicitud')"))
    columnas = [row[1] for row in result]
    if 'persona_vulnerable' not in columnas:
        conn.execute(text("ALTER TABLE solicitud ADD COLUMN persona_vulnerable TEXT"))
    conn.commit()

def tiene_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def confirmar_contraseña(contraseña: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(contraseña.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False

def validar_correo(correo: str) -> bool:
    # Solo rechaza si:
    # 1. No tiene @
    # 2. No tiene .
    # 3. La extensión es menor a 2 caracteres (ej: "com", "es", "co" son válidos, pero "c" no)
    if "@" not in correo:
        return False
    if "." not in correo:
        return False
    
    # Validar que después del punto hay al menos 2 caracteres
    partes = correo.split(".")
    if partes[-1].strip() and len(partes[-1].strip()) >= 2:
        return True
    return False

def cantida_minima_contraseña(contraseña: str) -> bool:
    # Requiere: al menos 8 caracteres, una mayúscula, una minúscula,
    # un número y al menos un carácter especial (cualquier signo de puntuación).
    return (
        len(contraseña) >= 8
        and re.search(r'[A-Z]', contraseña)
        and re.search(r'[a-z]', contraseña)
        and re.search(r'[0-9]', contraseña)
        and re.search(r'[^\w\s]', contraseña) is not None
    )

def sanitizar_nombre_archivo(nombre: str) -> str:
    """Sanitiza un nombre de archivo para evitar problemas de seguridad."""
    # Remover caracteres peligrosos
    nombre = re.sub(r'[^\w\s\-\.]', '', nombre)
    # Limitar la longitud
    nombre = nombre[:255]
    return nombre or "archivo"


def enviar_correo_bienvenida(email_destinatario: str, email_usuario: str):
    """Envía un correo de bienvenida. Intenta SMTP si `EMAIL_PASSWORD` está disponible;
    si no está o falla, intenta `SENDGRID_API_KEY`. Si todo falla, guarda el correo en
    `failed_emails.log` para reintento manual.
    """
    try:
        # Credenciales y configuración
        email_sender = os.getenv("EMAIL_SENDER", "enlacepqrs1755@gmail.com")
        email_password = os.getenv("EMAIL_PASSWORD")
        sendgrid_key = os.getenv("SENDGRID_API_KEY")
        smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        empresa_nombre = os.getenv("EMPRESA_NOMBRE", "Sistema de Gestión de PQRS")

        # Construir mensaje HTML
        mensaje = MIMEMultipart("alternative")
        mensaje["Subject"] = f"¡Bienvenido a {empresa_nombre}!"
        mensaje["From"] = email_sender
        mensaje["To"] = email_destinatario

        html = f"""
        <html>
            <body style="font-family: Arial, sans-serif; background-color: #f5f5f5; padding: 20px;">
                <div style="max-width: 600px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                    <h1 style="color: #1e40af; text-align: center;">¡Bienvenido!</h1>
                    <p style="color: #333; font-size: 16px;">Hola,</p>
                    <p style="color: #333; font-size: 16px;">Tu registro en <strong>{empresa_nombre}</strong> ha sido exitoso. A continuación, encontrarás tus datos de acceso:</p>
                    
                    <div style="background-color: #f0f7ff; padding: 15px; border-left: 4px solid #1e40af; margin: 20px 0; border-radius: 5px;">
                        <p style="margin: 5px 0;"><strong>📧 Correo:</strong> <code>{email_usuario}</code></p>
                    </div>
                    
                    <p style="color: #333; font-size: 16px;">Para iniciar sesión, ingresa a:</p>
                    <p style="text-align: center; margin: 20px 0;">
                        <a href="http://localhost:3000/login" style="background-color: #1e40af; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; font-weight: bold;">Ir a Iniciar Sesión</a>
                    </p>
                    
                    <hr style="border: 1px solid #ddd; margin: 20px 0;">
                    <p style="color: #666; font-size: 14px;"><strong>Recuerda:</strong> Nunca compartas tu contraseña con terceros. El equipo de soporte nunca te pedirá tu contraseña.</p>
                    <p style="color: #666; font-size: 14px;">Si tienes preguntas o problemas, contacta a nuestro equipo de soporte.</p>
                    <p style="text-align: center; color: #999; font-size: 12px; margin-top: 30px;">© 2026 {empresa_nombre}. Todos los derechos reservados.</p>
                </div>
            </body>
        </html>
        """

        parte_html = MIMEText(html, "html")
        mensaje.attach(parte_html)

        # 1) Intentar enviar por SMTP si tenemos contraseña
        if email_password:
            try:
                with smtplib.SMTP(smtp_server, smtp_port, timeout=10) as servidor:
                    servidor.starttls()
                    servidor.login(email_sender, email_password)
                    servidor.sendmail(email_sender, email_destinatario, mensaje.as_string())
                print(f"✅ Correo enviado exitosamente a {email_destinatario} vía SMTP")
                return True
            except smtplib.SMTPAuthenticationError as e:
                print("❌ Error al enviar correo de bienvenida: credenciales SMTP incorrectas o acceso no autorizado. Revisa EMAIL_SENDER, EMAIL_PASSWORD y la configuración de Gmail.")
                print(str(e))
            except Exception as e:
                print(f"❌ Error al enviar correo vía SMTP: {e}")

        # 2) Si falla o no hay contraseña, intentar SendGrid
        if sendgrid_key:
            sent = _send_with_sendgrid(email_destinatario, mensaje["Subject"], html, email_sender)
            if sent:
                print(f"✅ Correo enviado exitosamente a {email_destinatario} vía SendGrid")
                return True
            else:
                print("❌ Falló el envío vía SendGrid.")

        # 3) Registrar correo fallido en disco para reintento manual
        failed_path = BASE_DIR / "failed_emails.log"
        try:
            with open(failed_path, "a", encoding="utf-8") as f:
                f.write(f"{datetime.utcnow().isoformat()} | {email_destinatario} | subject: {mensaje['Subject']}\n{html}\n\n---\n")
            print(f"⚠️ Correo no enviado. Guardado en {failed_path}")
        except Exception as e:
            print("❌ No se pudo guardar el correo fallido:", e)

        return False
    except Exception as e:
        print(f"❌ Error inesperado al preparar correo: {e}")
        return False

def _send_with_sendgrid(to_email: str, subject: str, html: str, from_email: str) -> bool:
    """Envía correo usando la API de SendGrid si `SENDGRID_API_KEY` está configurada."""
    api_key = os.getenv("SENDGRID_API_KEY")
    if not api_key:
        return False
    try:
        import requests
        payload = {
            "personalizations": [{"to": [{"email": to_email}]}],
            "from": {"email": from_email},
            "subject": subject,
            "content": [{"type": "text/html", "value": html}],
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        resp = requests.post("https://api.sendgrid.com/v3/mail/send", json=payload, headers=headers, timeout=10)
        return resp.status_code in (200, 202)
    except Exception as e:
        print("❌ Error al enviar vía SendGrid:", e)
        return False


def enviar_correo_notificacion(email_destinatario: str, asunto: str, cuerpo: str) -> bool:
    """Envía una notificación por correo electrónico al ciudadano sobre actualizaciones en su solicitud."""
    try:
        smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        email_sender = os.getenv("EMAIL_SENDER")
        email_password = os.getenv("EMAIL_PASSWORD")
        empresa_nombre = os.getenv("EMPRESA_NOMBRE", "Sistema de Gestión de PQRS")

        if not email_sender or not email_password:
            print("⚠️ Advertencia: Credenciales de correo no configuradas en .env")
            return False

        # Crear el mensaje
        mensaje = MIMEMultipart("alternative")
        mensaje['From'] = email_sender
        mensaje['To'] = email_destinatario
        mensaje['Subject'] = asunto

        # Agregar el cuerpo del mensaje
        body = f"{cuerpo}\n\nAtentamente,\nEquipo {empresa_nombre}"
        mensaje.attach(MIMEText(body, 'plain'))

        # Enviar correo
        with smtplib.SMTP(smtp_server, smtp_port) as servidor:
            servidor.starttls()
            servidor.login(email_sender, email_password)
            servidor.sendmail(email_sender, email_destinatario, mensaje.as_string())

        print(f"✅ Notificación enviada exitosamente a {email_destinatario}")
        return True
    except smtplib.SMTPAuthenticationError as e:
        print("❌ Error al enviar notificación: credenciales SMTP incorrectas o acceso no autorizado. Revisa EMAIL_SENDER, EMAIL_PASSWORD y la configuración de seguridad de Gmail.")
        print(str(e))
        return False
    except Exception as e:
        print(f"❌ Error al enviar notificación: {str(e)}")
        return False


# quitar prints de prueba

class State(rx.State):


    # Dentro de class State, agrega estas variables:
    toast_mensaje: str = ""
    toast_tipo: str = ""  # "success" o "error"
    toast_visible: bool = False

    "En esta clase se define el estado de la aplicación, es decir, las variables que se van a usar en la aplicación y sus valores iniciales."
    state_auto_setters = True
    contraseña: str = ""
    confirmar_contraseña: str = ""
    correo: str = ""
    # Campos adicionales para registro extendido
    tipo_identificacion: str = ""
    numero_identificacion: str = ""
    nombres: str = ""
    apellidos: str = ""
    sexo: str = ""
    direccion: str = ""
    telefono: str = ""
    departamento: str = ""
    ciudad: str = ""
    etnia: str = ""
    persona_vulnerable_registro: str = ""
    # Estados de validación UX
    correo_validado: bool = False
    numero_identificacion_valid: bool = False
    nombres_valid: bool = False
    apellidos_valid: bool = False
    telefono_valid: bool = False
    departamento_valid: bool = False
    ciudad_valid: bool = False
    
    # Diccionario de departamentos y ciudades para dropdowns dinámicos
    departamentos_ciudades =  {
    "Amazonas": ["Leticia", "Puerto Nariño", "La Chorrera", "Tarapacá", "Puerto Santander", "Mirití-Paraná", "Puerto Alegría", "Puerto Arica", "La Victoria"],
    "Antioquia": ["Medellín", "Envigado", "Sabaneta", "Copacabana", "Girardota", "Barbosa", "Itagüí", "Bello", "Caldas", "La Estrella", "Rionegro", "La Ceja", "Apartadó", "Turbo", "Caucasia", "Santa Rosa de Osos"],
    "Arauca": ["Arauca", "Arauquita", "Cravo Norte", "Saravena", "Tame"],
    "Atlántico": ["Barranquilla", "Soledad", "Malambo", "Puerto Colombia", "Sabanalarga", "Baranoa", "Galapa"],
    "Bogotá D.C.": ["Bogotá D.C."],
    "Bolívar": ["Cartagena", "Turbaco", "Magangué", "Arjona", "El Carmen de Bolívar", "Mompox"],
    "Boyacá": ["Tunja", "Duitama", "Sogamoso", "Paipa", "Chiquinquirá", "Villa de Leyva", "Puerto Boyacá"],
    "Caldas": ["Manizales", "La Dorada", "Riosucio", "Chinchiná", "Villamaría", "Anserma"],
    "Caquetá": ["Florencia", "San Vicente del Caguán", "Puerto Rico", "Currillo"],
    "Casanare": ["Yopal", "Aguazul", "Paz de Ariporo", "Tauramena", "Maní"],
    "Cauca": ["Popayán", "Guachené", "Corinto", "Santander de Quilichao", "Puerto Tejada", "Patía"],
    "Cesar": ["Valledupar", "Aguachica", "Agustín Codazzi", "Bosconia", "Curumaní"],
    "Chocó": ["Quibdó", "Istmina", "Condoto", "Acandí", "Bahía Solano"],
    "Córdoba": ["Montería", "Cereté", "Sahagún", "Lorica", "Montelíbano", "Planeta Rica"],
    "Cundinamarca": ["Soacha", "Chía", "Sopó", "Tausa", "Tenjo", "Tena", "Tocaima", "Tocancipá", "Zipaquirá", "Fúquene", "Pacho", "Útica", "Villapinzón", "Villeta", "Facatativá", "Girardot", "Fusagasugá"],
    "Guainía": ["Inírida", "Barrancominas"],
    "Guaviare": ["San José del Guaviare", "Calamar", "El Retorno", "Miraflores"],
    "Huila": ["Neiva", "Pitalito", "Garzón", "La Plata", "Campoalegre", "San Agustín"],
    "La Guajira": ["Riohacha", "Maicao", "Uribia", "San Juan del Cesar", "Fonseca"],
    "Magdalena": ["Santa Marta", "Ciénaga", "Fundación", "El Banco", "Plato"],
    "Meta": ["Villavicencio", "Acacías", "Granada", "Puerto López", "Cumaral"],
    "Nariño": ["Pasto", "Ipiales", "Tumaco", "Sandoná", "Túquerres", "La Unión"],
    "Norte de Santander": ["Cúcuta", "Ocaña", "Pamplona", "Villa del Rosario", "Los Patios", "Tibú"],
    "Putumayo": ["Mocoa", "Puerto Asís", "Orito", "Valle del Guamuez", "Sibundoy"],
    "Quindío": ["Armenia", "Calarcá", "Filandia", "Circasia", "Montenegro", "Quimbaya"],
    "Risaralda": ["Pereira", "Dosquebradas", "Santa Rosa de Cabal", "La Virginia", "Belén de Umbría"],
    "San Andrés y Providencia": ["San Andrés", "Providencia"],
    "Santander": ["Bucaramanga", "Floridablanca", "Girón", "Piedecuesta", "Barrancabermeja", "San Gil", "Socorro"],
    "Sucre": ["Sincelejo", "Corozal", "Tolú", "San Marcos", "Sampués"],
    "Tolima": ["Ibagué", "Espinal", "Melgar", "Mariquita", "Honda", "Líbano"],
    "Valle del Cauca": ["Cali", "Palmira", "Yumbo", "Cartago", "Buenaventura", "Tuluá", "Buga", "Jamundí"],
    "Vaupés": ["Mitú", "Carurú", "Taraira"],
    "Vichada": ["Puerto Carreño", "La Primavera", "Santa Rosalía", "Cumaribo"]
}
    
    # Habeas data / autorizaciones
    acepta_notificaciones: bool = False
    acepta_politica_datos: bool = False
    # Para el formulario de solicitudes
    acepta_politica_solicitud: bool = False
    area_responsable: str = ""
    area_otro: str = ""
    tipo_solicitud: str = ""
    persona_vulnerable: str = ""
    asunto: str = ""
    descripcion: str = ""
    ubicacion: str = ""
    documento: str = ""
    documentos: list[dict] = []
    documento_nombres: list[str] = []
    documento_nombre: str = ""
    descripcion_len: int = 0
    query_solicitud: str = ""
    filter_tipo_solicitud: str = "Todos"
    filter_estado_solicitud: str = "Todos"
    solicitudes: list[dict[str, Any]] = []
    editar_solicitud_id: int = 0
    eliminar_solicitud_id: int = 0
    solicitud_mensaje: str = ""


    error_de_registro: str = ""
    succes: str = ""
    error_de_contraseña: str = ""
    succes2: str = ""
    
    id_usuario: int = 0
    es_autentica: bool = False
    email_actual: str = ""
    correo_usuario: str = ""
    rol_usuario: str = ""
    # Campo para ingresar la SendGrid API key desde la UI (admin)
    sendgrid_key_input: str = ""
    sendgrid_saved_message: str = ""
    show_password: bool = False
    # Campos para cambiar contraseña
    current_password: str = ""
    new_password: str = ""
    confirm_new_password: str = ""
    change_pw_message: str = ""
    # Campos para cambiar rol de ciudadano a funcionario
    cambiar_rol_email: str = ""
    cambiar_rol_mensaje: str = ""
    usuarios_registrados: list[dict[str, Any]] = []
    # Campos para editar estado de solicitud
    editar_estado_id: int = 0
    nuevo_estado: str = ""
    respuesta_solicitud: str = ""
    mensaje_actualizar_estado: str = ""
    respuesta_documento: str = ""
    respuesta_documento_nombre: str = ""
    # Variables para modal de política y validaciones
    modal_politica_visible: bool = False
    archivo_error_mensaje: str = ""
    correo_confirmacion_visible: bool = False
    correo_confirmacion_mensaje: str = ""
    
    # Campos para asignación de área con mensaje
    asignar_area_id: int = 0
    asignar_area_mensaje: str = ""
    asignar_area_nombre: str = ""
    asignar_area_seleccionada: str = ""
    mensaje_asignacion: str = ""
    
    # Campos para consultar estado de solicitud
    consulta_radicado: str = ""
    solicitud_consultada: dict[str, Any] = {}
    consulta_mensaje: str = ""
    # Enlace generado tras exportar reportes (archivo descargable)
    export_href: str = ""
    export_filename: str = ""
    mostrar_menu_descarga: bool = False

    @rx.var
    def ciudades_disponibles(self) -> list[str]:
        """Retorna las ciudades del departamento seleccionado."""
        if self.departamento in self.departamentos_ciudades:
            return self.departamentos_ciudades[self.departamento]
        return []

    @rx.var
    def data_grafica_tipo(self) -> list[dict]:
        counts = self.estadisticas_por_tipo
        selected = (self.filter_tipo_solicitud or "Todos").strip()
        if selected.lower() in {"todas", "todos"}:
            return [
                {"name": "Petición", "cantidad": counts.get("Petición", 0)},
                {"name": "Queja", "cantidad": counts.get("Queja", 0)},
                {"name": "Reclamo", "cantidad": counts.get("Reclamo", 0)},
                {"name": "Sugerencia", "cantidad": counts.get("Sugerencia", 0)},
            ]

        normalized = self._normalize_tipo_solicitud(selected)
        if normalized:
            return [{"name": normalized, "cantidad": counts.get(normalized, 0)}]

        return []
    
    @rx.var
    def data_grafica_estado(self) -> list[dict]:
        return [
            {"name": "Radicada", "cantidad": int(self.numero_solicitudes_radicadas)},
            {"name": "Actualizada", "cantidad": int(self.numero_solicitudes_actualizadas)},
            {"name": "Cerrada", "cantidad": int(self.numero_solicitudes_cerradas)},
        ]

    def mostrar_toast(self, mensaje: str, tipo: str = "success"):
        self.toast_mensaje = mensaje
        self.toast_tipo = tipo
        self.toast_visible = True
        # Ocultar automáticamente después de 2.5 segundos
        import threading
        threading.Timer(2.5, lambda: setattr(self, 'toast_visible', False)).start()

    def export_reportes_csv(self):
        """Genera un CSV en memoria desde `self.solicitudes` para descarga."""
        try:
            import csv
            import io
            from datetime import datetime

            data = self.solicitudes or []
            if not data:
                self.mostrar_toast("No hay datos para exportar.", "warning")
                self.mostrar_menu_descarga = False
                return
            
            # Generar CSV en memoria
            output = io.StringIO()
            if data and isinstance(data[0], dict):
                writer = csv.DictWriter(output, fieldnames=data[0].keys())
                writer.writeheader()
                writer.writerows(data)
            else:
                output.write("Error: Datos en formato inválido")
            
            # Guardar en almacenamiento temporal
            csv_bytes = output.getvalue().encode('utf-8')
            filename = f"reportes_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.csv"
            download_id = str(uuid.uuid4())
            
            TEMP_DOWNLOADS[download_id] = {
                "data": csv_bytes,
                "filename": filename,
                "mime": "text/csv; charset=utf-8"
            }
            
            self.export_filename = filename
            self.mostrar_toast(f"✓ CSV generado. {len(data)} registros. Descargando...", "success")
            self.mostrar_menu_descarga = False
            self.export_href = f"/api/download/{download_id}"
            
        except Exception as e:
            print(f"ERROR en export_reportes_csv: {type(e).__name__}: {e}")
            self.mostrar_toast(f"Error: {str(e)[:100]}", "error")
            self.mostrar_menu_descarga = False

    def descargar_excel_y_abrir(self):
        """Genera Excel en memoria y dispara la descarga."""
        try:
            import io
            from datetime import datetime
            import pandas as pd

            data = self.solicitudes or []
            if not data:
                self.mostrar_toast("No hay datos para exportar.", "warning")
                return

            df = pd.DataFrame(data)
            output = io.BytesIO()
            df.to_excel(output, index=False, sheet_name="Solicitudes", engine="openpyxl")
            output.seek(0)

            filename = f"reportes_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.xlsx"
            return rx.download(
                data=output.read(),
                filename=filename,
                mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        except (ImportError, ModuleNotFoundError):
            self.mostrar_toast("No se pudo generar Excel. Descargando CSV en su lugar.", "warning")
            return self.descargar_csv_y_abrir()
        except Exception as e:
            print(f"ERROR en descargar_excel_y_abrir: {e}")
            self.mostrar_toast(f"Error exportando Excel: {str(e)[:100]}", "error")

    def descargar_csv_y_abrir(self):
        """Genera CSV en memoria y dispara la descarga."""
        try:
            import csv
            import io
            from datetime import datetime

            data = self.solicitudes or []
            if not data:
                self.mostrar_toast("No hay datos para exportar.", "warning")
                return

            output = io.StringIO()
            if data and isinstance(data[0], dict):
                writer = csv.DictWriter(output, fieldnames=data[0].keys())
                writer.writeheader()
                writer.writerows(data)
            else:
                output.write("Error: Datos en formato inválido")

            filename = f"reportes_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.csv"
            return rx.download(
                data=output.getvalue().encode('utf-8'),
                filename=filename,
                mime_type="text/csv; charset=utf-8"
            )
        except Exception as e:
            print(f"ERROR en descargar_csv_y_abrir: {e}")
            self.mostrar_toast(f"Error exportando CSV: {str(e)[:100]}", "error")


    def ocultar_toast(self):
        self.toast_visible = False
        self.toast_mensaje = ""

    def guardar_sendgrid_api_key(self) -> bool:
        """Guarda la SendGrid API Key desde `self.sendgrid_key_input` en `email_config.json`.
        Puede ser llamada desde la UI de admin.
        """
        key = (self.sendgrid_key_input or "").strip()
        if not key:
            self.sendgrid_saved_message = "Clave vacía."
            return False
        try:
            save_email_config({"SENDGRID_API_KEY": key, "EMAIL_SENDER": os.getenv("EMAIL_SENDER", "enlacepqrs1755@gmail.com")})
            self.sendgrid_saved_message = "Clave guardada correctamente."
            self.sendgrid_key_input = ""
            return True
        except Exception as e:
            print("Error guardando SendGrid key:", e)
            self.sendgrid_saved_message = "Error al guardar."
            return False

    def toggle_menu_descarga(self):
        """Alterna la visibilidad del menú de descarga."""
        self.mostrar_menu_descarga = not self.mostrar_menu_descarga
        
     
    @rx.var
    def numero_solicitudes(self) -> str:
        return str(len(self.solicitudes or []))
    
    @rx.var
    def numero_solicitudes_radicadas(self) -> str:
        return str(sum(1 for solicitud in (self.solicitudes or []) if (str(solicitud.get('estado') or '').strip().lower()) == 'radicada'))
    
    @rx.var
    def numero_solicitudes_actualizadas(self) -> str:
        return str(sum(1 for solicitud in (self.solicitudes or []) if (str(solicitud.get('estado') or '').strip().lower()) == 'actualizada'))
    
    @rx.var
    def numero_solicitudes_cerradas(self) -> str:
        return str(sum(1 for solicitud in (self.solicitudes or []) if (str(solicitud.get('estado') or '').strip().lower()) == 'cerrada'))
    
    def _normalize_tipo_solicitud(self, tipo_raw: str) -> str:
        """Normaliza tipos de solicitud a las categorías usadas en los reportes."""
        if not tipo_raw:
            return ""
        tipo = str(tipo_raw).strip().lower()
        if tipo in ("peticion", "petición", "pqr", "solicitud"):
            return "Petición"
        if tipo == "queja":
            return "Queja"
        if tipo == "reclamo":
            return "Reclamo"
        if tipo == "sugerencia":
            return "Sugerencia"
        if "petici" in tipo:
            return "Petición"
        if "queja" in tipo:
            return "Queja"
        if "reclam" in tipo:
            return "Reclamo"
        if "suger" in tipo:
            return "Sugerencia"
        return ""

    @rx.var
    def estadisticas_por_tipo(self) -> dict[str, int]:
        counts = {"Petición": 0, "Queja": 0, "Reclamo": 0, "Sugerencia": 0}
        for solicitud in self.solicitudes or []:
            tipo = self._normalize_tipo_solicitud(solicitud.get("tipo_solicitud") or "")
            if tipo in counts:
                counts[tipo] += 1
        return counts

    @rx.var
    def max_registros_tipo(self) -> int:
        values = list(self.estadisticas_por_tipo.values())
        return max(values) if values else 1

    @rx.var
    def monthly_response_times(self) -> list[dict]:
        """Calcula el tiempo promedio de respuesta por mes (Ene..Dic) a partir de self.solicitudes.
        Devuelve lista de dicts: {month: 'Ene', value: float}
        """
        # Nuevo comportamiento: generar serie diaria para los últimos 30 días
        today = date.today()
        start_date = today - timedelta(days=29)
        # preparar buckets por día
        buckets: dict[str, list[int]] = {}
        for i in range(30):
            d = start_date + timedelta(days=i)
            buckets[d.strftime("%Y-%m-%d")] = []

        for s in (self.solicitudes or []):
            try:
                frp = self._parse_dt(s.get('fecha_respuesta'))
                if not frp:
                    continue
                resp_date = frp.date()
                if resp_date < start_date or resp_date > today:
                    continue
                fr = self._parse_dt(s.get('fecha') or s.get('fecha_radicado'))
                if not fr:
                    continue
                start = fr.date() + timedelta(days=1)
                dias = self._business_days_between(start, resp_date, set())
                # If response happened same day and dias == 0, simulate 1-5 days for visualization/testing
                if dias == 0:
                    dias = random.randint(1, 5)
                key = resp_date.strftime("%Y-%m-%d")
                buckets.setdefault(key, []).append(dias)
            except Exception:
                continue

        result = []
        for i in range(30):
            d = start_date + timedelta(days=i)
            key = d.strftime("%Y-%m-%d")
            vals = buckets.get(key, [])
            avg = round(sum(vals) / len(vals), 1) if vals else 0
            label = d.strftime('%d %b')
            result.append({"month": label, "value": avg})

        # Si todos los valores son 0, usamos un fallback de simulación para visualización
        if all(item.get("value", 0) == 0 for item in result):
            simulated = []
            for i in range(30):
                d = start_date + timedelta(days=i)
                label = d.strftime('%d %b')
                # 60% probabilidad de mostrar un valor entre 0.5 y 4.0, else 0
                if random.random() < 0.6:
                    val = round(random.uniform(0.5, 4.0), 1)
                else:
                    val = 0
                simulated.append({"month": label, "value": val})
            return simulated

        return result

    @rx.var
    def compliance_percentage(self) -> int:
        """Calcula cumplimiento: (solicitudes resueltas / total) * 100.
        Resueltas = estado 'Respondida' o 'Cerrada'.
        """
        total = len(self.solicitudes or [])
        if total == 0:
            return 0
        closed_states = {"resuelta", "cerrada", "respondida", "finalizada"}
        cerradas = sum(1 for s in (self.solicitudes or []) if (s.get('estado') or "").lower() in closed_states)
        return int((cerradas / total) * 100) if total > 0 else 0

    @rx.var
    def compliance_chart_data(self) -> list[dict]:
        pct = int(self.compliance_percentage)
        return [
            {"name": "Cerradas", "value": pct, "fill": "#10b981"},
            {"name": "No cerradas", "value": max(0, 100 - pct), "fill": "#ef4444"},
        ]

    # --- Semáforo: días hábiles y conteos por color ---
    def _parse_dt(self, v):
        if v is None:
            return None
        if isinstance(v, datetime):
            return v
        try:
            # ISO format usually works
            return datetime.fromisoformat(v)
        except Exception:
            try:
                from dateutil import parser as _p
                return _p.parse(v)
            except Exception:
                return None

    def _is_business_day(self, d: date, holidays: set):
        return d.weekday() < 5 and d not in holidays

    def _business_days_between(self, start: date, end: date, holidays: set) -> int:
        if end < start:
            return 0
        days = 0
        cur = start
        while cur <= end:
            if self._is_business_day(cur, holidays):
                days += 1
            cur += timedelta(days=1)
        return days

    def _legal_days_for(self, tipo: str, detalle: str | None = None) -> int:
        if not tipo:
            return 15
        t = tipo.lower()
        d = (detalle or "").lower()
        if "consulta" in d or t == "consulta":
            return 30
        if "inform" in d or "copia" in d or "informacion" in d:
            return 10
        if t in ("peticion", "petición", "queja", "reclamo", "sugerencia"):
            return 15
        return 15


    @staticmethod
    def _compute_remaining_for_solicitud(solicitud: dict) -> dict:
        """Computa días restantes y color (fill) para una solicitud dada.
        Usa llaves comunes que retorna `_solicitud_a_dict` como `fecha` y `tipo_solicitud`.
        Retorna dict con `remaining` (int or None) y `fill` (hex color).
        """
        try:
            fecha_raw = solicitud.get("fecha") or solicitud.get("fecha_radicado")
            if not fecha_raw:
                return {"remaining": None, "fill": "gray"}
            # intentar parseo ISO, sino dateutil
            try:
                dt = datetime.fromisoformat(str(fecha_raw))
            except Exception:
                try:
                    from dateutil import parser as _p
                    dt = _p.parse(str(fecha_raw))
                except Exception:
                    return {"remaining": None, "fill": "gray"}

            start = dt.date()
            ref = date.today()  # SIEMPRE usar hoy, no fecha_respuesta

            # Contar días calendario desde la fecha de creación hasta hoy.
            days = max((ref - start).days, 0)

            tipo = (solicitud.get("tipo_solicitud") or solicitud.get("tipo_pqrs") or "").lower()
            if "consulta" in tipo:
                legal = 30
            elif "inform" in tipo or "copia" in tipo or "informacion" in tipo:
                legal = 10
            elif tipo in ("peticion", "petición", "queja", "reclamo", "sugerencia"):
                legal = 15
            else:
                legal = 15

            remaining = legal - days
            if remaining <= 0:
                fill = "#ef4444"
            elif remaining <= 5:
                fill = "#f59e0b"
            else:
                fill = "#10b981"
            # Representar visualmente el avance hacia el vencimiento.
            if legal > 0:
                width = int(min(max((legal - remaining) / legal * 100, 0), 100))
            else:
                width = 0
            return {"remaining": remaining, "fill": fill, "width": width}
        except Exception:
            return {"remaining": None, "fill": "gray", "width": 0}

    @rx.var
    def semaforo_counts(self) -> dict:
        # lee self.solicitudes y devuelve conteo por color
        holidays = set()  # puedes poblar con una consulta a festivos si la tienes
        counts = {"verde": 0, "amarillo": 0, "rojo": 0}
        # Estados que consideramos cerrados/resueltos (normalizados en minúsculas)
        closed_states = {"respondida", "respondido", "respondida", "respondida", "cerrada", "cerrado", "finalizada", "finalizado"}
        for s in (self.solicitudes or []):
            estado_raw = (s.get("estado") or "").strip().lower()
            # Si el estado está en la lista de cerrados, lo saltamos; así consideramos activo todo lo demás
            if estado_raw in closed_states:
                continue
            fr = self._parse_dt(s.get("fecha") or s.get("fecha_radicado"))
            if not fr:
                # intentar usar la llave 'fecha_radicado' si existe (compatibilidad)
                fr = self._parse_dt(s.get("fecha_radicado"))
            if not fr:
                continue
            start = fr.date() + timedelta(days=1)
            ref = date.today()
            if s.get("fecha_respuesta"):
                resp = self._parse_dt(s.get("fecha_respuesta"))
                if resp:
                    ref = resp.date()
            used = self._business_days_between(start, ref, holidays)
            # usar `tipo_solicitud` por consistencia con `_solicitud_a_dict`
            legal = self._legal_days_for(s.get("tipo_solicitud"), s.get("tipo_detalle") or s.get("asunto"))
            remaining = legal - used
            if remaining <= 0:
                counts["rojo"] += 1
            elif remaining <= 5:
                counts["amarillo"] += 1
            else:
                counts["verde"] += 1
        return counts

    @rx.var
    def semaforo_chart_data(self) -> list[dict]:
        c = self.semaforo_counts
        return [
            {"name": "Verde", "value": c.get("verde", 0), "fill": "#10b981"},
            {"name": "Amarillo", "value": c.get("amarillo", 0), "fill": "#f59e0b"},
            {"name": "Rojo", "value": c.get("rojo", 0), "fill": "#ef4444"},
        ]

    @rx.var
    def semaforo_total(self) -> int:
        c = self.semaforo_counts
        total_from_counts = int(c.get("verde", 0) + c.get("amarillo", 0) + c.get("rojo", 0))
        # Fallback: si no hay conteos, usar data_grafica_tipo (cantidad)
        fallback = 0
        try:
            for it in (self.data_grafica_tipo or []):
                fallback += int(it.get("cantidad", 0))
        except Exception:
            fallback = 0
        return max(total_from_counts, fallback)

    @rx.var
    def semaforo_bar_data(self) -> list[dict]:
        # Devuelve una lista con un único registro que contiene los valores por color
        c = self.semaforo_counts
        total = int(c.get("verde", 0) + c.get("amarillo", 0) + c.get("rojo", 0))
        if total > 0:
            return [{
                "name": "Semáforo",
                "verde": int(c.get("verde", 0)),
                "amarillo": int(c.get("amarillo", 0)),
                "rojo": int(c.get("rojo", 0)),
            }]
        # Fallback a partir de data_grafica_tipo: sumar todas las solicitudes en verde (representación)
        fallback = 0
        try:
            for it in (self.data_grafica_tipo or []):
                fallback += int(it.get("cantidad", 0))
        except Exception:
            fallback = 0
        return [{"name": "Semáforo", "verde": fallback, "amarillo": 0, "rojo": 0}]

    @rx.var
    def top_areas(self) -> list[dict]:
        """Devuelve las top 3 áreas por cantidad de solicitudes.
        """
        counts = {}
        for s in (self.solicitudes or []):
            a = s.get('area_responsable') or 'N/A'
            counts[a] = counts.get(a, 0) + 1
        items = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:3]
        return [{"name": name, "total": total} for name, total in items]

    @rx.var
    def solicitudes_por_vencer_data(self) -> list[dict]:
        counts = {
            "Vencidas": 0,
            "1-5 días": 0,
            "6-10 días": 0,
            ">10 días": 0,
        }
        closed_states = {"respondida", "respondido", "cerrada", "cerrado", "finalizada", "finalizado", "resuelta", "resuelto"}
        for s in (self.solicitudes or []):
            estado_raw = str(s.get("estado") or "").strip().lower()
            if estado_raw in closed_states:
                continue
            rem = s.get("semaforo_remaining")
            if rem is None:
                continue
            if rem <= 0:
                counts["Vencidas"] += 1
            elif rem <= 5:
                counts["1-5 días"] += 1
            elif rem <= 10:
                counts["6-10 días"] += 1
            else:
                counts[">10 días"] += 1
        return [{"name": label, "cantidad": total} for label, total in counts.items()]

    @rx.var
    def solicitudes_por_vencer_total(self) -> int:
        return sum(item.get("cantidad", 0) for item in self.solicitudes_por_vencer_data if item.get("name") != ">10 días")

    @rx.var
    def kpi_counts(self) -> dict:
        """Devuelve los 3 KPIs: pendientes (>10 días), en proceso (1-10 días), cerradas (estados cerrados).
        """
        closed_states = {"respondida", "respondido", "cerrada", "cerrado", "finalizada", "finalizado", "resuelta", "resuelto"}
        pendientes = 0
        en_curso = 0
        cerradas = 0
        for s in (self.solicitudes or []):
            estado_raw = str(s.get("estado") or "").strip().lower()
            if estado_raw in closed_states:
                cerradas += 1
                continue
            rem = s.get("semaforo_remaining")
            if rem is None:
                continue
            try:
                rem_i = int(rem)
            except Exception:
                continue
            if rem_i > 10:
                pendientes += 1
            elif 1 <= rem_i <= 10:
                en_curso += 1
            # rem_i <= 0 (vencidas) quedan fuera de estos KPIs según definición
        return {"pendientes": pendientes, "en_curso": en_curso, "cerradas": cerradas}

    @rx.var
    def kpi_pendientes_count(self) -> int:
        return int(self.kpi_counts.get("pendientes", 0))

    @rx.var
    def kpi_en_curso_count(self) -> int:
        return int(self.kpi_counts.get("en_curso", 0))

    @rx.var
    def kpi_cerradas_count(self) -> int:
        return int(self.kpi_counts.get("cerradas", 0))

    @rx.var
    def solicitudes_filtradas(self) -> list[dict]:
        query = (self.query_solicitud or "").strip().lower()
        tipo = (self.filter_tipo_solicitud or "Todos").lower()
        estado = (self.filter_estado_solicitud or "Todos").lower()
        resultados = []
        for solicitud in self.solicitudes or []:
            texto = " ".join(
                str(solicitud.get(field, "") or "")
                for field in ("radicado", "asunto", "descripcion", "creado_por")
            ).lower()
            if query and query not in texto:
                continue
            if tipo not in {"todas", "todos"} and self._normalize_tipo_solicitud(solicitud.get("tipo_solicitud", "")).lower() != tipo:
                continue
            if estado not in {"todas", "todos"} and solicitud.get("estado", "").lower() != estado:
                continue
            resultados.append(solicitud)
        return resultados

    @rx.var
    def documento_nombres_joined(self) -> str:
        return ", ".join(self.documento_nombres or [])
    
    @rx.var
    def documento_nombres_count(self) -> str:
        return str(len(self.documento_nombres or []))

    @rx.var
    def documento_tamano_total(self) -> str:
        total = 0
        for item in self.documentos or []:
            if isinstance(item, dict):
                total += int(item.get("size") or 0)
        return f"{total / (1024 * 1024):.2f} MB"
    
    @rx.var
    def usuarios_registrados_count(self) -> int:
        return len(self.usuarios_registrados or [])
    
    @rx.var
    def solicitud_consultada_adjuntos(self) -> list[dict]:
        documento_str = self.solicitud_consultada.get("documento", "")
        documento_basename_str = self.solicitud_consultada.get("documento_basename", "")
        
        if not documento_str:
            return []
        
        try:
            documentos = json.loads(documento_str)
            basenames = json.loads(documento_basename_str) if documento_basename_str else []
            
            result = []
            for i, doc in enumerate(documentos or []):
                basename = basenames[i] if i < len(basenames) else f"Documento {i+1}"
                result.append({
                    "basename": basename,
                    "href": f"/assets/uploads/{doc.split('/')[-1]}"
                })
            return result
        except:
            return []
    
    
    
    def set_query_solicitud(self, value: str):
        self.query_solicitud = value or ""
    
    def set_filter_tipo_solicitud(self, value: str):
        self.filter_tipo_solicitud = value or "Todos"

    def set_filter_estado_solicitud(self, value: str):
        self.filter_estado_solicitud = value or "Todas"

    def buscar_solicitudes(self):
        self.query_solicitud = (self.query_solicitud or "").strip()

    def set_new_password(self, value: str):
        self.new_password = value
    
    def set_confirm_new_password(self, value: str):
        self.confirm_new_password = value
    
    def borrar_mensajes_de_estado(self):
        self.error_de_registro = ""
        self.succes = ""
        self.error_de_contraseña = ""
        self.succes2 = ""
        
    def validacion_de_entradas(self, require_strong_pw: bool = True) -> bool:
        self.correo_confirmacion_visible = False
        self.correo_confirmacion_mensaje = ""
        if not validar_correo(self.correo):
            self.error_de_registro = "Correo no válido."
            self.correo_confirmacion_visible = True
            self.correo_confirmacion_mensaje = "Correo no válido."
            return False
        self.correo_confirmacion_visible = True
        self.correo_confirmacion_mensaje = "Correo válido."
        if require_strong_pw and not cantida_minima_contraseña(self.contraseña):
            self.error_de_registro = "La contraseña debe tener al menos 8 caracteres, incluyendo mayúsculas, minúsculas, números y caracteres especiales."
            return False
        if require_strong_pw and self.contraseña != self.confirmar_contraseña:
            self.error_de_registro = "Las contraseñas no coinciden."
            return False
        return True
    def validar_campo_simple(self, campo: str) -> bool:
        """Validaciones simples para mostrar iconos de confirmación.
        Retorna True si el campo parece correcto."""
        val = getattr(self, campo, "")
        ok = False
        if campo == "telefono":
            ok = isinstance(val, str) and len(val) >= 7
        elif campo == "numero_identificacion":
            ok = isinstance(val, str) and len(val) >= 6
        elif campo == "correo":
            ok = validar_correo(val)
        else:
            ok = bool(val and str(val).strip())
        # set dedicated flags for reactivity
        if campo == "telefono":
            self.telefono_valid = ok
        elif campo == "numero_identificacion":
            self.numero_identificacion_valid = ok
        elif campo == "nombres":
            self.nombres_valid = ok
        elif campo == "apellidos":
            self.apellidos_valid = ok
        elif campo == "departamento":
            self.departamento_valid = ok
        elif campo == "ciudad":
            self.ciudad_valid = ok
        return ok

    def validar_correo_accion(self):
        """Acción invocada por el botón 'Validar' junto al correo."""
        self.correo_validado = validar_correo(self.correo)
        if not self.correo_validado:
            self.error_de_registro = "Correo inválido."
        else:
            self.error_de_registro = ""
        return

    # Setters that also validate so we can show inline icons
    def set_and_validate_nombres(self, val: str):
        self.nombres = val
        self.validar_campo_simple("nombres")

    def set_and_validate_apellidos(self, val: str):
        self.apellidos = val
        self.validar_campo_simple("apellidos")

    def set_and_validate_numero_identificacion(self, val: str):
        self.numero_identificacion = val
        self.validar_campo_simple("numero_identificacion")

    def set_and_validate_telefono(self, val: str):
        self.telefono = val
        self.validar_campo_simple("telefono")

    def set_and_validate_departamento(self, val: str):
        self.departamento = val
        self.ciudad = ""  # Limpia la ciudad cuando cambia el departamento
        self.validar_campo_simple("departamento")

    def set_and_validate_ciudad(self, val: str):
        self.ciudad = val
        self.validar_campo_simple("ciudad")

    def set_and_validate_correo(self, val: str):
        """Valida el correo en tiempo real y borra el mensaje si es válido o vacío."""
        self.correo = val or ""
        
        # Si el correo está vacío, borra el mensaje
        if not self.correo.strip():
            self.correo_confirmacion_visible = False
            self.correo_confirmacion_mensaje = ""
            self.error_de_registro = ""
            self.correo_validado = False
            return
        
        # Si es válido, muestra mensaje verde y borra error
        if validar_correo(self.correo):
            self.correo_confirmacion_visible = True
            self.correo_confirmacion_mensaje = "Correo válido."
            self.error_de_registro = ""
            self.correo_validado = True
        else:
            # Si es inválido, muestra mensaje rojo
            self.correo_confirmacion_visible = True
            self.correo_confirmacion_mensaje = "Correo no válido."
            self.error_de_registro = "Correo no válido."
            self.correo_validado = False

    def set_etnia(self, val: str):
        self.etnia = val or ""

    def set_persona_vulnerable_registro(self, val: str):
        self.persona_vulnerable_registro = val or ""

    def set_etnia(self, val: str):
        self.etnia = val or ""

    def set_modal_politica_visible(self, visible: bool):
        self.modal_politica_visible = bool(visible)

    def set_archivo_error_mensaje(self, mensaje: str):
        self.archivo_error_mensaje = mensaje or ""

    def set_correo_confirmacion_visible(self, visible: bool):
        self.correo_confirmacion_visible = bool(visible)

    def set_correo_confirmacion_mensaje(self, mensaje: str):
        self.correo_confirmacion_mensaje = mensaje or ""

    def validar_email(self):
        if validar_correo(self.correo):
            self.correo_confirmacion_visible = True
            self.correo_confirmacion_mensaje = "Correo válido."
        else:
            self.correo_confirmacion_visible = True
            self.correo_confirmacion_mensaje = "Correo no válido."

    def set_descripcion(self, val: str):
        # Guardar descripción y longitud para el contador de caracteres
        self.descripcion = val if val is not None else ""
        # Limitar a 1000 caracteres en la UI
        if len(self.descripcion) > 1000:
            self.descripcion = self.descripcion[:1000]
        self.descripcion_len = len(self.descripcion)

    def set_tipo_solicitud(self, val: str):
        self.tipo_solicitud = val or ""

    def set_persona_vulnerable(self, val: str):
        self.persona_vulnerable = val or ""

    def set_asunto(self, val: str):
        self.asunto = val or ""

    def set_ubicacion(self, val: str):
        self.ubicacion = val or ""

    def set_acepta_politica_solicitud(self, checked: bool):
        self.acepta_politica_solicitud = bool(checked)

    def preconfirmar_politica(self, checked: bool):
        if checked:
            self.modal_politica_visible = True
        else:
            self.acepta_politica_datos = False

    def confirmar_politica(self):
        self.acepta_politica_datos = True
        self.modal_politica_visible = False

    def cancelar_politica(self):
        self.acepta_politica_datos = False
        self.modal_politica_visible = False

    def set_acepta_notificaciones(self, checked: bool):
        self.acepta_notificaciones = bool(checked)

    def set_documento(self, documento: Any):
        """Actualiza los adjuntos cuando el ciudadano selecciona uno o varios archivos."""
        self.documentos = []
        self.documento_nombres = []
        self.documento = ""
        self.documento_nombre = ""
        self.archivo_error_mensaje = ""

        allowed_ext = {"pdf", "png", "jpg", "jpeg"}
        max_files = 3
        max_total_size = 10 * 1024 * 1024

        def file_key(item: Any) -> tuple[str, int]:
            if isinstance(item, dict):
                name = item.get("name") or item.get("filename") or "adjunto"
                size = int(item.get("size") or 0)
        max_size = 10 * 1024 * 1024

        def valid_document(item: Any) -> bool:
            if isinstance(item, dict):
                name = item.get("name") or item.get("filename") or "adjunto"
                size = item.get("size") or 0
            elif isinstance(item, str):
                name = os.path.basename(item)
                size = 0
            else:
                name = "adjunto"
                size = 0
            return (name, size)

        def get_name(item: Any) -> str:
            if isinstance(item, dict):
                return item.get("name") or item.get("filename") or "adjunto"
            return os.path.basename(item) if isinstance(item, str) else "adjunto"

        def get_size(item: Any) -> int:
            if isinstance(item, dict):
                return int(item.get("size") or 0)
            return 0

        def valid_document(item: Any) -> bool:
            name = get_name(item)
            size = get_size(item)

            return True

            ext = os.path.splitext(name)[1].lower().lstrip(".")
            if ext not in allowed_ext:
                self.archivo_error_mensaje = "Solo se aceptan archivos PDF, PNG o JPG."
                return False
            if size > max_total_size:
             if size and size > max_size:
                self.archivo_error_mensaje = "Cada archivo no puede superar los 10MB."
                return False
            return True

        def append_document(item: Any):
            name = get_name(item)
            if isinstance(item, dict):
                self.documento_nombres.append(name)
                self.documentos.append(item)
            elif isinstance(item, str):
                self.documento_nombres.append(name)
            if isinstance(item, dict):
                name = item.get("name") or item.get("filename") or "adjunto"
                self.documento_nombres.append(name)
                self.documentos.append(item)
            elif isinstance(item, str):
                self.documento_nombres.append(os.path.basename(item))
                self.documentos.append(item)
            else:
                self.documentos.append(item)

        archivos = documento if isinstance(documento, list) else [documento]
        nuevos_archivos: list[Any] = []
        existentes = {file_key(item) for item in self.documentos}

        for item in archivos:
            llave = file_key(item)
            if llave in existentes:
                continue
            nuevos_archivos.append(item)
            existentes.add(llave)

        total_files = len(self.documentos) + len(nuevos_archivos)
        if total_files > max_files:
            self.archivo_error_mensaje = "Solo puedes adjuntar hasta 3 archivos."
            return

        current_total_size = sum(get_size(item) for item in self.documentos)
        added_total_size = sum(get_size(item) for item in nuevos_archivos)
        if current_total_size + added_total_size > max_total_size:
            self.archivo_error_mensaje = "La suma de los archivos no puede superar los 10MB."
            return

        for item in nuevos_archivos:
            if not valid_document(item):
                self.documentos = []
                self.documento_nombres = []
                return
        if len(archivos) > max_files:
            self.archivo_error_mensaje = "Solo puedes adjuntar hasta 3 archivos."
            return

        for item in archivos:
            if not valid_document(item):
                self.documentos = []
                self.documento_nombres = []
                return
            append_document(item)

        if self.documento_nombres:
            self.documento_nombre = ", ".join(self.documento_nombres)

    def set_editar_solicitud_id(self, id: int):
        self.editar_solicitud_id = id

    def set_eliminar_solicitud_id(self, id: int):
        self.eliminar_solicitud_id = id

    def eliminar_documento(self, index: int):
        # Reconstruir listas para evitar comportamiento reactivo inesperado
        if not (0 <= index < len(self.documentos)):
            return
        nuevos_docs: list[Any] = []
        nuevos_nombres: list[str] = []
        for i, item in enumerate(self.documentos):
            if i == index:
                continue
            nuevos_docs.append(item)
        for i, nombre in enumerate(self.documento_nombres):
            if i == index:
                continue
            nuevos_nombres.append(nombre)
        self.documentos = nuevos_docs
        self.documento_nombres = nuevos_nombres
        self.documento_nombre = ", ".join(self.documento_nombres)
        self.archivo_error_mensaje = ""

    def eliminar_documento_por_nombre(self, nombre: str):
        if nombre in self.documento_nombres:
            index = self.documento_nombres.index(nombre)
            self.eliminar_documento(index)

    def confirmar_editar_solicitud(self):
        if self.editar_solicitud_id:
            self.editar_solicitud(self.editar_solicitud_id)
            self.editar_solicitud_id = 0

    def confirmar_eliminar_solicitud(self):
        if self.eliminar_solicitud_id:
            self.eliminar_solicitud(self.eliminar_solicitud_id)
            self.eliminar_solicitud_id = 0

    def set_area_responsable(self, val: str):
        self.area_responsable = val
        if val != "Otros":
            self.area_otro = ""

    def set_area_otro(self, val: str):
        self.area_otro = val

    def set_nuevo_estado(self, val: str):
        self.nuevo_estado = val

    def set_respuesta_solicitud(self, val: str):
        self.respuesta_solicitud = val

    def set_respuesta_documento(self, documento: Any):
        """Actualiza el documento adjunto en la respuesta del funcionario."""
        if isinstance(documento, dict):
            name = documento.get("name") or documento.get("filename") or "respuesta_adjunto"
            self.respuesta_documento_nombre = name
            self.respuesta_documento = documento
        elif isinstance(documento, str):
            self.respuesta_documento_nombre = os.path.basename(documento)
            self.respuesta_documento = documento
        else:
            self.respuesta_documento_nombre = ""
            self.respuesta_documento = documento

    def set_asignar_area_mensaje(self, val: str):
        self.asignar_area_mensaje = val

    def set_asignar_area_seleccionada(self, val: str):
        self.asignar_area_seleccionada = val or ""

    def set_asignar_area_nombre(self, val: str):
        self.asignar_area_nombre = val or ""

    def cerrar_editor_estado(self):
        self.editar_estado_id = 0
        self.nuevo_estado = ""
        self.respuesta_solicitud = ""
        self.respuesta_documento = ""
        self.respuesta_documento_nombre = ""
        self.mensaje_actualizar_estado = ""

    def set_consulta_radicado(self, val: str):
        self.consulta_radicado = val

    def actualizar_estado_solicitud(self):
        """Actualiza el estado de una solicitud con validación para cerrada."""
        self.mensaje_actualizar_estado = ""
        
        if not self.editar_estado_id or not self.nuevo_estado:
            self.mensaje_actualizar_estado = "Selecciona un estado válido."
            return
        
        # Validar que si se quiere cerrar, debe haber respuesta
        if self.nuevo_estado == "Cerrada" and not self.respuesta_solicitud:
            self.mensaje_actualizar_estado = "No puedes cerrar una solicitud sin escribir una respuesta."
            return
        
        # Guardar documento de respuesta si existe
        documento_respuesta_guardado = ""
        if self.respuesta_documento:
            try:
                os.makedirs(UPLOAD_DIR, exist_ok=True)
                # Caso: data URL (base64)
                if isinstance(self.respuesta_documento, str) and self.respuesta_documento.startswith("data:"):
                    header, b64 = self.respuesta_documento.split(",", 1)
                    mime = header.split(";")[0].split(":")[1] if ":" in header else ""
                    ext = mime.split("/")[-1] if "/" in mime else "bin"
                    saved_name = f"respuesta_{uuid.uuid4().hex}.{ext}"
                    path = os.path.join(UPLOAD_DIR, saved_name)
                    with open(path, "wb") as f:
                        f.write(base64.b64decode(b64))
                    documento_respuesta_guardado = path
                # Caso: objeto con 'content' y 'name'
                elif isinstance(self.respuesta_documento, dict) and "content" in self.respuesta_documento:
                    content = self.respuesta_documento.get("content")
                    name = self.respuesta_documento.get("name", f"respuesta_{uuid.uuid4().hex}")
                    # Sanitizar nombre de archivo
                    name = sanitizar_nombre_archivo(name)
                    if isinstance(content, str) and content.startswith("data:"):
                        _, b64 = content.split(",", 1)
                        data = base64.b64decode(b64)
                    else:
                        data = base64.b64decode(content)
                    path = os.path.join(UPLOAD_DIR, name)
                    with open(path, "wb") as f:
                        f.write(data)
                    documento_respuesta_guardado = path
                else:
                    # Si viene solo el nombre o ruta, lo conservamos tal cual
                    documento_respuesta_guardado = str(self.respuesta_documento)
            except Exception as e:
                print(f"Error guardando documento de respuesta: {e}")
                # Continuamos sin guardar el documento
        
        try:
            with Session(engine) as session:
                solicitud_obj = session.get(Solicitud, self.editar_estado_id)
                if not solicitud_obj:
                    self.mensaje_actualizar_estado = "Solicitud no encontrada."
                    return
                
                solicitud_obj.estado = self.nuevo_estado
                if self.respuesta_solicitud:
                    solicitud_obj.respuesta = self.respuesta_solicitud
                
                # Guardar documento de respuesta si existe
                if documento_respuesta_guardado:
                    # Si la solicitud no tiene campo para respuesta_documento, lo agregamos como metadato en respuesta
                    solicitud_obj.respuesta = (solicitud_obj.respuesta or "") + f"\n\n[DOCUMENTO ADJUNTO: {os.path.basename(documento_respuesta_guardado)}]"
                
                session.add(solicitud_obj)
                session.commit()
            
            solicitud_id = self.editar_estado_id
            estado_enviado = self.nuevo_estado
            respuesta_enviada = self.respuesta_solicitud
            self.mensaje_actualizar_estado = f"Estado actualizado a '{estado_enviado}' correctamente."
            self.editar_estado_id = 0
            self.nuevo_estado = ""
            self.respuesta_solicitud = ""
            self.respuesta_documento = ""
            self.respuesta_documento_nombre = ""
            self.cargar_solicitudes()
            
            # Enviar notificación por correo al ciudadano
            try:
                # Obtener información de la solicitud y el ciudadano
                solicitud_info = None
                for sol in self.solicitudes:
                    if sol['id'] == solicitud_id:
                        solicitud_info = sol
                        break
                
                if solicitud_info:
                    asunto_email = f"Actualización en tu solicitud PQRS - {solicitud_info['radicado']}"
                    cuerpo_email = f"""
Estimado ciudadano,

Tu solicitud PQRS con número de radicado {solicitud_info['radicado']} ha sido actualizada.

Detalles de la solicitud:
- Tipo: {solicitud_info['tipo_solicitud']}
- Asunto: {solicitud_info['asunto']}
- Estado actual: {estado_enviado}
- Fecha de actualización: {datetime.now().strftime('%Y-%m-%d %H:%M')}

"""
                    if respuesta_enviada:
                        cuerpo_email += f"Respuesta del funcionario:\n{respuesta_enviada}\n\n"
                    
                    if documento_respuesta_guardado:
                        doc_name = os.path.basename(documento_respuesta_guardado)
                        host_url = os.getenv("APP_URL", "http://localhost:3000").rstrip("/")
                        doc_url = f"{host_url}/assets/uploads/{doc_name}"
                        cuerpo_email += f"Documento adjunto: {doc_name}\nDescarga: {doc_url}\n\n"
                    
                    cuerpo_email += """
Puedes consultar el estado completo de tu solicitud en nuestro portal web.

Atentamente,
Equipo de Atención al Ciudadano
Sistema PQRS
"""
                    
                    # Enviar correo al ciudadano
                    enviar_correo_notificacion(solicitud_info['creado_por'], asunto_email, cuerpo_email)
                    
            except Exception as e:
                print(f"Error enviando notificación: {e}")
                # No fallar la actualización por error en notificación
        except Exception as e:
            self.mensaje_actualizar_estado = f"Error actualizando estado: {e}"

    def abrir_editor_estado(self, solicitud_id: int, estado_actual: str):
        """Abre el editor de estado para una solicitud."""
        self.editar_estado_id = solicitud_id
        self.nuevo_estado = estado_actual
        self.respuesta_solicitud = ""
        self.respuesta_documento = ""
        self.respuesta_documento_nombre = ""
        self.mensaje_actualizar_estado = ""

    def abrir_asignar_area(self, solicitud_id: int, area_actual: str):
        """Abre el diálogo para asignar un área a una solicitud con mensaje."""
        self.asignar_area_id = solicitud_id
        self.asignar_area_nombre = area_actual
        self.asignar_area_seleccionada = area_actual or "Atención al Ciudadano"
        self.asignar_area_mensaje = ""
        self.mensaje_asignacion = ""

    def cerrar_asignar_area(self):
        """Cierra el diálogo de asignación de área."""
        self.asignar_area_id = 0
        self.asignar_area_nombre = ""
        self.asignar_area_seleccionada = ""
        self.asignar_area_mensaje = ""
        self.mensaje_asignacion = ""

    def asignar_area_con_mensaje(self):
        """Asigna un área a una solicitud y envía un mensaje al ciudadano."""
        self.mensaje_asignacion = ""
        
        area_a_asignar = self.asignar_area_seleccionada or self.asignar_area_nombre
        if not self.asignar_area_id or not area_a_asignar:
            self.mensaje_asignacion = "Selecciona un área válida."
            return
        
        if not self.asignar_area_mensaje:
            self.mensaje_asignacion = "Escribe un mensaje para el ciudadano."
            return
        
        try:
            with Session(engine) as session:
                solicitud_obj = session.get(Solicitud, self.asignar_area_id)
                if not solicitud_obj:
                    self.mensaje_asignacion = "Solicitud no encontrada."
                    return
                
                solicitud_obj.area_responsable = area_a_asignar
                session.add(solicitud_obj)
                session.commit()
            
            # Enviar notificación por correo al ciudadano
            solicitud_info = None
            for sol in self.solicitudes:
                if sol['id'] == self.asignar_area_id:
                    solicitud_info = sol
                    break
            
            if solicitud_info:
                area_a_asignar = self.asignar_area_seleccionada or self.asignar_area_nombre
                asunto_email = f"Tu solicitud PQRS ha sido asignada a {area_a_asignar}"
                cuerpo_email = f"""
Estimado ciudadano,

Tu solicitud PQRS con número de radicado {solicitud_info['radicado']} ha sido asignada a {area_a_asignar} para su tratamiento.

Detalles de la solicitud:
- Tipo: {solicitud_info['tipo_solicitud']}
- Asunto: {solicitud_info['asunto']}
- Área responsable: {area_a_asignar}

Mensaje del funcionario:
{self.asignar_area_mensaje}

Puedes consultar el estado completo de tu solicitud en nuestro portal web.

Atentamente,
Equipo de Atención al Ciudadano
Sistema PQRS
"""

                # Enviar correo al ciudadano
                enviar_correo_notificacion(solicitud_info['creado_por'], asunto_email, cuerpo_email)
            
            self.mensaje_asignacion = f"Área asignada a {area_a_asignar} y mensaje enviado correctamente."
            self.cargar_solicitudes()
            self.cerrar_asignar_area()
        except Exception as e:
            self.mensaje_asignacion = f"Error asignando área: {e}"

    def _solicitud_a_dict(self, solicitud: Solicitud) -> dict[str, Any]:
        respuesta_text = solicitud.respuesta or ""
        respuesta_documento_basename = None
        if respuesta_text:
            match = re.search(r"\[DOCUMENTO ADJUNTO:\s*([^\]\|]+)\]", respuesta_text)
            if match:
                respuesta_documento_basename = match.group(1).strip()
                respuesta_text = re.sub(r"\s*\[DOCUMENTO ADJUNTO:[^\]]+\]", "", respuesta_text).strip()

        documento_basenames = []
        if solicitud.documento_basename:
            try:
                parsed_names = json.loads(solicitud.documento_basename)
                if isinstance(parsed_names, list):
                    documento_basenames = parsed_names
                else:
                    documento_basenames = [parsed_names]
            except Exception:
                documento_basenames = [solicitud.documento_basename]

        documento_paths = []
        if solicitud.documento:
            try:
                parsed_paths = json.loads(solicitud.documento)
                if isinstance(parsed_paths, list):
                    documento_paths = parsed_paths
                else:
                    documento_paths = [parsed_paths]
            except Exception:
                documento_paths = [solicitud.documento]

        documento_adjuntos = []
        for idx, path in enumerate(documento_paths):
            basename = documento_basenames[idx] if idx < len(documento_basenames) else os.path.basename(str(path))
            documento_adjuntos.append(
                {
                    "basename": basename,
                    "href": f"/assets/uploads/{quote(basename)}" if basename else "",
                }
            )

        documento_basename = documento_adjuntos[0]["basename"] if documento_adjuntos else ""
        documento_href = documento_adjuntos[0]["href"] if documento_adjuntos else ""

        return {
            "id": solicitud.id,
            "radicado": solicitud.radicado,
            "tipo_solicitud": solicitud.tipo_solicitud,
            "persona_vulnerable": solicitud.persona_vulnerable,
            "asunto": solicitud.asunto,
            "descripcion": solicitud.descripcion,
            "ubicacion": solicitud.ubicacion,
            "area_responsable": solicitud.area_responsable,
            "documento": solicitud.documento,
            "documento_basename": documento_basename,
            "documento_href": documento_href,
            "documento_adjuntos": documento_adjuntos,
            "documento_adjuntos_json": json.dumps(documento_adjuntos),
            "estado": solicitud.estado,
            "respuesta": respuesta_text,
            "respuesta_documento_basename": respuesta_documento_basename,
            "respuesta_documento_href": f"/assets/uploads/{quote(respuesta_documento_basename)}" if respuesta_documento_basename else "",
            "fecha": solicitud.fecha.strftime("%Y-%m-%d %H:%M") if isinstance(solicitud.fecha, datetime) else str(solicitud.fecha),
            "creado_por": solicitud.creado_por,
           "usuario_id": solicitud.usuario_id,
        
        
        }
        

        # Extraer metadata embebida en `documento` si existe (usado para pruebas/seed)
        try:
            if solicitud.documento:
                parsed = json.loads(solicitud.documento)
                if isinstance(parsed, dict):
                    if "tiempo_respuesta_dias" in parsed:
                        result["tiempo_respuesta_dias"] = parsed.get("tiempo_respuesta_dias")
                    if "fecha_respuesta" in parsed:
                        result["fecha_respuesta"] = parsed.get("fecha_respuesta")
                    if "cumple_plazo" in parsed:
                        result["cumple_plazo"] = parsed.get("cumple_plazo")
        except Exception:
            pass

        return result
        
        

    @rx.var
    def solicitud_consultada_adjuntos(self) -> list[dict[str, str]]:
        docs = self.solicitud_consultada.get("documento_adjuntos", [])
        if not isinstance(docs, list):
            return []

        resultado = []
        for doc in docs:
            if isinstance(doc, dict):
                resultado.append({
                    "basename": str(doc.get("basename", "")),
                    "href": str(doc.get("href", "")),
                })
        return resultado

    def cargar_solicitudes(self):
        try:
            with rx.session() as session:
                # Ordenar por fecha descendente para mostrar las más nuevas primero
                query = select(Solicitud).order_by(Solicitud.fecha.desc())
                if self.rol_usuario == "ciudadano" and self.email_actual:
                    query = query.where(Solicitud.creado_por == self.email_actual)
                solicitudes_obj = session.exec(query).all()
                self.solicitudes = [self._solicitud_a_dict(s) for s in solicitudes_obj]
                # Precompute semáforo values per solicitud to ensure reliable rendering
                # Fetch DB-stored fecha_respuesta (if any) into each solicitud dict so charts can use it
                with engine.connect() as conn:
                    for s in self.solicitudes:
                        try:
                            row = conn.execute(text("SELECT fecha_respuesta FROM solicitud WHERE id = :id"), {"id": s.get('id')}).fetchone()
                            if row and row[0]:
                                # store raw DB value (string/datetime)
                                s['fecha_respuesta'] = str(row[0])
                            else:
                                s['fecha_respuesta'] = None
                        except Exception:
                            s['fecha_respuesta'] = None

                for s in self.solicitudes:
                    try:
                        sem = State._compute_remaining_for_solicitud(s)
                        s['semaforo_remaining'] = sem.get('remaining')
                        s['semaforo_fill'] = sem.get('fill')
                        s['semaforo_width'] = sem.get('width', 0)
                        s['semaforo_expired'] = s['semaforo_remaining'] is not None and s['semaforo_remaining'] <= 0
                    except Exception:
                        s['semaforo_remaining'] = None
                        s['semaforo_fill'] = 'gray'
                        s['semaforo_width'] = 0
                        s['semaforo_expired'] = False

        except Exception as e:
            print(f"Error cargando solicitudes: {e}")
            self.solicitudes = []

    def export_reportes_excel(self):
        """Genera un Excel en memoria desde `self.solicitudes` para descarga.
        
        Si pandas no está disponible, genera un CSV como fallback.
        """
        try:
            import io
            from datetime import datetime

            data = self.solicitudes or []
            if not data:
                self.mostrar_toast("No hay datos para exportar.", "warning")
                self.mostrar_menu_descarga = False
                return
            
            # Intentar con Excel primero
            try:
                import pandas as pd

                
                # Usar BytesIO para guardar en memoria
                output = io.BytesIO()
                df.to_excel(output, index=False, sheet_name="Solicitudes", engine="openpyxl")
                output.seek(0)
                
                excel_bytes = output.getvalue()
                filename = f"reportes_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.xlsx"
                download_id = str(uuid.uuid4())
                
                TEMP_DOWNLOADS[download_id] = {
                    "data": excel_bytes,
                    "filename": filename,
                    "mime": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                }
                
                self.export_filename = filename
                self.mostrar_toast(f"✓ Excel generado. {len(data)} registros. Descargando...", "success")
                self.mostrar_menu_descarga = False
                self.export_href = f"/api/download/{download_id}"
                
            except (ImportError, ModuleNotFoundError):
                # Fallback a CSV
                self.export_reportes_csv()
                
        except Exception as e:
            print(f"ERROR CRITICO en export_reportes_excel: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            self.mostrar_toast(f"Error: {str(e)[:100]}", "error")
            self.mostrar_menu_descarga = False


    def descargar_reporte_excel(self):
        """Descarga el archivo Excel generado."""
        try:
            if not self.export_filename:
                self.mostrar_toast("No hay archivo para descargar.", "warning")
                return
            
            filepath = os.path.join(UPLOAD_DIR, self.export_filename)
            if not os.path.exists(filepath):
                self.mostrar_toast(f"Archivo no encontrado: {self.export_filename}", "error")
                self.export_filename = ""
                self.export_href = ""
                return
            
            # Leer el archivo y preparar para descarga
            with open(filepath, 'rb') as f:
                content = f.read()
            
            # Usar rx.download para forzar la descarga
            return rx.download(
                data=content,
                filename=self.export_filename,
                mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
        except Exception as e:
            print(f"ERROR en descargar_reporte_excel: {e}")
            import traceback
            traceback.print_exc()
            self.mostrar_toast(f"Error descargando: {str(e)}", "error")

    def _validar_registro_basico(self) -> None:
        self.error_de_registro = ""
        if not self.validacion_de_entradas():
            return
        required_fields = ["nombres", "apellidos", "tipo_identificacion", "numero_identificacion"]
        for f in required_fields:
            if not getattr(self, f, ""):
                self.error_de_registro = "Completa los campos obligatorios de información personal."
                return
        if not self.acepta_politica_datos or not self.acepta_notificaciones:
            self.error_de_registro = "Debes aceptar la política de datos y recibir notificaciones para registrarte."
            return

    def _crear_usuario(self, rol: str, exito_mensaje: str):
        with rx.session() as session:
            existing_user = session.exec(select(Usuario).where(Usuario.email == self.correo)).first()
            if existing_user:
                self.error_de_registro = "El correo ya está registrado."
                return
            hashed = tiene_password(self.contraseña)
            nuevo_usuario = Usuario(
                email=self.correo,
                Contraseña=hashed,
                rol=rol,
                is_active=True,
                Fecha_de_creacion=datetime.now(),
                tipo_identificacion=self.tipo_identificacion,
                numero_identificacion=self.numero_identificacion,
                nombres=self.nombres,
                apellidos=self.apellidos,
                sexo=self.sexo,
                direccion=self.direccion,
                telefono=self.telefono,
                departamento=self.departamento,
                ciudad=self.ciudad,
                etnia=self.etnia,
                persona_vulnerable=self.persona_vulnerable_registro,
            )
            session.add(nuevo_usuario)
            session.commit()
        print(f"Usuario registrado: {self.correo}")
        enviar_correo_bienvenida(self.correo, self.correo)
        self.succes = exito_mensaje
        self.mostrar_toast("¡Registro exitoso! Bienvenido al sistema.", "success")
        self.error_de_registro = ""
        self.contraseña = ""
        self.confirmar_contraseña = ""
        self.show_password = False
        # Login automático después del registro
        self.es_autentica = True
        self.correo_usuario = self.correo
        self.rol_usuario = "ciudadano"
        self.cargar_usuarios()

    def signup(self):
        self.borrar_mensajes_de_estado()
        self._validar_registro_basico()
        if self.error_de_registro:
            return
        self._crear_usuario(
            rol="ciudadano",
            exito_mensaje="Registro exitoso. Revisa tu correo para confirmar. Ahora el funcionario puede iniciar sesión.",
        )
        # Redirigir a solicitudes después del registro
        if not self.error_de_registro:
            return rx.redirect("/solicitudes")

    def signup_funcionario(self):
        self.borrar_mensajes_de_estado()
        if not self.es_autentica or self.rol_usuario != "funcionario":
            self.error_de_registro = "Solo los funcionarios autenticados pueden registrar nuevos funcionarios."
            return
        self._validar_registro_basico()
        if self.error_de_registro:
            return
        return self._crear_usuario(
            rol="funcionario",
            exito_mensaje="Funcionario registrado con éxito. Ahora puede iniciar sesión con su correo institucional.",
        )

    def login(self):
        self.borrar_mensajes_de_estado()
        if not self.validacion_de_entradas(require_strong_pw=False):
            self.succes2 = ""
            self.error_de_contraseña = self.error_de_registro or "Correo o contraseña incorrectos."
            self.error_de_registro = ""
            return
        with Session(engine) as session:
            user = session.exec(select(Usuario).where(Usuario.email == self.correo)).first()
            print(f"Login lookup for: {self.correo} -> {'FOUND' if user else 'NOT FOUND'}")
            if user:
                print(f"  stored hash present: {bool(user.Contraseña)}")
            pw_ok = False
            try:
                pw_ok = confirmar_contraseña(self.contraseña, user.Contraseña) if user else False
            except Exception as e:
                print(f"Error comprobando contraseña: {e}")
            print(f"Login attempt for: {self.correo}, success: {pw_ok}")
            if not user or not pw_ok:
                self.error_de_contraseña = "Correo o contraseña incorrectos."
                color="red"
                self.succes2 = ""
                return
            if not user.is_active:
                self.error_de_contraseña = "La cuenta no está activa."
                color="red"
                self.succes2 = ""
                return
            self.id_usuario = user.id
            self.rol_usuario = user.rol
            self.email_actual = user.email
            self.es_autentica = True
            self.cargar_solicitudes()
            self.cargar_usuarios()
            self.error_de_contraseña = ""
            self.contraseña = ""
            self.confirmar_contraseña = ""
            self.show_password = False
            self.mostrar_toast("¡Inicio de sesión exitoso! Redirigiendo automáticamente...", "success")
            # Redirigir después de mostrar el toast
            if self.rol_usuario == "funcionario":
                return rx.redirect("/dashboard-funcionario")
            else:
                return rx.redirect("/dashboard")
        

    def redirect_after_login(self):
        if self.rol_usuario == "funcionario":
            return rx.redirect("/dashboard-funcionario")
        return rx.redirect("/dashboard")

    def logout(self):
        "cerrar sesion de usuario"
        self.id_usuario = 0
        self.correo = ""
        self.contraseña = ""
        self.confirmar_contraseña = ""
        self.rol_usuario = ""
        self.email_actual = ""
        self.es_autentica = False
        self.show_password = False
        self.succes2 = "Has cerrado sesión exitosamente."
        self.error_de_contraseña = ""
        return rx.redirect("/")

    def change_password(self):
        """Cambiar la contraseña del usuario autenticado."""
        self.change_pw_message = ""
        if not self.es_autentica or not self.id_usuario:
            self.change_pw_message = "Debes iniciar sesión para cambiar la contraseña."
            return
        # Validaciones básicas
        if not self.current_password or not self.new_password or not self.confirm_new_password:
            self.change_pw_message = "Completa todos los campos."
            return
        if self.new_password != self.confirm_new_password:
            self.change_pw_message = "La nueva contraseña y su confirmación no coinciden."
            return
        if not cantida_minima_contraseña(self.new_password):
            self.change_pw_message = "La nueva contraseña no cumple los requisitos de seguridad."
            return
        with Session(engine) as session:
            user = session.exec(select(Usuario).where(Usuario.id == self.id_usuario)).first()
            if not user:
                self.change_pw_message = "Usuario no encontrado."
                return
            try:
                if not confirmar_contraseña(self.current_password, user.Contraseña):
                    self.change_pw_message = "La contraseña actual es incorrecta."
                    return
            except Exception as e:
                self.change_pw_message = f"Error comprobando contraseña: {e}"
                return
            # Actualizar contraseña
            user.Contraseña = tiene_password(self.new_password)
            session.add(user)
            session.commit()
            self.change_pw_message = "Contraseña cambiada correctamente."
            # Limpiar campos
            self.current_password = ""
            self.new_password = ""
            self.confirm_new_password = ""

    def toggle_show_password(self):
        self.show_password = not self.show_password

    def limpiar_formulario_solicitud(self, keep_message: bool = False):
        self.tipo_solicitud = ""
        self.persona_vulnerable = ""
        self.asunto = ""
        self.descripcion = ""
        self.ubicacion = ""
        self.documento = ""
        self.documentos = []
        self.documento_nombres = []
        self.documento_nombre = ""
        self.area_responsable = ""
        self.area_otro = ""
        self.descripcion_len = 0
        self.editar_solicitud_id = 0
        self.acepta_politica_solicitud = False
        if not keep_message:
            self.solicitud_mensaje = ""

    def crear_solicitud(self):
        self.solicitud_mensaje = ""
        if not self.tipo_solicitud or not self.asunto or not self.descripcion:
            self.solicitud_mensaje = "Completa los campos obligatorios antes de enviar."
            return
        if not self.area_responsable:
            self.solicitud_mensaje = "Selecciona el área responsable."
            return
        if self.area_responsable == "Otros" and not self.area_otro:
            self.solicitud_mensaje = "Por favor indica el área responsable cuando eliges Otros."
            return
        # Verificar aceptación de política de tratamiento de datos
        if not self.acepta_politica_solicitud:
            self.solicitud_mensaje = "Debes aceptar la Política de Tratamiento de Datos Personales antes de enviar."
            return

        documentos_guardados: list[str] = []
        documento_basenames_guardados: list[str] = []

        def guardar_archivo(item: Any) -> None:
            if isinstance(item, str) and not item.startswith("data:"):
                documentos_guardados.append(item)
                documento_basenames_guardados.append(os.path.basename(item))
                return

            if isinstance(item, str) and item.startswith("data:"):
                header, b64 = item.split(",", 1)
                mime = header.split(";")[0].split(":")[1] if ":" in header else ""
                ext = mime.split("/")[-1] if "/" in mime else "bin"
                saved_name = f"solicitud_{uuid.uuid4().hex}.{ext}"
                path = os.path.join(UPLOAD_DIR, saved_name)
                with open(path, "wb") as f:
                    f.write(base64.b64decode(b64))
                documentos_guardados.append(path)
                documento_basenames_guardados.append(saved_name)
                return

            if isinstance(item, dict) and "content" in item:
                content = item.get("content")
                name = item.get("name", f"solicitud_{uuid.uuid4().hex}")
                name = sanitizar_nombre_archivo(name)
                if isinstance(content, str) and content.startswith("data:"):
                    _, b64 = content.split(",", 1)
                    data = base64.b64decode(b64)
                else:
                    data = base64.b64decode(content)
                path = os.path.join(UPLOAD_DIR, name)
                with open(path, "wb") as f:
                    f.write(data)
                documentos_guardados.append(path)
                documento_basenames_guardados.append(name)
                return

            if isinstance(item, dict):
                name = item.get("name") or item.get("filename") or f"solicitud_{uuid.uuid4().hex}"
                name = sanitizar_nombre_archivo(name)
                documento_basenames_guardados.append(name)
                documentos_guardados.append(name)
                return

            documento_basenames_guardados.append(str(item))
            documentos_guardados.append(str(item))

        if self.documentos:
            try:
                os.makedirs(UPLOAD_DIR, exist_ok=True)
                for item in self.documentos:
                    guardar_archivo(item)
            except Exception as e:
                self.solicitud_mensaje = f"Error guardando documento: {e}"
                return
        elif self.documento:
            try:
                os.makedirs(UPLOAD_DIR, exist_ok=True)
                guardar_archivo(self.documento)
            except Exception as e:
                self.solicitud_mensaje = f"Error guardando documento: {e}"
                return

        if self.editar_solicitud_id:
            try:
                with Session(engine) as session:
                    solicitud_obj = session.get(Solicitud, self.editar_solicitud_id)
                    if not solicitud_obj:
                        self.solicitud_mensaje = "Solicitud no encontrada para editar."
                        return
                    # Obtener persona_vulnerable del usuario autenticado
                    usuario = session.get(Usuario, self.id_usuario)
                    persona_vulnerable_valor = usuario.persona_vulnerable if usuario else None
                    
                    solicitud_obj.tipo_solicitud = self.tipo_solicitud
                    solicitud_obj.persona_vulnerable = persona_vulnerable_valor or None
                    solicitud_obj.asunto = self.asunto
                    solicitud_obj.descripcion = self.descripcion
                    solicitud_obj.ubicacion = self.ubicacion or None
                    solicitud_obj.area_responsable = self.area_otro if self.area_responsable == "Otros" else self.area_responsable
                    if documentos_guardados:
                        solicitud_obj.documento = json.dumps(documentos_guardados)
                        solicitud_obj.documento_basename = json.dumps(documento_basenames_guardados)
                    solicitud_obj.estado = "Actualizada"
                    session.add(solicitud_obj)
                    session.commit()
                self.solicitud_mensaje = "Solicitud actualizada con éxito."
                self.editar_solicitud_id = 0
                self.limpiar_formulario_solicitud(keep_message=True)
                self.cargar_solicitudes()
                return
            except Exception as e:
                self.solicitud_mensaje = f"Error actualizando solicitud: {e}"
                return

        try:
            with rx.session() as session:
                # Obtener persona_vulnerable del usuario autenticado
                usuario = session.get(Usuario, self.id_usuario)
                persona_vulnerable_valor = usuario.persona_vulnerable if usuario else None
                
                solicitud_obj = Solicitud(
                    radicado=f"PQRS-{datetime.now().year}-{uuid.uuid4().hex[:8]}".upper(),
                    tipo_solicitud=self.tipo_solicitud,
                    persona_vulnerable=persona_vulnerable_valor or None,
                    asunto=self.asunto,
                    descripcion=self.descripcion,
                    ubicacion=self.ubicacion or None,
                    area_responsable=self.area_otro if self.area_responsable == "Otros" else self.area_responsable,
                    documento=json.dumps(documentos_guardados) if documentos_guardados else None,
                    documento_basename=json.dumps(documento_basenames_guardados) if documento_basenames_guardados else None,
                    estado="Radicada",
                    fecha=datetime.now(),
                    creado_por=self.email_actual or self.correo,
                    usuario_id=self.id_usuario if self.id_usuario else None,
                )
                session.add(solicitud_obj)
                session.commit()
                radicado_generado = solicitud_obj.radicado
            self.solicitud_mensaje = f"✅ Solicitud enviada con éxito. Radicado: {radicado_generado}"
            self.limpiar_formulario_solicitud(keep_message=True)
            self.cargar_solicitudes()
        except Exception as e:
            self.solicitud_mensaje = f"Error guardando solicitud: {e}"

    def editar_solicitud(self, solicitud_id: int):
        try:
            with Session(engine) as session:
                solicitud_obj = session.get(Solicitud, solicitud_id)
                if solicitud_obj:
                    self.editar_solicitud_id = solicitud_id
                    self.tipo_solicitud = solicitud_obj.tipo_solicitud
                    self.asunto = solicitud_obj.asunto
                    self.descripcion = solicitud_obj.descripcion
                    self.ubicacion = solicitud_obj.ubicacion or ""
                    self.area_responsable = solicitud_obj.area_responsable or ""
                    self.area_otro = solicitud_obj.area_responsable if solicitud_obj.area_responsable and solicitud_obj.area_responsable not in ["Secretaría", "Contabilidad", "Bienestar", "Tesorería", "Atención al Ciudadano"] else ""
                    self.persona_vulnerable = solicitud_obj.persona_vulnerable or ""
                    self.documento = solicitud_obj.documento or ""
                    self.solicitud_mensaje = "Editando solicitud. Actualiza los campos y guarda cambios."
                else:
                    self.solicitud_mensaje = "Solicitud no encontrada."
        except Exception as e:
            self.solicitud_mensaje = f"Error cargando solicitud: {e}"

    def consultar_estado_solicitud(self):
        """Consulta el estado de una solicitud por número de radicado."""
        self.consulta_mensaje = ""
        self.solicitud_consultada = {}
        
        if not self.consulta_radicado:
            self.consulta_mensaje = "Ingresa un número de radicado válido."
            return
        
        try:
            with Session(engine) as session:
                solicitud = session.exec(
                    select(Solicitud).where(Solicitud.radicado == self.consulta_radicado)
                ).first()
                
                if not solicitud:
                    self.consulta_mensaje = "No se encontró una solicitud con ese número de radicado."
                    return
                
                self.solicitud_consultada = self._solicitud_a_dict(solicitud)
                self.consulta_mensaje = "Solicitud encontrada."
                
        except Exception as e:
            self.consulta_mensaje = f"Error consultando solicitud: {e}"

    def cargar_usuarios(self):
        """Carga la lista de usuarios registrados en el sistema."""
        try:
            with rx.session() as session:
                usuarios = session.exec(select(Usuario)).all()
                self.usuarios_registrados = [
                    {
                        "id": u.id,
                        "email": u.email,
                        "nombres": u.nombres or "",
                        "apellidos": u.apellidos or "",
                        "rol": u.rol,
                        "fecha_creacion": u.Fecha_de_creacion.strftime("%Y-%m-%d") if isinstance(u.Fecha_de_creacion, datetime) else str(u.Fecha_de_creacion),
                        "is_active": "Activo" if u.is_active else "Inactivo",
                    }
                    for u in usuarios
                ]
        except Exception as e:
            print(f"Error cargando usuarios: {e}")
            self.usuarios_registrados = []

    def cambiar_rol_ciudadano_a_funcionario(self):
        """Cambia el rol de un ciudadano a funcionario."""
        self.cambiar_rol_mensaje = ""
        
        if not self.cambiar_rol_email:
            self.cambiar_rol_mensaje = "Ingresa el correo del usuario."
            return
        
        try:
            with rx.session() as session:
                usuario = session.exec(
                    select(Usuario).where(Usuario.email == self.cambiar_rol_email)
                ).first()
                
                if not usuario:
                    self.cambiar_rol_mensaje = f"No se encontró usuario con el correo {self.cambiar_rol_email}."
                    return
                
                if usuario.rol == "funcionario":
                    self.cambiar_rol_mensaje = f"El usuario ya es funcionario."
                    return
                
                usuario.rol = "funcionario"
                session.add(usuario)
                session.commit()
                
                # Enviar notificación
                try:
                    asunto = "Rol actualizado - Has sido promovido a Funcionario"
                    cuerpo = f"""
Estimado usuario,

Te informamos que tu rol en el sistema ha sido actualizado.

Tu nuevo rol: FUNCIONARIO

Con este rol podrás:
- Gestionar solicitudes PQRS
- Asignar áreas responsables
- Actualizar estados de solicitudes
- Ver reportes del sistema

Accede al Dashboard Funcionario con tu correo y contraseña.

Atentamente,
Sistema PQRS
"""
                    enviar_correo_notificacion(self.cambiar_rol_email, asunto, cuerpo)
                except:
                    pass  # No fallar si no se envía el correo
                
                self.cambiar_rol_mensaje = f"✅ Rol del usuario {self.cambiar_rol_email} actualizado a funcionario."
                self.cambiar_rol_email = ""
                self.cargar_usuarios()
        except Exception as e:
            self.cambiar_rol_mensaje = f"Error al cambiar rol: {e}"

    def set_cambiar_rol_email(self, value: str):
        self.cambiar_rol_email = value


    def set_confirmar_contraseña(self, value: str):
        self.confirmar_contraseña = value

    def set_correo(self, value: str):
        self.correo = value

    def set_contraseña(self, value: str):
        self.contraseña = value

    def set_tipo_identificacion(self, value: str):
        self.tipo_identificacion = value

    def set_genero(self, value: str):
        self.genero = value

    def set_sexo(self, value: str):
        self.sexo = value

    def set_direccion(self, value: str):
        self.direccion = value

    def set_current_password(self, value: str):
        self.current_password = value


    """The app state."""
def label_requerido(texto: str) -> rx.Component:
    return rx.hstack(
        rx.text(texto, color=rx.color_mode_cond(light="black", dark="white")),
        rx.text("*", color="orange.500"),
        spacing="1",
        align_items="center",
    )

def auth_card(title: str, on_submit, show_confirm: bool = False) -> rx.Component:
    text_color = rx.color_mode_cond(light="black", dark="white")
    input_bg = rx.color_mode_cond(light="white", dark="#2d3748")
    input_border = rx.color_mode_cond(light="#cbd5e1", dark="#4a5568")
    placeholder_color = rx.color_mode_cond(light="#718096", dark="#a0aec0")

    input_style = {
        "bg": input_bg,
        "border": f"1px solid {input_border}",
        "color": text_color,
        "_placeholder": {"color": placeholder_color},
    }

    confirmar_field = (
        rx.vstack(
            label_requerido("Confirmar Contraseña"),
            rx.input(
                placeholder="Confirmar Contraseña",
                type=rx.cond(State.show_password, "text", "password"),
                value=State.confirmar_contraseña,
                on_change=State.set_confirmar_contraseña,
                border_radius="md",
                size="3",
                **input_style,
            ),
        )
        if show_confirm
        else rx.box(display="none")
    )

    return rx.card(
        rx.form(
            rx.vstack(
                rx.heading(title, size={"base": "5", "md": "7"}, color=text_color, margin_bottom="1em"),
                rx.grid(
                    rx.vstack(
                        label_requerido("Correo electrónico"),
                        rx.hstack(
                            rx.input(
                                placeholder="Correo electrónico",
                                type="email",
                                value=State.correo,
                                on_change=State.set_and_validate_correo,
                                on_blur=State.validar_correo_accion,
                                border_radius="md",
                                size="3",
                                width="100%",
                                **input_style,
                            ),
                            rx.cond(
                                State.correo_validado,
                                rx.image(src="/check-green.svg", height="16px", ml="2"),
                                rx.box(),
                            ),
                            width="100%",
                        ),
                        rx.cond(
                            State.correo_confirmacion_visible,
                            rx.text(
                                State.correo_confirmacion_mensaje,
                                color=rx.cond(State.correo_validado, "green.500", "red.500"),
                                font_size="sm",
                                mt="2",
                            ),
                            rx.box(),
                        ),
                    ),
                    rx.vstack(
                        label_requerido("Contraseña"),
                        rx.hstack(
                            rx.input(
                                placeholder="Contraseña",
                                type=rx.cond(State.show_password, "text", "password"),
                                value=State.contraseña,
                                on_change=State.set_contraseña,
                                border_radius="10px",
                                width="100%",
                                size="3",
                                **input_style,
                            ),
                            rx.button(
                                rx.cond(State.show_password, rx.icon("eye_off"), rx.icon("eye")),
                                on_click=State.toggle_show_password,
                                variant="ghost",
                                size="3",
                            ),
                            width="100%",
                            spacing="2",
                        ),
                        col_span="2",
                    ),
                    confirmar_field,
                    rx.vstack(
                        rx.text("Tipo de Identificación", font_weight="semibold", color=text_color),
                        rx.select(
                            ["Cédula", "Pasaporte", "Tarjeta de Identidad"],
                            placeholder="Selecciona",
                            value=State.tipo_identificacion,
                            on_change=State.set_tipo_identificacion,
                            border_radius="md",
                            **input_style,
                        ),
                    ),
                    rx.vstack(
                        label_requerido("Número de Identificación"),
                        rx.hstack(
                            rx.input(
                                placeholder="Número de Identificación",
                                value=State.numero_identificacion,
                                on_change=State.set_and_validate_numero_identificacion,
                                border_radius="md",
                                **input_style,
                            ),
                            rx.cond(
                                State.numero_identificacion_valid,
                                rx.image(src="/check-green.svg", height="16px", ml="2"),
                                rx.box(),
                            ),
                        ),
                    ),
                    rx.vstack(
                        label_requerido("Nombres"),
                        rx.hstack(
                            rx.input(
                                placeholder="Nombres",
                                value=State.nombres,
                                on_change=State.set_and_validate_nombres,
                                border_radius="md",
                                **input_style,
                            ),
                            rx.cond(
                                State.nombres_valid,
                                rx.image(src="/check-green.svg", height="16px", ml="2"),
                                rx.box(),
                            ),
                        ),
                    ),
                    rx.vstack(
                        label_requerido("Apellidos"),
                        rx.hstack(
                            rx.input(
                                placeholder="Apellidos",
                                value=State.apellidos,
                                on_change=State.set_and_validate_apellidos,
                                border_radius="md",
                                **input_style,
                            ),
                            rx.cond(
                                State.apellidos_valid,
                                rx.image(src="/check-green.svg", height="16px", ml="2"),
                                rx.box(),
                            ),
                        ),
                    ),
                    rx.vstack(
                        rx.text("Sexo", color=text_color),
                        rx.select(
                            ["Femenino", "Masculino", "Prefiero no decirlo"],
                            placeholder="Selecciona",
                            value=State.sexo,
                            on_change=State.set_sexo,
                            border_radius="md",
                            **input_style,
                        ),
                    ),
                    rx.vstack(
                        rx.text("Teléfono", color=text_color),
                        rx.hstack(
                            rx.input(
                                placeholder="Teléfono",
                                value=State.telefono,
                                on_change=State.set_and_validate_telefono,
                                border_radius="md",
                                **input_style,
                            ),
                            rx.cond(
                                State.telefono_valid,
                                rx.image(src="/check-green.svg", height="16px", ml="2"),
                                rx.box(),
                            ),
                        ),
                    ),
                    rx.vstack(
                        rx.text("Departamento", color=text_color),
                        rx.select(
                            [
                                "Amazonas",
                                "Antioquia",
                                "Arauca",
                                "Atlántico",
                                "Bolívar",
                                "Boyacá",
                                "Caldas",
                                "Caquetá",
                                "Casanare",
                                "Cauca",
                                "Cesar",
                                "Chocó",
                                "Córdoba",
                                "Cundinamarca",
                                "Guainía",
                                "Guaviare",
                                "Huila",
                                "La Guajira",
                                "Magdalena",
                                "Meta",
                                "Nariño",
                                "Norte de Santander",
                                "Putumayo",
                                "Quindío",
                                "Risaralda",
                                "Santander",
                                "Sucre",
                                "Tolima",
                                "Valle del Cauca",
                                "Vaupés",
                                "Vichada",
                                
                            ],
                            placeholder="Selecciona",
                            value=State.departamento,
                            on_change=State.set_and_validate_departamento,
                            border_radius="md",
                            **input_style,
                        ),
                    ),
                    rx.vstack(
                        rx.text("Ciudad", color=text_color),
                        rx.select(
                            State.ciudades_disponibles,
                            placeholder="Selecciona una ciudad",
                            value=State.ciudad,
                            on_change=State.set_and_validate_ciudad,
                            border_radius="md",
                            is_disabled=State.departamento == "",
                            **input_style,
                        ),
                    ),
                    rx.box(
                        rx.vstack(
                            label_requerido("Dirección"),
                            rx.input(
                                placeholder="Dirección",
                                value=State.direccion,
                                on_change=State.set_direccion,
                                border_radius="md",
                                **input_style,
                            ),
                        ),
                        grid_column="1 / -1",
                    ),
                    template_columns={"base": "1fr", "md": "repeat(3, 1fr)"},
                    gap="4",
                    width="100%",
                ),
                rx.grid(
                    rx.vstack(
                        rx.text("Etnia", color=text_color),
                        rx.select(
                            [
                                "Ninguna",
                                "Indígena",
                                "Afrocolombiano",
                                "Raizal",
                                "Palenquero",
                                "Gitano/a",
                                "Otro",
                            ],
                            placeholder="Selecciona",
                            value=State.etnia,
                            on_change=State.set_etnia,
                            border_radius="md",
                            **input_style,
                        ),
                    ),
                    rx.vstack(
                        rx.text("Características del ciudadano", color=text_color),
                        rx.select(
                            [
                                "Ninguna",
                                "Habitante de la calle",
                                "No brinda información",
                                "Peligro Inminente",
                                "Periodistas en ejercicio de su actividad",
                                "Primera Infancia",
                                "Veteranos Fuerza Pública",
                                "Víctimas - Conflicto Armado",
                            ],
                            placeholder="Selecciona una característica",
                            value=State.persona_vulnerable_registro,
                            on_change=State.set_persona_vulnerable_registro,
                            border_radius="md",
                            **input_style,
                        ),
                    ),
                    template_columns={"base": "1fr", "md": "repeat(2, 1fr)"},
                    gap="4",
                    width="100%",
                ),
                rx.vstack(
                    rx.checkbox(
                        "Acepto recibir notificaciones por correo",
                        is_checked=State.acepta_notificaciones,
                        on_change=State.set_acepta_notificaciones,
                        color=text_color,
                    ),
                    rx.checkbox(
                        rx.hstack(
                            rx.link(
                                "He leído y acepto la Política de Protección de Datos",
                                href="/politica-privacidad",
                                color="blue.500",
                            ),
                            rx.text("(Al aceptarla se mostrará un aviso)", color=rx.color_mode_cond(light="gray.500", dark="gray.400"), font_size="xs")
                        ),
                        is_checked=State.acepta_politica_datos,
                        on_change=State.preconfirmar_politica,
                        color=text_color,
                    ),
                    spacing="3",
                    padding_top="4",
                    align_items="start",
                    width="100%",
                ),
                rx.cond(
                    State.modal_politica_visible,
                    rx.box(
                        rx.box(
                            rx.heading("Confirmación de Política de Privacidad", size="4", color=rx.color_mode_cond(light="black", dark="white")),
                            rx.text(
                                "Al aceptar la Política de Protección de Datos, confirmas que has leído y comprendido el uso de tus datos personales.",
                                color=rx.color_mode_cond(light="gray.700", dark="gray.300"),
                                font_size="sm"
                            ),
                            rx.text(
                                "La aceptación es necesaria para continuar con el registro.",
                                color=rx.color_mode_cond(light="gray.600", dark="gray.400"),
                                font_size="sm"
                            ),
                            rx.hstack(
                                rx.button("Aceptar", on_click=State.confirmar_politica, color_scheme="blue"),
                                rx.button("Cancelar", on_click=State.cancelar_politica, variant="outline"),
                                spacing="3"
                            ),
                            spacing="4",
                            p="6",
                            bg=rx.color_mode_cond(light="white", dark="#1a202c"),
                            border_radius="2xl",
                            border="2px solid #2563eb",
                            box_shadow="0 20px 60px rgba(0, 0, 0, 0.3), 0 0 40px rgba(37, 99, 235, 0.2)",
                            width="100%",
                            max_width="520px"
                        ),
                        position="fixed",
                        inset="0",
                        bg="rgba(0,0,0,0.45)",
                        display="flex",
                        align_items="center",
                        justify_content="center",
                        z_index="1000",
                        p="6"
                    )
                ),
                rx.cond(
                    State.error_de_registro != "",
                    rx.text(State.error_de_registro, color="red.500", font_size="sm", font_weight="bold"),
                    rx.box(),
                ),
                rx.cond(
                    State.succes != "",
                    rx.text(State.succes, color="green.500", font_size="sm", font_weight="bold"),
                    rx.box(),
                ),
                rx.hstack(
                    rx.button(title, type="submit", color_scheme="blue", size="4", width={"base": "100%", "md": "220px"}),
                    rx.link(
                        "¿Ya tienes una cuenta? Inicia sesión",
                        href="/login",
                        margin_left={"base": "0", "md": "4"},
                        color="blue.500",
                        width={"base": "100%", "md": "auto"},
                    ),
                    spacing="4",
                    justify={"base": "center", "md": "start"},
                    width="100%",
                ),
                spacing="4",
                align_items="stretch",
                width="100%",
            ),
            on_submit=on_submit,
        ),
        p={"base": "4", "md": "8"},
        max_width={"base": "95%", "md": "1100px"},
        box_shadow="2xl",
        border_radius="2xl",
        bg=rx.color_mode_cond(light="white", dark="#1a202c"),
        width="100%",
    )


def navbar() -> rx.Component:
    return rx.box(
        rx.hstack(
            # Agrupamos los links a la izquierda o centro
            rx.hstack(
                rx.cond(
                    State.es_autentica & (State.rol_usuario == "funcionario"),
                    rx.box(),
                    rx.hstack(
                        rx.link("Inicio", href="/", color="white", font_weight="bold", _hover={"opacity": 0.8}),
                        rx.link("Nueva Solicitud", href="/solicitudes", color="white", font_weight="bold", _hover={"opacity": 0.8}),
                        rx.link("Registro de Ciudadano", href="/registro", color="white", font_weight="bold", _hover={"opacity": 0.8}),
                        spacing="6",
                    )
                ),
                rx.cond(
                    State.es_autentica & (State.rol_usuario == "funcionario"),
                    rx.link("Reportes", href="/reportes", color="white", font_weight="bold", _hover={"opacity": 0.8})
                ),
                rx.text("", display="none"),
                rx.cond(
                    State.es_autentica & (State.rol_usuario == "funcionario"),
                    rx.link("Ver Usuarios", href="/usuarios", color="white", font_weight="bold", _hover={"opacity": 0.8}),
                    rx.text("", display="none")
                ),
                rx.cond(
                    State.es_autentica & (State.rol_usuario == "funcionario"),
                    rx.link("Cambiar Rol", href="/cambiar-rol", color="white", font_weight="bold", _hover={"opacity": 0.8}),
                    rx.text("", display="none")
                ),
                rx.cond(
                    State.es_autentica,
                    rx.cond(
                        State.rol_usuario == "funcionario",
                        rx.link("Dashboard Funcionario", href="/dashboard-funcionario", color="white", font_weight="bold", _hover={"opacity": 0.8}),
                        rx.link("Dashboard", href="/dashboard", color="white", font_weight="bold", _hover={"opacity": 0.8})
                    ),
                    rx.link("Dashboard", href="/dashboard", color="white", font_weight="bold", _hover={"opacity": 0.8})
                ),
                spacing="6", # Espacio entre links
            ),
            # Cerrar sesión solo si hay sesión activa y toggle de modo
            rx.hstack(
                rx.color_mode.button(),
                rx.cond(
                    State.es_autentica,
                    rx.button(
                        "Cerrar Sesión", 
                        on_click=State.logout, 
                        color_scheme="red", 
                        variant="solid"
                    ),
                    rx.text("", display="none")
                ),
                spacing="2",
                align_items="center"
            ),
            justify="between", # Separa los links del botón de cerrar sesión
            align_items="center",
            width="100%",
            max_width="none",
            margin="0",
        ),
        bg=rx.color_mode_cond(light="#1e40af", dark="#1e3a8a"),
        padding_y="1em",
        padding_x="2em",
        width="100%",
        style={"margin": "0", "padding": "1em 2em"}
    )


def access_denied_widget(message: str) -> rx.Component:
    return rx.vstack(
        rx.heading("Acceso Denegado", size="8", color="red.500"),
        rx.text(message, color="gray.600"),
        rx.cond(
            State.es_autentica,
            rx.vstack(
                rx.button("Cerrar Sesión", on_click=State.logout, color_scheme="red", width="100%"),
                rx.link(rx.button("Volver al inicio", color_scheme="blue"), href="/"),
                spacing="4",
                align_items="center"
            ),
            rx.link(rx.button("Ir al Login", color_scheme="blue"), href="/login"),
        ),
        spacing="4",
        align_items="center"
    )


def utility_bar() -> rx.Component:
    return rx.hstack(
        rx.link("GOV.CO", href="/", font_weight="bold", color="white", text_decoration="none"),
        rx.spacer(),
        rx.hstack(
            rx.link("Opciones de Accesibilidad", href="#", font_size="sm", color="white", text_decoration="none"),
            rx.text("|", color="white"),
            rx.link("Inicia sesión", href="/login", font_size="sm", color="white", text_decoration="none"),
            rx.text("|", color="white"),
            rx.link("Regístrate", href="/registro", font_size="sm", color="white", text_decoration="none"),
            spacing="4",
            align_items="center"
        ),
        width="100%",
        padding_x="16px",
        padding_y="3",
        bg=rx.color_mode_cond(light="#0f172a", dark="#020617"),
        border_bottom="1px solid rgba(255,255,255,0.08)",
        style={"margin": "0", "padding": "0.75rem 16px"}
    )
def toast_notification() -> rx.Component:
    return rx.cond(
        State.toast_visible,
        rx.box(
            rx.hstack(
                rx.box(
                    rx.cond(
                        State.toast_tipo == "success",
                        rx.icon("circle-check", size=22, color="white"),
                        rx.icon("circle-x", size=22, color="white"),
                    ),
                    display="flex",
                    align_items="center",
                    justify_content="center",
                    width="36px",
                    height="36px",
                    border_radius="full",
                    bg=rx.cond(State.toast_tipo == "success", "rgba(255,255,255,0.25)", "rgba(255,255,255,0.25)"),
                    flex_shrink="0",
                ),
                rx.vstack(
                    rx.text(
                        rx.cond(State.toast_tipo == "success", "¡Éxito!", "Error"),
                        font_weight="bold",
                        color="white",
                        font_size="sm",
                        line_height="1.1",
                    ),
                    rx.text(
                        State.toast_mensaje,
                        color="rgba(255,255,255,0.95)",
                        font_size="xs",
                        line_height="1.3",
                    ),
                    spacing="1",
                    align_items="start",
                ),
                rx.spacer(),
                rx.button(
                    rx.icon("x", size=16, color="white"),
                    on_click=State.ocultar_toast,
                    variant="ghost",
                    size="1",
                    _hover={"bg": "rgba(255,255,255,0.15)"},
                    padding="0",
                    min_width="24px",
                    height="24px",
                ),
                spacing="3",
                align_items="center",
                width="100%",
            ),
            position="fixed",
            top="50%",
            left="50%",
            transform="translate(-50%, -50%)",
            z_index="9999",
            min_width="200px",
            max_width="280px",
            padding="10px 12px",
            border_radius="18px",
            bg=rx.cond(
                State.toast_tipo == "success",
                "linear-gradient(135deg, #16a34a, #15803d)",
                "linear-gradient(135deg, #dc2626, #b91c1c)",
            ),
            box_shadow="0 8px 32px rgba(0,0,0,0.22), 0 2px 8px rgba(0,0,0,0.12)",
            style={
                "animation": "slideInToast 0.35s cubic-bezier(0.34, 1.56, 0.64, 1)",
                "@keyframes slideInToast": {
                    "from": {"opacity": "0", "transform": "translateY(24px) scale(0.95)"},
                    "to": {"opacity": "1", "transform": "translateY(0) scale(1)"},
                }
            }
        ),
        rx.box()
    )

def index() -> rx.Component:
    hero_text = rx.color_mode_cond(light="rgba(15, 23, 42, 0.96)", dark="white")
    hero_sub = rx.color_mode_cond(light="rgba(15, 23, 42, 0.72)", dark="rgba(255,255,255,0.75)")
    card_bg = rx.color_mode_cond(light="white", dark="#111827")
    section_bg = rx.color_mode_cond(light="#f8fafc", dark="#020617")
    body_bg = rx.color_mode_cond(light="#f1f5f9", dark="#020617")

    return rx.box(
        utility_bar(),
        navbar(),
        rx.box(
            rx.hstack(
                rx.vstack(
                    rx.text("Plataforma oficial de atención ciudadana", color="white", font_size="sm", bg="#2563eb", padding_x="3", padding_y="2", border_radius="full", mb="4"),
                    rx.heading("Atención PQRS - Enlace 1755", size="8", color=hero_text, line_height="1.1"),
                    rx.text(
                        "Radica, consulta y gestiona tus Peticiones, Quejas, Reclamos y Sugerencias de forma clara, rápida y segura.",
                        color=hero_sub,
                        font_size="lg",
                        max_width="680px"
                    ),
                    rx.hstack(
                        rx.link(rx.button("Radicar PQRS", color_scheme="blue", size="4", width="200px"), href="/solicitudes"),
                        rx.link(rx.button("Consultar Estado",color_scheme="blue", size="4", width="200px"), href="/consultar-estado"),
                        spacing="4",
                        flex_wrap="wrap"
                    ),
                    spacing="6",
                    align_items="start",
                    width="100%",
                    max_width="720px"
                ),
                rx.card(
                    rx.vstack(
                        rx.heading("Accesos rápidos", size="5", color="#000000"),
                        rx.link(rx.button("Registrarme", color_scheme="blue", width="100%"), href="/registro"),
                        rx.link(rx.button("Iniciar sesión", variant="solid", color_scheme="gray", width="100%"), href="/login"),
                        rx.link(rx.button("Nueva solicitud", variant="outline", color_scheme="gray", width="100%"), href="/solicitudes"),
                        rx.text("Disponible para ciudadanos que deseen registrar y hacer seguimiento a sus solicitudes.", color="rgba(255,255,255,0.8)", font_size="sm"),
                        spacing="4",
                        align_items="stretch"
                    ),
                    p="6",
                    bg="rgba(255,255,255,0.08)",
                    border="1px solid rgba(255,255,255,0.15)",
                    border_radius="2xl",
                    width="100%",
                    max_width="340px"
                ),
                spacing="8",
                align_items="center",
                justify="between",
                flex_wrap="wrap"
            ),
            padding_y="20",
            padding_x="6",
            width="100%",
            style={"margin": "0 auto", "padding": "20px 6"}
        ),
        rx.box(
            rx.hstack(
                rx.vstack(
                    rx.text("Plataforma oficial de atención ciudadana", color="white", font_size="sm", bg="#2563eb", padding_x="3", padding_y="2", border_radius="full", mb="4"),
                    rx.heading("Atención PQRS - Enlace 1755", size="8", color="white", line_height="1.1"),
                    rx.text(
                        "Radica, consulta y gestiona tus Peticiones, Quejas, Reclamos y Sugerencias de forma clara, rápida y segura.",
                        color="rgba(255,255,255,0.85)",
                        font_size="lg",
                        max_width="680px"
                    ),
                    rx.hstack(
                        rx.link(rx.button("Radicar PQRS", color_scheme="blue", size="4", width="200px"), href="/solicitudes"),
                        rx.link(rx.button("Consultar Estado",color_scheme="blue", size="4", width="200px"), href="/consultar-estado"),
                        spacing="4",
                        flex_wrap="wrap"
                    ),
                    spacing="6",
                    align_items="start",
                    width="100%",
                    max_width="720px"
                ),
                rx.card(
                    rx.vstack(
                        rx.heading("Accesos rápidos", size="5", color="#000000"),
                        rx.link(rx.button("Registrarme", color_scheme="blue", width="100%"), href="/registro"),
                        rx.link(rx.button("Iniciar sesión", variant="solid", color_scheme="gray", width="100%"), href="/login"),
                        rx.link(rx.button("Nueva solicitud", variant="outline", color_scheme="gray", width="100%"), href="/solicitudes"),
                        rx.text("Disponible para ciudadanos que deseen registrar y hacer seguimiento a sus solicitudes.", color="rgba(255,255,255,0.8)", font_size="sm"),
                        spacing="4",
                        align_items="stretch"
                    ),
                    p="6",
                    bg="rgba(255,255,255,0.08)",
                    border="1px solid rgba(255,255,255,0.15)",
                    border_radius="2xl",
                    width="100%",
                    max_width="340px"
                ),
                spacing="8",
                align_items="center",
                justify="between",
                flex_wrap="wrap"
            ),
            width="100%",
            style={
                "backgroundImage": "linear-gradient(90deg, rgba(15,23,42,0.84), rgba(15,23,42,0.30)), url('/Gemini_Generated_Image_ouyornouyornouyo.png')",
                "backgroundSize": "cover",
                "backgroundPosition": "center",
                "backgroundRepeat": "no-repeat",
                "margin": "0",
                "padding": "20px 6"
            }
        ),

        rx.box(
            rx.vstack(
                rx.vstack(
                    rx.heading("¿Qué deseas hacer hoy?", size="7", color="#0f172a"),
                    rx.text("Accede rápidamente a los servicios principales del sistema.", color="#475569", font_size="md"),
                    spacing="3",
                    align_items="center"
                ),
                rx.hstack(
                    quick_action_card("Radicar PQRS", "Crea una nueva petición, queja, reclamo o sugerencia.", "Ir al formulario", "/solicitudes", "blue"),
                    quick_action_card("Consultar estado", "Revisa el avance y respuesta de tus solicitudes.", "Consultar", "/consultar-estado", "cyan"),
                    quick_action_card("Registro ciudadano", "Crea tu cuenta para gestionar trámites de forma segura.", "Registrarme", "/registro", "green"),
                    quick_action_card("Iniciar sesión", "Accede a tu cuenta y continúa tus gestiones.", "Entrar", "/login", "gray"),
                    spacing="5",
                    justify="center",
                    flex_wrap="wrap"
                ),
                spacing="9",
                align_items="center"
            ),
            padding_y="20",
            padding_x="6",
            width="100%",
            style={"margin": "0", "padding": "20px 6"}
        ),

        rx.box(
            rx.vstack(
                rx.heading("Atención clara y transparente para la ciudadanía", size="7", color="#0f172a"),
                rx.text("Este portal facilita la recepción, gestión y seguimiento de solicitudes ciudadanas de manera organizada y accesible.", color="#64748b", font_size="md", text_align="center", max_width="850px"),
                spacing="4",
                align_items="center"
            ),
            rx.hstack(
                info_card("Canal seguro", "Tus datos y solicitudes se gestionan en un entorno controlado."),
                info_card("Trazabilidad", "Cada solicitud puede registrarse y consultarse con mayor claridad."),
                info_card("Atención oportuna", "El sistema está pensado para mejorar tiempos y experiencia ciudadana."),
                spacing="5",
                justify="center",
                flex_wrap="wrap"
            ),
            spacing="9",
            align_items="center",
            width="100%",
            bg=section_bg,
            padding_y="20",
            style={"margin": "0", "padding": "20px 0"}
        ),

        rx.box(
            rx.vstack(
                rx.heading("¿Qué significa PQRS?", size="7", color="#0f172a"),
                rx.hstack(
                    pqrs_badge("Petición", "Solicitud respetuosa de información o actuación por parte de la entidad.", "#2563eb"),
                    pqrs_badge("Queja", "Manifestación de inconformidad por la conducta o atención recibida.", "#f59e0b"),
                    pqrs_badge("Reclamo", "Expresión de inconformidad por una prestación deficiente o incumplimiento.", "#ef4444"),
                    pqrs_badge("Sugerencia", "Propuesta o recomendación para mejorar la atención o el servicio.", "#10b981"),
                    spacing="5",
                    justify="center",
                    flex_wrap="wrap"
                ),
                spacing="8",
                align_items="center"
            ),
            padding_y="20",
            padding_x="6",
            width="100%",
            style={"margin": "0", "padding": "20px 6"}
        ),

        footer(),
        brand_footer(),
        bg=body_bg,
        width="100%",
        min_height="100vh",
        style={"margin": "0", "padding": "0", "boxSizing": "border-box"}
    )


def quick_action_card(title: str, desc: str, button_text: str, href: str, accent: str = "blue") -> rx.Component:
    card_bg = rx.color_mode_cond(light="white", dark="#111827")
    border = rx.color_mode_cond(light="1px solid #e2e8f0", dark="1px solid #334155")
    text_main = rx.color_mode_cond(light="#0f172a", dark="white")
    text_sec = rx.color_mode_cond(light="#475569", dark="#cbd5e1")

    return rx.card(
        rx.vstack(
            rx.heading(title, size="5", color=text_main),
            rx.text(desc, color=text_sec, font_size="sm"),
            rx.link(rx.button(button_text, color_scheme=accent, width="100%"), href=href),
            spacing="4",
            align_items="start",
            width="100%"
        ),
        bg=card_bg,
        border=border,
        border_radius="2xl",
        p="6",
        width="100%",
        max_width="260px",
        box_shadow="lg"
    )


def info_card(title: str, desc: str) -> rx.Component:
    card_bg = rx.color_mode_cond(light="white", dark="#111827")
    border = rx.color_mode_cond(light="1px solid #e2e8f0", dark="1px solid #334155")
    text_main = rx.color_mode_cond(light="#0f172a", dark="white")
    text_sec = rx.color_mode_cond(light="#475569", dark="#cbd5e1")

    return rx.card(
        rx.vstack(
            rx.text(title, font_weight="bold", color=text_main, font_size="md"),
            rx.text(desc, color=text_sec, font_size="sm"),
            spacing="3",
            align_items="start"
        ),
        bg=card_bg,
        border=border,
        border_radius="xl",
        p="5",
        width="100%",
        max_width="360px",
        box_shadow="sm"
    )


def pqrs_badge(title: str, desc: str, color: str) -> rx.Component:
    card_bg = rx.color_mode_cond(light="white", dark="#111827")
    border = rx.color_mode_cond(light="1px solid #e2e8f0", dark="1px solid #334155")
    text_sec = rx.color_mode_cond(light="#475569", dark="#cbd5e1")

    return rx.card(
        rx.vstack(
            rx.box(
                rx.text(title, color="white", font_weight="bold", font_size="sm"),
                bg=color,
                padding_x="3",
                padding_y="2",
                border_radius="full"
            ),
            rx.text(desc, color=text_sec, font_size="sm"),
            spacing="3",
            align_items="start"
        ),
        bg=card_bg,
        border=border,
        border_radius="xl",
        p="5",
        width="100%",
        max_width="360px",
        box_shadow="sm"
    )


def footer() -> rx.Component:
    header_color = rx.color_mode_cond(light="black", dark="white")
    text_color = rx.color_mode_cond(light="gray.700", dark="gray.400")
    link_color = rx.color_mode_cond(light="blue.600", dark="blue.300")
    bg_footer = rx.color_mode_cond(light="#f7fafc", dark="#111827")
    border_color = rx.color_mode_cond(light="1px solid #e2e8f0", dark="1px solid #2d3748")

    return rx.container(
        rx.hstack(
            # Columna 1: Información de la Entidad
            rx.vstack(
                rx.heading("Información de la Entidad", size="6", color=header_color),
                rx.text("Sede Principal: Calle 10 # 5-20, Cali, Valle del Cauca", color=text_color),
                rx.text("Código Postal: 760001", color=text_color),
                rx.text("PBX: (+57) 602 XXX XXXX", color=text_color),
                rx.link(
                    "Correo institucional: atencionalciudadano@empresa.gov.co", 
                    href="mailto:atencionalciudadano@empresa.gov.co",
                    color=link_color
                ),
                rx.link(
                    "Sitio web principal: www.empresa.gov.co", 
                    href="http://www.empresa.gov.co", 
                    target="_blank",
                    color=link_color
                ),
                rx.text(
                    "Horario de atención presencial: Lunes a Viernes, 7:30 a.m. - 12:00 p.m. y 2:00 p.m. - 5:30 p.m.",
                    color=text_color
                ),
                align_items="start",
            ),
            # Columna 2: Servicio al Ciudadano
            rx.vstack(
                rx.heading("Servicio al Ciudadano", size="6", color=header_color),
                rx.link("Radicar solicitud PQRS (HU4)", href="/solicitudes", color=link_color),
                rx.link("Consultar estado de solicitud (HU11)", href="/consultar-estado", color=link_color),
                rx.link("Preguntas Frecuentes (FAQ)", href="/faq", color=link_color),
                rx.link("Tiempos de respuesta (Ley 1755 de 2015)", href="/tiempos-respuesta", color=link_color),
                rx.link("Notificaciones por aviso y judiciales", href="/notificaciones", color=link_color),
                rx.link("Política de privacidad y protección de datos", href="/politica-privacidad", color=link_color),
                rx.link("Manual de usuario (Enlace 1755)", href="/manual-1755", color=link_color),
                align_items="start",
            ),
            # Columna 3: Contacto Directo y Redes
            rx.vstack(
                rx.heading("Contacto Directo y Redes", size="6", color=header_color),
                rx.text("Recepción de correspondencia física: Lunes a viernes, 8:00 a.m. a 4:00 p.m.", color=text_color),
                rx.text("Línea gratuita nacional: 01 8000 91XXXX", color=text_color),
                rx.hstack(
                    rx.link("Facebook", href="https://facebook.com", target="_blank", color=link_color),
                    rx.link("X/Twitter", href="https://twitter.com", target="_blank", color=link_color),
                    rx.link("YouTube", href="https://youtube.com", target="_blank", color=link_color),
                    rx.link("LinkedIn", href="https://linkedin.com", target="_blank", color=link_color),
                    spacing="4"
                ),
                rx.text("Sistema gestionado por: Enlace 1755 (Versión 1.0)", font_size="sm", color=text_color),
                align_items="start",
            ),
            spacing="9",
            align_items="start"
        ),
        width="100%",
        padding_top="24px",
        padding_bottom="24px",
        bg=bg_footer,
        border_top=border_color,
        justify="center"
    )


def brand_footer() -> rx.Component:
    """Franja inferior con logos institucionales (Universidad del Valle y GOV.CO)."""
    return rx.container(
        rx.hstack(
            rx.image(src="/unival_logo.svg", alt="Universidad del Valle", height="48px"),
            rx.spacer(),
            rx.image(src="/govco_logo.svg", alt="Gobierno de Colombia", height="48px"),
            spacing="6",
            align_items="center",
            justify="center"
        ),
        width="100%",
        padding_top="12px",
        padding_bottom="12px",
        bg="white",
        _dark={"bg": "gray.900", "borderColor": "gray.700"},
        border_top="1px solid #e2e8f0"
    )

def registro_page() -> rx.Component:
    return rx.container(
        toast_notification(),
        navbar(),
        rx.center(
            # Llamamos a auth_card con la función de signup y pidiendo confirmación
            auth_card("Registrarme como Ciudadano", State.signup, show_confirm=True),
            size="3"
        ),
        bg=rx.color_mode_cond(light="#f8fafc", dark="#0f172a")
    )


def registro_funcionario_page() -> rx.Component:
    return rx.cond(
        State.es_autentica & (State.rol_usuario == "funcionario"),
        rx.container(
            navbar(),
            rx.center(
                auth_card("Registrar Funcionario", State.signup_funcionario, show_confirm=True),
                size="3"
            ),
            bg=rx.color_mode_cond(light="#f8fafc", dark="#0f172a")
        ),
        rx.container(
            navbar(),
            rx.center(
                access_denied_widget("Solo los funcionarios autenticados pueden registrar nuevos funcionarios."),
                size="3"
            ),
            bg=rx.color_mode_cond(light="#f8fafc", dark="#0f172a")
        )
    )


def change_password_page() -> rx.Component:
    return rx.container(
        navbar(),
        rx.center(
            rx.card(
                rx.vstack(
                    rx.heading("Cambiar Contraseña", size={"base": "5", "md": "7"}, color=rx.color_mode_cond(light="black", dark="white")),
                    rx.input(placeholder="Contraseña actual", type="password", value=State.current_password, on_change=State.set_current_password, width="100%"),
                    rx.input(placeholder="Nueva contraseña", type="password", value=State.new_password, on_change=State.set_new_password, width="100%"),
                    rx.input(placeholder="Confirmar nueva contraseña", type="password", value=State.confirm_new_password, on_change=State.set_confirm_new_password, width="100%"),
                    rx.button("Cambiar contraseña", on_click=State.change_password, color_scheme="blue", width="100%"),
                    rx.text(State.change_pw_message, color="green.500", font_size="sm")
                ),
                p={"base": "4", "md": "8"},
                max_width={"base": "90%", "md": "560px"},
                width="100%",
            ),
            size="3"
        ),
        bg=rx.color_mode_cond(light="#f8fafc", dark="#0f172a")
    )

def login_page() -> rx.Component:
    return rx.vstack(
        toast_notification(),
        rx.toast.provider(position="top-center", close_button=True, offset="20px"),
        rx.center(
            rx.card(
                rx.vstack(
                    rx.heading(
                        "Iniciar Sesión",
                        size={"base": "5", "md": "7"},
                        margin_bottom="1em",
                        color=rx.color_mode_cond(light="black", dark="white"),
                    ),
                    rx.input(
                        placeholder="Correo electrónico",
                        value=State.correo,
                        on_change=State.set_correo,
                        width="100%",
                    ),
                    rx.hstack(
                        rx.input(
                            placeholder="Contraseña",
                            type=rx.cond(State.show_password, "text", "password"),
                            value=State.contraseña,
                            on_change=State.set_contraseña,
                            width="100%",
                        ),
                        rx.button(
                            rx.cond(State.show_password, rx.icon("eye_off"), rx.icon("eye")),
                            on_click=State.toggle_show_password,
                            variant="ghost",
                            size="2",
                        ),
                        width="100%",
                        spacing="2",
                    ),
                    rx.cond(
                        State.error_de_contraseña != "",
                        rx.text(State.error_de_contraseña, color="red.500", font_size="1em", font_weight="bold", padding="8px", bg="rgba(239, 68, 68, 0.1)", border_radius="md"),
                        rx.box(),
                    ),
                    rx.button(
                        "Entrar",
                        on_click=State.login,
                        color_scheme="blue",
                        width="100%",
                        margin_top="1em",
                    ),
                    rx.link(
                        "¿No tienes cuenta? Regístrate",
                        href="/registro",
                        font_size="0.8em",
                        color="#60a5fa",
                    ),
                    spacing="4",
                    padding={"base": "1em", "md": "1.5em"},
                ),
                width={"base": "90%", "md": "750px"},
                max_width="95%",
                box_shadow="lg",
                border_radius="15px",
            ),
            width="100%",
            min_height="85vh",
        ),
        bg=rx.color_mode_cond(light="#f4f4f5", dark="#0f172a"),
        width="100%",
        min_height="100vh",
    )


def politica_privacidad_page() -> rx.Component:
    return rx.container(
        navbar(),
        rx.center(
            rx.box(
                rx.vstack(
                    rx.heading("Política de Privacidad y Protección de Datos", size="6", color=rx.color_mode_cond(light="black", dark="white")),
                    rx.text(
                        "En esta plataforma tratamos tus datos con responsabilidad, transparencia y seguridad. "
                        "Tu información personal se usa únicamente para gestionar solicitudes PQRS y mejorar el servicio.",
                        color=rx.color_mode_cond(light="gray.700", dark="gray.300"),
                        font_size="md"
                    ),
                    rx.text(
                        "Al enviar una solicitud aceptas la Política de Tratamiento de Datos Personales y los términos de uso de la plataforma.",
                        color=rx.color_mode_cond(light="gray.700", dark="gray.300"),
                        font_size="md"
                    ),
                    rx.heading("Datos recolectados", size="7", color=rx.color_mode_cond(light="black", dark="white")),
                    rx.text(
                        "Correo electrónico, identificación, nombre, apellidos, teléfono y datos de ubicación para poder gestionar la solicitud.",
                        color=rx.color_mode_cond(light="gray.700", dark="gray.300")
                    ),
                    rx.heading("Finalidad", size="7", color=rx.color_mode_cond(light="black", dark="white")),
                    rx.text(
                        "Usar tus datos para contactar al ciudadano, radicar la solicitud en el sistema y generar trazabilidad de atención.",
                        color=rx.color_mode_cond(light="gray.700", dark="gray.300")
                    ),
                    rx.heading("Derechos", size="7", color=rx.color_mode_cond(light="black", dark="white")),
                    rx.text("Puedes solicitar corrección o eliminación de tus datos conforme a la normativa vigente de protección de datos personales.", color=rx.color_mode_cond(light="gray.700", dark="gray.300")),
                    rx.link("Volver al inicio", href="/", color_scheme="blue", font_weight="bold"),
                    spacing="4",
                    align_items="flex-start"
                ),
                p="8",
                max_width="840px",
                border_radius="2xl",
                bg=rx.color_mode_cond(light="white", dark="gray.800")
            ),
            size="3"
        )
    )

def dashboard() -> rx.Component:
    return rx.cond(
        State.es_autentica & (State.rol_usuario == "ciudadano"),
        rx.box(
            navbar(),
            rx.center(
                rx.vstack(
                    rx.heading(
                        "Panel de Ciudadano",
                        size="6",
                        color=rx.color_mode_cond(light="black", dark="white")
                    ),
                    rx.text(
                        "¡Bienvenido! Aquí podrás gestionar tus Peticiones, Quejas, Reclamos y Sugerencias.",
                        color=rx.color_mode_cond(light="gray.600", dark="gray.300"),
                        font_size="sm"
                    ),
                    rx.vstack(
                        rx.heading(
                            "Mis Solicitudes",
                            size="5",
                            color=rx.color_mode_cond(light="black", dark="white")
                        ),
                        rx.cond(
                            State.solicitudes,
                            rx.vstack(
                                rx.foreach(
                                    State.solicitudes,
                                    lambda solicitud: rx.box(
                                        rx.vstack(
                                            rx.hstack(
                                                rx.badge(
                                                    solicitud["tipo_solicitud"],
                                                    color_scheme=rx.cond(
                                                        solicitud["tipo_solicitud"] == "Petición", "blue",
                                                        rx.cond(solicitud["tipo_solicitud"] == "Queja", "orange",
                                                        rx.cond(solicitud["tipo_solicitud"] == "Reclamo", "red", "green"))
                                                    )
                                                ),
                                                rx.badge(
                                                    solicitud["estado"],
                                                    color_scheme=rx.cond(
                                                        solicitud["estado"] == "Radicada", "blue",
                                                        rx.cond(solicitud["estado"] == "Actualizada", "orange", "green")
                                                    )
                                                ),
                                                rx.spacer(),
                                                rx.text(
                                                    solicitud["fecha"],
                                                    font_size="xs",
                                                    color="gray.400"
                                                ),
                                            ),
                                            rx.text(
                                                solicitud["radicado"],
                                                font_size="xs",
                                                color="gray.400",
                                                font_family="monospace",
                                                style={"wordBreak": "break-all"}
                                            ),
                                            rx.text(
                                                solicitud["asunto"],
                                                font_weight="semibold",
                                                font_size="sm",
                                                color=rx.color_mode_cond(light="gray.800", dark="white")
                                            ),
                                            rx.text(
                                             solicitud["descripcion"],
                                             font_size="sm",
                                              color=rx.color_mode_cond(light="gray.600", dark="gray.300"),
                                              style={
                                              "display": "-webkit-box",
                                              "WebkitLineClamp": "3",
                                              "WebkitBoxOrient": "vertical",
                                              "overflow": "hidden",
                                              "wordBreak": "break-word",   # <-- corta palabras largas
                                              "overflowWrap": "anywhere",  # <-- maneja URLs y texto sin espacios
                                                }
                                            ),
                                            rx.cond(
                                                solicitud.get("documento_basename"),
                                                rx.hstack(
                                                    rx.icon("paperclip", size=13, color="blue.400"),
                                                    rx.link(
                                                        solicitud["documento_basename"],
                                                        href=solicitud.get("documento_href", "#"),
                                                        color="blue.500",
                                                        font_size="xs",
                                                        target="_blank"
                                                    ),
                                                    spacing="1",
                                                    align_items="center"
                                                ),
                                                rx.box()
                                            ),
                                            spacing="2",
                                            align_items="start",
                                            width="100%"
                                        ),
                                        p="4",
                                        border="1px solid",
                                        border_color=rx.color_mode_cond(light="#e2e8f0", dark="#2d3748"),
                                        border_radius="lg",
                                        bg=rx.color_mode_cond(light="white", dark="#1e293b"),
                                        width="100%",
                                        _hover={
                                            "box_shadow": "sm",
                                            "border_color": "#3b82f6"
                                        }
                                    )
                                ),
                                spacing="3",
                                width="100%"
                            ),
                            rx.box(
                                rx.vstack(
                                    rx.icon("inbox", size=32, color="gray.300"),
                                    rx.text(
                                        "No tienes solicitudes registradas aún.",
                                        color="gray.400",
                                        font_size="sm",
                                        text_align="center"
                                    ),
                                    rx.link(
                                        rx.button(
                                            "Crear primera solicitud",
                                            color_scheme="blue",
                                            size="2"
                                        ),
                                        href="/solicitudes"
                                    ),
                                    spacing="3",
                                    align_items="center",
                                ),
                                p="8",
                                width="100%",
                                text_align="center"
                            )
                        ),
                        spacing="4",
                        width="100%"
                    ),
                    rx.button(
                        "Cerrar Sesión",
                        on_click=State.logout,
                        color_scheme="red",
                        size="2",
                        variant="soft",
                        width="100%"
                    ),
                    spacing="5",
                    align_items="stretch",
                    width="100%",
                    max_width="680px",
                    padding_x="4",
                    padding_y="8",
                ),
                width="100%",
                size="3",
                align_items="start",
                padding_top="6"
            ),
            bg=rx.color_mode_cond(light="#f8fafc", dark="#0f172a"),
            width="100%",
            min_height="100vh",
            style={"margin": "0", "padding": "0", "boxSizing": "border-box"}
        ),
        rx.container(
            navbar(),
            rx.center(
                access_denied_widget("Esta página es solo para ciudadanos."),
                size="3"
            )
        )
    )


def funcionario_dashboard() -> rx.Component:
    return rx.cond(
        State.es_autentica & (State.rol_usuario == "funcionario"),
        rx.container(
            navbar(),
            rx.center(
                rx.vstack(
                    rx.heading("Panel de Funcionario", size="6", color=rx.color_mode_cond(light="black", dark="white")),
                    rx.text("Bienvenido, funcionario. Esta es tu página principal donde puedes revisar todas las peticiones.", color=rx.color_mode_cond(light="gray.600", dark="gray.300"), font_size="sm"),
                    rx.text("Usa el menú superior para navegar: 'Nueva Solicitud' para crear peticiones, 'Registrar Funcionario' para añadir nuevos funcionarios.", color=rx.color_mode_cond(light="gray.500", dark="gray.400"), font_size="sm"), 
                    rx.hstack(
                        rx.box(
                            rx.vstack(
                                rx.text("Total de solicitudes", font_weight="semibold", color=rx.color_mode_cond(light="gray.600", dark="gray.300"), font_size="sm"),
                                rx.heading(State.numero_solicitudes, size="3", color=rx.color_mode_cond(light="black", dark="white"))
                            ),
                            p="6",
                            min_width="180px",
                            min_height="180px",
                            display="flex",
                            align_items="center",
                            justify_content="center",
                            text_align="center",
                            border_radius="full",
                            box_shadow="xl",
                            border=f"1px solid {rx.color_mode_cond(light='#bfdbfe', dark='#334155')}",
                            bg=rx.color_mode_cond(light="linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%)", dark="linear-gradient(135deg, #0f172a 0%, #1f2937 100%)")
                        ),
                        rx.box(
                            rx.vstack(
                                rx.text("Radicadas", font_weight="semibold", color=rx.color_mode_cond(light="gray.600", dark="gray.300"), font_size="sm"),
                                rx.heading(State.numero_solicitudes_radicadas, size="3", color=rx.color_mode_cond(light="black", dark="white"))
                            ),
                            p="6",
                            min_width="180px",
                            min_height="180px",
                            display="flex",
                            align_items="center",
                            justify_content="center",
                            text_align="center",
                            border_radius="full",
                            box_shadow="xl",
                            border=f"1px solid {rx.color_mode_cond(light='#fee2e2', dark='#334155')}",
                            bg=rx.color_mode_cond(light="linear-gradient(135deg, #fff1f2 0%, #fee2e2 100%)", dark="linear-gradient(135deg, #111827 0%, #1f2937 100%)")
                        ),
                        rx.box(
                            rx.vstack(
                                rx.text("Actualizadas", font_weight="semibold", color=rx.color_mode_cond(light="gray.600", dark="gray.300"), font_size="sm"),
                                rx.heading(State.numero_solicitudes_actualizadas, size="3", color=rx.color_mode_cond(light="black", dark="white"))
                            ),
                            p="6",
                            min_width="180px",
                            min_height="180px",
                            display="flex",
                            align_items="center",
                            justify_content="center",
                            text_align="center",
                            border_radius="full",
                            box_shadow="xl",
                            border=f"1px solid {rx.color_mode_cond(light='#d1fae5', dark='#334155')}",
                            bg=rx.color_mode_cond(light="linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%)", dark="linear-gradient(135deg, #0f172a 0%, #1e293b 100%)")
                        ),
                        rx.box(
                            rx.vstack(
                                rx.text("Cerradas", font_weight="semibold", color=rx.color_mode_cond(light="gray.600", dark="gray.300"), font_size="sm"),
                                rx.heading(State.numero_solicitudes_cerradas, size="3", color=rx.color_mode_cond(light="black", dark="white"))
                            ),
                            p="6",
                            min_width="180px",
                            min_height="180px",
                            display="flex",
                            align_items="center",
                            justify_content="center",
                            text_align="center",
                            border_radius="full",
                            box_shadow="xl",
                            border=f"1px solid {rx.color_mode_cond(light='#c7d2fe', dark='#334155')}",
                            bg=rx.color_mode_cond(light="linear-gradient(135deg, #eef2ff 0%, #c7d2fe 100%)", dark="linear-gradient(135deg, #0f172a 0%, #1f2937 100%)")
                        ),
                        spacing="6",
                        width="100%",
                        flex_wrap="wrap",
                        justify_content="center"
                    ),
                    rx.box(
                        rx.vstack(
                            rx.box(
                                rx.vstack(
                                    rx.hstack(
                                        rx.vstack(
                                            rx.text("Usuarios registrados", font_weight="semibold", color=rx.color_mode_cond(light="gray.500", dark="gray.300"), font_size="xs", letter_spacing="wider", text_transform="uppercase"),
                                            rx.heading(State.usuarios_registrados_count, size="3", color=rx.color_mode_cond(light="black", dark="white")),
                                        ),
                                        rx.text("Resumen del sistema", font_size="sm", color=rx.color_mode_cond(light="gray.500", dark="gray.400")),
                                        spacing="4",
                                        align_items="center",
                                        justify_content="space-between",
                                        width="100%"
                                    ),
                                    rx.text("Últimos usuarios cargados en el sistema", font_size="sm", color=rx.color_mode_cond(light="gray.600", dark="gray.400")),
                                    spacing="4"
                                ),
                                p="4",
                                bg=rx.color_mode_cond(light="#eef2ff", dark="#111827"),
                                border_radius="2xl"
                            ),
                            rx.vstack(
                                rx.foreach(
                                    State.usuarios_registrados[:5],
                                    lambda usuario: rx.hstack(
                                        rx.text(
                                            usuario["email"],
                                            font_size="sm",
                                            no_wrap=True,
                                            overflow="hidden",
                                            text_overflow="ellipsis",
                                            white_space="nowrap",
                                            flex="1",
                                            color=rx.color_mode_cond(light="gray.800", dark="white")
                                        ),
                                        rx.badge(usuario["rol"], color_scheme=rx.cond(usuario["rol"] == "funcionario", "blue", "gray"), variant="solid"),
                                        spacing="3",
                                        align_items="center",
                                        width="100%",
                                        p="3",
                                        border_radius="2xl",
                                        bg=rx.color_mode_cond(light="#f8fafc", dark="#111827"),
                                        border=rx.color_mode_cond(light="1px solid #e2e8f0", dark="1px solid #1f2937")
                                    )
                                ),
                                rx.cond(
                                    State.usuarios_registrados_count > 5,
                                    rx.text("Se muestran los 5 usuarios más recientes.", font_size="xs", color=rx.color_mode_cond(light="gray.500", dark="gray.400"), pt="2")
                                ),
                                width="100%",
                                spacing="2"
                            ),
                            rx.hstack(
                                rx.link("Ver todos los usuarios", href="/usuarios", color_scheme="blue", font_weight="bold"),
                                rx.text(f"Total: {State.usuarios_registrados_count}", font_size="xs", color=rx.color_mode_cond(light="gray.500", dark="gray.400")),
                                justify_content="space-between",
                                width="100%",
                                align_items="center"
                            ),
                            spacing="4"
                        ),
                        p="0",
                        border_radius="2xl",
                        box_shadow=rx.color_mode_cond(light="0 30px 80px rgba(15, 23, 42, 0.08)", dark="0 30px 80px rgba(15, 23, 42, 0.45)"),
                        border=rx.color_mode_cond(light="1px solid rgba(148, 163, 184, 0.16)", dark="1px solid rgba(148, 163, 184, 0.12)"),
                        bg=rx.color_mode_cond(light="#ffffff", dark="#0b1220"),
                        width="100%"
                    ),
                    # SendGrid Admin Card (solo visible para funcionarios)
                    rx.cond(
                        State.rol_usuario == "funcionario",
                        rx.box(
                            rx.vstack(
                                rx.heading("Configuración de correo (SendGrid)", size="5"),
                                rx.text("Agrega la API Key de SendGrid para habilitar envío de correos desde la app."),
                                rx.hstack(
                                    rx.input(
                                        placeholder="SendGrid API Key",
                                        value=State.sendgrid_key_input,
                                        on_change=State.set_sendgrid_key_input,
                                        width="100%",
                                    ),
                                    rx.button("Guardar", on_click=State.guardar_sendgrid_api_key, color_scheme="green"),
                                ),
                                rx.text(
                                    State.sendgrid_saved_message,
                                    color=rx.cond(
                                        State.sendgrid_saved_message == "Clave guardada correctamente.",
                                        "green",
                                        "red",
                                    ),
                                ),
                                spacing="3",
                            ),
                            p="4",
                            border="1px solid #cbd5e1",
                            border_radius="md",
                            bg=rx.color_mode_cond(light="#ffffff", dark="#0b1220"),
                            width="100%",
                            margin_bottom="1em",
                        ),
                    ),
                    # Barra de búsqueda y filtros
                    rx.box(
                        rx.vstack(
                            rx.heading("Buscar y Filtrar Solicitudes", size="4", color=rx.color_mode_cond(light="black", dark="white"), margin_bottom="1em"),
                            rx.hstack(
                                rx.icon("search", size=20, color=rx.color_mode_cond(light="gray.500", dark="gray.400")),
                                rx.input(
                                    placeholder="Buscar por radicado, asunto, descripción o creador...",
                                    value=State.query_solicitud,
                                    on_change=State.set_query_solicitud,
                                    flex="1",
                                    width="100%",
                                    min_width={"base": "100%", "md": "520px"},
                                    min_height="56px",
                                    border=f"1px solid {rx.color_mode_cond(light='#cbd5e1', dark='#4a5568')}",
                                    padding="16px",
                                    border_radius="md",
                                    font_size="16px",
                                    bg=rx.color_mode_cond(light="white", dark="#2d3748"),
                                    color=rx.color_mode_cond(light="black", dark="white"),
                                ),
                                rx.button(
                                    "Buscar",
                                    on_click=State.buscar_solicitudes,
                                    color_scheme="blue",
                                    size="2",
                                    min_width="150px"
                                ),
                                width="100%",
                                align_items="center",
                                spacing="4"
                            ),
                            rx.hstack(
                                rx.vstack(
                                    rx.text("Filtrar por Estado", font_weight="semibold", color=rx.color_mode_cond(light="gray.700", dark="gray.300")),
                                    rx.select(
                                        ["Todas", "pendiente", "en proceso", "resuelta"],
                                        value=State.filter_estado_solicitud,
                                        on_change=State.set_filter_estado_solicitud,
                                        width="100%",
                                        min_width={"base": "100%", "md": "320px"},
                                        bg="white",
                                        border="1px solid #cbd5e1",
                                        border_radius="md",
                                        _dark={"bg": "gray.700", "color": "white", "borderColor": "gray.600"}
                                    ),
                                    width="100%",
                                    flex="1"
                                ),
                                rx.vstack(
                                    rx.text("Filtrar por Tipo", font_weight="semibold", color=rx.color_mode_cond(light="gray.700", dark="gray.300")),
                                    rx.select(
                                        ["Todas", "Petición", "Queja", "Reclamo", "Sugerencia"],
                                        value=State.filter_tipo_solicitud,
                                        on_change=State.set_filter_tipo_solicitud,
                                        width="100%",
                                        min_width={"base": "100%", "md": "320px"},
                                        bg="white",
                                        border="1px solid #cbd5e1",
                                        border_radius="md",
                                        _dark={"bg": "gray.700", "color": "white", "borderColor": "gray.600"}
                                    ),
                                    width="100%",
                                    flex="1"
                                ),
                                width="100%",
                                spacing="4"
                            ),
                            spacing="4",
                            width="100%"
                        ),
                        p="5",
                        border=f"1px solid {rx.color_mode_cond(light='#e2e8f0', dark='#334155')}",
                        border_radius="lg",
                        bg=rx.color_mode_cond(light="#f9fafb", dark="#1e293b"),
                        width="100%",
                        max_width={"base": "100%", "md": "1400px"},
                        mx="auto",
                        margin_bottom="2em"
                    ),
                    rx.box(
                        rx.vstack(
                            rx.cond(
                                State.solicitudes,
                                rx.vstack(
                                    rx.foreach(
                                        State.solicitudes_filtradas,
                                        lambda solicitud: rx.box(
                                            rx.vstack(
                                                rx.hstack(
                                                    rx.vstack(
                                                        rx.hstack(
                                                            rx.heading(f"Radicado: {solicitud['radicado']}", size="4", color=rx.color_mode_cond(light="#1e40af", dark="#60a5fa")),
                                                            rx.badge(
                                                                solicitud['estado'],
                                                                color_scheme=rx.cond(
                                                                    solicitud['estado'] == 'Radicada',
                                                                    "orange",
                                                                    rx.cond(solicitud['estado'] == 'Actualizada', "blue", "green")
                                                                ),
                                                                variant="solid"
                                                            ),
                                                            spacing="3",
                                                            align_items="center"
                                                        ),
                                                        rx.hstack(
                                                            rx.text(f"Tipo: {solicitud['tipo_solicitud']}", font_weight="medium", color=rx.color_mode_cond(light="gray.600", dark="gray.400"), font_size="sm"),
                                                            rx.cond(
                                                                (solicitud.get("persona_vulnerable") != None) & (solicitud.get("persona_vulnerable") != "Ninguna"),
                                                                rx.text(f"• {solicitud['persona_vulnerable']}", color=rx.color_mode_cond(light="gray.500", dark="gray.500"), font_size="sm"),
                                                            ),
                                                            spacing="3",
                                                            align_items="center"
                                                        ),
                                                        spacing="3"
                                                    ),
                                                    rx.spacer(),
                                                    rx.vstack(
                                                        rx.hstack(
                                                            rx.box(
                                                                rx.box(
                                                                    height="100%",
                                                                    width=f"{solicitud.get('semaforo_width', 0)}%",
                                                                    bg=solicitud.get('semaforo_fill', '#34d399'),
                                                                    border_radius="full"
                                                                ),
                                                                width="90px",
                                                                height="10px",
                                                                border_radius="full",
                                                                bg=rx.color_mode_cond(light="#dbeafe", dark="#1e293b"),
                                                                overflow="hidden"
                                                            ),
                                                            rx.cond(
                                                                solicitud['semaforo_remaining'] == None,
                                                                rx.text("-", font_size="xs", ml="2", color=rx.color_mode_cond(light="gray.600", dark="gray.400")),
                                                                rx.cond(
                                                                    solicitud['semaforo_expired'],
                                                                    rx.hstack(
                                                                        rx.badge("Vencida", color_scheme="red", variant="soft"),
                                                                        rx.text("0 días", font_size="xs", ml="2", color="#ef4444")
                                                                    ),
                                                                    rx.hstack(
                                                                        rx.text(f"{solicitud['semaforo_remaining']}d", font_weight="bold", font_size="sm", color=rx.color_mode_cond(light="#1f2937", dark="#f8fafc")),
                                                                        rx.text(" restantes", font_size="xs", ml="1", color=rx.color_mode_cond(light="gray.600", dark="gray.400"))
                                                                    )
                                                                )
                                                            ),
                                                            spacing="2",
                                                            align_items="center"
                                                        ),
                                                        rx.text(
                                                            solicitud.get('area_responsable', 'Área no asignada'),
                                                            font_size="xs",
                                                            color=rx.color_mode_cond(light="gray.500", dark="gray.500"),
                                                            font_style="italic"
                                                        ),
                                                        spacing="2"
                                                    ),
                                                    align_items="flex-start",
                                                    width="100%",
                                                    spacing="6"
                                                ),
                                                rx.divider(),
                                                rx.vstack(
                                                    rx.hstack(
                                                        rx.vstack(
                                                            rx.text("Asunto", font_weight="semibold", color=rx.color_mode_cond(light="gray.700", dark="gray.200"), font_size="sm"),
                                                            rx.text(solicitud['asunto'], color=rx.color_mode_cond(light="black", dark="white"))
                                                        ),
                                                        rx.vstack(
                                                            rx.text("Fecha", font_weight="semibold", color=rx.color_mode_cond(light="gray.700", dark="gray.200"), font_size="sm"),
                                                            rx.text(solicitud['fecha'], color=rx.color_mode_cond(light="gray.600", dark="gray.400"), font_size="sm")
                                                        ),
                                                        width="100%",
                                                        justify_content="space-between",
                                                        spacing="6"
                                                    ),
                                                    rx.text("Descripción", font_weight="semibold", color=rx.color_mode_cond(light="gray.700", dark="gray.200"), font_size="sm"),
                                                    rx.text(solicitud['descripcion'], color=rx.color_mode_cond(light="gray.600", dark="gray.400")),
                                                    rx.hstack(
                                                        rx.vstack(
                                                            rx.text("Creado por", font_weight="semibold", font_size="xs", color=rx.color_mode_cond(light="gray.500", dark="gray.500")),
                                                            rx.text(solicitud.get('creado_por', 'Desconocido'), color=rx.color_mode_cond(light="gray.700", dark="gray.300"), font_size="sm")
                                                        ),
                                                        rx.vstack(
                                                            rx.text("Área", font_weight="semibold", font_size="xs", color=rx.color_mode_cond(light="gray.500", dark="gray.500")),
                                                            rx.text(solicitud.get('area_responsable', 'No asignada'), color=rx.color_mode_cond(light="gray.700", dark="gray.300"), font_size="sm")
                                                        ),
                                                        width="100%",
                                                        justify_content="space-between",
                                                        spacing="6"
                                                    ),
                                                    spacing="4",
                                                    mt="3"
                                                ),
                                                rx.cond(
                                                    solicitud.get("documento_basename"),
                                                    rx.vstack(
                                                        rx.text("Documento adjunto:", color=rx.color_mode_cond(light="gray.600", dark="gray.400"), font_size="sm"),
                                                        rx.hstack(
                                                            rx.icon("paperclip", size=16),
                                                            rx.link(
                                                                solicitud["documento_basename"],
                                                                href=solicitud.get("documento_href", "#"),
                                                                color="blue.600",
                                                                font_weight="bold",
                                                                target="_blank",
                                                                download=solicitud.get("documento_basename", "documento")
                                                            ),
                                                            rx.text("(Descargar)", color="blue.500", font_size="sm"),
                                                            spacing="2",
                                                            align_items="center"
                                                        )
                                                    ),
                                                    rx.text("Sin documentos adjuntos", color=rx.color_mode_cond(light="gray.500", dark="gray.500"), font_size="sm")
                                                ),
                                                # Botones de acción para actualizar estado
                                                rx.hstack(
                                                    rx.button(
                                                        "Actualizar Estado",
                                                        on_click=lambda _event, id=solicitud['id'], estado=solicitud['estado']: State.abrir_editor_estado(id, estado),
                                                        color_scheme="blue",
                                                        size="2",
                                                        variant="outline"
                                                    ),
                                                    rx.button(
                                                        "Asignar Área",
                                                        on_click=lambda _event, id=solicitud['id'], area=solicitud.get('area_responsable', ''): State.abrir_asignar_area(id, area),
                                                        color_scheme="green",
                                                        size="2",
                                                        variant="outline"
                                                    ),
                                                    spacing="2"
                                                ),
                                                spacing="3",
                                                align_items="start"
                                            ),
                                            p="5",
                                            border=f"1px solid {rx.color_mode_cond(light='#e5e7eb', dark='#334155')}",
                                            border_radius="2xl",
                                            bg=rx.color_mode_cond(light="white", dark="#111827"),
                                            width="100%",
                                            box_shadow=rx.color_mode_cond(light="sm", dark="2xl"),
                                            _hover={"box_shadow": "2xl", "transform": "translateY(-4px)", "border_color": "#3b82f6"},
                                            transition="all 0.2s ease",
                                            overflow="hidden"
                                        )
                                    ),
                                    spacing="4"
                                ),
                                rx.text("No hay solicitudes que coincidan con los filtros.", color=rx.color_mode_cond(light="gray.600", dark="gray.400"), font_size="md", text_align="center", padding="4em")
                            ),
                            spacing="4"
                        ),
                        width="100%"
                    ),
                    # Modal para actualizar estado de solicitud
                    rx.cond(
                        State.editar_estado_id,
                        rx.box(
                            rx.vstack(
                                rx.heading("Notificar al usuario", size="6", color=rx.color_mode_cond(light="black", dark="white")),
                                rx.form(
                                    rx.vstack(
                                        rx.vstack(
                                            rx.text("Nuevo Estado", font_weight="semibold", color=rx.color_mode_cond(light="gray.700", dark="gray.300")),
                                            rx.select(
                                                ["Radicada", "Actualizada", "Cerrada"],
                                                value=State.nuevo_estado,
                                                on_change=State.set_nuevo_estado,
                                                required=True,
                                                bg=rx.color_mode_cond(light="white", dark="#2d3748"),
                                                border=f"1px solid {rx.color_mode_cond(light='#cbd5e1', dark='#4a5568')}",
                                                border_radius="md",
                                                color=rx.color_mode_cond(light="black", dark="white"),
                                            ),
                                        ),
                                        rx.cond(
                                            State.nuevo_estado == "Cerrada",
                                            rx.vstack(
                                                rx.text("Respuesta (obligatoria para cerrar)", font_weight="semibold", color=rx.color_mode_cond(light="gray.700", dark="gray.300")),
                                                rx.text_area(
                                                    placeholder="Escribe la respuesta o solución a la solicitud...",
                                                    value=State.respuesta_solicitud,
                                                    on_change=State.set_respuesta_solicitud,
                                                    rows="4",
                                                    required=True,
                                                    bg=rx.color_mode_cond(light="white", dark="#2d3748"),
                                                    border=f"1px solid {rx.color_mode_cond(light='#cbd5e1', dark='#4a5568')}",
                                                    border_radius="md",
                                                    width="100%",
                                                    color=rx.color_mode_cond(light="black", dark="white"),
                                                ),
                                            )
                                        ),
                                        rx.cond(
                                            State.nuevo_estado != "Cerrada",
                                            rx.vstack(
                                                rx.text("Respuesta (opcional)", font_weight="semibold", color=rx.color_mode_cond(light="gray.700", dark="gray.300")),
                                                rx.text_area(
                                                    placeholder="Escribe una respuesta o actualización (opcional)...",
                                                    value=State.respuesta_solicitud,
                                                    on_change=State.set_respuesta_solicitud,
                                                    rows="4",
                                                    bg=rx.color_mode_cond(light="white", dark="#2d3748"),
                                                    border=f"1px solid {rx.color_mode_cond(light='#cbd5e1', dark='#4a5568')}",
                                                    border_radius="md",
                                                    width="100%",
                                                    color=rx.color_mode_cond(light="black", dark="white"),
                                                ),
                                            )
                                        ),
                                        rx.vstack( 
                                            rx.text("Documento adjunto (Si quieres adjuntar mas de 2 archivos puedes ponerlos en un ZIP)", font_weight="semibold", color=rx.color_mode_cond(light="gray.700", dark="gray.300")),
                                            rx.box(
                                                rx.hstack(
                                                    rx.image(src="/clip-icon.svg", alt="Adjuntar", height="20px"),
                                                    rx.text("Arrastra y suelta un archivo o haz clic para explorar", color=rx.color_mode_cond(light="gray.600", dark="gray.400")),
                                                    rx.spacer(),
                                                    rx.text(State.respuesta_documento_nombre, font_size="sm", color=rx.color_mode_cond(light="gray.500", dark="gray.400"))
                                                ),
                                                rx.input(type="file", accept="*/*", on_change=State.set_respuesta_documento, style={"position": "absolute", "inset": "0", "width": "100%", "height": "100%", "opacity": 0, "cursor": "pointer"}),
                                                position="relative",
                                                padding="3",
                                                border="2px dashed #cbd5e1",
                                                border_radius="8px",
                                                bg="#f8fafc",
                                                width="100%",
                                                _dark={"bg": "gray.700", "borderColor": "gray.600"},
                                            )
                                        ),
                                        rx.button(
                                            "Actualizar Estado",
                                            on_click=State.actualizar_estado_solicitud,
                                            color_scheme="blue",
                                            width="100%"
                                        ),
                                        rx.button(
                                            "Cancelar",
                                            on_click=State.cerrar_editor_estado,
                                            variant="outline",
                                            width="100%"
                                        ),
                                        rx.cond(
                                            State.mensaje_actualizar_estado,
                                            rx.text(
                                                State.mensaje_actualizar_estado,
                                                color=rx.cond(
                                                    State.mensaje_actualizar_estado.contains("correctamente"),
                                                    "green.500",
                                                    "red.500"
                                                ),
                                                font_weight="semibold"
                                            )
                                        ),
                                        spacing="4",
                                        align_items="stretch"
                                    ),
                                    on_submit=State.actualizar_estado_solicitud
                                ),
                                spacing="4",
                                align_items="stretch"
                            ),
                            p="6",
                            border=f"1px solid {rx.color_mode_cond(light='#e5e7eb', dark='#334155')}",
                            border_radius="3xl",
                            bg=rx.color_mode_cond(light="white", dark="#111827"),
                            width="100%",
                            max_width="600px",
                            position="fixed",
                            top="50%",
                            left="50%",
                            transform="translate(-50%, -50%)",
                            z_index="1000",
                            box_shadow="2xl"
                        )
                    ),
                    rx.cond(
                        State.asignar_area_id,
                        rx.box(
                            rx.vstack(
                                rx.box(
                                    rx.hstack(
                                        rx.vstack(
                                            rx.heading("Asignar área responsable", size="6", color=rx.color_mode_cond(light="#0f172a", dark="#f8fafc")),
                                            rx.text(
                                                "Selecciona el área adecuada y envía un mensaje formal al ciudadano.",
                                                color=rx.color_mode_cond(light="gray.600", dark="gray.400"),
                                                font_size="sm"
                                            )
                                        ),
                                        rx.badge("Módulo de administración", color_scheme="blue", variant="soft", border_radius="full", px="3", py="2"),
                                        spacing="4",
                                        align_items="center",
                                        justify="between"
                                    ),
                                    p="5",
                                    bg=rx.color_mode_cond(light="#f8fafc", dark="#0b1120"),
                                    border_bottom=f"1px solid {rx.color_mode_cond(light='#e5e7eb', dark='#273449')}",
                                    border_top_left_radius="3xl",
                                    border_top_right_radius="3xl"
                                ),
                                rx.form(
                                    rx.vstack(
                                        rx.vstack(
                                            rx.text("Área responsable", font_weight="semibold", color=rx.color_mode_cond(light="#1f2937", dark="#cbd5e1")),
                                            rx.select(
                                                ["Secretaría", "Contabilidad", "Bienestar", "Tesorería", "Atención al Ciudadano", "Otros"],
                                                placeholder="Selecciona el área responsable",
                                                value=State.asignar_area_seleccionada,
                                                on_change=State.set_asignar_area_seleccionada,
                                                width="100%",
                                                bg=rx.color_mode_cond(light="#ffffff", dark="#1f2937"),
                                                border=f"1px solid {rx.color_mode_cond(light='#d1d5db', dark='#334155')}",
                                                border_radius="2xl",
                                                px="4",
                                                py="3",
                                                color=rx.color_mode_cond(light="#111827", dark="#f8fafc"),
                                            ),
                                        ),
                                        rx.cond(
                                            State.asignar_area_seleccionada == "Otros",
                                            rx.vstack(
                                                rx.text("Otra área", font_weight="semibold", color=rx.color_mode_cond(light="#1f2937", dark="#cbd5e1")),
                                                rx.input(
                                                    placeholder="Escribe el área responsable",
                                                    value=State.asignar_area_nombre,
                                                    on_change=State.set_asignar_area_nombre,
                                                    width="100%",
                                                    bg=rx.color_mode_cond(light="#ffffff", dark="#1f2937"),
                                                    border=f"1px solid {rx.color_mode_cond(light='#d1d5db', dark='#334155')}",
                                                    border_radius="2xl",
                                                    px="4",
                                                    py="3",
                                                    color=rx.color_mode_cond(light="#111827", dark="#f8fafc"),
                                                ),
                                            ),
                                            rx.box()
                                        ),
                                        rx.vstack(
                                            rx.text("Mensaje para el ciudadano", font_weight="semibold", color=rx.color_mode_cond(light="#1f2937", dark="#cbd5e1")),
                                            rx.text_area(
                                                placeholder="Escribe el mensaje que llegará al ciudadano...",
                                                value=State.asignar_area_mensaje,
                                                on_change=State.set_asignar_area_mensaje,
                                                rows="5",
                                                bg=rx.color_mode_cond(light="#ffffff", dark="#1f2937"),
                                                border=f"1px solid {rx.color_mode_cond(light='#d1d5db', dark='#334155')}",
                                                border_radius="2xl",
                                                width="100%",
                                                color=rx.color_mode_cond(light="#111827", dark="#f8fafc"),
                                                px="4",
                                                py="4",
                                            ),
                                        ),
                                        rx.cond(
                                            State.mensaje_asignacion,
                                            rx.box(
                                                rx.text(
                                                    State.mensaje_asignacion,
                                                    color=rx.cond(
                                                        State.mensaje_asignacion.contains("correctamente"),
                                                        "green.500",
                                                        "red.500"
                                                    ),
                                                    font_weight="semibold"
                                                ),
                                                bg=rx.color_mode_cond(light="#ecfdf5", dark="#052e16"),
                                                border=f"1px solid {rx.color_mode_cond(light='#d1fae5', dark='#064e3b')}",
                                                border_radius="2xl",
                                                p="4"
                                            )
                                        ),
                                        spacing="4",
                                        align_items="stretch"
                                    ),
                                    on_submit=State.asignar_area_con_mensaje
                                ),
                                rx.hstack(
                                    rx.button(
                                        "Enviar mensaje y asignar",
                                        on_click=State.asignar_area_con_mensaje,
                                        color_scheme="green",
                                        flex="1",
                                        min_width="220px",
                                        box_shadow="md"
                                    ),
                                    rx.button(
                                        "Cancelar",
                                        on_click=State.cerrar_asignar_area,
                                        variant="outline",
                                        flex="0",
                                        min_width="140px",
                                        border_color=rx.color_mode_cond(light="#9ca3af", dark="#475569"),
                                        color=rx.color_mode_cond(light="#1f2937", dark="#f8fafc")
                                    ),
                                    spacing="3",
                                    width="100%"
                                )
                            ),
                            # Close button in corner
                            rx.button(
                                rx.text("✕", font_size="lg"),
                                on_click=State.cerrar_asignar_area,
                                variant="ghost",
                                position="absolute",
                                top="12px",
                                right="12px",
                                padding="2",
                                border_radius="full",
                                _hover={"bg": rx.color_mode_cond(light="#f3f4f6", dark="#1f2937")},
                            ),
                            p="0",
                            border=f"1px solid {rx.color_mode_cond(light='#e5e7eb', dark='#334155')}",
                            border_radius="3xl",
                            bg=rx.color_mode_cond(light="#ffffff", dark="#020617"),
                            width="100%",
                            max_width="640px",
                            position="fixed",
                            top="50%",
                            left="50%",
                            transform="translate(-50%, -50%)",
                            z_index="1000",
                            box_shadow=rx.color_mode_cond(light="2xl", dark="2xl")
                        )
                    ),
                    rx.button("Cerrar Sesión", on_click=State.logout, color_scheme="red", width="100%"),
                    spacing="6",
                    align_items="stretch"
                ),
                size="3"
            )
        ),
        rx.container(
            navbar(),
            rx.center(
                access_denied_widget("Solo los funcionarios autenticados pueden acceder a esta página."),
                size="3"
            )
        )
    )


def solicitudes_page() -> rx.Component:
    return rx.cond(
        State.es_autentica,
        rx.container(
            navbar(),
            rx.center(
                rx.card(
                    rx.vstack(
                        rx.heading("Nueva Solicitud PQRS", size="8", color=rx.color_mode_cond(light="black", dark="white")),
                        rx.text("Completa el formulario para radicar tu Petición, Queja, Reclamo o Sugerencia.", color="gray.600"),
                        rx.form(
                            rx.vstack(
                                # Mensaje de validación/éxito al inicio
                                rx.cond(
                                    State.solicitud_mensaje,
                                    rx.box(
                                        rx.text(
                                            State.solicitud_mensaje,
                                            color="white",
                                            font_weight="semibold",
                                            font_size="sm"
                                        ),
                                        p="4",
                                        border_radius="lg",
                                        bg=rx.cond(State.solicitud_mensaje.contains("éxito"), "green.500", "red.500"),
                                        width="100%"
                                    )
                                ),
                                # Tipo de solicitud (label + select)
                                rx.vstack(
                                    label_requerido("Tipo de Solicitud"),
                                    rx.select(["Petición", "Queja", "Reclamo", "Sugerencia"], placeholder="Selecciona el tipo de solicitud", value=State.tipo_solicitud, on_change=State.set_tipo_solicitud, required=True, bg=rx.color_mode_cond(light="white", dark="#2d3748"), border=f"1px solid {rx.color_mode_cond(light='#cbd5e1', dark='#4a5568')}", border_radius="md", color=rx.color_mode_cond(light="black", dark="white")),
                                ),

                                # Asunto (label + input)
                                rx.vstack(
                                    label_requerido("Asunto"),
                                    rx.text_area(
                                        placeholder="Escribe el asunto detallado...",
                                        value=State.asunto,
                                        on_change=State.set_asunto,
                                        required=True,
                                        bg=rx.color_mode_cond(light="white", dark="#2d3748"),
                                        border=f"1px solid {rx.color_mode_cond(light='#cbd5e1', dark='#4a5568')}",
                                        border_radius="md",
                                        width="100%",
                                        height="150px",
                                        resize="both",
                                        color=rx.color_mode_cond(light="black", dark="white"),
                                    ),
                                ),

                                # Descripción detallada (label + textarea + contador)
                                rx.vstack(
                                    label_requerido("Descripción detallada"),
                                    rx.text_area(
                                        placeholder="Escribe aquí los detalles de tu solicitud...",
                                        value=State.descripcion,
                                        on_change=State.set_descripcion,
                                        required=True,
                                        rows="4",
                                        max_length=1000,
                                        bg=rx.color_mode_cond(light="white", dark="#2d3748"),
                                        border=f"1px solid {rx.color_mode_cond(light='#cbd5e1', dark='#4a5568')}",
                                        border_radius="md",
                                        width="100%",
                                        resize="both",
                                        min_height="150px",
                                        color=rx.color_mode_cond(light="black", dark="white"),
                                    ),
                                    rx.hstack(rx.spacer(), rx.text(State.descripcion_len, font_size="sm", color=rx.color_mode_cond(light="gray.600", dark="gray.400")), rx.text(" / 1000 caracteres", font_size="sm", color=rx.color_mode_cond(light="gray.600", dark="gray.400"))),
                                ),

                                rx.vstack(
                                    label_requerido("Área Responsable"),
                                    rx.select(
                                        ["Secretaría", "Contabilidad", "Bienestar", "Tesorería", "Atención al Ciudadano", "Otros"],
                                        placeholder="Selecciona el área responsable",
                                        value=State.area_responsable,
                                        on_change=State.set_area_responsable,
                                        required=True,
                                        bg=rx.color_mode_cond(light="white", dark="#2d3748"),
                                        border=f"1px solid {rx.color_mode_cond(light='#cbd5e1', dark='#4a5568')}",
                                        border_radius="md",
                                        color=rx.color_mode_cond(light="black", dark="white"),
                                    ),
                                ),

                                rx.cond(
                                    State.area_responsable == "Otros",
                                    rx.vstack(
                                        label_requerido("Otra área"),
                                        rx.input(
                                            placeholder="Escribe el área responsable",
                                            value=State.area_otro,
                                            on_change=State.set_area_otro,
                                            required=True,
                                            bg=rx.color_mode_cond(light="white", dark="#2d3748"),
                                            border=f"1px solid {rx.color_mode_cond(light='#cbd5e1', dark='#4a5568')}",
                                            border_radius="md",
                                            color=rx.color_mode_cond(light="black", dark="white"),
                                        ),
                                    )
                                ),

                                # Archivo adjunto: zona arrastrar y soltar moderna
                                rx.vstack(
                                    rx.text("Documento adjunto (si quieres enviar mas de 2 archivos puedes ponerlos en un Zip)", font_weight="semibold"),
                                    rx.box(
                                        rx.hstack(
                                            rx.image(src="/clip-icon.svg", alt="Adjuntar", height="20px"),
                                            rx.cond(
                                                State.documento_nombres,
                                                rx.text(
                                                    State.documento_nombres_joined,
                                                    color=rx.color_mode_cond(light="gray.600", dark="gray.400"),
                                                    no_wrap=False,
                                                ),
                                                rx.text("Arrastra y suelta hasta 3 archivos PDF, PNG o JPG (máx 10MB cada uno)", color=rx.color_mode_cond(light="gray.600", dark="gray.400")),
                                            ),
                                            rx.spacer(),
                                            rx.cond(
                                                State.documento_nombres,
                                                rx.text(f"{State.documento_nombres_count} archivos seleccionados", font_size="sm", color=rx.color_mode_cond(light="gray.500", dark="gray.400")),
                                                rx.text("Ningún archivo seleccionado", font_size="sm", color=rx.color_mode_cond(light="gray.500", dark="gray.400")),
                                            ),
                                        ),
                                        rx.input(type="file", accept="application/pdf,image/png,image/jpeg", multiple=True, on_change=State.set_documento, style={"position": "absolute", "inset": "0", "width": "100%", "height": "100%", "opacity": 0, "cursor": "pointer"}),
                                        position="relative",
                                        padding="4",
                                        border="2px dashed #cfe7ff",
                                        border_radius="8px",
                                        bg="#00ff08",
                                        _dark={"bg": "gray.700", "borderColor": "gray.600"},
                                        width="100%",
                                    ),
                                    rx.cond(
                                        State.documento_nombres,
                                        rx.vstack(
                                            rx.text("Archivos seleccionados:", font_size="sm", font_weight="semibold", color=rx.color_mode_cond(light="gray.700", dark="gray.300")),
                                            rx.vstack(
                                                rx.foreach(
                                                    State.documento_nombres,
                                                    lambda nombre: rx.hstack(
                                                        rx.text(nombre, font_size="sm", no_wrap=False),
                                                        rx.spacer(),
                                                        rx.button("Eliminar", size="2", color_scheme="red", on_click=lambda nombre=nombre: State.eliminar_documento_por_nombre(nombre))
                                                    )
                                                ),
                                                spacing="2",
                                                mt="2"
                                            ),
                                            rx.text(f"Tamaño total: {State.documento_tamano_total}", font_size="sm", color=rx.color_mode_cond(light="gray.600", dark="gray.400"), mt="2"),
                                        )
                                    ),
                                    rx.cond(
                                        State.archivo_error_mensaje,
                                        rx.text(State.archivo_error_mensaje, color="red.500", font_size="sm", mt="2"),
                                    )
                                ),
                                rx.checkbox(rx.link("He leído y acepto la Política de Tratamiento de Datos Personales", href="/politica-privacidad", color="blue"), is_checked=State.acepta_politica_solicitud, on_change=State.set_acepta_politica_solicitud),
                                rx.button("Enviar Solicitud", on_click=State.crear_solicitud, color_scheme="blue", width="100%", is_disabled=~State.acepta_politica_solicitud),
                                spacing="4",
                                align_items="stretch"
                            ),
                            on_submit=State.crear_solicitud
                        ),
                        spacing="4",
                        align_items="center"
                    ),
                    bg=rx.color_mode_cond(light="white", dark="#1a202c"),
                    max_width="640px",
                    p="10",
                    box_shadow="2xl",
                    border_radius="2xl"
                ),
                size="3"
            ),
            bg=rx.color_mode_cond(light="#f8fafc", dark="#0f172a")
        ),
        rx.container(
            navbar(),
            rx.center(
                access_denied_widget("Necesitas iniciar sesión para crear una solicitud."),
                size="3"
            )
        )
    )


def consultar_estado_page() -> rx.Component:
    return rx.container(
        navbar(),
        rx.center(
            rx.card(
                rx.vstack(
                    rx.heading("Consultar Estado de Solicitud", size="4", color=rx.color_mode_cond(light="black", dark="white")),
                    rx.text("Ingresa el número de radicado de tu solicitud para consultar su estado actual.", color=rx.color_mode_cond(light="gray.600", dark="gray.400")),
                    
                    # Formulario de consulta
                    rx.vstack(
                        rx.text("Número de Radicado", font_weight="semibold", color=rx.color_mode_cond(light="black", dark="white")),
                        rx.input(
                            placeholder="Ej: PQRS-2024-abc12345",
                            value=State.consulta_radicado,
                            on_change=State.set_consulta_radicado,
                            bg=rx.color_mode_cond(light="white", dark="#2d3748"),
                            border=f"1px solid {rx.color_mode_cond(light='#cbd5e1', dark='#4a5568')}",
                            border_radius="md",
                            color=rx.color_mode_cond(light="black", dark="white"),
                            _placeholder={"color": rx.color_mode_cond(light="#718096", dark="#a0aec0")}
                        ),
                        rx.button(
                            "Consultar Estado",
                            on_click=State.consultar_estado_solicitud,
                            color_scheme="blue",
                            width="100%"
                        ),
                        spacing="3",
                        width="100%"
                    ),
                    
                    # Mensaje de resultado
                    rx.cond(
                        State.consulta_mensaje,
                        rx.text(
                            State.consulta_mensaje,
                            color=rx.cond(
                                State.consulta_mensaje.contains("encontrada") & ~State.consulta_mensaje.contains("No se encontró"),
                                "green.500",
                                "red.500"
                            ),
                            font_weight="semibold"
                        )
                    ),
                    
                    # Mostrar detalles de la solicitud si se encontró
                    rx.cond(
                        State.solicitud_consultada,
                        rx.box(
                            rx.vstack(
                                rx.heading("Detalles de la Solicitud", size="6", color=rx.color_mode_cond(light="black", dark="white")),
                                rx.grid(
                                    rx.vstack(
                                        rx.text("Número de Radicado:", font_weight="semibold", color=rx.color_mode_cond(light="black", dark="white"), font_size="sm"),
                                        rx.text(State.solicitud_consultada.get("radicado", ""), color=rx.color_mode_cond(light="gray.700", dark="gray.300"), font_size="sm")
                                    ),
                                    rx.vstack(
                                        rx.text("Tipo de Solicitud:", font_weight="semibold", color=rx.color_mode_cond(light="black", dark="white"), font_size="sm"),
                                        rx.text(State.solicitud_consultada.get("tipo_solicitud", ""), color=rx.color_mode_cond(light="gray.700", dark="gray.300"), font_size="sm")
                                    ),
                                    rx.vstack(
                                        rx.text("Estado Actual:", font_weight="semibold", color=rx.color_mode_cond(light="black", dark="white"), font_size="sm"),
                                        rx.badge(
                                            State.solicitud_consultada.get("estado", ""),
                                            color_scheme=rx.cond(
                                                State.solicitud_consultada.get("estado") == "Radicada",
                                                "blue",
                                                rx.cond(
                                                    State.solicitud_consultada.get("estado") == "Actualizada",
                                                    "yellow",
                                                    rx.cond(
                                                        State.solicitud_consultada.get("estado") == "Cerrada",
                                                        "green",
                                                        "gray"
                                                    )
                                                )
                                            )
                                        )
                                    ),
                                    rx.vstack(
                                        rx.text("Fecha de Creación:", font_weight="semibold", color=rx.color_mode_cond(light="black", dark="white"), font_size="sm"),
                                        rx.text(State.solicitud_consultada.get("fecha", ""), color=rx.color_mode_cond(light="gray.700", dark="gray.300"), font_size="sm")
                                    ),
                                    rx.vstack(
                                        rx.text("Asunto:", font_weight="semibold", color=rx.color_mode_cond(light="black", dark="white"), font_size="sm"),
                                        rx.text(State.solicitud_consultada.get("asunto", ""), color=rx.color_mode_cond(light="gray.700", dark="gray.300"), font_size="sm")
                                    ),
                                    rx.vstack(
                                        rx.text("Área Responsable:", font_weight="semibold", color=rx.color_mode_cond(light="black", dark="white"), font_size="sm"),
                                        rx.text(State.solicitud_consultada.get("area_responsable", ""), color=rx.color_mode_cond(light="gray.700", dark="gray.300"), font_size="sm")
                                    ),
                                    template_columns="repeat(2, 1fr)",
                                    gap="4",
                                    width="100%"
                                ),
                                
                                # Descripción
                                rx.cond(
                                    State.solicitud_consultada.get("descripcion"),
                                    rx.vstack(
                                        rx.text("Descripción:", font_weight="semibold", color=rx.color_mode_cond(light="black", dark="white"), font_size="sm"),
                                        rx.box(
                                            rx.text(State.solicitud_consultada.get("descripcion", ""), color=rx.color_mode_cond(light="gray.700", dark="gray.300"), font_size="sm"),
                                            p="3",
                                            border=f"1px solid {rx.color_mode_cond(light='#e2e8f0', dark='#4a5568')}",
                                            border_radius="md",
                                            bg=rx.color_mode_cond(light="#f7fafc", dark="#2d3748"),
                                            width="100%"
                                        ),
                                        spacing="2",
                                        width="100%"
                                    )
                                ),
                                
                                # Respuesta del funcionario (si existe)
                                rx.cond(
                                    State.solicitud_consultada.get("respuesta"),
                                    rx.vstack(
                                        rx.text("Respuesta del Funcionario:", font_weight="semibold", color=rx.color_mode_cond(light="black", dark="white"), font_size="sm"),
                                        rx.box(
                                            rx.text(State.solicitud_consultada.get("respuesta", ""), color=rx.color_mode_cond(light="gray.700", dark="gray.300"), font_size="sm"),
                                            p="3",
                                            border="2px solid #48bb78",
                                            border_radius="md",
                                            bg=rx.color_mode_cond(light="#f0fff4", dark="#2f4f2f"),
                                            width="100%"
                                        ),
                                        spacing="2",
                                        width="100%"
                                    )
                                ),
                                
                                # Documento adjunto (si existe)
                                rx.cond(
                                    State.solicitud_consultada.get("documento_adjuntos"),
                                    rx.vstack(
                                        rx.text("Documentos adjuntos:", font_weight="semibold", color=rx.color_mode_cond(light="black", dark="white"), font_size="sm"),
                                        rx.foreach(
                                            State.solicitud_consultada_adjuntos,
                                            lambda doc: rx.link(
                                                doc["basename"],
                                                href=doc["href"],
                                                color="blue.500",
                                                target="_blank",
                                                font_size="sm"
                                            )
                                        ),
                                        spacing="2"
                                    )
                                ),
                                rx.cond(
                                    State.solicitud_consultada.get("respuesta_documento_basename"),
                                    rx.vstack(
                                        rx.text("Documento adjunto en la respuesta:", font_weight="semibold", color=rx.color_mode_cond(light="black", dark="white"), font_size="sm"),
                                        rx.cond(
                                            State.solicitud_consultada.get("respuesta_documento_href"),
                                            rx.link(
                                                State.solicitud_consultada.get("respuesta_documento_basename", "Ver documento"),
                                                href=State.solicitud_consultada["respuesta_documento_href"],
                                                color="blue.500",
                                                target="_blank",
                                                font_size="sm"
                                            ),
                                            rx.text("Documento no disponible", color="gray.500", font_size="sm")
                                        ),
                                        spacing="2"
                                    )
                                ),
                                
                                spacing="4",
                                align_items="start",
                                width="100%"
                            ),
                            p="6",
                            border=f"1px solid {rx.color_mode_cond(light='#e2e8f0', dark='#4a5568')}",
                            border_radius="lg",
                            bg=rx.color_mode_cond(light="white", dark="#1a202c"),
                            width="100%",
                            margin_top="4"
                        )
                    ),
                    
                    spacing="6",
                    align_items="center",
                    width="100%"
                ),
                bg=rx.color_mode_cond(light="white", dark="#1a202c"),
                max_width="800px",
                p="8",
                box_shadow="2xl",
                border_radius="2xl"
            ),
            size="3"
        ),
        bg=rx.color_mode_cond(light="#f8fafc", dark="#0f172a")
    )


def reportes_page() -> rx.Component:
    tipo_counts = State.estadisticas_por_tipo
    max_count = State.max_registros_tipo

    def grafica_barra(label: str, value, color: str):
        # Calcular el porcentaje de forma simple para evitar errores de tipo en Reflex
        # Usar una expresión simple que Reflex pueda compilar
        return rx.vstack(
            rx.text(label, font_weight="semibold", color=rx.color_mode_cond(light="black", dark="white")),
            rx.hstack(
                rx.box(
                    bg=color,
                    height="18px",
                    width="30%",  # Ancho fijo para evitar cálculos complejos con Vars
                    border_radius="full",
                    transition="width 0.4s ease"
                ),
                rx.text(f"{value}", color="gray.600", font_size="sm", ml="3"),
                spacing="3",
                align_items="center"
            ),
            spacing="2",
            width="100%"
        )

    # Layout principal: filtros superior, grid con dos columnas (contenido + columna lateral)
    content = rx.container(
        navbar(),
        rx.center(
            rx.vstack(
                rx.heading("Reportes PQRS", size="8", color=rx.color_mode_cond(light="black", dark="white")),
                rx.text("Panel de métricas y volumen por tipo. Filtra por rango, tipo y área.", color=rx.color_mode_cond(light="gray.600", dark="gray.400")),

                # Filtros superiores
                rx.hstack(
                    rx.select(["Últimos 12 meses", "Últimos 6 meses", "Este año"], placeholder="Rango de fecha", width="220px"),
                    rx.select(
                        ["Todos", "Petición", "Queja", "Reclamo", "Sugerencia"],
                        placeholder="Tipo de Solicitud",
                        width="220px",
                        value=State.filter_tipo_solicitud,
                        on_change=State.set_filter_tipo_solicitud,
                    ),
                    rx.select(["Todos", "Atención al Cliente", "Trámites", "Soporte"], placeholder="Área Responsable", width="220px"),
                    rx.spacer(),
                    rx.vstack(
                        rx.button("📥 Descargar CSV", on_click=State.toggle_menu_descarga, color_scheme="blue", width="160px"),
                        rx.cond(
                            State.mostrar_menu_descarga,
                            rx.vstack(
                                rx.button("📊 Descargar Excel", on_click=State.descargar_excel_y_abrir, color_scheme="green", width="160px", size="1"),
                                rx.button("📋 Descargar CSV", on_click=State.descargar_csv_y_abrir, color_scheme="cyan", width="160px", size="1"),
                                spacing="2",
                                position="absolute",
                                bg=rx.color_mode_cond(light="white", dark="#111827"),
                                border=rx.color_mode_cond(light="1px solid #e2e8f0", dark="1px solid #374151"),
                                border_radius="md",
                                p="2",
                                box_shadow="lg",
                                z_index="10",
                                mt="-2",
                            ),
                            rx.box()
                        ),
                        spacing="2",
                        position="relative",
                    ),
                    rx.cond(
                        State.export_href,
                        rx.link(
                            "⬇️ Descargar",
                            href=State.export_href,
                            is_external=True,
                            target="_blank",
                            _hover={"text_decoration": "underline"}
                        ),
                        rx.box()
                    ),
                    width="100%",
                    spacing="4",
                ),

                # Grid principal
                rx.hstack(
                    # Columna principal (gráficas)
                    rx.vstack(
                        rx.hstack(
                            # Card: Solicitudes por Tipo (barras) usando Recharts
                            rx.box(
                                rx.vstack(
                                    rx.heading("Solicitudes por Tipo", size="6"),
                                    rc.bar_chart(
                                        rc.x_axis(data_key="name"),
                                        # Forzar dominio Y desde 0 hasta el máximo encontrado para mostrar conteos reales
                                        rc.y_axis(domain=[0, State.max_registros_tipo]),
                                        rc.tooltip(),
                                        rc.bar(data_key="cantidad", fill="#1D4ED8"),
                                        data=State.data_grafica_tipo,
                                        width=560,
                                        height=320,
                                    ),
                                    spacing="4",
                                ),
                                p="4",
                                border="1px solid #e2e8f0",
                                border_radius="lg",
                                bg=rx.color_mode_cond(light="#ffffff", dark="#111827"),
                                width="560px",
                            ),
                            spacing="4",
                            width="100%",
                        ),

                        rx.hstack(
                            # Card: Tiempos Promedio (línea) usando Recharts
                            rx.box(
                                rx.vstack(
                                    rx.heading("Tiempos Promedio de Respuesta", size="6"),
                                    rc.line_chart(
                                        rc.x_axis(data_key="month"),
                                        rc.y_axis(),
                                        rc.tooltip(),
                                        rc.line(type="monotone", data_key="value", stroke="#0ea5a4", stroke_width=3, dot={"r": 4, "fill": "#0ea5a4", "stroke": "#ffffff"}),
                                        data=State.monthly_response_times,
                                        width=560,
                                        height=280,
                                    ),
                                    spacing="3",
                                ),
                                p="4",
                                border="1px solid #e2e8f0",
                                border_radius="lg",
                                bg=rx.color_mode_cond(light="#ffffff", dark="#111827"),
                                width="560px",
                            ),
                            spacing="4",
                            width="100%",
                        ),

                        rx.box(
                            rx.vstack(
                                rx.heading("Semáforo Global", size="6"),
                                rx.cond(
                                    State.semaforo_total,
                                    # Usar gráfica de barras coloreadas como alternativa más fiable
                                    rc.bar_chart(
                                        rc.x_axis(data_key="name"),
                                        rc.y_axis(),
                                        rc.tooltip(),
                                        rc.bar(data_key="verde", fill="#10b981"),
                                        rc.bar(data_key="amarillo", fill="#f59e0b"),
                                        rc.bar(data_key="rojo", fill="#ef4444"),
                                        data=State.semaforo_bar_data,
                                        width=560,
                                        height=240,
                                    ),
                                    rx.center(rx.text("No hay solicitudes activas", color="gray.500"))
                                ),
                                rx.center(rx.hstack(rx.text(State.semaforo_counts.get('verde',0), font_size="lg", font_weight="bold", color="#10b981"), rx.text(" verde", font_size="sm", ml="2"))),
                                spacing="3",
                            ),
                            p="4",
                            border="1px solid #e2e8f0",
                            border_radius="lg",
                            bg=rx.color_mode_cond(light="#ffffff", dark="#111827"),
                            width="560px",
                        ),

                        rx.box(
                            rx.vstack(
                                rx.heading("Solicitudes por vencer", size="6"),
                                rc.bar_chart(
                                    rc.x_axis(data_key="name"),
                                    rc.y_axis(),
                                    rc.tooltip(),
                                    rc.bar(
                                        # Map colors per category: Vencidas (rojo), 1-5 (naranja), 6-10 (naranja), >10 (verde)
                                        rc.cell(fill="#ef4444"),
                                        rc.cell(fill="#f59e0b"),
                                        rc.cell(fill="#f59e0b"),
                                        rc.cell(fill="#10b981"),
                                        data_key="cantidad",
                                    ),
                                    data=State.solicitudes_por_vencer_data,
                                    width=560,
                                    height=280,
                                ),
                                rx.text(f"{State.solicitudes_por_vencer_total} solicitudes próximas a vencer o vencidas", color=rx.color_mode_cond(light="gray.600", dark="gray.400"), font_size="sm"),
                                spacing="3",
                            ),
                            p="4",
                            border="1px solid #e2e8f0",
                            border_radius="lg",
                            bg=rx.color_mode_cond(light="#ffffff", dark="#111827"),
                            width="560px",
                        ),

                        # KPIs: Pendientes / En Proceso / Cerradas
                        rx.box(
                            rx.hstack(
                                rx.vstack(
                                    rx.text(State.kpi_pendientes_count, font_size="2xl", font_weight="bold", color="#10b981"),
                                    rx.text("Pendientes (>10d)", font_size="sm", color=rx.color_mode_cond(light="gray.600", dark="gray.400")),
                                    align_items="center",
                                ),
                                rx.vstack(
                                    rx.text(State.kpi_en_curso_count, font_size="2xl", font_weight="bold", color="#f59e0b"),
                                    rx.text("En Proceso (1-10d)", font_size="sm", color=rx.color_mode_cond(light="gray.600", dark="gray.400")),
                                    align_items="center",
                                ),
                                rx.vstack(
                                    rx.text(State.kpi_cerradas_count, font_size="2xl", font_weight="bold", color="#0ea5a4"),
                                    rx.text("Cerradas", font_size="sm", color=rx.color_mode_cond(light="gray.600", dark="gray.400")),
                                    align_items="center",
                                ),
                                spacing="9",
                                justify="between",
                                width="100%",
                            ),
                            p="4",
                            border="1px solid #e2e8f0",
                            border_radius="lg",
                            bg=rx.color_mode_cond(light="#ffffff", dark="#111827"),
                            width="560px",
                        ),

                        rx.box(
                            rx.vstack(
                                rx.heading("Nivel de Cumplimiento", size="6"),
                                # Gráfica de cumplimiento con visualización alternativa (barra horizontal coloreada + dona)
                                rx.vstack(
                                    # Barra de cumplimiento visual (fallback más visible)
                                    rx.vstack(
                                        rx.hstack(
                                            rx.box(
                                                bg="#10b981",
                                                height="16px",
                                                width=rx.cond(State.compliance_percentage > 0, f"{State.compliance_percentage}%", "0%"),
                                                border_radius="2px",
                                                transition="width 0.3s ease",
                                            ),
                                            rx.box(
                                                bg="#e5e7eb",
                                                height="16px",
                                                width=rx.cond(State.compliance_percentage < 100, f"{100 - State.compliance_percentage}%", "0%"),
                                                border_radius="2px",
                                                transition="width 0.3s ease",
                                            ),
                                            border="1px solid #d1d5db",
                                            border_radius="2px",
                                            overflow="hidden",
                                            width="100%",
                                            spacing="0",
                                        ),
                                        spacing="2",
                                        width="100%",
                                    ),
                                    rx.center(
                                        rx.hstack(
                                            rx.text(State.compliance_percentage, font_size="4xl", font_weight="bold", color="#10b981"),
                                            rx.text("%", font_size="xl", font_weight="bold", color="#10b981"),
                                        )
                                    ),
                                    # Gráfica de dona con leyenda y etiquetas
                                    rx.center(
                                        rc.pie_chart(
                                            rc.tooltip(),
                                            rc.legend(layout="horizontal", vertical_align="bottom", align="center"),
                                            rc.pie(
                                                rc.cell(fill="#10b981"),
                                                rc.cell(fill="#ef4444"),
                                                data=State.compliance_chart_data,
                                                data_key="value",
                                                name_key="name",
                                                cx="50%",
                                                cy="50%",
                                                outer_radius=100,
                                                inner_radius=40,
                                                label=True,
                                            ),
                                            width=420,
                                            height=300,
                                        ),
                                        width="100%"
                                    ),
                                    spacing="3",
                                    width="100%",
                                ),
                                spacing="3",
                            ),
                            p="4",
                            border="1px solid #e2e8f0",
                            border_radius="lg",
                            bg=rx.color_mode_cond(light="#ffffff", dark="#111827"),
                            width="560px",
                        ),
                    ),

                    # Columna lateral (KPIs)
                    rx.vstack(
                        rx.box(
                            rx.vstack(
                                rx.hstack(rx.text("Solicitudes Totales", color="gray.600", font_size="sm"), rx.spacer(), rx.text(State.numero_solicitudes, font_weight="bold")),
                                rx.hstack(rx.text("Tiempo Promedio de Cierre", color="gray.600", font_size="sm"), rx.spacer(), rx.text("10 min", font_weight="bold")),
                                spacing="2",
                            ),
                            p="3",
                            border="1px solid #e2e8f0",
                            border_radius="lg",
                            bg=rx.color_mode_cond(light="#ffffff", dark="#111827"),
                            width="100%",
                        ),

                        rx.box(
                            rx.vstack(
                                rx.heading("Solicitudes por Áreas", size="6"),
                                rx.foreach(
                                    State.top_areas,
                                    lambda row: rx.hstack(rx.text(row.get('name'), font_size="sm"), rx.spacer(), rx.text(row.get('total'), font_weight="bold", font_size="sm")),
                                ),
                                spacing="1",
                            ),
                            p="3",
                            border="1px solid #e2e8f0",
                            border_radius="lg",
                            bg=rx.color_mode_cond(light="#ffffff", dark="#111827"),
                            width="100%",
                        ),
                        spacing="3",
                        align_items="stretch",
                        width="100%",
                    ),
                    spacing="8",
                    width="100%",
                    align_items="start",
                ),

                spacing="6",
                width="100%",
            ),
            width="100%",
            p="6",
            box_shadow="2xl",
            border_radius="2xl",
            bg=rx.color_mode_cond(light="white", dark="#1a202c")
        ),
        width="100%",
        min_height="100vh",
        style={"margin": "0", "padding": "0", "boxSizing": "border-box"},
        bg=rx.color_mode_cond(light="#f8fafc", dark="#0f172a")
    )
    # Restringir acceso: solo funcionarios y administradores
    return rx.cond(
        State.es_autentica & ((State.rol_usuario == "funcionario") | (State.rol_usuario == "administrador")),
        content,
        rx.container(
            navbar(),
            rx.center(
                access_denied_widget("Solo funcionarios autenticados pueden ver esta página."),
                size="3"
            )
        )
    )


def usuarios_page() -> rx.Component:
    """Página para que funcionarios vean la lista de usuarios registrados."""
    return rx.cond(
        State.es_autentica & (State.rol_usuario == "funcionario"),
        rx.container(
            navbar(),
            rx.center(
                rx.vstack(
                    rx.heading("Gestión de Usuarios", size="6", color=rx.color_mode_cond(light="black", dark="white")),
                    rx.text("Lista de usuarios registrados en el sistema", color=rx.color_mode_cond(light="gray.600", dark="gray.300"), font_size="sm"),
                    
                    rx.box(
                        rx.cond(
                            State.usuarios_registrados,
                            rx.vstack(
                                rx.table.root(
                                    rx.table.header(
                                        rx.table.row(
                                            rx.table.column_header_cell("ID"),
                                            rx.table.column_header_cell("Email"),
                                            rx.table.column_header_cell("Nombres"),
                                            rx.table.column_header_cell("Apellidos"),
                                            rx.table.column_header_cell("Rol"),
                                            rx.table.column_header_cell("Fecha de Creación"),
                                            rx.table.column_header_cell("Estado"),
                                        ),
                                    ),
                                    rx.table.body(
                                        rx.foreach(
                                            State.usuarios_registrados,
                                            lambda usuario: rx.table.row(
                                                rx.table.cell(rx.text(str(usuario["id"]), font_size="sm")),
                                                rx.table.cell(rx.text(usuario["email"], font_size="sm")),
                                                rx.table.cell(rx.text(usuario["nombres"], font_size="sm")),
                                                rx.table.cell(rx.text(usuario["apellidos"], font_size="sm")),
                                                rx.table.cell(
                                                    rx.badge(
                                                        usuario["rol"],
                                                        color_scheme=rx.cond(usuario["rol"] == "funcionario", "blue", "gray"),
                                                        variant="soft",
                                                    )
                                                ),
                                                rx.table.cell(rx.text(usuario["fecha_creacion"], font_size="sm")),
                                                rx.table.cell(rx.text(usuario["is_active"], font_size="sm")),
                                            )
                                        )
                                    ),
                                    width="100%",
                                    size="2",
                                ),
                                rx.text(f"Total de usuarios: {State.usuarios_registrados_count}", font_weight="semibold", color=rx.color_mode_cond(light="gray.600", dark="gray.300"), font_size="sm"),
                                spacing="4",
                                width="100%"
                            ),
                            rx.vstack(
                                rx.text("No hay usuarios registrados aún.", color="gray.500"),
                                spacing="4"
                            )
                        ),
                        p="6",
                        border="1px solid #e2e8f0",
                        border_radius="lg",
                        bg=rx.color_mode_cond(light="white", dark="#1a202c"),
                        width="100%",
                        overflow_x="auto"
                    ),
                    
                    spacing="4",
                    align_items="center",
                    width="100%"
                ),
                bg=rx.color_mode_cond(light="white", dark="#1a202c"),
                max_width="1200px",
                p="8",
                box_shadow="2xl",
                border_radius="2xl",
                width="100%"
            ),
            size="3"
        ),
        rx.container(
            navbar(),
            rx.center(
                access_denied_widget("Solo funcionarios autenticados pueden ver esta página."),
                size="3"
            )
        )
    )


def cambiar_rol_page() -> rx.Component:
    """Página para cambiar el rol de ciudadano a funcionario."""
    return rx.cond(
        State.es_autentica & (State.rol_usuario == "funcionario"),
        rx.container(
            navbar(),
            rx.center(
                rx.vstack(
                    rx.heading("Cambiar Rol de Usuario", size="6", color=rx.color_mode_cond(light="black", dark="white")),
                    rx.text("Promueve un ciudadano a funcionario", color=rx.color_mode_cond(light="gray.600", dark="gray.300"), font_size="sm"),
                    
                    rx.card(
                        rx.vstack(
                            rx.vstack(
                                rx.text("Correo del usuario a promover", font_weight="semibold", color=rx.color_mode_cond(light="black", dark="white")),
                                rx.input(
                                    placeholder="usuario@ejemplo.com",
                                    value=State.cambiar_rol_email,
                                    on_change=State.set_cambiar_rol_email,
                                    width="100%",
                                    type="email",
                                ),
                            ),
                            
                            rx.button(
                                "Promover a Funcionario",
                                on_click=State.cambiar_rol_ciudadano_a_funcionario,
                                color_scheme="blue",
                                width="100%",
                                is_disabled=~(State.cambiar_rol_email != "")
                            ),
                            
                            rx.cond(
                                State.cambiar_rol_mensaje != "",
                                rx.box(
                                    rx.text(
                                        State.cambiar_rol_mensaje,
                                        color=rx.cond(
                                            State.cambiar_rol_mensaje.contains("✅"),
                                            "green.500",
                                            "red.500"
                                        ),
                                        font_size="sm",
                                        white_space="pre-wrap"
                                    ),
                                    p="4",
                                    border_radius="md",
                                    bg=rx.color_mode_cond(light="#f0fdf4", dark="#1f2937"),
                                    width="100%"
                                )
                            ),
                            
                            spacing="4",
                            align_items="stretch",
                            width="100%"
                        ),
                        p="8",
                        bg=rx.color_mode_cond(light="white", dark="#1a202c"),
                        border_radius="2xl",
                        box_shadow="2xl",
                        max_width="500px",
                        width="100%"
                    ),
                    
                    spacing="4",
                    align_items="center",
                    width="100%"
                ),
                size="3"
            ),
            bg=rx.color_mode_cond(light="#f8fafc", dark="#0f172a")
        ),
        rx.container(
            navbar(),
            rx.center(
                access_denied_widget("Solo funcionarios autenticados pueden acceder a esta función."),
                size="3"
            )
        )
    )


app = rx.App()
app.add_page(index, route="/", title="Inicio - Sistema PQRS")
app.add_page(registro_page, route="/registro", title="Registro de Ciudadano")
app.add_page(registro_funcionario_page, route="/registro-funcionario", title="Registro de Funcionario")
app.add_page(login_page, route="/login", title="Iniciar Sesión")
app.add_page(solicitudes_page, route="/solicitudes", title="Nueva Solicitud PQRS")
app.add_page(change_password_page, route="/cambiar-contrasena", title="Cambiar Contraseña")
app.add_page(dashboard, route="/dashboard", title="Panel de Ciudadano")
app.add_page(funcionario_dashboard, route="/dashboard-funcionario", title="Panel de Funcionario")
app.add_page(usuarios_page, route="/usuarios", title="Gestión de Usuarios")
app.add_page(cambiar_rol_page, route="/cambiar-rol", title="Cambiar Rol de Usuario")
app.add_page(consultar_estado_page, route="/consultar-estado", title="Consultar Estado de Solicitud")
app.add_page(politica_privacidad_page, route="/politica-privacidad", title="Política de Privacidad")
app.add_page(reportes_page, route="/reportes", title="Reportes PQRS", on_load=State.cargar_solicitudes)

if app._api is not None:
    app._api.mount(
        "/assets/uploads",
        StaticFiles(directory=str(UPLOAD_DIR), check_dir=False),
        name="uploads",
    )
    
    # Endpoints para descargas con "Guardar como"
    from starlette.responses import Response
    
    async def download_file(download_id: str):
        """Descarga un archivo del almacenamiento temporal."""
        try:
            if download_id not in TEMP_DOWNLOADS:
                return Response(
                    content=b"Archivo no encontrado o expirado",
                    status_code=404,
                    media_type="text/plain"
                )
            
            file_data = TEMP_DOWNLOADS[download_id]
            filename = file_data.get("filename", "descargar.bin")
            data = file_data.get("data", b"")
            mime = file_data.get("mime", "application/octet-stream")
            
            # Limpiar después de acceder (descarga única)
            del TEMP_DOWNLOADS[download_id]
            
            return Response(
                content=data,
                media_type=mime,
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )
        except Exception as e:
            print(f"Error en download_file: {e}")
            return Response(
                content=b"Error al descargar el archivo",
                status_code=500,
                media_type="text/plain"
            )
    
