"""Sistema de Gestión de PQRS para Empresas Públicas - Sprint 1: Registro de Ciudadanos"""
import re
from datetime import datetime, date, timedelta
import random
import bcrypt
import base64
import json
import uuid
import os
import shutil
from pathlib import Path
from urllib.parse import quote
import reflex as rx
from .usuario_model import Usuario, Solicitud
from .solicitud_estado_historial_model import SolicitudEstadoHistorial
from sqlmodel import select, SQLModel, create_engine, text, Session
from rxconfig import config
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from starlette.staticfiles import StaticFiles
from dotenv import load_dotenv
from reflex.components import recharts as rc
from notificaciones import (
    notificar_solicitud_creada,
    notificar_cambio_estado,
    notificar_respuesta_final,
    enviar_correo_smtp,
    formatear_nota_documento,
    get_app_base_url,
)

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
    if 'acepta_notificaciones' not in columnas:
        conn.execute(text("ALTER TABLE usuario ADD COLUMN acepta_notificaciones INTEGER DEFAULT 0"))
    if 'acepta_politica_datos' not in columnas:
        conn.execute(text("ALTER TABLE usuario ADD COLUMN acepta_politica_datos INTEGER DEFAULT 0"))
    conn.commit()

# Asegura que la columna persona_vulnerable exista en la tabla solicitud cuando se añada al modelo
with engine.connect() as conn:
    result = conn.execute(text("PRAGMA table_info('solicitud')"))
    columnas = [row[1] for row in result]
    if 'persona_vulnerable' not in columnas:
        conn.execute(text("ALTER TABLE solicitud ADD COLUMN persona_vulnerable TEXT"))
    if 'fecha_respuesta' not in columnas:
        conn.execute(text("ALTER TABLE solicitud ADD COLUMN fecha_respuesta TIMESTAMP"))
    # Backfill: si una solicitud ya está cerrada, usar el último cambio de estado como fecha_respuesta.
    try:
        conn.execute(
            text(
                """
                UPDATE solicitud
                SET fecha_respuesta = (
                    SELECT MAX(h.fecha_cambio)
                    FROM solicitudestadohistorial AS h
                    WHERE h.solicitud_id = solicitud.id
                      AND lower(coalesce(h.estado_nuevo,'')) IN ('cerrada','resuelta','finalizada','respondida')
                )
                WHERE fecha_respuesta IS NULL
                  AND lower(coalesce(estado,'')) IN ('cerrada','resuelta','finalizada','respondida')
                """
            )
        )
    except Exception as e:
        print("No se pudo backfillear fecha_respuesta:", e)
    conn.commit()

def tiene_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def confirmar_contraseña(contraseña: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(contraseña.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False


def normalizar_texto(valor: Any) -> str:
    """Quita espacios sobrantes y aplica formato título para campos de registro."""
    if valor is None:
        return ""
    texto = re.sub(r"\s+", " ", str(valor).strip())
    return texto.title() if texto else ""


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


REFLEX_UPLOAD_DIRS = (
    BASE_DIR / ".web" / "uploaded_files",
    BASE_DIR / ".web" / "backend" / "uploaded_files",
    BASE_DIR / "uploaded_files",
)


def _resolver_ruta_archivo_existente(ruta: str) -> str:
    """Devuelve ruta absoluta si el archivo existe en disco."""
    if not ruta:
        return ""
    candidato = Path(ruta)
    if candidato.is_file():
        return str(candidato.resolve())

    candidatos_busqueda = [
        candidato,
        BASE_DIR / ruta,
        BASE_DIR / ".web" / ruta,
        BASE_DIR / ".web" / "uploaded_files" / candidato.name,
    ]
    for base in REFLEX_UPLOAD_DIRS:
        candidatos_busqueda.extend([base / candidato.name, base / ruta.lstrip("/\\")])
    candidatos_busqueda.append(UPLOAD_DIR / candidato.name)

    for path in candidatos_busqueda:
        if path.is_file():
            return str(path.resolve())
    return ""


def persistir_archivo_en_uploads(
    item: Any,
    nombre_preferido: str = "",
    prefijo: str = "adjunto",
) -> str:
    """Guarda un archivo subido en UPLOAD_DIR y devuelve la ruta absoluta."""
    if item is None:
        return ""

    if isinstance(item, list):
        if not item:
            return ""
        item = item[0]

    os.makedirs(UPLOAD_DIR, exist_ok=True)

    def _guardar_bytes(data: bytes, nombre: str) -> str:
        nombre_limpio = sanitizar_nombre_archivo(nombre)
        destino = UPLOAD_DIR / nombre_limpio
        with open(destino, "wb") as f:
            f.write(data)
        return str(destino.resolve())

    if isinstance(item, str):
        if item.startswith("data:"):
            header, b64 = item.split(",", 1)
            mime = header.split(";")[0].split(":")[1] if ":" in header else ""
            ext = mime.split("/")[-1] if "/" in mime else "bin"
            nombre = nombre_preferido or f"{prefijo}_{uuid.uuid4().hex}.{ext}"
            if not os.path.splitext(nombre)[1] and ext not in ("", "bin"):
                nombre = f"{nombre}.{ext}"
            return _guardar_bytes(base64.b64decode(b64), nombre)

        existente = _resolver_ruta_archivo_existente(item)
        if existente:
            destino = UPLOAD_DIR / Path(existente).name
            if Path(existente).resolve() != destino.resolve():
                shutil.copy2(existente, destino)
            return str(destino.resolve())
        return ""

    if isinstance(item, dict):
        nombre = sanitizar_nombre_archivo(
            item.get("name") or item.get("filename") or nombre_preferido or f"{prefijo}_{uuid.uuid4().hex}"
        )
        contenido = item.get("content") or item.get("data") or item.get("file")
        if contenido:
            if isinstance(contenido, str) and contenido.startswith("data:"):
                _, b64 = contenido.split(",", 1)
                data = base64.b64decode(b64)
            elif isinstance(contenido, str):
                data = base64.b64decode(contenido)
            else:
                data = bytes(contenido)
            return _guardar_bytes(data, nombre)

        for clave in ("path", "filepath", "full_path", "tmp_path", "file_path"):
            existente = _resolver_ruta_archivo_existente(str(item.get(clave) or ""))
            if existente:
                destino = UPLOAD_DIR / Path(existente).name
                if Path(existente).resolve() != destino.resolve():
                    shutil.copy2(existente, destino)
                return str(destino.resolve())
        return ""

    nombre_obj = (
        getattr(item, "filename", None)
        or getattr(item, "name", None)
        or nombre_preferido
        or f"{prefijo}_{uuid.uuid4().hex}"
    )
    for attr in ("path", "file_path", "filepath", "full_path"):
        existente = _resolver_ruta_archivo_existente(str(getattr(item, attr, "") or ""))
        if existente:
            destino = UPLOAD_DIR / sanitizar_nombre_archivo(str(nombre_obj))
            if Path(existente).resolve() != destino.resolve():
                shutil.copy2(existente, destino)
            return str(destino.resolve())

    return ""


def enviar_correo_bienvenida(email_destinatario: str, email_usuario: str):
    """Envía un correo de bienvenida después de un registro exitoso.

    El servicio se activa desde `_crear_usuario()` cuando un ciudadano o funcionario
    se registra correctamente. Usa SMTP (`EMAIL_SENDER`, `EMAIL_PASSWORD`, `SMTP_SERVER`, `SMTP_PORT`).
    Si falla, guarda el correo en local para reintento.
    """
    try:
        email_sender = os.getenv("EMAIL_SENDER", "enlacepqrs1755@gmail.com")
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
                        <a href="{get_app_base_url() or 'http://localhost:3000'}/login" style="background-color: #1e40af; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; font-weight: bold;">Ir a Iniciar Sesión</a>
                    </p>
                    
                    <hr style="border: 1px solid #ddd; margin: 20px 0;">
                    <p style="color: #666; font-size: 14px;"><strong>Recuerda:</strong> Nunca compartas tu contraseña con terceros. El equipo de soporte nunca te pedirá tu contraseña.</p>
                    <p style="color: #666; font-size: 14px;">Si tienes preguntas o problemas, contacta a nuestro equipo de soporte.</p>
                    <p style="text-align: center; color: #999; font-size: 12px; margin-top: 30px;">© 2026 {empresa_nombre}. Todos los derechos reservados.</p>
                </div>
            </body>
        </html>
        """

        if enviar_correo_smtp(email_destinatario, mensaje["Subject"], html):
            print(f"✅ Correo enviado exitosamente a {email_destinatario} vía SMTP")
            return True

        print("❌ No se pudo enviar el correo de bienvenida por SMTP. Revisa EMAIL_SENDER y EMAIL_PASSWORD.")

        # Registrar correo fallido en disco para reintento manual
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

def enviar_correo_notificacion(email_destinatario: str, asunto: str, cuerpo: str) -> bool:
    """Envía una notificación por correo electrónico al ciudadano sobre actualizaciones en su solicitud."""
    try:
        empresa_nombre = os.getenv("EMPRESA_NOMBRE", "Sistema de Gestión de PQRS")
        html = (
            f"<html><body>"
            f"<pre style='font-family:Arial,sans-serif'>{cuerpo}</pre>"
            f"<p style='color:#666;font-size:12px'>© 2026 {empresa_nombre}</p>"
            f"</body></html>"
        )
        if enviar_correo_smtp(email_destinatario, asunto, html):
            print(f"✅ Notificación enviada a {email_destinatario} (SMTP)")
            return True
        print(f"⚠️ No se pudo enviar notificación a {email_destinatario}")
        return False
    except Exception as e:
        print(f"❌ Error inesperado al enviar notificación: {e}")
        return False



# quitar prints de prueba

class State(rx.State):
    # --- Modal de Vencimiento de Reportes ---
    vencimiento_modal_abierto: bool = False
    rango_vencimiento_seleccionado: str = ""
    solicitudes_vencimiento_filtradas: list[dict] = []
    detalle_solicitud_modal_abierto: bool = False

    def abrir_detalle_solicitud(self, solicitud_id: int):
        for s in self.solicitudes:
            if s.get("id") == solicitud_id:
                self.solicitud_consultada = s
                self.detalle_solicitud_modal_abierto = True
                break

    def cerrar_detalle_solicitud(self):
        self.detalle_solicitud_modal_abierto = False

    def abrir_vencimiento_modal(self, data: Any):
        import logging
        print(f"[LOG] abrir_vencimiento_modal llamado con data: {data} (tipo: {type(data)})")
        
        rango = ""
        # 1. Si es un diccionario directo
        if isinstance(data, dict):
            # Podría venir en data['name'] o data['activeLabel']
            rango = data.get("name") or data.get("activeLabel") or ""
        # 2. Si viene de una lista de payload (en algunos charts de Recharts)
        elif isinstance(data, list) and len(data) > 0:
            item = data[0]
            if isinstance(item, dict):
                rango = item.get("name") or item.get("payload", {}).get("name", "")
        # 3. Si es un string directo
        elif isinstance(data, str):
            rango = data
            
        print(f"[LOG] Rango determinado: '{rango}'")
        if not rango:
            print(f"[LOG] Rango vacío, no se hace nada.")
            return

        self.rango_vencimiento_seleccionado = rango
        self.solicitudes_vencimiento_filtradas = []
        
        filtered = []
        for s in (self.solicitudes_filtradas or []):
            rem = s.get("semaforo_remaining")
            
            match = False
            if rem is None:
                if rango == ">10 días":
                    match = True
            else:
                if rango == "Vencidas" and rem <= 0:
                    match = True
                elif rango == "1-5 días" and 1 <= rem <= 5:
                    match = True
                elif rango == "6-10 días" and 6 <= rem <= 10:
                    match = True
                elif rango == ">10 días" and rem > 10:
                    match = True
                
            if match:
                filtered.append({
                    "id": s.get("id"),
                    "radicado": s.get("radicado") or f"ID-{s.get('id')}",
                    "tipo_solicitud": s.get("tipo_solicitud") or s.get("tipo_pqrs") or "N/A",
                    "asunto": s.get("asunto") or "Sin asunto",
                    "creado_por": s.get("creado_por") or "N/A",
                    "estado": s.get("estado") or "Radicada",
                    "area_responsable": s.get("area_responsable") or "N/A",
                    "semaforo_remaining": s.get("semaforo_remaining"),
                    "semaforo_fill": s.get("semaforo_fill") or "gray",
                    "is_expired": bool(rem is not None and rem <= 0),
                    "remaining_str": "Vencida" if (rem is not None and rem <= 0) else (f"{int(rem)} días" if rem is not None else "N/A")
                })
        
        print(f"[LOG] Encontradas {len(filtered)} solicitudes para el rango '{rango}'")
        self.solicitudes_vencimiento_filtradas = filtered
        self.vencimiento_modal_abierto = True

    def cerrar_vencimiento_modal(self):
        self.vencimiento_modal_abierto = False
        self.rango_vencimiento_seleccionado = ""
        self.solicitudes_vencimiento_filtradas = []

    # --- Historial de estados ---
    historial_modal_abierto: bool = False
    historial_solicitud_id: int = 0
    historial_estados: list[dict[str, Any]] = []

    def abrir_historial(self, solicitud_id: int):
        """Carga el historial de estados de una solicitud y abre el modal."""
        self.historial_solicitud_id = solicitud_id
        self.historial_estados = []
        from .solicitud_estado_historial_model import SolicitudEstadoHistorial
        with Session(engine) as session:
            rows = session.exec(
                select(SolicitudEstadoHistorial)
                .where(SolicitudEstadoHistorial.solicitud_id == solicitud_id)
                .order_by(SolicitudEstadoHistorial.fecha_cambio)
            ).all()
            self.historial_estados = [
                {
                    "fecha": h.fecha_cambio.strftime("%Y-%m-%d %H:%M"),
                    "anterior": h.estado_anterior,
                    "nuevo": h.estado_nuevo,
                    "obs": h.observaciones or ""
                }
                for h in rows
            ]
        self.historial_modal_abierto = True

    def cerrar_historial(self):
        self.historial_modal_abierto = False
        self.historial_solicitud_id = 0
        self.historial_estados = []


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
    documentos: list[dict[str, str | int]] = []
    documento_nombres: list[str] = []
    documento_nombre: str = ""
    documento_previews: list[dict[str, str]] = []
    descripcion_len: int = 0
    query_solicitud: str = ""
    filter_tipo_solicitud: str = "Todos"
    filter_estado_solicitud: str = "Todos"
    filter_dias_restantes: str = "Todos"
    solicitudes: list[dict[str, Any]] = []
    editar_solicitud_id: int = 0
    eliminar_solicitud_id: int = 0
    solicitud_mensaje: str = ""


    error_de_registro: str = ""
    succes: str = ""
    error_de_contraseña: str = ""
    succes2: str = ""
    
    id_usuario: str = rx.Cookie("0")
    es_autentica: str = rx.Cookie("false")
    email_actual: str = rx.Cookie("")
    correo_usuario: str = rx.Cookie("")
    rol_usuario: str = rx.Cookie("")
    nombres: str = rx.Cookie("")
    show_password: bool = False
    # Campos para cambiar contraseña
    current_password: str = ""
    new_password: str = ""
    confirm_new_password: str = ""
    change_pw_message: str = ""
    # Campos para cambiar rol de ciudadano a funcionario
    cambiar_rol_email: str = ""
    cambiar_rol_mensaje: str = ""
    confirmar_promocion_rol: bool = False
    usuarios_registrados: list[dict[str, Any]] = []
    # Campos para editar estado de solicitud
    editar_estado_id: int = 0
    nuevo_estado: str = ""
    respuesta_solicitud: str = ""
    mensaje_actualizar_estado: str = ""
    respuesta_documento: str = ""
    respuesta_documento_nombre: str = ""
    respuesta_documento_preview_src: str = ""
    respuesta_documento_es_imagen: bool = False
    # Variables para modal de política y validaciones
    modal_politica_visible: bool = False
    archivo_error_mensaje: str = ""
    correo_confirmacion_visible: bool = False
    correo_confirmacion_mensaje: str = ""
    ayuda_seccion_abierta: str = "estados"
    registro_seccion_abierta: str = "cuenta"
    registro_paso_habilitado: int = 1
    
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
    def id_usuario_num(self) -> int:
        """Convierte el id de cookie a entero seguro."""
        try:
            return int(str(self.id_usuario or "0"))
        except Exception:
            return 0

    @rx.var
    def es_autenticada(self) -> bool:
        """Normaliza la cookie de sesión a booleano."""
        return str(self.es_autentica or "").strip().lower() in {"true", "1", "yes", "si", "sí"}

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
            {"name": "En Proceso", "cantidad": int(self.numero_solicitudes_actualizadas)},
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
        """Genera un CSV en memoria desde `solicitudes_filtradas` para descarga respetando filtros."""
        try:
            import csv
            import io
            from datetime import datetime

            data = self.solicitudes_filtradas or []
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
        """Genera Excel en memoria con datos FILTRADOS y dispara la descarga."""
        try:
            import io
            from datetime import datetime
            import pandas as pd

            data = self.solicitudes_filtradas or []
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
        """Genera CSV en memoria con datos FILTRADOS y dispara la descarga."""
        try:
            import csv
            import io
            from datetime import datetime

            data = self.solicitudes_filtradas or []
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

    def toggle_menu_descarga(self):
        """Alterna la visibilidad del menú de descarga."""
        self.mostrar_menu_descarga = not self.mostrar_menu_descarga
        
     
    @rx.var
    def numero_solicitudes(self) -> str:
        return str(len(self.solicitudes_filtradas or []))
    
    @rx.var
    def numero_solicitudes_radicadas(self) -> str:
        return str(sum(1 for solicitud in (self.solicitudes_filtradas or []) if (str(solicitud.get('estado') or '').strip().lower()) == 'radicada'))
    
    @rx.var
    def numero_solicitudes_actualizadas(self) -> str:
        # 'en proceso', 'actualizada', 'asignada' y 'en revisión' representan solicitudes activas / en proceso
        return str(sum(1 for solicitud in (self.solicitudes_filtradas or []) if (str(solicitud.get('estado') or '').strip().lower()) in ('en proceso', 'actualizada', 'asignada', 'en revisión', 'en revision')))
    
    @rx.var
    def numero_solicitudes_cerradas(self) -> str:
        return str(sum(1 for solicitud in (self.solicitudes_filtradas or []) if (str(solicitud.get('estado') or '').strip().lower()) in ('cerrada', 'finalizada', 'resuelta')))
    
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
        for solicitud in self.solicitudes_filtradas or []:
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
        """Calcula el tiempo promedio de respuesta diario para los últimos 30 días.
        Devuelve lista de dicts: {month: '26 May', dias: float}
        """
        today = date.today()
        start_date = today - timedelta(days=29)
        
        # preparar buckets por día
        buckets: dict[str, list[int]] = {}
        for i in range(30):
            d = start_date + timedelta(days=i)
            buckets[d.strftime("%Y-%m-%d")] = []

        for s in (self.solicitudes_filtradas or []):
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
            result.append({"month": label, "dias": avg})

        return result

    @rx.var
    def compliance_percentage(self) -> int:
        """Calcula cumplimiento: (solicitudes resueltas / total) * 100.
        Resueltas = estado 'Respondida' o 'Cerrada'.
        """
        total = len(self.solicitudes_filtradas or [])
        if total == 0:
            return 0
        closed_states = {"resuelta", "cerrada", "respondida", "finalizada"}
        cerradas = sum(1 for s in (self.solicitudes_filtradas or []) if (s.get('estado') or "").lower() in closed_states)
        return int((cerradas / total) * 100) if total > 0 else 0

    @rx.var
    def compliance_chart_data(self) -> list[dict]:
        total = len(self.solicitudes_filtradas or [])
        closed_states = {"resuelta", "cerrada", "respondida", "finalizada"}
        cerradas = sum(1 for s in (self.solicitudes_filtradas or []) if (s.get('estado') or "").lower() in closed_states)
        no_cerradas = total - cerradas
        return [
            {"name": "Cerradas", "value": cerradas, "fill": "#10b981"},
            {"name": "No cerradas", "value": max(0, no_cerradas), "fill": "#ef4444"},
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
            
            estado_raw = str(solicitud.get("estado") or "").strip().lower()
            closed_states = {"respondida", "respondido", "cerrada", "cerrado", "finalizada", "finalizado", "resuelta", "resuelto"}
            
            ref = date.today()
            if estado_raw in closed_states and solicitud.get("fecha_respuesta"):
                try:
                    ref_dt = datetime.fromisoformat(str(solicitud.get("fecha_respuesta")))
                    ref = ref_dt.date()
                except Exception:
                    try:
                        from dateutil import parser as _p
                        ref = _p.parse(str(solicitud.get("fecha_respuesta"))).date()
                    except Exception:
                        pass

            # Contar días calendario desde la fecha de creación hasta la referencia calculada.
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
        # Lee solicitudes_filtradas y devuelve conteo por color (dinámico por filtros)
        holidays = set()  # puedes poblar con una consulta a festivos si la tienes
        counts = {"verde": 0, "amarillo": 0, "rojo": 0}
        # Estados que consideramos cerrados/resueltos (normalizados en minúsculas)
        closed_states = {"respondida", "respondido", "respondida", "respondida", "cerrada", "cerrado", "finalizada", "finalizado"}
        for s in (self.solicitudes_filtradas or []):
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
    search_area_query: str = ""
    
    @rx.var
    def top_areas(self) -> list[dict]:
        """Devuelve las áreas responsables por cantidad de solicitudes filtradas (de mayor a menor), filtrables por búsqueda.
        """
        counts = {}
        for s in (self.solicitudes_filtradas or []):
            a = s.get('area_responsable') or 'N/A'
            counts[a] = counts.get(a, 0) + 1
        items = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        
        q = self.search_area_query.strip().lower()
        if q:
            items = [item for item in items if q in str(item[0]).lower()]
            
        return [{"name": name, "total": total} for name, total in items]

    @rx.var
    def solicitudes_por_vencer_data(self) -> list[dict]:
        counts = {
            "Vencidas": 0,
            "1-5 días": 0,
            "6-10 días": 0,
            ">10 días": 0,
        }
        for s in (self.solicitudes_filtradas or []):
            rem = s.get("semaforo_remaining")
            if rem is None:
                counts[">10 días"] += 1
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
        return sum(item.get("cantidad", 0) for item in self.solicitudes_por_vencer_data)

    @rx.var
    def kpi_counts(self) -> dict:
        """Devuelve los 3 KPIs: pendientes (>10 días), en proceso (1-10 días), cerradas (estados cerrados).
        Usa solicitudes filtradas para ser dinámico.
        """
        closed_states = {"respondida", "respondido", "cerrada", "cerrado", "finalizada", "finalizado", "resuelta", "resuelto"}
        pendientes = 0
        en_curso = 0
        cerradas = 0
        for s in (self.solicitudes_filtradas or []):
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
        return int(self.numero_solicitudes_radicadas)

    @rx.var
    def kpi_en_curso_count(self) -> int:
        return int(self.numero_solicitudes_actualizadas)

    @rx.var
    def kpi_cerradas_count(self) -> int:
        return int(self.numero_solicitudes_cerradas)

    @rx.var
    def solicitudes_filtradas(self) -> list[dict]:
        query = (self.query_solicitud or "").strip().lower()
        tipo = (self.filter_tipo_solicitud or "Todos").lower()
        estado = (self.filter_estado_solicitud or "Todos").lower()
        rango = (self.filter_dias_restantes or "Todos").lower()
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
            if estado not in {"todas", "todos"}:
                s_est = str(solicitud.get("estado", "")).lower()
                if estado == "en proceso":
                    if s_est not in ("en proceso", "actualizada"):
                        continue
                elif s_est != estado:
                    continue
            if rango not in {"todas", "todos"}:
                expired = bool(solicitud.get("semaforo_expired", False))
                remaining_raw = solicitud.get("semaforo_remaining", 0)
                try:
                    remaining = int(float(str(remaining_raw).strip() or "0"))
                except Exception:
                    remaining = 0
                if rango == "vencidas":
                    if not expired:
                        continue
                elif rango == "0-3":
                    if expired or remaining < 0 or remaining > 3:
                        continue
                elif rango == "4-10":
                    if expired or remaining < 4 or remaining > 10:
                        continue
                elif rango == "11+":
                    if expired or remaining < 11:
                        continue
            resultados.append(solicitud)
        return resultados

    @rx.var
    def solicitudes_abiertas(self) -> list[dict]:
        closed_states = {"cerrada", "resuelta", "finalizada", "respondida"}
        return [
            s
            for s in (self.solicitudes_filtradas or [])
            if str(s.get("estado") or "").strip().lower() not in closed_states
        ]

    @rx.var
    def solicitudes_cerradas_lista(self) -> list[dict]:
        closed_states = {"cerrada", "resuelta", "finalizada", "respondida"}
        return [
            s
            for s in (self.solicitudes_filtradas or [])
            if str(s.get("estado") or "").strip().lower() in closed_states
        ]

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

    def set_filter_dias_restantes(self, value: str):
        self.filter_dias_restantes = value or "Todos"

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
        """Validaciones simples para mostrar iconos de confirmación. Retorna True si el campo parece correcto."""
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

    def _infer_mime_type(self, name: str) -> str:
        ext = os.path.splitext((name or "").lower())[1].lstrip(".")
        if ext in {"png"}:
            return "image/png"
        if ext in {"jpg", "jpeg"}:
            return "image/jpeg"
        if ext in {"webp"}:
            return "image/webp"
        if ext in {"gif"}:
            return "image/gif"
        if ext in {"pdf"}:
            return "application/pdf"
        return "application/octet-stream"

    def _build_file_preview(self, item: Any) -> dict[str, str]:
        name = "adjunto"
        raw_content = ""
        if isinstance(item, dict):
            name = item.get("name") or item.get("filename") or "adjunto"
            if item.get("src"):
                return {
                    "name": str(name),
                    "src": str(item.get("src") or ""),
                    "mime": str(item.get("mime") or self._infer_mime_type(str(name))),
                }
            raw_content = str(item.get("content") or item.get("data") or "")
        elif isinstance(item, str):
            name = os.path.basename(item) or "adjunto"
        else:
            name = (
                getattr(item, "name", None)
                or getattr(item, "filename", None)
                or "adjunto"
            )

        mime = self._infer_mime_type(name)
        es_imagen = mime.startswith("image/")
        src = ""
        if es_imagen and raw_content:
            if raw_content.startswith("data:"):
                src = raw_content
            else:
                src = f"data:{mime};base64,{raw_content}"
        return {"name": name, "src": src, "mime": mime}

    def _upload_to_preview_dict(self, upload: rx.UploadFile) -> dict[str, str | int]:
        name = (
            getattr(upload, "name", None)
            or getattr(upload, "filename", None)
            or "adjunto"
        )
        size = int(getattr(upload, "size", 0) or 0)
        path_val = str(getattr(upload, "path", "") or "")
        mime = self._infer_mime_type(name)
        src = ""
        if mime.startswith("image/"):
            try:
                file_obj = getattr(upload, "file", None)
                if file_obj is not None:
                    if hasattr(file_obj, "seek"):
                        file_obj.seek(0)
                    content_bytes = file_obj.read()
                    if content_bytes:
                        src = f"data:{mime};base64,{base64.b64encode(content_bytes).decode('utf-8')}"
            except Exception:
                src = ""
        return {"name": str(name), "size": size, "path": path_val, "src": src, "mime": mime}

    def set_documento(self, documento: list[rx.UploadFile]):
        """Actualiza adjuntos del ciudadano sin guardar UploadFile en el estado."""
        self.documentos = []
        self.documento_nombres = []
        self.documento = ""
        self.documento_nombre = ""
        self.documento_previews = []
        self.archivo_error_mensaje = ""

        allowed_ext = {"pdf", "png", "jpg", "jpeg", "zip"}
        max_files = 3
        max_total_size = 10 * 1024 * 1024
        archivos = documento if isinstance(documento, list) else [documento]

        if len(archivos) > max_files:
            self.archivo_error_mensaje = "Solo puedes adjuntar hasta 3 archivos."
            return

        normalized: list[dict[str, str | int]] = []
        total_size = 0
        for item in archivos:
            item_data = self._upload_to_preview_dict(item)
            name = str(item_data.get("name") or "adjunto")
            size = int(item_data.get("size") or 0)
            ext = os.path.splitext(name)[1].lower().lstrip(".")
            if ext not in allowed_ext:
                self.archivo_error_mensaje = "Solo se aceptan archivos PDF, PNG, JPG o ZIP."
                return
            if size > max_total_size:
                self.archivo_error_mensaje = "Cada archivo no puede superar los 10MB."
                return
            total_size += size
            normalized.append(item_data)

        if total_size > max_total_size:
            self.archivo_error_mensaje = "La suma de los archivos no puede superar los 10MB."
            return

        self.documentos = normalized
        self.documento_nombres = [str(item.get("name") or "adjunto") for item in normalized]
        self.documento_nombre = ", ".join(self.documento_nombres)
        self.documento_previews = [self._build_file_preview(item) for item in normalized]

    def set_editar_solicitud_id(self, id: int):
        self.editar_solicitud_id = id

    def set_eliminar_solicitud_id(self, id: int):
        self.eliminar_solicitud_id = id

    def eliminar_documento(self, index: int):
        # Reconstruir listas para evitar comportamiento reactivo inesperado
        if not (0 <= index < len(self.documentos)):
            return
        nuevos_docs: list[dict[str, str | int]] = []
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
        self.documento_previews = [self._build_file_preview(item) for item in self.documentos]
        self.archivo_error_mensaje = ""

    def eliminar_documento_por_nombre(self, nombre: str):
        if nombre in self.documento_nombres:
            index = self.documento_nombres.index(nombre)
            self.eliminar_documento(index)

    def quitar_todos_documentos(self):
        self.documento = ""
        self.documentos = []
        self.documento_nombres = []
        self.documento_nombre = ""
        self.documento_previews = []
        self.archivo_error_mensaje = ""

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

    def set_respuesta_documento(self, documento: list[rx.UploadFile]):
        """Actualiza el documento adjunto en la respuesta del funcionario."""
        self.respuesta_documento_preview_src = ""
        self.respuesta_documento_es_imagen = False
        archivo = documento[0] if isinstance(documento, list) and documento else None
        if archivo is not None:
            item_data = self._upload_to_preview_dict(archivo)
            name = str(item_data.get("name") or "respuesta_adjunto")
            path_val = str(item_data.get("path") or "")
            self.respuesta_documento_nombre = name
            self.respuesta_documento = path_val
            self.respuesta_documento_preview_src = str(item_data.get("src") or "")
            self.respuesta_documento_es_imagen = self.respuesta_documento_preview_src != ""
        else:
            self.respuesta_documento_nombre = ""
            self.respuesta_documento = ""

    def quitar_respuesta_documento(self):
        self.respuesta_documento = ""
        self.respuesta_documento_nombre = ""
        self.respuesta_documento_preview_src = ""
        self.respuesta_documento_es_imagen = False

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
        self.respuesta_documento_preview_src = ""
        self.respuesta_documento_es_imagen = False
        self.mensaje_actualizar_estado = ""

    def set_consulta_radicado(self, val: str):
        self.consulta_radicado = val

    def toggle_ayuda_seccion(self, seccion: str):
        self.ayuda_seccion_abierta = "" if self.ayuda_seccion_abierta == seccion else seccion

    def set_registro_seccion_abierta(self, seccion: str):
        seccion = seccion or "cuenta"
        paso = {"cuenta": 1, "identidad": 2, "ubicacion": 3}.get(seccion, 1)
        if paso <= self.registro_paso_habilitado:
            self.registro_seccion_abierta = seccion
            return
        self.error_de_registro = "Completa el paso actual para continuar."

    def _validar_paso_cuenta(self) -> bool:
        self.error_de_registro = ""
        correo = str(self.correo or "").strip()
        if not correo:
            self.error_de_registro = "Completa el correo electrónico."
            return False
        if not validar_correo(correo):
            self.error_de_registro = "Correo no válido."
            return False
        if not str(self.contraseña or "").strip():
            self.error_de_registro = "Completa la contraseña."
            return False
        if not cantida_minima_contraseña(self.contraseña):
            self.error_de_registro = "La contraseña debe tener al menos 8 caracteres, incluyendo mayúsculas, minúsculas, números y caracteres especiales."
            return False
        if not str(self.confirmar_contraseña or "").strip():
            self.error_de_registro = "Confirma la contraseña."
            return False
        if self.contraseña != self.confirmar_contraseña:
            self.error_de_registro = "Las contraseñas no coinciden."
            return False
        return True

    def _validar_paso_identidad(self) -> bool:
        self.error_de_registro = ""
        if not str(self.nombres or "").strip():
            self.error_de_registro = "Completa el campo Nombres."
            return False
        if not str(self.apellidos or "").strip():
            self.error_de_registro = "Completa el campo Apellidos."
            return False
        if not str(self.sexo or "").strip():
            self.error_de_registro = "Selecciona el sexo."
            return False
        if not str(self.tipo_identificacion or "").strip():
            self.error_de_registro = "Selecciona el tipo de identificación."
            return False
        if len(str(self.numero_identificacion or "").strip()) < 6:
            self.error_de_registro = "El número de identificación debe tener al menos 6 caracteres."
            return False
        if len(re.sub(r"\D", "", str(self.telefono or ""))) < 7:
            self.error_de_registro = "Ingresa un teléfono válido con al menos 7 dígitos."
            return False
        return True

    def continuar_a_identidad(self):
        if not self._validar_paso_cuenta():
            return
        self.registro_paso_habilitado = max(self.registro_paso_habilitado, 2)
        self.registro_seccion_abierta = "identidad"
        self.error_de_registro = ""

    def continuar_a_ubicacion(self):
        if not self._validar_paso_identidad():
            return
        self.registro_paso_habilitado = max(self.registro_paso_habilitado, 3)
        self.registro_seccion_abierta = "ubicacion"
        self.error_de_registro = ""

    def actualizar_estado_solicitud(self, files: Any = None):
        """Actualiza el estado de una solicitud con validación para cerrada y guarda historial."""
        self.mensaje_actualizar_estado = ""
        if not self.editar_estado_id or not self.nuevo_estado:
            self.mensaje_actualizar_estado = "Selecciona un estado válido."
            return
        if self.nuevo_estado == "Cerrada" and not self.respuesta_solicitud:
            self.mensaje_actualizar_estado = "No puedes cerrar una solicitud sin escribir una respuesta."
            return
        documento_respuesta_guardado = ""
        fuente_documento = files if files else self.respuesta_documento
        if fuente_documento:
            try:
                documento_respuesta_guardado = persistir_archivo_en_uploads(
                    fuente_documento,
                    nombre_preferido=self.respuesta_documento_nombre,
                    prefijo="respuesta",
                )
                if documento_respuesta_guardado:
                    self.respuesta_documento_nombre = os.path.basename(documento_respuesta_guardado)
                elif self.respuesta_documento_nombre:
                    print(
                        "No se pudo guardar el documento de respuesta en disco:",
                        self.respuesta_documento_nombre,
                    )
            except Exception as e:
                print(f"Error guardando documento de respuesta: {e}")
        estado_nuevo = self.nuevo_estado
        respuesta_enviada = self.respuesta_solicitud or ""
        datos_notificacion: dict[str, Any] | None = None
        try:
            with Session(engine) as session:
                solicitud_obj = session.get(Solicitud, self.editar_estado_id)
                if not solicitud_obj:
                    self.mensaje_actualizar_estado = "Solicitud no encontrada."
                    return
                estado_anterior = solicitud_obj.estado
                solicitud_obj.estado = estado_nuevo
                if respuesta_enviada:
                    solicitud_obj.respuesta = respuesta_enviada
                closed_states = {"cerrada", "resuelta", "finalizada", "respondida"}
                if str(estado_nuevo or "").strip().lower() in closed_states:
                    solicitud_obj.fecha_respuesta = datetime.now()
                if documento_respuesta_guardado:
                    solicitud_obj.respuesta = (solicitud_obj.respuesta or "") + f"\n\n[DOCUMENTO ADJUNTO: {os.path.basename(documento_respuesta_guardado)}]"
                session.add(solicitud_obj)
                historial = SolicitudEstadoHistorial(
                    solicitud_id=solicitud_obj.id,
                    estado_anterior=estado_anterior,
                    estado_nuevo=estado_nuevo,
                    fecha_cambio=datetime.now(),
                    observaciones=respuesta_enviada or None,
                )
                session.add(historial)
                session.commit()

                correo_dest = solicitud_obj.creado_por or ""
                nombre_sol = correo_dest
                if solicitud_obj.usuario_id:
                    usuario = session.get(Usuario, solicitud_obj.usuario_id)
                    if usuario:
                        correo_dest = usuario.email or correo_dest
                        nombre_sol = usuario.nombres or nombre_sol

                datos_notificacion = {
                    "correo": correo_dest,
                    "nombre": nombre_sol,
                    "radicado": solicitud_obj.radicado,
                    "tipo": solicitud_obj.tipo_solicitud,
                    "estado_anterior": estado_anterior,
                    "estado_nuevo": estado_nuevo,
                    "respuesta": respuesta_enviada,
                }

            self.mensaje_actualizar_estado = f"Estado actualizado a '{estado_nuevo}' correctamente."
            self.editar_estado_id = 0
            self.nuevo_estado = ""
            self.respuesta_solicitud = ""
            self.respuesta_documento = ""
            self.respuesta_documento_nombre = ""
            self.cargar_solicitudes()

            if datos_notificacion and datos_notificacion.get("correo"):
                try:
                    adjuntos_correo: list[str] = []
                    if datos_notificacion["estado_nuevo"].lower() == "cerrada":
                        descripcion_respuesta = datos_notificacion["respuesta"] or "Su solicitud ha sido cerrada."
                        if documento_respuesta_guardado:
                            doc_name = os.path.basename(documento_respuesta_guardado)
                            nota_doc, adjuntos_correo = formatear_nota_documento(
                                doc_name, documento_respuesta_guardado
                            )
                            descripcion_respuesta += nota_doc
                        notificar_respuesta_final(
                            nombre_solicitante=datos_notificacion["nombre"],
                            correo_solicitante=datos_notificacion["correo"],
                            numero_solicitud=datos_notificacion["radicado"],
                            tipo_pqrs=datos_notificacion["tipo"],
                            fecha_respuesta=datetime.now().strftime("%d/%m/%Y %H:%M"),
                            descripcion_respuesta=descripcion_respuesta,
                            adjuntos=adjuntos_correo or None,
                        )
                    else:
                        observaciones = datos_notificacion["respuesta"] or None
                        if documento_respuesta_guardado:
                            doc_name = os.path.basename(documento_respuesta_guardado)
                            nota_doc, adjuntos_correo = formatear_nota_documento(
                                doc_name, documento_respuesta_guardado
                            )
                            observaciones = (observaciones or "") + nota_doc
                        notificar_cambio_estado(
                            nombre_solicitante=datos_notificacion["nombre"],
                            correo_solicitante=datos_notificacion["correo"],
                            numero_solicitud=datos_notificacion["radicado"],
                            estado_anterior=datos_notificacion["estado_anterior"],
                            estado_nuevo=datos_notificacion["estado_nuevo"],
                            fecha_cambio=datetime.now().strftime("%d/%m/%Y %H:%M"),
                            observaciones=observaciones,
                            adjuntos=adjuntos_correo or None,
                        )
                except Exception as e:
                    print(f"Error enviando notificación: {e}")
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

    def cargar_datos_funcionario(self):
        self.cargar_solicitudes()
        self.cargar_usuarios()

    def export_reportes_excel(self):
        """Genera un Excel en memoria desde `solicitudes_filtradas` para descarga respetando filtros.
        
        Si pandas no está disponible, genera un CSV como fallback.
        """
        try:
            import io
            from datetime import datetime

            data = self.solicitudes_filtradas or []
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
        """Descarga el archivo Excel generado"""
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
        required_fields = [
            ("nombres", "Nombre"),
            ("apellidos", "Apellido"),
            ("tipo_identificacion", "Tipo de identificación"),
            ("numero_identificacion", "Número de identificación"),
            ("telefono", "Teléfono"),
            ("direccion", "Dirección"),
            ("departamento", "Departamento"),
            ("ciudad", "Ciudad"),
        ]
        for field_name, label in required_fields:
            if not str(getattr(self, field_name, "")).strip():
                self.error_de_registro = f"Completa el campo obligatorio: {label}."
                return

        if len(re.sub(r"\D", "", str(self.telefono))) < 7:
            self.error_de_registro = "Ingresa un teléfono válido con al menos 7 dígitos."
            return

        if len(str(self.numero_identificacion).strip()) < 6:
            self.error_de_registro = "El número de identificación debe tener al menos 6 caracteres."
            return

        if not self.acepta_politica_datos or not self.acepta_notificaciones:
            self.error_de_registro = "Debes aceptar la política de datos y recibir notificaciones para registrarte."
            return

    def _crear_usuario(self, rol: str, exito_mensaje: str):
        with rx.session() as session:
            correo_normalizado = str(self.correo or "").strip().lower()
            existing_user = session.exec(select(Usuario).where(Usuario.email == correo_normalizado)).first()
            if existing_user:
                self.error_de_registro = "El correo ya está registrado."
                return
            hashed = tiene_password(self.contraseña)
            nuevo_usuario = Usuario(
                email=correo_normalizado,
                Contraseña=hashed,
                rol=rol,
                is_active=True,
                Fecha_de_creacion=datetime.now(),
                tipo_identificacion=str(self.tipo_identificacion or "").strip(),
                numero_identificacion=str(self.numero_identificacion or "").strip(),
                nombres=normalizar_texto(self.nombres),
                apellidos=normalizar_texto(self.apellidos),
                genero=normalizar_texto(self.sexo),
                direccion=str(self.direccion or "").strip(),
                telefono=str(self.telefono or "").strip(),
                departamento=str(self.departamento or "").strip(),
                ciudad=str(self.ciudad or "").strip(),
                etnia=normalizar_texto(self.etnia),
                persona_vulnerable=normalizar_texto(self.persona_vulnerable_registro),
                acepta_notificaciones=bool(self.acepta_notificaciones),
                acepta_politica_datos=bool(self.acepta_politica_datos),
            )
            session.add(nuevo_usuario)
            session.commit()
        print(f"Usuario registrado: {self.correo}")
        # Dispara el correo de bienvenida inmediatamente después del registro.
        enviar_correo_bienvenida(self.correo, self.correo)
        self.succes = exito_mensaje
        self.mostrar_toast("¡Registro exitoso! Bienvenido al sistema.", "success")
        self.error_de_registro = ""
        self.contraseña = ""
        self.confirmar_contraseña = ""
        self.show_password = False
        self.registro_seccion_abierta = "cuenta"
        self.registro_paso_habilitado = 1
        # Login automático después del registro
        self.es_autentica = "true"
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
        if not self.es_autenticada or self.rol_usuario != "funcionario":
            self.error_de_registro = "Solo los funcionarios autenticados pueden registrar nuevos funcionarios."
            return
        self._validar_registro_basico()
        if self.error_de_registro:
            return
        return self._crear_usuario(
            rol="funcionario",
            exito_mensaje="Funcionario registrado con éxito. Ahora puede iniciar sesión con su correo institucional.",
        )

    def login(self, form_data: dict | None = None):
        self.borrar_mensajes_de_estado()
        if form_data:
            self.correo = str(form_data.get("correo") or self.correo or "").strip().lower()
            self.contraseña = str(form_data.get("contraseña") or self.contraseña or "")
        else:
            self.correo = str(self.correo or "").strip().lower()
        if not self.validacion_de_entradas(require_strong_pw=False):
            self.succes2 = ""
            self.error_de_contraseña = self.error_de_registro or "Correo o contraseña incorrectos."
            self.error_de_registro = ""
            return
        with Session(engine) as session:
            user = session.exec(select(Usuario).where(Usuario.email == self.correo)).first()
            pw_ok = False
            try:
                pw_ok = confirmar_contraseña(self.contraseña, user.Contraseña) if user else False
            except Exception:
                pw_ok = False
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
            self.id_usuario = str(user.id)
            self.rol_usuario = user.rol
            self.email_actual = user.email
            self.nombres = getattr(user, 'nombres', 'Ciudadano')  # Extraer nombre si existe en DB
            self.es_autentica = "true"
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
        self.id_usuario = "0"
        self.correo = ""
        self.contraseña = ""
        self.confirmar_contraseña = ""
        self.rol_usuario = ""
        self.email_actual = ""
        self.es_autentica = "false"
        self.nombres = ""
        self.show_password = False
        self.succes2 = "Has cerrado sesión exitosamente."
        self.error_de_contraseña = ""
        return rx.redirect("/")

    def change_password(self):
        """Cambiar la contraseña usuario autenticado"""
        self.change_pw_message = ""
        if not self.es_autenticada or not self.id_usuario_num:
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
            user = session.exec(select(Usuario).where(Usuario.id == self.id_usuario_num)).first()
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
        self.documento_previews = []
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
                    usuario = session.get(Usuario, self.id_usuario_num)
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
                # Enviar notificación de cambio de estado (si hay correo disponible)
                try:
                    correo_dest = self.email_actual or self.correo
                    if correo_dest and isinstance(correo_dest, str) and "@" in correo_dest:
                        fecha_cambio = datetime.now().strftime("%d/%m/%Y %H:%M")
                        notificar_cambio_estado(
                            nombre_solicitante=getattr(self, 'nombres', correo_dest) or correo_dest,
                            correo_solicitante=correo_dest,
                            numero_solicitud=solicitud_obj.radicado,
                            estado_anterior="(anterior)",
                            estado_nuevo=solicitud_obj.estado,
                            fecha_cambio=fecha_cambio,
                            observaciones="Actualizada desde interfaz",
                            correos_adicionales=None
                        )
                except Exception:
                    pass

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
                usuario = session.get(Usuario, self.id_usuario_num)
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
                    usuario_id=self.id_usuario_num if self.id_usuario_num else None,
                )
                session.add(solicitud_obj)
                session.commit()
                radicado_generado = solicitud_obj.radicado
            # Enviar notificación de creación (si hay correo disponible)
            try:
                correo_dest = self.email_actual or self.correo
                if correo_dest and isinstance(correo_dest, str) and "@" in correo_dest:
                    fecha_creacion = solicitud_obj.fecha.strftime("%d/%m/%Y %H:%M")
                    fecha_vencimiento = (solicitud_obj.fecha + timedelta(days=15)).strftime("%d/%m/%Y")
                    notificar_solicitud_creada(
                        nombre_solicitante=getattr(self, 'nombres', correo_dest) or correo_dest,
                        correo_solicitante=correo_dest,
                        numero_solicitud=solicitud_obj.radicado,
                        tipo_pqrs=solicitud_obj.tipo_solicitud,
                        fecha_creacion=fecha_creacion,
                        fecha_vencimiento=fecha_vencimiento,
                        correos_adicionales=None
                    )
            except Exception:
                pass

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
        """Consulta el estado de una solicitud por número de radicado"""
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
        """Carga la lista de usuarios registrados en el sistema"""
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
        """Cambia el rol de un ciudadano a funcionario"""
        self.cambiar_rol_mensaje = ""
        
        if not self.cambiar_rol_email:
            self.cambiar_rol_mensaje = "Ingresa el correo del usuario."
            return
        if not self.confirmar_promocion_rol:
            self.cambiar_rol_mensaje = "Debes confirmar la validación del usuario antes de promover el rol."
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
                    cuerpo = """
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
                self.confirmar_promocion_rol = False
                self.cargar_usuarios()
        except Exception as e:
            self.cambiar_rol_mensaje = f"Error al cambiar rol: {e}"

    def degradar_funcionario_a_ciudadano(self, email: str):
        """Cambia el rol de un funcionario a ciudadano (solo funcionarios autenticados)."""
        self.cambiar_rol_mensaje = ""
        if not self.es_autenticada or self.rol_usuario != "funcionario":
            self.cambiar_rol_mensaje = "Solo funcionarios autenticados pueden cambiar roles."
            return
        email_norm = str(email or "").strip().lower()
        if not email_norm:
            self.cambiar_rol_mensaje = "Correo inválido."
            return
        if self.email_actual and str(self.email_actual).strip().lower() == email_norm:
            self.cambiar_rol_mensaje = "No puedes degradarte a ti mismo."
            return

        try:
            with rx.session() as session:
                usuario = session.exec(select(Usuario).where(Usuario.email == email_norm)).first()
                if not usuario:
                    self.cambiar_rol_mensaje = f"No se encontró usuario con el correo {email_norm}."
                    return
                if usuario.rol != "funcionario":
                    self.cambiar_rol_mensaje = f"El usuario {email_norm} no es funcionario."
                    return

                usuario.rol = "ciudadano"
                session.add(usuario)
                session.commit()

            # Notificación (no bloquear si falla)
            try:
                asunto = "Rol actualizado - Has sido asignado como Ciudadano"
                cuerpo = f"""\
Estimado usuario,

Te informamos que tu rol en el sistema ha sido actualizado.

Tu nuevo rol: CIUDADANO

Atentamente,
Sistema PQRS
"""
                enviar_correo_notificacion(email_norm, asunto, cuerpo)
            except Exception:
                pass

            self.cambiar_rol_mensaje = f"✅ Rol del usuario {email_norm} actualizado a ciudadano."
            self.cargar_usuarios()
        except Exception as e:
            self.cambiar_rol_mensaje = f"Error al cambiar rol: {e}"

    def set_cambiar_rol_email(self, value: str):
        self.cambiar_rol_email = str(value or "").strip().lower()
        self.cambiar_rol_mensaje = ""
        self.confirmar_promocion_rol = False

    def set_confirmar_promocion_rol(self, value: bool):
        self.confirmar_promocion_rol = bool(value)

    def limpiar_form_promocion_rol(self):
        self.cambiar_rol_email = ""
        self.confirmar_promocion_rol = False
        self.cambiar_rol_mensaje = ""


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


def label_requerido(texto: str) -> rx.Component:
    return rx.hstack(
        rx.text(texto, color=rx.color_mode_cond(light="black", dark="white")),
        rx.text("*", color="orange.500"),
        spacing="1",
        align_items="center",
    )

def password_strength_label(password: str) -> rx.Component:
    # This will be rendered conditionally in the UI
    return rx.cond(
        password != "",
        rx.text(
            "Fortaleza de la contraseña: ",
            rx.cond(
                (password.length() >= 8) & (password != ""),
                "Media",
                "Débil"
            ),
            color=rx.cond(
                (password.length() >= 8) & (password != ""),
                "yellow.400",
                "red.400"
            ),
            font_size="xs"
        ),
        rx.box()
    )


def auth_card(title: str, on_submit, show_confirm: bool = False) -> rx.Component:
    text_color = rx.color_mode_cond(light="#1e293b", dark="#f8fafc")
    input_bg = rx.color_mode_cond(light="rgba(255, 255, 255, 0.8)", dark="rgba(30, 41, 59, 0.6)")
    input_border = rx.color_mode_cond(light="rgba(226, 232, 240, 0.8)", dark="rgba(51, 65, 85, 0.8)")
    placeholder_color = rx.color_mode_cond(light="#94a3b8", dark="#64748b")

    input_style = {
        "bg": input_bg,
        "border": f"1px solid {input_border}",
        "color": text_color,
        "size": "2",
        "radius": "large",
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
                width="100%",
                **input_style,
            ),
        )
        if show_confirm
        else rx.box(display="none")
    )

    return rx.box(
        rx.form(
            rx.vstack(
                rx.hstack(
                    rx.heading("CO.", size="6", color=rx.color_mode_cond(light="#1e3a8a", dark="#93c5fd"), font_weight="black"),
                  
                    justify="between",
                    width="100%",
                ),
                rx.heading(title, size="7", color=text_color, font_weight="bold", margin_bottom="0.4em"),
                rx.text(
                    "Completa tus datos para activar tu cuenta y gestionar tus solicitudes.",
                    color=rx.color_mode_cond(light="#475569", dark="#94a3b8"),
                    font_size="sm",
                    width="100%",
                ),
                
                rx.hstack(
                    rx.button("1. Cuenta", type="button", size="2", variant=rx.cond(State.registro_seccion_abierta == "cuenta", "solid", "soft"), color_scheme="blue", on_click=State.set_registro_seccion_abierta("cuenta")),
                    rx.button("2. Identidad", type="button", size="2", variant=rx.cond(State.registro_seccion_abierta == "identidad", "solid", "soft"), color_scheme="blue", on_click=State.set_registro_seccion_abierta("identidad"), is_disabled=State.registro_paso_habilitado < 2),
                    rx.button("3. Ubicación", type="button", size="2", variant=rx.cond(State.registro_seccion_abierta == "ubicacion", "solid", "soft"), color_scheme="blue", on_click=State.set_registro_seccion_abierta("ubicacion"), is_disabled=State.registro_paso_habilitado < 3),
                    width="100%",
                    spacing="2",
                    flex_wrap="wrap",
                ),
                rx.vstack(
                    rx.hstack(
                        rx.text("Progreso del registro", font_size="xs", color=rx.color_mode_cond(light="#64748b", dark="#94a3b8")),
                        rx.spacer(),
                        rx.text(
                            rx.cond(
                                State.registro_seccion_abierta == "cuenta",
                                "33%",
                                rx.cond(
                                    State.registro_seccion_abierta == "identidad",
                                    "66%",
                                    "100%",
                                ),
                            ),
                            font_size="xs",
                            font_weight="semibold",
                            color=rx.color_mode_cond(light="#1d4ed8", dark="#93c5fd"),
                        ),
                        width="100%",
                    ),
                    rx.box(
                        rx.box(
                            height="100%",
                            width=rx.cond(
                                State.registro_seccion_abierta == "cuenta",
                                "33%",
                                rx.cond(
                                    State.registro_seccion_abierta == "identidad",
                                    "66%",
                                    "100%",
                                ),
                            ),
                            bg="linear-gradient(90deg, #2563eb 0%, #0ea5e9 100%)",
                            border_radius="full",
                            transition="width 0.25s ease",
                        ),
                        width="100%",
                        height="8px",
                        border_radius="full",
                        bg=rx.color_mode_cond(light="#dbeafe", dark="rgba(30, 64, 175, 0.28)"),
                        overflow="hidden",
                    ),
                    spacing="1",
                    width="100%",
                ),

                rx.cond(
                    State.registro_seccion_abierta == "cuenta",
                    rx.vstack(
                        rx.vstack(
                            label_requerido("Correo electrónico"),
                            rx.hstack(
                                rx.input(
                                    placeholder="usuario@ejemplo.com",
                                    type="email",
                                    value=State.correo,
                                    on_change=State.set_and_validate_correo,
                                    on_blur=State.validar_correo_accion,
                                    width="100%",
                                    **input_style,
                                ),
                                rx.cond(State.correo_validado, rx.icon("circle-check", color="#10b981", size=20, ml="2"), rx.box()),
                                width="100%",
                            ),
                            rx.cond(State.correo_confirmacion_visible, rx.text(State.correo_confirmacion_mensaje, color=rx.cond(State.correo_validado, "green.500", "red.500"), font_size="sm", mt="1"), rx.box()),
                            width="100%",
                        ),
                        rx.vstack(
                            label_requerido("Contraseña"),
                            rx.hstack(
                                rx.input(
                                    placeholder="••••••••",
                                    type=rx.cond(State.show_password, "text", "password"),
                                    value=State.contraseña,
                                    on_change=State.set_contraseña,
                                    width="100%",
                                    **input_style,
                                ),
                                rx.button(rx.cond(State.show_password, rx.icon("eye-off", size=18), rx.icon("eye", size=18)), on_click=State.toggle_show_password, variant="soft", size="3", radius="large"),
                                width="100%",
                                spacing="2",
                            ),
                            rx.text("Mínimo 8 caracteres, mayúscula, número y símbolo.", font_size="xs", color=rx.color_mode_cond(light="#64748b", dark="#94a3b8")),
                            password_strength_label(State.contraseña),
                            width="100%",
                        ),
                        confirmar_field,
                        rx.hstack(
                            rx.spacer(),
                            rx.button("Continuar", type="button", size="3", color_scheme="blue", on_click=State.continuar_a_identidad),
                            width="100%",
                        ),
                        spacing="4",
                        width="100%",
                        animation="fadeInUp 0.28s ease",
                        style={
                            "@keyframes fadeInUp": {
                                "0%": {"opacity": "0", "transform": "translateY(8px)"},
                                "100%": {"opacity": "1", "transform": "translateY(0px)"},
                            }
                        },
                    ),
                    rx.box(),
                ),

                rx.cond(
                    State.registro_seccion_abierta == "identidad",
                    rx.vstack(
                        rx.grid(
                            rx.vstack(
                                label_requerido("Nombres"),
                                rx.hstack(
                                    rx.input(placeholder="Tus nombres", value=State.nombres, on_change=State.set_and_validate_nombres, width="100%", **input_style),
                                    rx.cond(State.nombres_valid, rx.icon("circle-check", color="#10b981", size=18, ml="2"), rx.box()),
                                    width="100%",
                                ),
                                width="100%",
                            ),
                            rx.vstack(
                                label_requerido("Apellidos"),
                                rx.hstack(
                                    rx.input(placeholder="Tus apellidos", value=State.apellidos, on_change=State.set_and_validate_apellidos, width="100%", **input_style),
                                    rx.cond(State.apellidos_valid, rx.icon("circle-check", color="#10b981", size=18, ml="2"), rx.box()),
                                    width="100%",
                                ),
                                width="100%",
                            ),
                            template_columns={"base": "1fr", "md": "1fr 1fr"},
                            gap="3",
                            width="100%",
                        ),
                        rx.grid(
                            rx.vstack(
                                rx.text("Sexo", color=text_color, font_weight="medium", font_size="sm"),
                                rx.select(["Femenino", "Masculino", "Prefiero no decirlo"], placeholder="Selecciona", value=State.sexo, on_change=State.set_sexo, **input_style),
                                width="100%",
                            ),
                            rx.vstack(
                                rx.text("Tipo de ID", font_weight="medium", font_size="sm", color=text_color),
                                rx.select(["Cédula", "Pasaporte", "Tarjeta de Identidad"], placeholder="Selecciona", value=State.tipo_identificacion, on_change=State.set_tipo_identificacion, **input_style),
                                width="100%",
                            ),
                            rx.vstack(
                                label_requerido("Número de ID"),
                                rx.hstack(
                                    rx.input(placeholder="123456789", value=State.numero_identificacion, on_change=State.set_and_validate_numero_identificacion, width="100%", **input_style),
                                    rx.cond(State.numero_identificacion_valid, rx.icon("circle-check", color="#10b981", size=20, ml="2"), rx.box()),
                                ),
                                width="100%",
                            ),
                            rx.vstack(
                                rx.text("Teléfono", color=text_color, font_weight="medium", font_size="sm"),
                                rx.hstack(
                                    rx.input(placeholder="Tu teléfono", value=State.telefono, on_change=State.set_and_validate_telefono, width="100%", **input_style),
                                    rx.cond(State.telefono_valid, rx.icon("circle-check", color="#10b981", size=20, ml="2"), rx.box()),
                                ),
                                width="100%",
                            ),
                            template_columns={"base": "1fr", "md": "1fr 1fr"},
                            gap="3",
                            width="100%",
                        ),
                        rx.hstack(
                            rx.button("Atrás", type="button", size="3", variant="soft", on_click=State.set_registro_seccion_abierta("cuenta")),
                            rx.spacer(),
                            rx.button("Continuar", type="button", size="3", color_scheme="blue", on_click=State.continuar_a_ubicacion),
                            width="100%",
                        ),
                        spacing="4",
                        width="100%",
                        animation="fadeInUp 0.28s ease",
                        style={
                            "@keyframes fadeInUp": {
                                "0%": {"opacity": "0", "transform": "translateY(8px)"},
                                "100%": {"opacity": "1", "transform": "translateY(0px)"},
                            }
                        },
                    ),
                    rx.box(),
                ),

                rx.cond(
                    State.registro_seccion_abierta == "ubicacion",
                    rx.vstack(
                        rx.grid(
                            rx.vstack(
                                rx.text("Departamento", color=text_color, font_weight="medium", font_size="sm"),
                                rx.select(
                                    [
                                        "Amazonas", "Antioquia", "Arauca", "Atlántico", "Bolívar", "Boyacá", "Caldas", "Caquetá", "Casanare", "Cauca", "Cesar", "Chocó", "Córdoba",
                                        "Cundinamarca", "Guainía", "Guaviare", "Huila", "La Guajira", "Magdalena", "Meta", "Nariño", "Norte de Santander", "Putumayo", "Quindío", "Risaralda",
                                        "Santander", "Sucre", "Tolima", "Valle del Cauca", "Vaupés", "Vichada",
                                    ],
                                    placeholder="Selecciona",
                                    value=State.departamento,
                                    on_change=State.set_and_validate_departamento,
                                    **input_style,
                                ),
                                width="100%",
                            ),
                            rx.vstack(
                                rx.text("Ciudad", color=text_color, font_weight="medium", font_size="sm"),
                                rx.select(State.ciudades_disponibles, placeholder="Selecciona", value=State.ciudad, on_change=State.set_and_validate_ciudad, is_disabled=State.departamento == "", **input_style),
                                width="100%",
                            ),
                            template_columns={"base": "1fr", "md": "1fr 1fr"},
                            gap="3",
                            width="100%",
                        ),
                        rx.vstack(
                            label_requerido("Dirección"),
                            rx.input(placeholder="Tu dirección", value=State.direccion, on_change=State.set_direccion, width="100%", **input_style),
                            width="100%",
                        ),
                        rx.grid(
                            rx.vstack(
                                rx.text("Etnia", color=text_color, font_weight="medium", font_size="sm"),
                                rx.select(["Ninguna", "Indígena", "Afrocolombiano", "Raizal", "Palenquero", "Gitano/a", "Otro"], placeholder="Selecciona", value=State.etnia, on_change=State.set_etnia, **input_style),
                                width="100%",
                            ),
                            rx.vstack(
                                rx.text("Características especiales", color=text_color, font_weight="medium", font_size="sm"),
                                rx.select(
                                    ["Ninguna", "Habitante de la calle", "No brinda información", "Peligro Inminente", "Periodistas en ejercicio de su actividad", "Primera Infancia", "Veteranos Fuerza Pública", "Víctimas - Conflicto Armado"],
                                    placeholder="Selecciona",
                                    value=State.persona_vulnerable_registro,
                                    on_change=State.set_persona_vulnerable_registro,
                                    **input_style,
                                ),
                                width="100%",
                            ),
                            template_columns={"base": "1fr", "md": "1fr 1fr"},
                            gap="3",
                            width="100%",
                        ),
                        rx.divider(margin_y="2", bg=input_border),
                        rx.vstack(
                            rx.checkbox("Acepto recibir notificaciones por correo", is_checked=State.acepta_notificaciones, on_change=State.set_acepta_notificaciones, color=text_color, size="3"),
                            rx.checkbox(
                                rx.hstack(
                                    rx.link("He leído y acepto la Política de Protección de Datos", href="/politica-privacidad", color="#3b82f6", font_weight="medium"),
                                    rx.text("(Aviso obligatorio)", color=rx.color_mode_cond(light="#94a3b8", dark="#64748b"), font_size="sm"),
                                ),
                                is_checked=State.acepta_politica_datos,
                                on_change=State.preconfirmar_politica,
                                color=text_color,
                                size="3",
                            ),
                            spacing="3",
                            width="100%",
                        ),
                        rx.hstack(
                            rx.button("Atrás", type="button", size="3", variant="soft", on_click=State.set_registro_seccion_abierta("identidad")),
                            rx.spacer(),
                            rx.text("Último paso", font_size="xs", color=rx.color_mode_cond(light="#64748b", dark="#94a3b8")),
                            width="100%",
                        ),
                        spacing="4",
                        width="100%",
                        animation="fadeInUp 0.28s ease",
                        style={
                            "@keyframes fadeInUp": {
                                "0%": {"opacity": "0", "transform": "translateY(8px)"},
                                "100%": {"opacity": "1", "transform": "translateY(0px)"},
                            }
                        },
                    ),
                    rx.box(),
                ),
                
                rx.cond(
                    State.modal_politica_visible,
                    rx.box(
                        rx.box(
                            rx.box(
                                position="absolute",
                                top="-60px",
                                right="-40px",
                                width="180px",
                                height="180px",
                                bg="rgba(59, 130, 246, 0.35)",
                                border_radius="full",
                                filter="blur(50px)",
                            ),
                            rx.box(
                                position="absolute",
                                bottom="-40px",
                                left="-30px",
                                width="140px",
                                height="140px",
                                bg="rgba(14, 165, 233, 0.25)",
                                border_radius="full",
                                filter="blur(45px)",
                            ),
                            rx.vstack(
                                rx.center(
                                    rx.box(
                                        rx.icon("shield-check", size=32, color="#60a5fa"),
                                        p="4",
                                        bg=rx.color_mode_cond(
                                            light="linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%)",
                                            dark="linear-gradient(135deg, rgba(37, 99, 235, 0.25) 0%, rgba(14, 165, 233, 0.15) 100%)",
                                        ),
                                        border=rx.color_mode_cond(
                                            light="1px solid #93c5fd",
                                            dark="1px solid rgba(96, 165, 250, 0.35)",
                                        ),
                                        border_radius="2xl",
                                        box_shadow=rx.color_mode_cond(
                                            light="0 12px 28px -8px rgba(37, 99, 235, 0.35)",
                                            dark="0 12px 28px -8px rgba(2, 6, 23, 0.8)",
                                        ),
                                    ),
                                    width="100%",
                                ),
                                rx.badge(
                                    "Ley 1581 de 2012",
                                    color_scheme="blue",
                                    variant="soft",
                                    radius="full",
                                    size="1",
                                ),
                                rx.heading(
                                    "Política de Privacidad",
                                    size="6",
                                    color=rx.color_mode_cond(light="#0f172a", dark="#f8fafc"),
                                    font_weight="bold",
                                    text_align="center",
                                    letter_spacing="-0.02em",
                                ),
                                rx.text(
                                    "Al aceptar, confirmas que has leído y comprendido cómo tratamos tus datos personales para la gestión de PQRS.",
                                    color=rx.color_mode_cond(light="#475569", dark="#94a3b8"),
                                    font_size="sm",
                                    line_height="1.6",
                                    text_align="center",
                                ),
                                rx.box(
                                    rx.vstack(
                                        rx.hstack(
                                            rx.icon("lock", size=16, color="#38bdf8"),
                                            rx.text(
                                                "Tus datos se usan solo para trámites y notificaciones.",
                                                font_size="xs",
                                                color=rx.color_mode_cond(light="#334155", dark="#cbd5e1"),
                                            ),
                                            spacing="2",
                                            align_items="center",
                                        ),
                                        rx.hstack(
                                            rx.icon("file-text", size=16, color="#38bdf8"),
                                            rx.link(
                                                "Leer política completa",
                                                href="/politica-privacidad",
                                                font_size="xs",
                                                font_weight="semibold",
                                                color=rx.color_mode_cond(light="#2563eb", dark="#93c5fd"),
                                                _hover={"text_decoration": "underline"},
                                            ),
                                            spacing="2",
                                            align_items="center",
                                        ),
                                        spacing="2",
                                        align_items="start",
                                        width="100%",
                                    ),
                                    width="100%",
                                    p="4",
                                    border_radius="xl",
                                    bg=rx.color_mode_cond(
                                        light="rgba(239, 246, 255, 0.85)",
                                        dark="rgba(15, 23, 42, 0.55)",
                                    ),
                                    border=rx.color_mode_cond(
                                        light="1px solid #bfdbfe",
                                        dark="1px solid rgba(51, 65, 85, 0.8)",
                                    ),
                                ),
                                rx.vstack(
                                    rx.button(
                                        rx.hstack(
                                            rx.icon("check", size=18),
                                            rx.text("Acepto y continúo", font_weight="bold"),
                                            spacing="2",
                                            justify="center",
                                        ),
                                        on_click=State.confirmar_politica,
                                        color_scheme="blue",
                                        size="3",
                                        width="100%",
                                        radius="full",
                                        box_shadow="0 10px 24px -10px rgba(37, 99, 235, 0.65)",
                                    ),
                                    rx.button(
                                        "Cancelar",
                                        on_click=State.cancelar_politica,
                                        variant="ghost",
                                        size="3",
                                        width="100%",
                                        color=rx.color_mode_cond(light="#64748b", dark="#94a3b8"),
                                    ),
                                    spacing="2",
                                    width="100%",
                                ),
                                spacing="4",
                                align_items="center",
                                width="100%",
                                z_index="1",
                            ),
                            position="relative",
                            overflow="hidden",
                            p={"base": "6", "md": "8"},
                            bg=rx.color_mode_cond(
                                light="rgba(255, 255, 255, 0.92)",
                                dark="rgba(15, 23, 42, 0.88)",
                            ),
                            backdrop_filter="blur(24px)",
                            border=rx.color_mode_cond(
                                light="1px solid rgba(147, 197, 253, 0.9)",
                                dark="1px solid rgba(96, 165, 250, 0.28)",
                            ),
                            border_radius="3xl",
                            box_shadow=rx.color_mode_cond(
                                light="0 32px 64px -20px rgba(30, 64, 175, 0.45), 0 0 0 1px rgba(255,255,255,0.5) inset",
                                dark="0 32px 64px -16px rgba(2, 6, 23, 0.95), 0 0 0 1px rgba(255,255,255,0.06) inset",
                            ),
                            width="100%",
                            max_width="480px",
                            animation="modalPop 0.32s cubic-bezier(0.22, 1, 0.36, 1)",
                            style={
                                "@keyframes modalPop": {
                                    "0%": {"opacity": "0", "transform": "scale(0.94) translateY(12px)"},
                                    "100%": {"opacity": "1", "transform": "scale(1) translateY(0px)"},
                                }
                            },
                        ),
                        position="fixed",
                        inset="0",
                        bg="rgba(2, 6, 23, 0.72)",
                        backdrop_filter="blur(10px)",
                        display="flex",
                        align_items="center",
                        justify_content="center",
                        z_index="1000",
                        p="6",
                    ),
                ),
                
                rx.cond(
                    State.error_de_registro != "",
                    rx.box(
                        rx.text(State.error_de_registro, color="#ef4444", font_size="sm", font_weight="medium"),
                        p="3", bg=rx.color_mode_cond(light="#fef2f2", dark="rgba(239, 68, 68, 0.1)"),
                        border_radius="lg",
                        width="100%",
                        animation="flashMessage 5s ease forwards",
                        style={
                            "@keyframes flashMessage": {
                                "0%": {"opacity": "0", "transform": "translateY(-4px)"},
                                "10%": {"opacity": "1", "transform": "translateY(0px)"},
                                "80%": {"opacity": "1", "transform": "translateY(0px)"},
                                "100%": {"opacity": "0", "transform": "translateY(-4px)"},
                            }
                        },
                    ),
                    rx.box(),
                ),
                rx.cond(
                    State.succes != "",
                    rx.box(
                        rx.text(State.succes, color="#10b981", font_size="sm", font_weight="medium"),
                        p="3", bg=rx.color_mode_cond(light="#ecfdf5", dark="rgba(16, 185, 129, 0.1)"),
                        border_radius="lg",
                        width="100%",
                        animation="flashMessage 5s ease forwards",
                        style={
                            "@keyframes flashMessage": {
                                "0%": {"opacity": "0", "transform": "translateY(-4px)"},
                                "10%": {"opacity": "1", "transform": "translateY(0px)"},
                                "80%": {"opacity": "1", "transform": "translateY(0px)"},
                                "100%": {"opacity": "0", "transform": "translateY(-4px)"},
                            }
                        },
                    ),
                    rx.box(),
                ),
                
                rx.hstack(
                    rx.button(
                        "Crear cuenta",
                        type="submit",
                        color_scheme="blue",
                        size="4",
                        radius="large",
                        width={"base": "100%", "md": "300px"},
                        box_shadow="0 8px 20px -8px rgba(37, 99, 235, 0.55)",
                        is_disabled=(State.registro_paso_habilitado < 3) | (State.registro_seccion_abierta != "ubicacion"),
                    ),
                    rx.link("¿Ya tienes una cuenta? Inicia sesión", href="/login", margin_left={"base": "0", "md": "4"}, color="#3b82f6", font_weight="medium"),
                    spacing="6",
                    justify={"base": "center", "md": "start"},
                    width="100%",
                    margin_top="4"
                ),
                
                spacing="4",
                width="100%",
            ),
            on_submit=on_submit,
            width="100%",
        ),
        p={"base": "6", "md": "8"},
        max_width="1100px",
        width="100%",
        bg=rx.color_mode_cond(light="linear-gradient(145deg, #dbeafe 0%, #bfdbfe 100%)", dark="linear-gradient(145deg, #0f172a 0%, #1e3a8a 100%)"),
        border=rx.color_mode_cond(light="1px solid #93c5fd", dark="1px solid #1e40af"),
        border_radius="2xl",
        box_shadow=rx.color_mode_cond(light="0 30px 60px -25px rgba(30, 64, 175, 0.35)", dark="0 30px 60px -25px rgba(2, 6, 23, 0.85)"),
        z_index="1",
        position="relative",
        overflow="hidden",
        style={"borderLeft": "8px solid #2563eb"},
        max_height={"base": "none", "lg": "84vh"},
        overflow_y={"base": "visible", "lg": "auto"},
    )




def navbar() -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.hstack(
                rx.cond(
                    State.es_autenticada,
                    rx.cond(
                        State.rol_usuario == "funcionario",
                        # Menú de Funcionario
                        rx.hstack(
                            rx.link("Inicio", href="/", color="white", font_weight="bold", _hover={"opacity": 0.8}),
                            rx.link("Nueva Solicitud", href="/solicitudes", color="white", font_weight="bold", _hover={"opacity": 0.8}),
                            rx.link("Registro de Ciudadano", href="/registro", color="white", font_weight="bold", _hover={"opacity": 0.8}),
                            spacing="6",
                        ),
                        # Menú de Ciudadano (Limpio)
                        rx.hstack(
                            rx.link("Nueva Solicitud", href="/solicitudes", color="white", font_weight="bold", _hover={"opacity": 0.8}),
                            spacing="6",
                        )
                    ),
                    # Menú Anónimo
                    rx.hstack(
                        rx.link("Inicio", href="/", color="white", font_weight="bold", _hover={"opacity": 0.8}),
                        rx.link("Nueva Solicitud", href="/solicitudes", color="white", font_weight="bold", _hover={"opacity": 0.8}),
                        rx.link("Registro de Ciudadano", href="/registro", color="white", font_weight="bold", _hover={"opacity": 0.8}),
                        spacing="6",
                    )
                ),
                rx.cond(
                    State.es_autenticada & (State.rol_usuario == "funcionario"),
                    rx.link("Reportes", href="/reportes", color="white", font_weight="bold", _hover={"opacity": 0.8})
                ),
                rx.cond(
                    State.es_autenticada & (State.rol_usuario == "funcionario"),
                    rx.link("Ayuda", href="/ayuda-funcionario", color="white", font_weight="bold", _hover={"opacity": 0.8})
                ),
                rx.text("", display="none"),
                rx.cond(
                    State.es_autenticada & (State.rol_usuario == "funcionario"),
                    rx.link("Ver Usuarios", href="/usuarios", color="white", font_weight="bold", _hover={"opacity": 0.8}),
                    rx.text("", display="none")
                ),
                rx.cond(
                    State.es_autenticada & (State.rol_usuario == "funcionario"),
                    rx.link("Cambiar Rol", href="/cambiar-rol", color="white", font_weight="bold", _hover={"opacity": 0.8}),
                    rx.text("", display="none")
                ),
                rx.cond(
                    State.es_autenticada,
                    rx.cond(
                        State.rol_usuario == "funcionario",
                        rx.link("Dashboard Funcionario", href="/dashboard-funcionario", color="white", font_weight="bold", _hover={"opacity": 0.8}),
                        rx.link("Mi Panel", href="/dashboard", color="white", font_weight="bold", _hover={"opacity": 0.8})
                    ),
                    rx.text("", display="none")
                ),
                spacing="6",
            ),
            rx.hstack(
                rx.color_mode.button(),
                rx.cond(
                    State.es_autenticada,
                    rx.button("Cerrar Sesión", on_click=State.logout, color_scheme="red", variant="solid"),
                    rx.text("", display="none")
                ),
                spacing="2", align_items="center"
            ),
            justify="between", align_items="center", width="100%", max_width="none", margin="0",
        ),
        bg=rx.color_mode_cond(light="#1e40af", dark="#1e3a8a"),
        padding_y="1em", padding_x="2em", width="100%", style={"margin": "0", "padding": "1em 2em"}
    )


def access_denied_widget(message: str) -> rx.Component:
    # Auto-redirect to login if not authenticated; show access denied if authenticated but wrong role
    return rx.cond(
        rx.State.is_hydrated,
        rx.cond(
            State.es_autenticada,
            rx.vstack(
                rx.heading("Acceso Denegado", size="8", color="red.500"),
                rx.text(message, color="gray.600"),
                rx.vstack(
                    rx.button("Cerrar Sesión", on_click=State.logout, color_scheme="red", width="100%"),
                    rx.link(rx.button("Volver al inicio", color_scheme="blue"), href="/"),
                    spacing="4",
                    align_items="center"
                ),
                spacing="4",
                align_items="center"
            ),
            rx.script("window.location.href = '/login'")
        ),
        rx.center(rx.spinner(size="3", color="#3b82f6"), height="50vh")
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
    text_color = rx.color_mode_cond(light="#1e293b", dark="#f8fafc")
    subtext_color = rx.color_mode_cond(light="#475569", dark="#cbd5e1")
    section_bg = rx.color_mode_cond(light="#f8fafc", dark="#020617")
    body_bg = rx.color_mode_cond(light="#f1f5f9", dark="#020617")

    return rx.box(
        utility_bar(),
        navbar(),
        
        # 1. HERO SECTION (Mesh Gradient)
        rx.box(
            rx.box(
                rx.box(
                    rx.hstack(
                        rx.vstack(
                            rx.box(
                                rx.text("Plataforma oficial de atención ciudadana", color="#e0f2fe", font_size="sm", font_weight="medium"),
                                bg="rgba(59, 130, 246, 0.4)", padding_x="4", padding_y="1.5", border_radius="full", mb="2", border="1px solid rgba(147, 197, 253, 0.3)"
                            ),
                            rx.heading("Atención PQRS", size="9", color="white", font_weight="900", line_height="1", letter_spacing="-0.03em"),
                            rx.heading("Enlace 1755", size="8", color="#93c5fd", font_weight="800", margin_bottom="4"),
                            rx.text(
                                "Radica, consulta y gestiona tus Peticiones, Quejas, Reclamos y Sugerencias de forma clara, rápida y segura.",
                                color="rgba(255,255,255,0.9)", font_size="xl", max_width="600px", margin_bottom="6", line_height="1.6"
                            ),
                            rx.hstack(
                                rx.link(rx.button("Radicar PQRS", color_scheme="blue", size="4", radius="full", box_shadow="0 10px 15px -3px rgba(37, 99, 235, 0.4)", width="200px"), href="/solicitudes"),
                                rx.link(rx.button("Consultar Estado", color_scheme="gray", variant="soft", size="4", radius="full", width="200px", color="white", bg="rgba(255, 255, 255, 0.15)", _hover={"bg": "rgba(255, 255, 255, 0.25)"}), href="/consultar-estado"),
                                spacing="4", flex_wrap="wrap"
                            ),
                            spacing="4", align_items="start", width="100%", max_width="720px", z_index="2"
                        ),
                        rx.box(
                            rx.vstack(
                                rx.hstack(
                                    rx.icon("zap", size=24, color="#3b82f6"),
                                    rx.heading("Accesos rápidos", size="5", color=text_color),
                                    spacing="2", align_items="center", margin_bottom="4"
                                ),
                                rx.link(rx.button("Crear cuenta", color_scheme="blue", size="4", width="100%", radius="large"), href="/registro"),
                                rx.link(rx.button("Iniciar sesión", variant="soft", color_scheme="gray", size="4", width="100%", radius="large"), href="/login"),
                                rx.link(rx.button("Nueva solicitud", variant="outline", color_scheme="blue", size="4", width="100%", radius="large"), href="/solicitudes"),
                                rx.divider(margin_y="4", bg="rgba(0,0,0,0.1)"),
                                rx.text("Disponible para ciudadanos que deseen registrar y hacer seguimiento a sus solicitudes.", color=subtext_color, font_size="sm", text_align="center"),
                                spacing="4", align_items="stretch", width="100%"
                            ),
                            p="8",
                            bg=rx.color_mode_cond(light="rgba(255,255,255,0.85)", dark="rgba(15,23,42,0.85)"),
                            backdrop_filter="blur(20px)",
                            border=rx.color_mode_cond(light="1px solid rgba(255,255,255,0.5)", dark="1px solid rgba(51,65,85,0.5)"),
                            border_radius="3xl", box_shadow="0 25px 50px -12px rgba(0, 0, 0, 0.25)",
                            width="100%", max_width="380px", z_index="2"
                        ),
                        spacing="9", align_items="center", justify="between", flex_wrap="wrap", width="100%", max_width="1400px", padding_x={"base": "4", "md": "12"}
                    ),
                    width="100%"
                ),
                width="100%", padding_y={"base": "16", "md": "32"}
            ),
            width="100%",
            position="relative", overflow="hidden",
            # Imagen de fondo original con capa oscura
            style={
                "backgroundImage": "linear-gradient(rgba(15, 23, 42, 0.7), rgba(15, 23, 42, 0.8)), url('/Gemini_Generated_Image_ouyornouyornouyo.png')",
                "backgroundSize": "cover",
                "backgroundPosition": "center",
                "backgroundRepeat": "no-repeat",
                "margin": "0", "padding": "0"
            }
        ),

        # 2. ACCIONES RÁPIDAS
        rx.box(
            rx.vstack(
                rx.vstack(
                    rx.heading("¿Qué deseas hacer hoy?", size="8", color=text_color, font_weight="bold"),
                    rx.text("Accede rápidamente a los servicios principales del sistema.", color=subtext_color, font_size="lg"),
                    spacing="3", align_items="center", margin_bottom="12"
                ),
                rx.grid(
                    quick_action_card("Radicar PQRS", "Crea una nueva petición, queja, reclamo o sugerencia.", "Ir al formulario", "/solicitudes", "blue", "file-text"),
                    quick_action_card("Consultar estado", "Revisa el avance y respuesta de tus solicitudes.", "Consultar", "/consultar-estado", "cyan", "search"),
                    quick_action_card("Registro ciudadano", "Crea tu cuenta para gestionar trámites de forma segura.", "Registrarme", "/registro", "green", "user-plus"),
                    quick_action_card("Iniciar sesión", "Accede a tu cuenta y continúa tus gestiones.", "Entrar", "/login", "purple", "log-in"),
                    template_columns={"base": "1fr", "sm": "repeat(2, 1fr)", "lg": "repeat(4, 1fr)"},
                    gap="6", width="100%", max_width="1400px"
                ),
                spacing="9", align_items="center", width="100%"
            ),
            padding_y="24", padding_x={"base": "4", "md": "12"}, width="100%", bg=body_bg
        ),

        # 3. INFO CARDS
        rx.box(
            rx.vstack(
                rx.heading("Atención clara y transparente para la ciudadanía", size="8", color=text_color, text_align="center", font_weight="bold"),
                rx.text("Este portal facilita la recepción, gestión y seguimiento de solicitudes ciudadanas de manera organizada y accesible.", color=subtext_color, font_size="lg", text_align="center", max_width="850px", margin_bottom="12"),
                rx.grid(
                    info_card("Canal seguro", "Tus datos y solicitudes se gestionan en un entorno controlado.", "shield-check", "blue"),
                    info_card("Trazabilidad", "Cada solicitud puede registrarse y consultarse con mayor claridad.", "git-branch", "indigo"),
                    info_card("Atención oportuna", "El sistema está pensado para mejorar tiempos y experiencia ciudadana.", "clock", "emerald"),
                    template_columns={"base": "1fr", "md": "repeat(3, 1fr)"},
                    gap="8", width="100%", max_width="1400px"
                ),
                spacing="4", align_items="center", width="100%"
            ),
            width="100%", bg=section_bg, padding_y="24", padding_x={"base": "4", "md": "12"}
        ),

        # 4. PQRS BADGES
        rx.box(
            rx.vstack(
                rx.heading("¿Qué significa PQRS?", size="8", color=text_color, font_weight="bold", margin_bottom="12"),
                rx.grid(
                    pqrs_badge("P", "etición", "Solicitud respetuosa de información o actuación por parte de la entidad.", "blue"),
                    pqrs_badge("Q", "ueja", "Manifestación de inconformidad por la conducta o atención recibida.", "orange"),
                    pqrs_badge("R", "eclamo", "Expresión de inconformidad por una prestación deficiente o incumplimiento.", "red"),
                    pqrs_badge("S", "ugerencia", "Propuesta o recomendación para mejorar la atención o el servicio.", "emerald"),
                    template_columns={"base": "1fr", "sm": "repeat(2, 1fr)", "lg": "repeat(4, 1fr)"},
                    gap="6", width="100%", max_width="1400px"
                ),
                spacing="8", align_items="center", width="100%"
            ),
            padding_y="24", padding_x={"base": "4", "md": "12"}, width="100%", bg=body_bg
        ),

        footer(),
        brand_footer(),
        bg=body_bg, width="100%", min_height="100vh", style={"margin": "0", "padding": "0", "boxSizing": "border-box"}
    )

def quick_action_card(title: str, desc: str, button_text: str, href: str, accent: str, icon: str) -> rx.Component:
    card_bg = rx.color_mode_cond(light="white", dark="#1e293b")
    border = rx.color_mode_cond(light="1px solid #e2e8f0", dark="1px solid #334155")
    text_main = rx.color_mode_cond(light="#0f172a", dark="#f8fafc")
    text_sec = rx.color_mode_cond(light="#64748b", dark="#94a3b8")

    return rx.box(
        rx.vstack(
            rx.box(
                rx.icon(icon, size=32, color=f"var(--{accent}-500)"),
                bg=f"var(--{accent}-3)", padding="4", border_radius="2xl", margin_bottom="4"
            ),
            rx.heading(title, size="5", color=text_main, font_weight="bold"),
            rx.text(desc, color=text_sec, font_size="sm", min_height="60px"),
            rx.link(rx.button(button_text, color_scheme=accent, variant="soft", size="3", width="100%", radius="large"), href=href),
            spacing="3", align_items="start", width="100%"
        ),
        bg=card_bg, border=border, border_radius="3xl", p="8", width="100%", box_shadow="0 10px 15px -3px rgba(0, 0, 0, 0.05)",
        _hover={"transform": "translateY(-4px)", "box_shadow": f"0 20px 25px -5px var(--{accent}-4)", "border_color": f"var(--{accent}-6)"},
        transition="all 0.3s ease"
    )

def info_card(title: str, desc: str, icon: str, color: str) -> rx.Component:
    card_bg = rx.color_mode_cond(light="white", dark="#1e293b")
    border = rx.color_mode_cond(light="1px solid #e2e8f0", dark="1px solid #334155")
    text_main = rx.color_mode_cond(light="#0f172a", dark="white")
    text_sec = rx.color_mode_cond(light="#64748b", dark="#cbd5e1")

    return rx.box(
        rx.hstack(
            rx.box(
                rx.icon(icon, size=28, color=f"var(--{color}-500)"),
                bg=f"var(--{color}-3)", padding="4", border_radius="2xl"
            ),
            rx.vstack(
                rx.text(title, font_weight="bold", color=text_main, font_size="lg"),
                rx.text(desc, color=text_sec, font_size="sm"),
                spacing="1", align_items="start"
            ),
            spacing="5", align_items="center"
        ),
        bg=card_bg, border=border, border_radius="2xl", p="6", width="100%", box_shadow="sm",
        _hover={"border_color": f"var(--{color}-6)", "box_shadow": "md"}, transition="all 0.2s"
    )

def pqrs_badge(letter: str, rest: str, desc: str, color: str) -> rx.Component:
    card_bg = rx.color_mode_cond(light="white", dark="#1e293b")
    border = rx.color_mode_cond(light="1px solid #e2e8f0", dark="1px solid #334155")
    text_sec = rx.color_mode_cond(light="#64748b", dark="#cbd5e1")

    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.heading(letter, size="9", color=f"var(--{color}-500)", font_weight="900"),
                rx.heading(rest, size="6", color=rx.color_mode_cond(light="#0f172a", dark="white"), font_weight="bold", padding_top="3"),
                spacing="1", align_items="baseline"
            ),
            rx.divider(margin_y="2"),
            rx.text(desc, color=text_sec, font_size="sm"),
            spacing="2", align_items="start"
        ),
        bg=card_bg, border=border, border_radius="3xl", p="8", width="100%", box_shadow="md",
        _hover={"transform": "translateY(-4px)", "border_color": f"var(--{color}-6)"}, transition="all 0.3s"
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
    # Franja inferior con logos institucionales (Universidad del Valle y GOV.CO).
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
    return rx.box(
        toast_notification(),
        navbar(),
        rx.center(
            rx.box(position="absolute", top="-140px", left="-120px", width="360px", height="360px", bg="rgba(37, 99, 235, 0.24)", border_radius="full", filter="blur(95px)", z_index="0"),
            rx.box(position="absolute", bottom="-130px", right="-90px", width="340px", height="340px", bg="rgba(16, 185, 129, 0.18)", border_radius="full", filter="blur(90px)", z_index="0"),
            rx.grid(
                rx.box(
                    rx.vstack(
                        rx.badge("Registro ciudadano", color_scheme="blue", variant="soft", radius="full"),
                        rx.heading(
                            "Crea tu cuenta y haz seguimiento de tus PQRS",
                            size="8",
                            color=rx.color_mode_cond(light="#0f172a", dark="#f8fafc"),
                            line_height="1.1",
                            letter_spacing="-0.02em",
                        ),
                        rx.text(
                            "Registra tus datos una sola vez para radicar solicitudes y consultar su estado cuando quieras.",
                            color=rx.color_mode_cond(light="#475569", dark="#94a3b8"),
                            font_size="md",
                        ),
                        rx.box(
                            rx.image(
                                src="/pqrs.png",
                                alt="Registro PQRS",
                                width="100%",
                                height="190px",
                                object_fit="cover",
                            ),
                            width="100%",
                            border_radius="xl",
                            overflow="hidden",
                            border=rx.color_mode_cond(light="1px solid #cbd5e1", dark="1px solid #334155"),
                            box_shadow=rx.color_mode_cond(light="0 12px 30px -16px rgba(15, 23, 42, 0.45)", dark="0 12px 30px -16px rgba(2, 6, 23, 0.9)"),
                        ),
                        rx.vstack(
                            rx.hstack(rx.icon("check-check", size=16, color="#22c55e"), rx.text("Formulario guiado y validado", font_size="sm", color=rx.color_mode_cond(light="#334155", dark="#cbd5e1")), spacing="2"),
                            rx.hstack(rx.icon("shield-check", size=16, color="#22c55e"), rx.text("Protección de datos y consentimiento", font_size="sm", color=rx.color_mode_cond(light="#334155", dark="#cbd5e1")), spacing="2"),
                            rx.hstack(rx.icon("bell-ring", size=16, color="#22c55e"), rx.text("Notificaciones de avance por correo", font_size="sm", color=rx.color_mode_cond(light="#334155", dark="#cbd5e1")), spacing="2"),
                            spacing="3",
                            align_items="start",
                            width="100%",
                        ),
                        rx.spacer(),
                        rx.text(
                            "Plataforma oficial de atención ciudadana",
                            color=rx.color_mode_cond(light="#64748b", dark="#64748b"),
                            font_size="xs",
                            font_weight="medium",
                            text_transform="uppercase",
                            letter_spacing="0.08em",
                        ),
                        spacing="5",
                        align_items="start",
                        height="100%",
                    ),
                    bg=rx.color_mode_cond(light="rgba(241, 245, 249, 0.75)", dark="rgba(15, 23, 42, 0.45)"),
                    border=rx.color_mode_cond(light="1px solid rgba(203, 213, 225, 0.6)", dark="1px solid rgba(51, 65, 85, 0.65)"),
                    border_radius="2xl",
                    p={"base": "6", "md": "7"},
                    display={"base": "none", "lg": "block"},
                    height="100%",
                ),
                auth_card("Crear Cuenta Ciudadana", State.signup, show_confirm=True),
                columns={"base": "1", "lg": "0.85fr 1.35fr"},
                gap="5",
                width="100%",
                max_width={"base": "95%", "md": "1450px"},
                z_index="1",
                align_items="start",
            ),
            min_height="100vh",
            width="100%",
            padding_y={"base": "6", "md": "10"},
            padding_x={"base": "4", "md": "6"},
            position="relative",
            overflow="hidden"
        ),
        bg=rx.color_mode_cond(light="#f8fafc", dark="#0f172a"),
        min_height="100vh"
    )

def registro_funcionario_page() -> rx.Component:
    return rx.cond(
        State.es_autenticada & (State.rol_usuario == "funcionario"),
        rx.box(
            navbar(),
            rx.center(
                # Orbes Decorativos
                rx.box(position="absolute", top="20%", left="20%", width="300px", height="300px", bg="rgba(139, 92, 246, 0.15)", border_radius="full", filter="blur(80px)", z_index="0"),
                
                auth_card("Registrar Funcionario", State.signup_funcionario, show_confirm=True),
                
                min_height="90vh",
                width="100%",
                padding_y="12",
                padding_x={"base": "4", "md": "8"},
                position="relative",
                overflow="hidden"
            ),
            bg=rx.color_mode_cond(light="#f8fafc", dark="#0f172a"),
            min_height="100vh"
        ),
        rx.box(
            navbar(),
            rx.center(
                access_denied_widget("Solo los funcionarios autenticados pueden registrar nuevos funcionarios."),
                size="3"
            ),
            bg=rx.color_mode_cond(light="#f8fafc", dark="#0f172a"),
            min_height="100vh"
        )
    )


def change_password_page() -> rx.Component:
    return rx.box(
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
    return rx.box(
        toast_notification(),
        rx.toast.provider(position="top-center", close_button=True, offset="20px"),
        rx.center(
            rx.box(position="absolute", top="-140px", left="-120px", width="360px", height="360px", bg="rgba(37, 99, 235, 0.28)", border_radius="full", filter="blur(95px)", z_index="0"),
            rx.box(position="absolute", bottom="-130px", right="-90px", width="340px", height="340px", bg="rgba(14, 165, 233, 0.22)", border_radius="full", filter="blur(90px)", z_index="0"),
            rx.grid(
                rx.box(
                    rx.vstack(
                        rx.badge("Plataforma PQRS", color_scheme="blue", variant="soft", radius="full"),
                        rx.heading(
                            "Gestiona tus solicitudes en un solo lugar",
                            size="8",
                            color=rx.color_mode_cond(light="#0f172a", dark="#f8fafc"),
                            line_height="1.1",
                            letter_spacing="-0.02em",
                        ),
                        rx.text(
                            "Consulta estados, tiempos de respuesta y trazabilidad con una experiencia mas clara y segura.",
                            color=rx.color_mode_cond(light="#475569", dark="#94a3b8"),
                            font_size="md",
                        ),
                        rx.box(
                            rx.image(
                                src="/pqrs.png",
                                alt="Portal PQRS",
                                width="100%",
                                height="190px",
                                object_fit="cover",
                            ),
                            width="100%",
                            border_radius="xl",
                            overflow="hidden",
                            border=rx.color_mode_cond(light="1px solid #cbd5e1", dark="1px solid #334155"),
                            box_shadow=rx.color_mode_cond(light="0 12px 30px -16px rgba(15, 23, 42, 0.45)", dark="0 12px 30px -16px rgba(2, 6, 23, 0.9)"),
                        ),
                        rx.vstack(
                            rx.hstack(rx.icon("shield-check", size=16, color="#38bdf8"), rx.text("Acceso seguro y protegido", color=rx.color_mode_cond(light="#334155", dark="#cbd5e1"), font_size="sm"), spacing="2"),
                            rx.hstack(rx.icon("timer", size=16, color="#38bdf8"), rx.text("Seguimiento de tiempos de respuesta", color=rx.color_mode_cond(light="#334155", dark="#cbd5e1"), font_size="sm"), spacing="2"),
                            rx.hstack(rx.icon("bell-ring", size=16, color="#38bdf8"), rx.text("Notificaciones y trazabilidad", color=rx.color_mode_cond(light="#334155", dark="#cbd5e1"), font_size="sm"), spacing="2"),
                            spacing="3",
                            align_items="start",
                            width="100%",
                        ),
                        rx.spacer(),
                        rx.text("Sistema de atención ciudadana", color=rx.color_mode_cond(light="#64748b", dark="#64748b"), font_size="xs", font_weight="medium", text_transform="uppercase", letter_spacing="0.08em"),
                        spacing="5",
                        align_items="start",
                        height="100%",
                    ),
                    bg=rx.color_mode_cond(light="rgba(241, 245, 249, 0.75)", dark="rgba(15, 23, 42, 0.45)"),
                    border=rx.color_mode_cond(light="1px solid rgba(203, 213, 225, 0.6)", dark="1px solid rgba(51, 65, 85, 0.65)"),
                    border_radius="2xl",
                    p={"base": "6", "md": "7"},
                    display={"base": "none", "lg": "block"},
                    height="100%",
                ),
                rx.box(
                    rx.vstack(
                        rx.center(
                            rx.box(
                                rx.icon("lock", size=28, color=rx.color_mode_cond(light="#2563eb", dark="#60a5fa")),
                                p="3",
                                bg=rx.color_mode_cond(light="#eff6ff", dark="rgba(37, 99, 235, 0.14)"),
                                border="1px solid",
                                border_color=rx.color_mode_cond(light="#bfdbfe", dark="rgba(96, 165, 250, 0.25)"),
                                border_radius="xl",
                            ),
                            width="100%",
                        ),
                        rx.vstack(
                            rx.heading("Bienvenido de vuelta", size="8", color=rx.color_mode_cond(light="#0f172a", dark="#f8fafc"), text_align="center"),
                            rx.text("Ingresa tus credenciales para acceder al sistema", color=rx.color_mode_cond(light="#64748b", dark="#94a3b8"), font_size="md", text_align="center"),
                            spacing="2",
                            width="100%",
                        ),
                        rx.form(
                            rx.vstack(
                                rx.vstack(
                                    rx.text("Correo electrónico", font_weight="medium", font_size="sm", color=rx.color_mode_cond(light="#334155", dark="#cbd5e1")),
                                    rx.input(
                                        placeholder="usuario@empresa.com",
                                        name="correo",
                                        type="email",
                                        value=State.correo,
                                        on_change=State.set_correo,
                                        width="100%",
                                        size="3",
                                        radius="large",
                                        variant="surface",
                                    ),
                                    spacing="2",
                                    width="100%",
                                    align_items="start",
                                ),
                                rx.vstack(
                                    rx.text("Contraseña", font_weight="medium", font_size="sm", color=rx.color_mode_cond(light="#334155", dark="#cbd5e1")),
                                    rx.hstack(
                                        rx.input(
                                            placeholder="••••••••",
                                            name="contraseña",
                                            type=rx.cond(State.show_password, "text", "password"),
                                            value=State.contraseña,
                                            on_change=State.set_contraseña,
                                            width="100%",
                                            size="3",
                                            radius="large",
                                            variant="surface",
                                        ),
                                        rx.button(
                                            rx.cond(State.show_password, rx.icon("eye-off", size=18), rx.icon("eye", size=18)),
                                            on_click=State.toggle_show_password,
                                            type="button",
                                            variant="soft",
                                            size="3",
                                            radius="large",
                                            color_scheme="blue",
                                        ),
                                        width="100%",
                                        spacing="2",
                                    ),
                                    spacing="2",
                                    width="100%",
                                    align_items="start",
                                ),
                                rx.cond(
                                    State.error_de_contraseña != "",
                                    rx.box(
                                        rx.text(State.error_de_contraseña, color="#ef4444", font_size="sm", font_weight="medium"),
                                        p="3",
                                        bg=rx.color_mode_cond(light="#fef2f2", dark="rgba(127, 29, 29, 0.25)"),
                                        border=rx.color_mode_cond(light="1px solid #fecaca", dark="1px solid rgba(239, 68, 68, 0.32)"),
                                        border_radius="lg",
                                        width="100%",
                                        animation="flashMessage 5s ease forwards",
                                        style={
                                            "@keyframes flashMessage": {
                                                "0%": {"opacity": "0", "transform": "translateY(-4px)"},
                                                "10%": {"opacity": "1", "transform": "translateY(0px)"},
                                                "80%": {"opacity": "1", "transform": "translateY(0px)"},
                                                "100%": {"opacity": "0", "transform": "translateY(-4px)"},
                                            }
                                        },
                                    ),
                                    rx.box(),
                                ),
                                rx.button(
                                    rx.hstack(rx.icon("log-in", size=18), rx.text("Iniciar sesión", font_weight="bold"), spacing="2", justify="center"),
                                    type="submit",
                                    color_scheme="blue",
                                    width="100%",
                                    size="4",
                                    radius="large",
                                    margin_top="2",
                                    box_shadow="0 10px 25px -10px rgba(59, 130, 246, 0.75)",
                                    _hover={"transform": "translateY(-1px)", "box_shadow": "0 15px 30px -10px rgba(59, 130, 246, 0.85)"},
                                    transition="all 0.2s",
                                ),
                                spacing="4",
                                width="100%",
                            ),
                            on_submit=State.login,
                            width="100%",
                        ),
                        rx.text(
                            "Al continuar aceptas las políticas de uso y tratamiento de datos.",
                            color=rx.color_mode_cond(light="#64748b", dark="#94a3b8"),
                            font_size="xs",
                            text_align="center",
                        ),
                        rx.center(
                            rx.link(
                                "¿No tienes cuenta? Regístrate aquí",
                                href="/registro",
                                font_size="sm",
                                font_weight="medium",
                                color=rx.color_mode_cond(light="#2563eb", dark="#60a5fa"),
                                _hover={"text_decoration": "underline"},
                            ),
                            width="100%",
                        ),
                        spacing="6",
                        width="100%",
                        align_items="stretch",
                    ),
                    bg=rx.color_mode_cond(light="rgba(255, 255, 255, 0.92)", dark="rgba(15, 23, 42, 0.72)"),
                    border=rx.color_mode_cond(light="1px solid rgba(226, 232, 240, 0.9)", dark="1px solid rgba(51, 65, 85, 0.75)"),
                    border_radius="2xl",
                    p={"base": "6", "md": "8"},
                    box_shadow=rx.color_mode_cond(light="0 25px 55px -20px rgba(15, 23, 42, 0.35)", dark="0 25px 55px -20px rgba(2, 6, 23, 0.85)"),
                ),
                columns={"base": "1", "lg": "1.1fr 1fr"},
                gap="5",
                width="100%",
                max_width={"base": "95%", "md": "1000px"},
                z_index="1",
            ),
            width="100%",
            min_height="100vh",
            position="relative",
            overflow="hidden",
            px="4",
            py={"base": "6", "md": "10"},
        ),
        bg=rx.color_mode_cond(light="#f8fafc", dark="#0f172a"),
        width="100%",
        min_height="100vh",
    )


def politica_privacidad_page() -> rx.Component:
    text_color = rx.color_mode_cond(light="#0f172a", dark="#f8fafc")
    subtext = rx.color_mode_cond(light="#475569", dark="#94a3b8")
    card_bg = rx.color_mode_cond(light="rgba(255, 255, 255, 0.9)", dark="rgba(15, 23, 42, 0.7)")
    card_border = rx.color_mode_cond(light="1px solid rgba(203, 213, 225, 0.75)", dark="1px solid rgba(51, 65, 85, 0.65)")

    def section_card(title: str, icon: str, body: rx.Component) -> rx.Component:
        return rx.box(
            rx.vstack(
                rx.hstack(
                    rx.box(
                        rx.icon(icon, size=18, color="#60a5fa"),
                        p="2.5",
                        border_radius="lg",
                        bg=rx.color_mode_cond(light="rgba(219, 234, 254, 0.9)", dark="rgba(37, 99, 235, 0.18)"),
                        border=rx.color_mode_cond(light="1px solid #bfdbfe", dark="1px solid rgba(96, 165, 250, 0.28)"),
                    ),
                    rx.heading(title, size="4", color=text_color, font_weight="bold"),
                    spacing="3",
                    align_items="center",
                    width="100%",
                ),
                body,
                spacing="3",
                width="100%",
                align_items="start",
            ),
            p={"base": "5", "md": "6"},
            bg=card_bg,
            border=card_border,
            border_radius="2xl",
            backdrop_filter="blur(18px)",
            box_shadow=rx.color_mode_cond(light="0 18px 40px -24px rgba(30, 64, 175, 0.4)", dark="0 18px 40px -24px rgba(2, 6, 23, 0.9)"),
            width="100%",
        )

    return rx.box(
        navbar(),
        rx.center(
            rx.box(
                rx.box(position="absolute", top="-140px", left="-120px", width="360px", height="360px", bg="rgba(37, 99, 235, 0.20)", border_radius="full", filter="blur(95px)", z_index="0"),
                rx.box(position="absolute", bottom="-140px", right="-110px", width="360px", height="360px", bg="rgba(14, 165, 233, 0.18)", border_radius="full", filter="blur(95px)", z_index="0"),
                rx.vstack(
                    rx.box(
                        rx.vstack(
                            rx.badge("Transparencia y protección de datos", color_scheme="blue", variant="soft", radius="full"),
                            rx.heading("Política de Privacidad", size="8", color=text_color, font_weight="bold", letter_spacing="-0.02em"),
                            rx.text(
                                "En esta plataforma tratamos tus datos con responsabilidad, transparencia y seguridad. "
                                "Tu información personal se usa únicamente para gestionar solicitudes PQRS y mejorar el servicio.",
                                color=subtext,
                                font_size="md",
                                line_height="1.6",
                            ),
                            rx.hstack(
                                rx.box(
                                    rx.icon("scale", size=18, color="#93c5fd"),
                                    rx.text("Ley 1581 de 2012", font_size="xs", color=subtext, font_weight="medium"),
                                    spacing="2",
                                    align_items="center",
                                ),
                                rx.box(
                                    rx.icon("clipboard-check", size=18, color="#93c5fd"),
                                    rx.text("Uso limitado a PQRS", font_size="xs", color=subtext, font_weight="medium"),
                                    spacing="2",
                                    align_items="center",
                                ),
                                spacing="4",
                                flex_wrap="wrap",
                                width="100%",
                            ),
                            spacing="3",
                            align_items="start",
                        ),
                        p={"base": "5", "md": "7"},
                        bg=rx.color_mode_cond(light="rgba(255, 255, 255, 0.75)", dark="rgba(15, 23, 42, 0.55)"),
                        border=card_border,
                        border_radius="3xl",
                        backdrop_filter="blur(18px)",
                        box_shadow=rx.color_mode_cond(light="0 30px 60px -30px rgba(30, 64, 175, 0.35)", dark="0 30px 60px -20px rgba(2, 6, 23, 0.9)"),
                        width="100%",
                        z_index="1",
                    ),
                    rx.grid(
                        section_card(
                            "Datos recolectados",
                            "database",
                            rx.vstack(
                                rx.text("Recopilamos datos necesarios para la gestión de solicitudes:", color=subtext, font_size="sm"),
                                rx.vstack(
                                    rx.text("• Correo electrónico", color=subtext, font_size="sm"),
                                    rx.text("• Identificación (tipo y número)", color=subtext, font_size="sm"),
                                    rx.text("• Nombres y apellidos", color=subtext, font_size="sm"),
                                    rx.text("• Teléfono y ubicación (departamento/ciudad/dirección)", color=subtext, font_size="sm"),
                                    spacing="1",
                                    align_items="start",
                                ),
                                spacing="2",
                                width="100%",
                                align_items="start",
                            ),
                        ),
                        section_card(
                            "Finalidad del tratamiento",
                            "target",
                            rx.vstack(
                                rx.text("Usamos tus datos para:", color=subtext, font_size="sm"),
                                rx.vstack(
                                    rx.text("• Contactarte y notificarte sobre el estado de tu PQRS", color=subtext, font_size="sm"),
                                    rx.text("• Radicar y administrar la solicitud en el sistema", color=subtext, font_size="sm"),
                                    rx.text("• Generar trazabilidad y auditoría del proceso de atención", color=subtext, font_size="sm"),
                                    spacing="1",
                                    align_items="start",
                                ),
                                spacing="2",
                                width="100%",
                                align_items="start",
                            ),
                        ),
                        section_card(
                            "Derechos del titular",
                            "badge-check",
                            rx.vstack(
                                rx.text(
                                    "Puedes solicitar consulta, actualización, corrección o eliminación de tus datos conforme a la normativa vigente.",
                                    color=subtext,
                                    font_size="sm",
                                    line_height="1.6",
                                ),
                                rx.text(
                                    "También puedes revocar la autorización cuando sea procedente.",
                                    color=subtext,
                                    font_size="sm",
                                ),
                                spacing="2",
                                width="100%",
                                align_items="start",
                            ),
                        ),
                        section_card(
                            "Contacto y solicitudes",
                            "mail",
                            rx.vstack(
                                rx.text("Si necesitas ejercer tus derechos o tienes dudas:", color=subtext, font_size="sm"),
                                rx.hstack(
                                    rx.icon("at-sign", size=16, color="#60a5fa"),
                                    rx.text("Soporte: ", font_size="sm", color=subtext),
                                    rx.text("soporte@empresa.com", font_size="sm", color=rx.color_mode_cond(light="#1d4ed8", dark="#93c5fd"), font_weight="semibold"),
                                    spacing="2",
                                    flex_wrap="wrap",
                                ),
                                spacing="2",
                                width="100%",
                                align_items="start",
                            ),
                        ),
                        columns={"base": "1", "lg": "2"},
                        gap="4",
                        width="100%",
                        z_index="1",
                    ),
                    rx.hstack(
                        rx.link(
                            rx.button(
                                rx.icon("arrow-left", size=18),
                                "Volver",
                                size="3",
                                variant="soft",
                                radius="full",
                                color_scheme="gray",
                            ),
                            href="/registro",
                        ),
                        rx.spacer(),
                        rx.link(
                            rx.button(
                                rx.icon("file-text", size=18),
                                "Ir a registro",
                                size="3",
                                radius="full",
                                color_scheme="blue",
                                box_shadow="0 10px 24px -12px rgba(37, 99, 235, 0.65)",
                            ),
                            href="/registro",
                        ),
                        width="100%",
                        z_index="1",
                        flex_wrap="wrap",
                        spacing="3",
                    ),
                    spacing="5",
                    width="100%",
                    z_index="1",
                ),
                width="100%",
                max_width="1100px",
                position="relative",
                px={"base": "4", "md": "8"},
                py={"base": "8", "md": "12"},
            ),
            width="100%",
            min_height="90vh",
        ),
        bg=rx.color_mode_cond(light="#f8fafc", dark="#0f172a"),
        min_height="100vh",
    )



def dashboard() -> rx.Component:
    # Bento Variables
    text_color = rx.color_mode_cond(light="#0f172a", dark="#f8fafc")
    subtext_color = rx.color_mode_cond(light="#64748b", dark="#94a3b8")
    card_bg = rx.color_mode_cond(light="rgba(255, 255, 255, 0.6)", dark="rgba(30, 41, 59, 0.4)")
    card_border = rx.color_mode_cond(light="1px solid rgba(255, 255, 255, 0.8)", dark="1px solid rgba(51, 65, 85, 0.5)")
    accent_bg = rx.color_mode_cond(light="linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%)", dark="linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(30, 64, 175, 0.2) 100%)")

    # Bloque A: Perfil Izquierdo
    bento_profile = rx.box(
        rx.vstack(
            rx.box(
                rx.heading(rx.cond(State.nombres, State.nombres.to_string()[0:1], "C"), size="9", color="#3b82f6"),
                width="80px", height="80px", border_radius="2xl", bg=rx.color_mode_cond(light="white", dark="#0f172a"),
                display="flex", align_items="center", justify_content="center", box_shadow="0 10px 15px -3px rgba(0,0,0,0.1)",
                margin_bottom="4"
            ),
            rx.heading(f"¡Hola, {State.nombres}!", size="7", color=text_color, font_weight="bold"),
            rx.text("Bienvenido a tu panel digital.", color=subtext_color, font_size="sm"),
            
            rx.divider(margin_y="6", opacity="0.5"),
            
            rx.vstack(
                rx.hstack(rx.icon("file-text", size=18, color="#3b82f6"), rx.text("Total Solicitudes", font_weight="medium"), rx.spacer(), rx.heading(State.solicitudes.length(), size="4"), width="100%"),
                spacing="4", width="100%"
            ),
            
            rx.spacer(),
            rx.box(
                rx.icon("shield-check", size=24, color="#10b981", margin_bottom="2"),
                rx.text("Cuenta verificada y segura.", font_size="xs", color=subtext_color),
                bg=rx.color_mode_cond(light="white", dark="rgba(15, 23, 42, 0.5)"), padding="4", border_radius="xl", width="100%"
            ),
            spacing="2", align_items="start", height="100%", width="100%"
        ),
        p="8", bg=card_bg, backdrop_filter="blur(24px)", border=card_border, border_radius="3xl",
        box_shadow="0 25px 50px -12px rgba(0, 0, 0, 0.05)", height="100%", width="100%", grid_row="span 2"
    )

    # Bloque B: Banner de Acción Rápida (Arriba Derecha)
    bento_action = rx.box(
        rx.hstack(
            rx.vstack(
                rx.heading("¿Necesitas iniciar un trámite?", size="6", color=text_color),
                rx.text("Radica tu Petición, Queja, Reclamo o Sugerencia en minutos.", color=subtext_color),
                align_items="start", spacing="2"
            ),
            rx.spacer(),
            rx.link(
                rx.button(rx.icon("plus", size=20), "Nueva Solicitud", color_scheme="blue", size="4", radius="full", box_shadow="0 10px 15px -3px rgba(59, 130, 246, 0.4)", _hover={"transform": "scale(1.05)"}, transition="all 0.2s"),
                href="/solicitudes"
            ),
            width="100%", align_items="center", justify="between", flex_wrap="wrap"
        ),
        p="8", bg=accent_bg, border=card_border, border_radius="3xl", box_shadow="0 10px 15px -3px rgba(0,0,0,0.05)", width="100%", backdrop_filter="blur(16px)"
    )

    # Bloque C: Bandeja de Entrada (Grid Inferior)
    bento_grid = rx.cond(
        State.solicitudes,
        rx.grid(
            rx.foreach(
                State.solicitudes,
                lambda solicitud: rx.box(
                    rx.vstack(
                        rx.hstack(
                            rx.badge(
                                solicitud["tipo_solicitud"],
                                variant="soft",
                                radius="full",
                                size="2",
                                color_scheme=rx.cond(
                                    solicitud["tipo_solicitud"] == "Petición",
                                    "blue",
                                    rx.cond(
                                        solicitud["tipo_solicitud"] == "Queja",
                                        "orange",
                                        rx.cond(solicitud["tipo_solicitud"] == "Reclamo", "red", "green"),
                                    ),
                                ),
                            ),
                            rx.spacer(),
                            rx.badge(
                                solicitud["estado"],
                                variant="soft",
                                radius="full",
                                size="2",
                                font_weight="medium",
                                color_scheme=rx.cond(
                                    solicitud["estado"] == "Radicada",
                                    "blue",
                                    rx.cond(
                                        solicitud["estado"] == "Cerrada",
                                        "green",
                                        "orange",
                                    ),
                                ),
                            ),
                            width="100%",
                            align_items="center",
                        ),
                        rx.box(rx.text(solicitud["radicado"], font_size="xs", font_family="monospace", color="#94a3b8"), rx.text(solicitud["fecha"], font_size="xs", color="#94a3b8"), display="flex", justify_content="space-between", width="100%", margin_bottom="2"),
                        rx.heading(solicitud["asunto"], size="4", color=text_color, margin_bottom="1", line_height="1.3"),
                        rx.text(solicitud["descripcion"], font_size="sm", color=subtext_color, style={"display": "-webkit-box", "WebkitLineClamp": "3", "WebkitBoxOrient": "vertical", "overflow": "hidden"}),
                        rx.spacer(),
                        rx.cond(solicitud.get("documento_basename"), rx.hstack(rx.icon("paperclip", size=14, color="#3b82f6"), rx.link("Ver adjunto", href=solicitud.get("documento_href", "#"), color="#3b82f6", font_size="xs", target="_blank"), spacing="2", align_items="center", bg=rx.color_mode_cond(light="white", dark="rgba(15,23,42,0.5)"), padding_x="3", padding_y="1.5", border_radius="md", width="100%"), rx.box()),
                        spacing="0", align_items="start", width="100%", height="100%"
                    ),
                    p="6", bg=card_bg, border=card_border, border_radius="2xl", width="100%", height="100%", box_shadow="0 4px 6px -1px rgba(0, 0, 0, 0.05)", backdrop_filter="blur(16px)", _hover={"transform": "translateY(-4px)", "border_color": "rgba(59, 130, 246, 0.5)", "box_shadow": "0 20px 25px -5px rgba(0, 0, 0, 0.1)"}, transition="all 0.3s ease"
                )
            ),
            template_columns={"base": "1fr", "lg": "repeat(2, 1fr)"}, gap="6", width="100%"
        ),
        # Empty State
        rx.center(
            rx.vstack(
                rx.box(rx.icon("layers", size=48, color="#cbd5e1"), bg="rgba(255,255,255,0.5)", padding="6", border_radius="full"),
                rx.heading("Tu bandeja está impecable", size="5", color=text_color),
                rx.text("Aún no hay trámites aquí.", color=subtext_color),
                spacing="3", align_items="center"
            ),
            p="12", bg=card_bg, border=card_border, border_radius="3xl", width="100%", height="100%", min_height="300px", backdrop_filter="blur(16px)"
        )
    )

    return rx.cond(
        rx.State.is_hydrated,
        rx.cond(
            State.es_autenticada & (State.rol_usuario == "ciudadano"),
            rx.box(
                navbar(),
                rx.center(
                    # Fondos holográficos abstractos
                    rx.box(position="absolute", top="-10%", left="0%", width="500px", height="500px", bg="rgba(139, 92, 246, 0.1)", border_radius="full", filter="blur(120px)", z_index="0"),
                    rx.box(position="absolute", bottom="-10%", right="0%", width="600px", height="600px", bg="rgba(59, 130, 246, 0.1)", border_radius="full", filter="blur(150px)", z_index="0"),
                    
                    # Bento Grid Maestro
                    rx.grid(
                        bento_profile,
                        rx.vstack(bento_action, bento_grid, spacing="6", width="100%", height="100%"),
                        template_columns={"base": "1fr", "xl": "300px 1fr"},
                        gap="6", width="100%", max_width="1400px", padding_x={"base": "4", "md": "8"}, padding_y="12", z_index="1"
                    ),
                    width="100%", min_height="90vh", position="relative", overflow="hidden", align_items="start"
                ),
                bg=rx.color_mode_cond(light="#f8fafc", dark="#0f172a"), width="100%", min_height="100vh"
            ),
            rx.box(
                navbar(),
                rx.center(access_denied_widget("Esta página es solo para ciudadanos."), size="3"),
                bg=rx.color_mode_cond(light="#f8fafc", dark="#0f172a"), min_height="100vh"
            )
        ),
        rx.center(rx.spinner(size="3", color="#3b82f6"), height="50vh")
    )



def funcionario_dashboard() -> rx.Component:
    text_color = rx.color_mode_cond(light="#0f172a", dark="#f8fafc")
    subtext_color = rx.color_mode_cond(light="#64748b", dark="#94a3b8")
    card_bg = rx.color_mode_cond(light="rgba(255, 255, 255, 0.85)", dark="rgba(15, 23, 42, 0.7)")
    card_border = rx.color_mode_cond(light="1px solid rgba(255, 255, 255, 0.5)", dark="1px solid rgba(51, 65, 85, 0.5)")

    return rx.cond(
        rx.State.is_hydrated,
        rx.cond(
            State.es_autenticada & (State.rol_usuario == "funcionario"),
            rx.box(
                navbar(),
                rx.center(
                    # Fondo Atmosférico
                    rx.box(position="absolute", top="-10%", left="-5%", width="600px", height="600px", bg="rgba(59, 130, 246, 0.15)", border_radius="full", filter="blur(150px)", z_index="0"),
                    rx.box(position="absolute", bottom="-10%", right="-5%", width="700px", height="700px", bg="rgba(139, 92, 246, 0.1)", border_radius="full", filter="blur(150px)", z_index="0"),
                    
                    # Contenedor Principal (GRID BENTO BOX)
                    rx.grid(
                        # ==========================================
                        # COLUMNA IZQUIERDA (1/3) - Perfil y Admin
                        # ==========================================
                        rx.vstack(
                            # Perfil de Funcionario
                            rx.box(
                                rx.vstack(
                                    rx.hstack(
                                        rx.box(rx.icon("shield-check", size=32, color="white"), p="3", bg="linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%)", border_radius="2xl", box_shadow="0 10px 15px -3px rgba(59, 130, 246, 0.4)"),
                                        rx.vstack(
                                            rx.heading("Consola Operativa", size="6", color=text_color, font_weight="bold"),
                                            rx.badge("Admin / Funcionario", color_scheme="blue", variant="soft", radius="full"),
                                            spacing="1", align_items="start"
                                        ),
                                        spacing="4", align_items="center"
                                    ),
                                    rx.divider(margin_y="4", opacity="0.3"),
                                    rx.text("Supervisa, gestiona y da respuesta a las solicitudes ciudadanas desde este panel centralizado.", color=subtext_color, font_size="sm"),
                                    align_items="stretch"
                                ),
                                p="6", width="100%", bg=card_bg, backdrop_filter="blur(24px)", border=card_border, border_radius="3xl", box_shadow="0 20px 40px -15px rgba(0,0,0,0.1)"
                            ),
                            
                            # Modulo de Usuarios Registrados
                            rx.box(
                                rx.vstack(
                                    rx.hstack(
                                        rx.icon("users", size=20, color="#3b82f6"),
                                        rx.heading("Directorio", size="4", color=text_color, font_weight="bold"),
                                        rx.spacer(),
                                        rx.badge(State.usuarios_registrados_count, color_scheme="blue", radius="full"),
                                        width="100%", align_items="center"
                                    ),
                                    rx.divider(margin_y="2", opacity="0.3"),
                                    rx.box(
                                        rx.grid(
                                            rx.foreach(
                                                State.usuarios_registrados[:6],
                                                lambda usuario: rx.box(
                                                    rx.hstack(
                                                        rx.avatar(
                                                            fallback=rx.cond(usuario["rol"] == "funcionario", "FN", "CD"),
                                                            size="2",
                                                            radius="full",
                                                            color_scheme=rx.cond(usuario["rol"] == "funcionario", "blue", "gray"),
                                                        ),
                                                        rx.vstack(
                                                            rx.text(
                                                                usuario["email"],
                                                                font_size="xs",
                                                                font_weight="bold",
                                                                color=text_color,
                                                                no_wrap=True,
                                                                overflow="hidden",
                                                                text_overflow="ellipsis",
                                                                max_width="190px",
                                                            ),
                                                            rx.badge(
                                                                rx.cond(usuario["rol"] == "funcionario", rx.icon("shield", size=12), rx.icon("user", size=12)),
                                                                usuario["rol"],
                                                                color_scheme=rx.cond(usuario["rol"] == "funcionario", "blue", "gray"),
                                                                variant="soft",
                                                                radius="full",
                                                                size="1",
                                                            ),
                                                            spacing="1",
                                                            align_items="start",
                                                        ),
                                                        rx.spacer(),
                                                        rx.hstack(
                                                            rx.button(
                                                                rx.icon("mail", size=16),
                                                                variant="soft",
                                                                size="2",
                                                                radius="full",
                                                                color_scheme="blue",
                                                                is_disabled=True,
                                                            ),
                                                            rx.link(
                                                                rx.button(
                                                                    rx.icon("arrow-right", size=16),
                                                                    variant="soft",
                                                                    size="2",
                                                                    radius="full",
                                                                    color_scheme="gray",
                                                                ),
                                                                href="/usuarios",
                                                            ),
                                                            spacing="2",
                                                            align_items="center",
                                                        ),
                                                        width="100%",
                                                        align_items="center",
                                                    ),
                                                    p="3",
                                                    border_radius="xl",
                                                    bg=rx.color_mode_cond(light="rgba(248, 250, 252, 0.65)", dark="rgba(30, 41, 59, 0.25)"),
                                                    border=rx.color_mode_cond(light="1px solid rgba(226,232,240,0.9)", dark="1px solid rgba(51,65,85,0.6)"),
                                                    box_shadow=rx.color_mode_cond(light="0 8px 16px -12px rgba(15,23,42,0.25)", dark="0 10px 20px -16px rgba(0,0,0,0.65)"),
                                                    _hover={"transform": "translateY(-1px)"},
                                                    transition="all 0.18s",
                                                ),
                                            ),
                                            columns=rx.breakpoints(initial="1", sm="2"),
                                            spacing="3",
                                            width="100%",
                                        ),
                                        width="100%",
                                        max_height="320px",
                                        overflow_y="auto",
                                        pr="1",
                                    ),
                                    rx.cond(
                                        State.usuarios_registrados_count > 5,
                                        rx.link(rx.button("Ver directorio completo", variant="soft", size="2", width="100%", color_scheme="blue", mt="2"), href="/usuarios")
                                    ),
                                    align_items="stretch"
                                ),
                                p="5", width="100%", bg=card_bg, backdrop_filter="blur(24px)", border=card_border, border_radius="3xl", box_shadow="0 20px 40px -15px rgba(0,0,0,0.1)"
                            ),
                            
                            spacing="6", width="100%"
                        ),

                        # ==========================================
                        # COLUMNA DERECHA (2/3) - Gestion Operativa
                        # ==========================================
                        rx.vstack(
                            # Grid de Metricas (4 Tarjetas Horizontales)
                            rx.grid(
                                rx.box(
                                    rx.hstack(
                                        rx.box(
                                            rx.icon("layers", size=20, color="#3b82f6"),
                                            p="2",
                                            border_radius="lg",
                                            bg=rx.color_mode_cond(light="#dbeafe", dark="rgba(59, 130, 246, 0.18)"),
                                        ),
                                        rx.vstack(
                                            rx.text("Total", font_size="xs", color=subtext_color, font_weight="bold", text_transform="uppercase", letter_spacing="0.06em"),
                                            rx.heading(State.numero_solicitudes, size="7", color=text_color),
                                            spacing="1",
                                            align_items="start",
                                        ),
                                        spacing="3",
                                        align_items="center",
                                        width="100%",
                                        justify="between",
                                    ),
                                    p="4",
                                    bg=card_bg,
                                    backdrop_filter="blur(24px)",
                                    border=card_border,
                                    border_radius="2xl",
                                    border_left="4px solid #3b82f6",
                                ),
                                rx.box(
                                    rx.hstack(
                                        rx.box(
                                            rx.icon("file-plus-2", size=20, color="#f97316"),
                                            p="2",
                                            border_radius="lg",
                                            bg=rx.color_mode_cond(light="#ffedd5", dark="rgba(249, 115, 22, 0.16)"),
                                        ),
                                        rx.vstack(
                                            rx.text("Radicadas", font_size="xs", color=subtext_color, font_weight="bold", text_transform="uppercase", letter_spacing="0.06em"),
                                            rx.heading(State.numero_solicitudes_radicadas, size="7", color=text_color),
                                            spacing="1",
                                            align_items="start",
                                        ),
                                        spacing="3",
                                        align_items="center",
                                        width="100%",
                                        justify="between",
                                    ),
                                    p="4",
                                    bg=card_bg,
                                    backdrop_filter="blur(24px)",
                                    border=card_border,
                                    border_radius="2xl",
                                    border_left="4px solid #f97316",
                                ),
                                rx.box(
                                    rx.hstack(
                                        rx.box(
                                            rx.icon("activity", size=20, color="#10b981"),
                                            p="2",
                                            border_radius="lg",
                                            bg=rx.color_mode_cond(light="#dcfce7", dark="rgba(16, 185, 129, 0.14)"),
                                        ),
                                        rx.vstack(
                                            rx.text("En Proceso", font_size="xs", color=subtext_color, font_weight="bold", text_transform="uppercase", letter_spacing="0.06em"),
                                            rx.heading(State.numero_solicitudes_actualizadas, size="7", color=text_color),
                                            spacing="1",
                                            align_items="start",
                                        ),
                                        spacing="3",
                                        align_items="center",
                                        width="100%",
                                        justify="between",
                                    ),
                                    p="4",
                                    bg=card_bg,
                                    backdrop_filter="blur(24px)",
                                    border=card_border,
                                    border_radius="2xl",
                                    border_left="4px solid #10b981",
                                ),
                                rx.box(
                                    rx.hstack(
                                        rx.box(
                                            rx.icon("circle-check", size=20, color="#8b5cf6"),
                                            p="2",
                                            border_radius="lg",
                                            bg=rx.color_mode_cond(light="#ede9fe", dark="rgba(139, 92, 246, 0.18)"),
                                        ),
                                        rx.vstack(
                                            rx.text("Cerradas", font_size="xs", color=subtext_color, font_weight="bold", text_transform="uppercase", letter_spacing="0.06em"),
                                            rx.heading(State.numero_solicitudes_cerradas, size="7", color=text_color),
                                            spacing="1",
                                            align_items="start",
                                        ),
                                        spacing="3",
                                        align_items="center",
                                        width="100%",
                                        justify="between",
                                    ),
                                    p="4",
                                    bg=card_bg,
                                    backdrop_filter="blur(24px)",
                                    border=card_border,
                                    border_radius="2xl",
                                    border_left="4px solid #8b5cf6",
                                ),
                                template_columns={"base": "repeat(2, 1fr)", "md": "repeat(4, 1fr)"}, gap="4", width="100%"
                            ),
                            
                            # Command Bar (Buscador y Filtros Cristalinos)
                            rx.box(
                                rx.hstack(
                                    rx.hstack(
                                        rx.icon("search", size=20, color=subtext_color),
                                        rx.input(placeholder="Buscar por radicado, asunto...", value=State.query_solicitud, on_change=State.set_query_solicitud, variant="surface", outline="none", border="none", bg="transparent", _focus={"box_shadow": "none"}, width="250px"),
                                        align_items="center", bg=rx.color_mode_cond(light="rgba(255,255,255,0.5)", dark="rgba(15,23,42,0.5)"), p="2", border_radius="xl", flex="1"
                                    ),
                                    rx.vstack(
                                        rx.text("Estado", font_size="xs", color=subtext_color, font_weight="medium"),
                                        rx.select(
                                            ["Todas", "Radicada", "En Proceso", "Cerrada"],
                                            value=State.filter_estado_solicitud,
                                            on_change=State.set_filter_estado_solicitud,
                                            size="3",
                                            radius="full",
                                            variant="soft",
                                            width="170px",
                                        ),
                                        spacing="1",
                                        align_items="start",
                                    ),
                                    rx.vstack(
                                        rx.text("Tipo Solicitud", font_size="xs", color=subtext_color, font_weight="medium"),
                                        rx.select(
                                            ["Todas", "Petición", "Queja", "Reclamo", "Sugerencia"],
                                            value=State.filter_tipo_solicitud,
                                            on_change=State.set_filter_tipo_solicitud,
                                            size="3",
                                            radius="full",
                                            variant="soft",
                                            width="170px",
                                        ),
                                        spacing="1",
                                        align_items="start",
                                    ),
                                    rx.vstack(
                                        rx.text("Días Restantes", font_size="xs", color=subtext_color, font_weight="medium"),
                                        rx.select(
                                            ["Todos", "Vencidas", "0-3", "4-10", "11+"],
                                            value=State.filter_dias_restantes,
                                            on_change=State.set_filter_dias_restantes,
                                            size="3",
                                            radius="full",
                                            variant="soft",
                                            width="170px",
                                            placeholder="Días restantes",
                                        ),
                                        spacing="1",
                                        align_items="start",
                                    ),
                                    rx.button(rx.icon("filter", size=18), "Buscar", on_click=State.buscar_solicitudes, size="3", color_scheme="blue", radius="full", box_shadow="0 4px 10px rgba(59, 130, 246, 0.3)"),
                                    spacing="4", width="100%", align_items="center", flex_wrap="wrap"
                                ),
                                p="4", width="100%", bg=card_bg, backdrop_filter="blur(24px)", border=card_border, border_radius="2xl", margin_top="4"
                            ),
                            
                            # Solicitudes activas (las cerradas van a pestaña aparte)
                            rx.vstack(
                                rx.box(
                                    rx.hstack(
                                        rx.heading("Solicitudes activas", size="5", color=text_color, font_weight="bold"),
                                        rx.spacer(),
                                        rx.badge(State.solicitudes_abiertas.length(), color_scheme="blue", variant="soft", radius="full"),
                                        rx.link(
                                            rx.button(
                                                "Ver cerradas",
                                                size="2",
                                                variant="soft",
                                                color_scheme="green",
                                                radius="full",
                                            ),
                                            href="/dashboard-funcionario-cerradas",
                                        ),
                                        width="100%",
                                    ),
                                    width="100%",
                                    mt="4",
                                ),
                                rx.cond(
                                    State.solicitudes_abiertas,
                                    rx.grid(
                                        rx.foreach(
                                            State.solicitudes_abiertas,
                                            lambda solicitud: rx.box(
                                                rx.vstack(
                                                    rx.hstack(
                                                        rx.badge(
                                                            rx.icon("hash", size=12),
                                                            solicitud['radicado'],
                                                            color_scheme="gray",
                                                            variant="surface",
                                                            radius="full",
                                                        ),
                                                        rx.spacer(),
                                                        rx.badge(
                                                            rx.cond(
                                                                solicitud['estado'] == 'Radicada',
                                                                rx.icon("file-plus-2", size=12),
                                                                rx.cond(
                                                                    solicitud['estado'] == 'Actualizada',
                                                                    rx.icon("activity", size=12),
                                                                    rx.icon("circle-check", size=12),
                                                                ),
                                                            ),
                                                            solicitud['estado'],
                                                            color_scheme=rx.cond(
                                                                solicitud['estado'] == 'Radicada',
                                                                "orange",
                                                                rx.cond(solicitud['estado'] == 'Actualizada', "blue", "green"),
                                                            ),
                                                            variant="soft",
                                                            size="2",
                                                            radius="full",
                                                        ),
                                                        width="100%",
                                                        align_items="center",
                                                    ),
                                                    rx.vstack(
                                                        rx.heading(
                                                            solicitud['asunto'],
                                                            size="5",
                                                            color=text_color,
                                                            font_weight="bold",
                                                            line_height="1.25",
                                                            style={"display": "-webkit-box", "WebkitLineClamp": "2", "WebkitBoxOrient": "vertical", "overflow": "hidden"},
                                                        ),
                                                        rx.text(
                                                            solicitud['descripcion'],
                                                            font_size="sm",
                                                            color=subtext_color,
                                                            style={"display": "-webkit-box", "WebkitLineClamp": "3", "WebkitBoxOrient": "vertical", "overflow": "hidden"},
                                                            min_height="60px",
                                                        ),
                                                        rx.divider(opacity="0.35"),
                                                        rx.hstack(
                                                            rx.badge(
                                                                rx.icon("layers", size=12),
                                                                solicitud['tipo_solicitud'],
                                                                variant="soft",
                                                                color_scheme="purple",
                                                                radius="full",
                                                            ),
                                                            rx.badge(
                                                                rx.icon("users", size=12),
                                                                solicitud.get('area_responsable', 'No asignada'),
                                                                variant="soft",
                                                                color_scheme="cyan",
                                                                radius="full",
                                                            ),
                                                            rx.cond(
                                                                solicitud['estado'] != 'Cerrada',
                                                                rx.badge(
                                                                    rx.icon("clock", size=12),
                                                                    rx.cond(solicitud['semaforo_expired'], "Vencida", f"{solicitud['semaforo_remaining']} días"),
                                                                    color_scheme=rx.cond(
                                                                        solicitud['semaforo_fill'] == "green",
                                                                        "green",
                                                                        rx.cond(solicitud['semaforo_fill'] == "orange", "orange", "red"),
                                                                    ),
                                                                    variant="soft",
                                                                    radius="full",
                                                                ),
                                                                rx.box(),
                                                            ),
                                                            spacing="2",
                                                            width="100%",
                                                            flex_wrap="wrap",
                                                        ),
                                                        rx.spacer(),
                                                        rx.hstack(
                                                            rx.button(
                                                                rx.icon("history", size=16),
                                                                "Historial",
                                                                on_click=lambda _event, id=solicitud['id']: State.abrir_historial(id),
                                                                size="2",
                                                                variant="soft",
                                                                color_scheme="gray",
                                                                radius="full",
                                                                _hover={"transform": "translateY(-1px)"},
                                                                transition="all 0.2s ease",
                                                            ),
                                                            rx.button(
                                                                rx.icon("refresh-cw", size=16),
                                                                "Estado",
                                                                on_click=lambda _event, id=solicitud['id'], estado=solicitud['estado']: State.abrir_editor_estado(id, estado),
                                                                size="2",
                                                                color_scheme="blue",
                                                                variant="solid",
                                                                radius="full",
                                                                _hover={"transform": "translateY(-1px)", "box_shadow": "0 10px 20px -14px rgba(59,130,246,0.6)"},
                                                                transition="all 0.2s ease",
                                                            ),
                                                            rx.button(
                                                                rx.icon("users", size=16),
                                                                "Área",
                                                                on_click=lambda _event, id=solicitud['id'], area=solicitud.get('area_responsable', ''): State.abrir_asignar_area(id, area),
                                                                size="2",
                                                                color_scheme="green",
                                                                variant="soft",
                                                                radius="full",
                                                                _hover={"transform": "translateY(-1px)"},
                                                                transition="all 0.2s ease",
                                                            ),
                                                            width="100%",
                                                            align_items="center",
                                                        ),
                                                        spacing="3",
                                                        align_items="start",
                                                        width="100%",
                                                        height="100%",
                                                        p="4",
                                                    ),
                                                    spacing="3",
                                                    align_items="start",
                                                    width="100%",
                                                    height="100%",
                                                ),
                                                bg=rx.color_mode_cond(light="rgba(255,255,255,0.95)", dark="rgba(15,23,42,0.88)"),
                                                border=card_border,
                                                border_radius="2xl",
                                                width="100%",
                                                min_height="340px",
                                                position="relative",
                                                overflow="hidden",
                                                box_shadow="0 14px 28px -16px rgba(15,23,42,0.35)",
                                                _hover={"transform": "translateY(-5px)", "box_shadow": "0 26px 42px -18px rgba(59, 130, 246, 0.34)", "border_color": rx.color_mode_cond(light="rgba(59,130,246,0.35)", dark="rgba(96,165,250,0.35)")},
                                                transition="all 0.25s ease",
                                            )
                                        ),
                                        display="grid",
                                        grid_template_columns=rx.breakpoints(initial="repeat(1, minmax(0, 1fr))", md="repeat(2, minmax(0, 1fr))", xl="repeat(3, minmax(0, 1fr))"),
                                        grid_auto_rows="1fr",
                                        gap="5",
                                        width="100%",
                                    ),
                                    rx.center(
                                        rx.vstack(
                                            rx.icon("inbox", size=64, color=subtext_color, opacity="0.3"),
                                            rx.heading("Sin solicitudes activas", size="5", color=text_color),
                                            rx.text("No hay radicados activos en este filtro.", color=subtext_color),
                                            align_items="center", spacing="4"
                                        ),
                                        min_height="220px", width="100%"
                                    )
                                ),
                                spacing="4",
                                width="100%",
                            ),
                            
                            spacing="4", width="100%"
                        ),
                        
                        template_columns={"base": "1fr", "lg": "340px 1fr"}, gap="6", width="100%", max_width="100%", padding_y="8", padding_x={"base": "2", "md": "4"}, z_index="1"
                    ),
                    
                    # ==========================================
                    # MODALES DE ACCION (Pop-ups Glassmorphism)
                    # ==========================================
                    
                    # Modal: Historial
                    rx.cond(
                        State.historial_modal_abierto,
                        rx.dialog.root(
                            rx.dialog.content(
                                rx.vstack(
                                    rx.hstack(rx.icon("history", size=24, color="#3b82f6"), rx.heading("Historial de Estados", size="5"), rx.spacer(), rx.dialog.close(rx.button(rx.icon("x", size=20), on_click=State.cerrar_historial, variant="ghost", color_scheme="gray")), width="100%", align_items="center"),
                                    rx.divider(margin_y="2"),
                                    rx.cond(
                                        State.historial_estados,
                                        rx.vstack(
                                            rx.foreach(
                                                State.historial_estados,
                                                lambda evento: rx.box(
                                                    rx.hstack(
                                                        rx.box(rx.icon("git-commit-horizontal", size=20, color="#10b981"), p="2", bg="rgba(16, 185, 129, 0.1)", border_radius="full"),
                                                        rx.vstack(
                                                            rx.hstack(rx.text("Cambió a:", font_size="sm", color=subtext_color), rx.badge(evento['estado'], color_scheme="blue", radius="full"), rx.spacer(), rx.text(evento['fecha'], font_size="xs", color=subtext_color), width="100%", align_items="center"),
                                                            rx.text(rx.cond(evento['comentario'] != "", f'"{evento["comentario"]}"', "Sin comentarios."), font_size="sm", font_style="italic", color=text_color),
                                                            rx.text(f"Por: {evento['usuario']}", font_size="xs", color=subtext_color),
                                                            spacing="1", width="100%", align_items="start"
                                                        ),
                                                        spacing="4", align_items="start", width="100%"
                                                    ),
                                                    p="4", bg=rx.color_mode_cond(light="#f8fafc", dark="#1e293b"), border_radius="xl", width="100%", margin_bottom="3"
                                                )
                                            ),
                                            width="100%", max_height="400px", overflow_y="auto"
                                        ),
                                        rx.center(rx.text("Aún no hay historial de cambios para esta solicitud.", color=subtext_color), p="6")
                                    ),
                                    spacing="4", width="100%"
                                ),
                                style={"maxWidth": "600px", "borderRadius": "24px", "padding": "24px", "backgroundColor": card_bg, "backdropFilter": "blur(40px)", "border": card_border}
                            ),
                            open=True, on_open_change=State.cerrar_historial
                        )
                    ),
                    
                    # Modal: Editor de Estado
                    rx.cond(
                        State.editar_estado_id,
                        rx.box(
                            rx.vstack(
                                rx.box(
                                    # Decorative Orbs
                                    rx.box(position="absolute", top="-40px", left="-20%", width="150px", height="150px", bg="rgba(59, 130, 246, 0.6)", border_radius="full", filter="blur(40px)"),
                                    rx.box(position="absolute", bottom="-20px", right="-10%", width="120px", height="120px", bg="rgba(168, 85, 247, 0.5)", border_radius="full", filter="blur(40px)"),
                                    
                                    rx.hstack(
                                        rx.box(
                                            rx.icon("sparkles", color="white", size=28),
                                            bg="linear-gradient(135deg, #6366f1 0%, #a855f7 100%)",
                                            p="3",
                                            border_radius="2xl",
                                            box_shadow="0 10px 25px -5px rgba(168, 85, 247, 0.5)",
                                        ),
                                        rx.vstack(
                                            rx.heading("Actualización Inteligente", size="6", font_weight="900", background_image="linear-gradient(90deg, #ffffff, #e2e8f0)", background_clip="text", color="transparent"),
                                            rx.text(
                                                "Sincroniza y notifica en tiempo real.",
                                                color="rgba(255,255,255,0.8)",
                                                font_size="sm",
                                                font_weight="medium"
                                            ),
                                            spacing="1"
                                        ),
                                        spacing="4",
                                        align_items="center",
                                        position="relative",
                                        z_index="2",
                                        width="100%"
                                    ),
                                    p="8",
                                    bg="linear-gradient(135deg, #0f172a 0%, #1e293b 100%)",
                                    border_bottom="1px solid rgba(255,255,255,0.05)",
                                    border_top_left_radius="3xl",
                                    border_top_right_radius="3xl",
                                    position="relative",
                                    overflow="hidden",
                                    width="100%"
                                ),
                                rx.form(
                                    rx.vstack(
                                        rx.vstack(
                                            rx.text("Nuevo Estado", font_weight="semibold", font_size="sm", color=rx.color_mode_cond(light="#334155", dark="#cbd5e1")),
                                            rx.select(
                                                ["Radicada", "En Proceso", "Cerrada"],
                                                value=State.nuevo_estado,
                                                on_change=State.set_nuevo_estado,
                                                required=True,
                                                width="100%",
                                                size="3",
                                                radius="large",
                                            ),
                                            spacing="1",
                                            width="100%",
                                            align_items="start"
                                        ),
                                        rx.cond(
                                            State.nuevo_estado == "Cerrada",
                                            rx.vstack(
                                                rx.text("Respuesta (obligatoria para cerrar)", font_weight="semibold", font_size="sm", color=rx.color_mode_cond(light="#334155", dark="#cbd5e1")),
                                                rx.text_area(
                                                    placeholder="Escribe la respuesta o solución a la solicitud...",
                                                    value=State.respuesta_solicitud,
                                                    on_change=State.set_respuesta_solicitud,
                                                    rows="4",
                                                    required=True,
                                                    width="100%",
                                                    size="3",
                                                    radius="large",
                                                ),
                                                spacing="1",
                                                width="100%",
                                                align_items="start"
                                            )
                                        ),
                                        rx.cond(
                                            State.nuevo_estado != "Cerrada",
                                            rx.vstack(
                                                rx.text("Respuesta (opcional)", font_weight="semibold", font_size="sm", color=rx.color_mode_cond(light="#334155", dark="#cbd5e1")),
                                                rx.text_area(
                                                    placeholder="Escribe una respuesta o actualización (opcional)...",
                                                    value=State.respuesta_solicitud,
                                                    on_change=State.set_respuesta_solicitud,
                                                    rows="4",
                                                    width="100%",
                                                    size="3",
                                                    radius="large",
                                                ),
                                                spacing="1",
                                                width="100%",
                                                align_items="start"
                                            )
                                        ),
                                        rx.vstack(
                                            rx.text("Documento adjunto (opcional)", font_weight="semibold", font_size="sm", color=rx.color_mode_cond(light="#334155", dark="#cbd5e1")),
                                            rx.box(
                                                rx.vstack(
                                                    rx.upload(
                                                        rx.vstack(
                                                            rx.icon("paperclip", size=20, color=rx.color_mode_cond(light="#64748b", dark="#94a3b8")),
                                                            rx.text("Arrastra un archivo o haz clic aquí", font_size="sm", color=rx.color_mode_cond(light="#64748b", dark="#94a3b8")),
                                                            rx.text("(PDF, JPG, PNG, ZIP — máx. 10 MB)", font_size="xs", color="#94a3b8"),
                                                            spacing="2",
                                                            align_items="center",
                                                        ),
                                                        id="upload_respuesta",
                                                        multiple=False,
                                                        border="none",
                                                        width="100%",
                                                        padding="4",
                                                        on_drop=State.set_respuesta_documento,
                                                    ),
                                                    rx.cond(
                                                        State.respuesta_documento_nombre != "",
                                                        rx.box(
                                                            rx.vstack(
                                                                rx.cond(
                                                                    State.respuesta_documento_es_imagen & (State.respuesta_documento_preview_src != ""),
                                                                    rx.image(
                                                                        src=State.respuesta_documento_preview_src,
                                                                        alt="Vista previa del adjunto",
                                                                        width="100%",
                                                                        max_height="170px",
                                                                        object_fit="cover",
                                                                        border_radius="md",
                                                                    ),
                                                                    rx.hstack(
                                                                        rx.icon("file-check-2", size=17, color="#3b82f6"),
                                                                        rx.text("Archivo no previsualizable (PDF/ZIP)", font_size="xs", color=rx.color_mode_cond(light="#64748b", dark="#94a3b8")),
                                                                        spacing="2",
                                                                        align_items="center",
                                                                    ),
                                                                ),
                                                                rx.hstack(
                                                                    rx.icon("paperclip", size=15, color="#3b82f6"),
                                                                    rx.text(
                                                                        State.respuesta_documento_nombre,
                                                                        font_size="sm",
                                                                        color=rx.color_mode_cond(light="#1d4ed8", dark="#93c5fd"),
                                                                        font_weight="semibold",
                                                                    ),
                                                                    spacing="2",
                                                                    align_items="center",
                                                                ),
                                                                rx.button(
                                                                    rx.icon("x", size=14),
                                                                    "Quitar",
                                                                    type="button",
                                                                    size="1",
                                                                    variant="soft",
                                                                    color_scheme="red",
                                                                    on_click=State.quitar_respuesta_documento,
                                                                ),
                                                                rx.button(
                                                                    rx.icon("trash-2", size=14),
                                                                    "Quitar todo",
                                                                    type="button",
                                                                    size="1",
                                                                    variant="soft",
                                                                    color_scheme="red",
                                                                    on_click=State.quitar_respuesta_documento,
                                                                ),
                                                                spacing="2",
                                                                align_items="start",
                                                            ),
                                                            width="100%",
                                                            p="3",
                                                            border=rx.color_mode_cond(light="1px solid #bfdbfe", dark="1px solid rgba(96, 165, 250, 0.35)"),
                                                            border_radius="lg",
                                                            bg=rx.color_mode_cond(light="rgba(239, 246, 255, 0.7)", dark="rgba(30, 58, 138, 0.2)"),
                                                        ),
                                                    ),
                                                    spacing="2",
                                                    width="100%",
                                                ),
                                                padding="4",
                                                border=rx.color_mode_cond(light="2px dashed #cbd5e1", dark="2px dashed #475569"),
                                                border_radius="xl",
                                                bg=rx.color_mode_cond(light="rgba(248, 250, 252, 0.5)", dark="rgba(30, 41, 59, 0.5)"),
                                                width="100%",
                                                _hover={"border_color": rx.color_mode_cond(light="#3b82f6", dark="#60a5fa"), "bg": rx.color_mode_cond(light="rgba(239, 246, 255, 0.8)", dark="rgba(23, 37, 84, 0.8)")},
                                                transition="all 0.2s",
                                            ),
                                            spacing="1",
                                            width="100%",
                                            align_items="start",
                                        ),
                                        rx.cond(
                                            State.mensaje_actualizar_estado,
                                            rx.box(
                                                rx.text(
                                                    State.mensaje_actualizar_estado,
                                                    color=rx.cond(
                                                        State.mensaje_actualizar_estado.contains("correctamente"),
                                                        "green.700",
                                                        "red.700"
                                                    ),
                                                    font_weight="medium",
                                                    font_size="sm"
                                                ),
                                                bg=rx.cond(
                                                    State.mensaje_actualizar_estado.contains("correctamente"),
                                                    rx.color_mode_cond(light="#d1fae5", dark="#064e3b"),
                                                    rx.color_mode_cond(light="#fee2e2", dark="#7f1d1d")
                                                ),
                                                border_radius="xl",
                                                p="3",
                                                width="100%",
                                                animation="flashMessage 5s ease forwards",
                                                style={
                                                    "@keyframes flashMessage": {
                                                        "0%": {"opacity": "0", "transform": "translateY(-4px)"},
                                                        "10%": {"opacity": "1", "transform": "translateY(0px)"},
                                                        "80%": {"opacity": "1", "transform": "translateY(0px)"},
                                                        "100%": {"opacity": "0", "transform": "translateY(-4px)"},
                                                    }
                                                },
                                            )
                                        ),
                                        spacing="4",
                                        align_items="stretch",
                                        p="6"
                                    ),
                                    on_submit=State.actualizar_estado_solicitud(
                                        rx.upload_files(upload_id="upload_respuesta"),
                                    ),
                                ),
                                rx.box(
                                    rx.hstack(
                                        rx.button(
                                            "Cancelar",
                                            on_click=State.cerrar_editor_estado,
                                            variant="ghost",
                                            color_scheme="gray",
                                            size="3",
                                            flex="1",
                                            _hover={"bg": rx.color_mode_cond(light="#f1f5f9", dark="#1e293b")}
                                        ),
                                        rx.button(
                                            "Actualizar Estado",
                                            on_click=State.actualizar_estado_solicitud(
                                                rx.upload_files(upload_id="upload_respuesta"),
                                            ),
                                            bg="linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%)",
                                            color="white",
                                            size="3",
                                            flex="2",
                                            box_shadow="0 4px 14px 0 rgba(59,130,246,0.39)",
                                            _hover={"transform": "translateY(-2px)", "box_shadow": "0 6px 20px rgba(59,130,246,0.5)"},
                                            transition="all 0.2s"
                                        ),
                                        spacing="4",
                                        width="100%"
                                    ),
                                    p="5",
                                    border_top=rx.color_mode_cond(light="1px solid rgba(0,0,0,0.05)", dark="1px solid rgba(255,255,255,0.05)"),
                                    bg=rx.color_mode_cond(light="rgba(248, 250, 252, 0.4)", dark="rgba(11, 17, 32, 0.4)"),
                                    border_bottom_left_radius="3xl",
                                    border_bottom_right_radius="3xl",
                                    width="100%"
                                ),
                                spacing="0",
                            ),
                            p="0",
                            border=rx.color_mode_cond(light="1px solid rgba(255,255,255,0.6)", dark="1px solid rgba(255,255,255,0.08)"),
                            border_radius="3xl",
                            bg=rx.color_mode_cond(light="rgba(255, 255, 255, 0.9)", dark="rgba(15, 23, 42, 0.8)"),
                            backdrop_filter="blur(20px)",
                            width="100%",
                            max_width="550px",
                            position="fixed",
                            top="50%",
                            left="50%",
                            transform="translate(-50%, -50%)",
                            z_index="1000",
                            box_shadow=rx.color_mode_cond(light="0 25px 50px -12px rgba(0, 0, 0, 0.25), 0 0 0 1px rgba(0,0,0,0.05)", dark="0 25px 50px -12px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(255,255,255,0.1)")
                        )
                    ),
                    
                    # Modal: Asignar Área
                    rx.cond(
                        State.asignar_area_id,
                        rx.box(
                            rx.vstack(
                                rx.box(
                                    # Decorative Orbs
                                    rx.box(position="absolute", top="-40px", left="-20%", width="150px", height="150px", bg="rgba(16, 185, 129, 0.6)", border_radius="full", filter="blur(40px)"),
                                    rx.box(position="absolute", bottom="-20px", right="-10%", width="120px", height="120px", bg="rgba(5, 150, 105, 0.5)", border_radius="full", filter="blur(40px)"),
                                    
                                    rx.hstack(
                                        rx.box(
                                            rx.icon("network", color="white", size=28),
                                            bg="linear-gradient(135deg, #34d399 0%, #059669 100%)",
                                            p="3",
                                            border_radius="2xl",
                                            box_shadow="0 10px 25px -5px rgba(5, 150, 105, 0.5)",
                                        ),
                                        rx.vstack(
                                            rx.heading("Derivación de Área", size="6", font_weight="900", background_image="linear-gradient(90deg, #ffffff, #e2e8f0)", background_clip="text", color="transparent"),
                                            rx.text(
                                                "Asigna tareas con precisión láser.",
                                                color="rgba(255,255,255,0.8)",
                                                font_size="sm",
                                                font_weight="medium"
                                            ),
                                            spacing="1"
                                        ),
                                        spacing="4",
                                        align_items="center",
                                        position="relative",
                                        z_index="2",
                                        width="100%"
                                    ),
                                    p="8",
                                    bg="linear-gradient(135deg, #022c22 0%, #064e3b 100%)",
                                    border_bottom="1px solid rgba(255,255,255,0.05)",
                                    border_top_left_radius="3xl",
                                    border_top_right_radius="3xl",
                                    position="relative",
                                    overflow="hidden",
                                    width="100%"
                                ),
                                rx.form(
                                    rx.vstack(
                                        rx.vstack(
                                            rx.text("Área responsable", font_weight="semibold", font_size="sm", color=rx.color_mode_cond(light="#334155", dark="#cbd5e1")),
                                            rx.select(
                                                ["Secretaría", "Contabilidad", "Bienestar", "Tesorería", "Atención al Ciudadano", "Otros"],
                                                placeholder="Selecciona el área...",
                                                value=State.asignar_area_seleccionada,
                                                on_change=State.set_asignar_area_seleccionada,
                                                width="100%",
                                                size="3",
                                                radius="large",
                                            ),
                                            spacing="1",
                                            width="100%",
                                            align_items="start"
                                        ),
                                        rx.cond(
                                            State.asignar_area_seleccionada == "Otros",
                                            rx.vstack(
                                                rx.text("Otra área", font_weight="semibold", font_size="sm", color=rx.color_mode_cond(light="#334155", dark="#cbd5e1")),
                                                rx.input(
                                                    placeholder="Especifique el área...",
                                                    value=State.asignar_area_nombre,
                                                    on_change=State.set_asignar_area_nombre,
                                                    width="100%",
                                                    size="3",
                                                    radius="large",
                                                ),
                                                spacing="1",
                                                width="100%",
                                                align_items="start"
                                            ),
                                            rx.box()
                                        ),
                                        rx.vstack(
                                            rx.text("Mensaje para el ciudadano", font_weight="semibold", font_size="sm", color=rx.color_mode_cond(light="#334155", dark="#cbd5e1")),
                                            rx.text_area(
                                                placeholder="Escribe el mensaje que llegará al correo del ciudadano...",
                                                value=State.asignar_area_mensaje,
                                                on_change=State.set_asignar_area_mensaje,
                                                rows="4",
                                                width="100%",
                                                size="3",
                                                radius="large",
                                            ),
                                            spacing="1",
                                            width="100%",
                                            align_items="start"
                                        ),
                                        rx.cond(
                                            State.mensaje_asignacion,
                                            rx.box(
                                                rx.text(
                                                    State.mensaje_asignacion,
                                                    color=rx.cond(
                                                        State.mensaje_asignacion.contains("correctamente"),
                                                        "green.600",
                                                        "red.600"
                                                    ),
                                                    font_weight="medium",
                                                    font_size="sm"
                                                ),
                                                bg=rx.color_mode_cond(light="#ecfdf5", dark="#052e16"),
                                                border_radius="xl",
                                                p="3",
                                                width="100%",
                                                animation="flashMessage 5s ease forwards",
                                                style={
                                                    "@keyframes flashMessage": {
                                                        "0%": {"opacity": "0", "transform": "translateY(-4px)"},
                                                        "10%": {"opacity": "1", "transform": "translateY(0px)"},
                                                        "80%": {"opacity": "1", "transform": "translateY(0px)"},
                                                        "100%": {"opacity": "0", "transform": "translateY(-4px)"},
                                                    }
                                                },
                                            )
                                        ),
                                        spacing="4",
                                        align_items="stretch",
                                        p="5"
                                    ),
                                    on_submit=State.asignar_area_con_mensaje
                                ),
                                rx.box(
                                    rx.hstack(
                                        rx.button(
                                            "Cancelar",
                                            on_click=State.cerrar_asignar_area,
                                            variant="ghost",
                                            color_scheme="gray",
                                            size="3",
                                            flex="1",
                                            _hover={"bg": rx.color_mode_cond(light="#f1f5f9", dark="#1e293b")}
                                        ),
                                        rx.button(
                                            "Asignar y Enviar",
                                            on_click=State.asignar_area_con_mensaje,
                                            bg="linear-gradient(135deg, #10b981 0%, #059669 100%)",
                                            color="white",
                                            size="3",
                                            flex="2",
                                            box_shadow="0 4px 14px 0 rgba(16,185,129,0.39)",
                                            _hover={"transform": "translateY(-2px)", "box_shadow": "0 6px 20px rgba(16,185,129,0.5)"},
                                            transition="all 0.2s"
                                        ),
                                        spacing="4",
                                        width="100%"
                                    ),
                                    p="5",
                                    border_top=rx.color_mode_cond(light="1px solid rgba(0,0,0,0.05)", dark="1px solid rgba(255,255,255,0.05)"),
                                    bg=rx.color_mode_cond(light="rgba(248, 250, 252, 0.4)", dark="rgba(11, 17, 32, 0.4)"),
                                    border_bottom_left_radius="3xl",
                                    border_bottom_right_radius="3xl",
                                    width="100%"
                                ),
                                spacing="0",
                            ),
                            # Close button in corner
                            rx.button(
                                rx.icon("x", size=20, color="white"),
                                on_click=State.cerrar_asignar_area,
                                variant="ghost",
                                position="absolute",
                                top="16px",
                                right="16px",
                                padding="2",
                                border_radius="full",
                                _hover={"bg": "rgba(255,255,255,0.2)"},
                            ),
                            p="0",
                            border=rx.color_mode_cond(light="1px solid rgba(255,255,255,0.6)", dark="1px solid rgba(255,255,255,0.08)"),
                            border_radius="3xl",
                            bg=rx.color_mode_cond(light="rgba(255, 255, 255, 0.9)", dark="rgba(15, 23, 42, 0.8)"),
                            backdrop_filter="blur(20px)",
                            width="100%",
                            max_width="550px",
                            position="fixed",
                            top="50%",
                            left="50%",
                            transform="translate(-50%, -50%)",
                            z_index="1000",
                            box_shadow=rx.color_mode_cond(light="0 25px 50px -12px rgba(0, 0, 0, 0.25), 0 0 0 1px rgba(0,0,0,0.05)", dark="0 25px 50px -12px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(255,255,255,0.1)")
                        )
                    ),
                    
                    padding_x={"base": "4", "md": "8"}, width="100%", position="relative", min_height="90vh", align_items="start"
                ),
                bg=rx.color_mode_cond(light="#f1f5f9", dark="#020617"), width="100%", min_height="100vh", style={"margin": "0"}
            ),
            access_denied_widget("Esta página es solo para funcionarios autorizados.")
        ),
        rx.center(rx.spinner(size="3", color="#3b82f6"), height="100vh", bg=rx.color_mode_cond(light="#f1f5f9", dark="#0f172a"))
    )


def funcionario_cerradas_dashboard() -> rx.Component:
    text_color = rx.color_mode_cond(light="#0f172a", dark="#f8fafc")
    subtext_color = rx.color_mode_cond(light="#64748b", dark="#94a3b8")
    card_bg = rx.color_mode_cond(light="rgba(255, 255, 255, 0.85)", dark="rgba(15, 23, 42, 0.7)")
    card_border = rx.color_mode_cond(light="1px solid rgba(255, 255, 255, 0.5)", dark="1px solid rgba(51, 65, 85, 0.5)")

    return rx.cond(
        rx.State.is_hydrated,
        rx.cond(
            State.es_autenticada & (State.rol_usuario == "funcionario"),
            rx.box(
                navbar(),
                rx.box(
                    rx.vstack(
                        rx.hstack(
                            rx.vstack(
                                rx.heading("Solicitudes cerradas", size="7", color=text_color, font_weight="bold"),
                                rx.text("Histórico de radicados finalizados.", color=subtext_color),
                                align_items="start",
                                spacing="1",
                            ),
                            rx.spacer(),
                            rx.link(
                                rx.button("Volver a activas", variant="soft", color_scheme="blue", radius="full"),
                                href="/dashboard-funcionario",
                            ),
                            width="100%",
                            align_items="center",
                        ),
                        rx.divider(margin_y="4", opacity="0.3"),
                        rx.cond(
                            State.solicitudes_cerradas_lista,
                            rx.grid(
                                rx.foreach(
                                    State.solicitudes_cerradas_lista,
                                    lambda solicitud: rx.box(
                                        rx.vstack(
                                                    rx.box(
                                                        rx.hstack(
                                                            rx.badge(solicitud["radicado"], color_scheme="gray", variant="solid", radius="large"),
                                                            rx.spacer(),
                                                            rx.badge("Cerrada", color_scheme="green", variant="soft", size="2", radius="full"),
                                                            width="100%",
                                                            align_items="center",
                                                        ),
                                                        p="4",
                                                        width="100%",
                                                        bg=rx.color_mode_cond(
                                                            light="linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%)",
                                                            dark="linear-gradient(135deg, rgba(16,185,129,0.20) 0%, rgba(16,185,129,0.08) 100%)",
                                                        ),
                                                        border_bottom=rx.color_mode_cond(light="1px solid #a7f3d0", dark="1px solid #334155"),
                                                        border_top_left_radius="2xl",
                                                        border_top_right_radius="2xl",
                                            ),
                                                    rx.vstack(
                                                        rx.heading(solicitud["asunto"], size="5", color=text_color, font_weight="bold", line_height="1.25", style={"display": "-webkit-box", "WebkitLineClamp": "2", "WebkitBoxOrient": "vertical", "overflow": "hidden"}),
                                                        rx.text(solicitud["descripcion"], font_size="sm", color=subtext_color, style={"display": "-webkit-box", "WebkitLineClamp": "3", "WebkitBoxOrient": "vertical", "overflow": "hidden"}, min_height="62px"),
                                                        rx.hstack(
                                                            rx.badge(solicitud["tipo_solicitud"], variant="soft", color_scheme="purple", radius="full"),
                                                            rx.badge(solicitud.get("area_responsable", "No asignada"), variant="soft", color_scheme="cyan", radius="full"),
                                                            spacing="2",
                                                            width="100%",
                                                            flex_wrap="wrap",
                                                        ),
                                                        rx.spacer(),
                                                        rx.hstack(
                                                            rx.button(rx.icon("history", size=16), "Historial", on_click=lambda _event, id=solicitud["id"]: State.abrir_historial(id), size="2", variant="soft", color_scheme="gray", radius="full", _hover={"transform": "translateY(-1px)"}, transition="all 0.2s ease"),
                                                            rx.spacer(),
                                                            rx.button("Reabrir / Estado", on_click=lambda _event, id=solicitud["id"], estado=solicitud["estado"]: State.abrir_editor_estado(id, estado), size="2", color_scheme="blue", variant="solid", radius="full", _hover={"transform": "translateY(-1px)", "box_shadow": "0 10px 20px -14px rgba(59,130,246,0.6)"}, transition="all 0.2s ease"),
                                                            width="100%",
                                                            align_items="center",
                                                        ),
                                                        spacing="3",
                                                        align_items="start",
                                                width="100%",
                                                        height="100%",
                                                        p="4",
                                            ),
                                                    spacing="0",
                                            align_items="start",
                                            width="100%",
                                                    height="100%",
                                        ),
                                        bg=rx.color_mode_cond(light="rgba(250,255,251,0.96)", dark="rgba(15,23,42,0.9)"),
                                        border=card_border,
                                                border_radius="2xl",
                                                width="100%",
                                                min_height="340px",
                                                position="relative",
                                                overflow="hidden",
                                                box_shadow="0 16px 28px -14px rgba(0,0,0,0.16)",
                                                _hover={"transform": "translateY(-6px)", "box_shadow": "0 24px 38px -18px rgba(16, 185, 129, 0.28)"},
                                                transition="all 0.25s ease",
                                    ),
                                ),
                                        display="grid",
                                        grid_template_columns=rx.breakpoints(initial="repeat(1, minmax(0, 1fr))", md="repeat(2, minmax(0, 1fr))", xl="repeat(3, minmax(0, 1fr))"),
                                        grid_auto_rows="1fr",
                                gap="5",
                                width="100%",
                            ),
                            rx.center(
                                rx.vstack(
                                    rx.icon("inbox", size=64, color=subtext_color, opacity="0.3"),
                                    rx.heading("Sin solicitudes cerradas", size="5", color=text_color),
                                    rx.text("No hay cerradas para el filtro actual.", color=subtext_color),
                                    align_items="center",
                                    spacing="4",
                                ),
                                min_height="260px",
                                width="100%",
                            ),
                        ),
                        spacing="4",
                        width="100%",
                        max_width="100%",
                        p={"base": "3", "md": "5"},
                    ),
                    width="100%",
                    bg=rx.color_mode_cond(light="#f8fafc", dark="#0f172a"),
                    min_height="100vh",
                ),
            ),
            rx.box(
                navbar(),
                rx.center(access_denied_widget("Solo funcionarios autenticados pueden acceder a esta función."), size="3"),
                bg=rx.color_mode_cond(light="#f8fafc", dark="#0f172a"),
                min_height="100vh",
            ),
        ),
        rx.center(rx.spinner(size="3", color="#3b82f6"), height="50vh"),
    )


def solicitudes_page() -> rx.Component:
    text_color = rx.color_mode_cond(light="#0f172a", dark="#f8fafc")
    subtext_color = rx.color_mode_cond(light="#64748b", dark="#94a3b8")
    card_bg = rx.color_mode_cond(light="rgba(255, 255, 255, 0.75)", dark="rgba(30, 41, 59, 0.6)")
    card_border = rx.color_mode_cond(light="1px solid rgba(255, 255, 255, 0.9)", dark="1px solid rgba(51, 65, 85, 0.5)")
    input_bg = rx.color_mode_cond(light="rgba(255, 255, 255, 0.9)", dark="rgba(15, 23, 42, 0.6)")
    input_border = rx.color_mode_cond(light="1px solid #e2e8f0", dark="1px solid #334155")

    return rx.cond(
        rx.State.is_hydrated,
        rx.cond(
            State.es_autenticada,
            rx.box(
                navbar(),
                rx.center(
                    # Efectos holográficos de fondo
                    rx.box(position="absolute", top="0%", left="0%", width="500px", height="500px", bg="rgba(59, 130, 246, 0.15)", border_radius="full", filter="blur(100px)", z_index="0"),
                    rx.box(position="absolute", bottom="-10%", right="0%", width="600px", height="600px", bg="rgba(16, 185, 129, 0.1)", border_radius="full", filter="blur(150px)", z_index="0"),
                    
                    rx.vstack(
                        # Cabecera de la Consola
                        rx.box(
                            rx.hstack(
                                rx.box(
                                    rx.icon("send", size=40, color="#3b82f6"),
                                    p="4", bg=rx.color_mode_cond(light="#eff6ff", dark="rgba(59, 130, 246, 0.1)"), border_radius="2xl"
                                ),
                                rx.vstack(
                                    rx.heading("Radicación Oficial PQRS", size="8", color=text_color, font_weight="bold"),
                                    rx.text("Completa el siguiente formulario inmersivo para enviar tu caso a las autoridades competentes.", color=subtext_color, font_size="lg"),
                                    spacing="1", align_items="start"
                                ),
                                spacing="4", align_items="center", margin_bottom="6"
                            ),
                            width="100%", z_index="1"
                        ),

                        # Contenedor Principal Glassmorphism
                        rx.box(
                            rx.form(
                                rx.vstack(
                                    # Mensaje de Sistema
                                    rx.cond(
                                        State.solicitud_mensaje,
                                        rx.box(
                                            rx.hstack(
                                                rx.icon(rx.cond(State.solicitud_mensaje.contains("éxito"), "circle-check", "circle-alert"), color="white"),
                                                rx.text(State.solicitud_mensaje, color="white", font_weight="semibold"),
                                                spacing="2", align_items="center"
                                            ),
                                            p="4", border_radius="xl", width="100%", margin_bottom="6",
                                            bg=rx.cond(State.solicitud_mensaje.contains("éxito"), "linear-gradient(135deg, #10b981 0%, #059669 100%)", "linear-gradient(135deg, #ef4444 0%, #dc2626 100%)"),
                                            box_shadow="0 10px 15px -3px rgba(0, 0, 0, 0.1)",
                                            animation="flashMessage 5s ease forwards",
                                            style={
                                                "@keyframes flashMessage": {
                                                    "0%": {"opacity": "0", "transform": "translateY(-4px)"},
                                                    "10%": {"opacity": "1", "transform": "translateY(0px)"},
                                                    "80%": {"opacity": "1", "transform": "translateY(0px)"},
                                                    "100%": {"opacity": "0", "transform": "translateY(-4px)"},
                                                }
                                            },
                                        )
                                    ),
                                    
                                    # GRID DE 2 COLUMNAS
                                    rx.grid(
                                        # COLUMNA IZQUIERDA: Clasificación
                                        rx.vstack(
                                            rx.heading("Clasificación del Caso", size="5", color=text_color, margin_bottom="4"),
                                            
                                            rx.vstack(
                                                label_requerido("Tipo de Solicitud"),
                                                rx.select(["Petición", "Queja", "Reclamo", "Sugerencia"], placeholder="¿Qué tipo de trámite es?", value=State.tipo_solicitud, on_change=State.set_tipo_solicitud, required=True, bg=input_bg, border=input_border, border_radius="md", size="3"),
                                                width="100%"
                                            ),
                                            
                                            rx.vstack(
                                                label_requerido("Área Responsable"),
                                                rx.select(["Secretaría", "Contabilidad", "Bienestar", "Tesorería", "Atención al Ciudadano", "Otros"], placeholder="¿Hacia dónde va dirigido?", value=State.area_responsable, on_change=State.set_area_responsable, required=True, bg=input_bg, border=input_border, border_radius="md", size="3"),
                                                width="100%"
                                            ),
                                            
                                            rx.cond(
                                                State.area_responsable == "Otros",
                                                rx.vstack(
                                                    label_requerido("Especifica el Área"),
                                                    rx.input(placeholder="Escribe el área específica...", value=State.area_otro, on_change=State.set_area_otro, required=True, bg=input_bg, border=input_border, border_radius="md", size="3", width="100%"),
                                                    width="100%"
                                                )
                                            ),
                                            
                                            rx.vstack(
                                                label_requerido("Asunto"),
                                                rx.input(placeholder="Resumen corto de tu caso...", value=State.asunto, on_change=State.set_asunto, required=True, bg=input_bg, border=input_border, border_radius="md", size="3", width="100%"),
                                                width="100%"
                                            ),
                                            
                                            spacing="5", width="100%", align_items="start", p="6", bg=rx.color_mode_cond(light="rgba(255,255,255,0.4)", dark="rgba(15,23,42,0.3)"), border_radius="2xl"
                                        ),
                                        
                                        # COLUMNA DERECHA: Detalles
                                        rx.vstack(
                                            rx.heading("Detalles e Información Adicional", size="5", color=text_color, margin_bottom="4"),
                                            
                                            rx.vstack(
                                                label_requerido("Descripción completa"),
                                                rx.text_area(placeholder="Escribe todo el detalle que consideres necesario para que las autoridades puedan darte una respuesta certera...", value=State.descripcion, on_change=State.set_descripcion, required=True, max_length=1000, bg=input_bg, border=input_border, border_radius="md", size="3", min_height="200px", width="100%"),
                                                rx.hstack(rx.spacer(), rx.text(State.descripcion_len, font_size="xs", color=subtext_color), rx.text("/ 1000", font_size="xs", color=subtext_color)),
                                                width="100%"
                                            ),
                                            
                                            # Zona de Adjuntos Moderna
                                            rx.vstack(
                                                rx.text("Documentos de respaldo (Opcional)", font_weight="semibold", font_size="sm"),
                                                rx.box(
                                                    rx.vstack(
                                                        rx.icon("cloud-upload", size=32, color="#3b82f6", margin_bottom="2"),
                                                        rx.upload(
                                                            rx.text("Arrastra un archivo aquí o haz clic para subir", font_size="sm", color=subtext_color),
                                                            rx.text("(Formatos: PDF, JPG, PNG, ZIP. Máx 5MB)", font_size="xs", color="#94a3b8"),
                                                            id="upload_documento",
                                                            multiple=False,
                                                            border="none", width="100%", bg="transparent",
                                                            on_drop=State.set_documento,
                                                        ),
                                                        align_items="center", width="100%"
                                                    ),
                                                    p="6", width="100%", border="2px dashed rgba(59, 130, 246, 0.4)", border_radius="xl",
                                                    bg=rx.color_mode_cond(light="rgba(239, 246, 255, 0.5)", dark="rgba(30, 58, 138, 0.2)"),
                                                    _hover={"bg": rx.color_mode_cond(light="#eff6ff", dark="rgba(30, 58, 138, 0.4)"), "border_color": "#3b82f6"}, transition="all 0.2s"
                                                ),
                                                # Preview del archivo
                                                rx.cond(
                                                    State.documento_nombres,
                                                    rx.vstack(
                                                        rx.hstack(
                                                            rx.text("Vista previa de adjuntos", font_size="xs", color=subtext_color, font_weight="medium"),
                                                            rx.spacer(),
                                                            rx.button(
                                                                rx.icon("trash-2", size=14),
                                                                "Quitar todo",
                                                                type="button",
                                                                size="1",
                                                                variant="soft",
                                                                color_scheme="red",
                                                                on_click=State.quitar_todos_documentos,
                                                            ),
                                                            width="100%",
                                                            align_items="center",
                                                        ),
                                                        rx.foreach(
                                                            State.documento_previews,
                                                            lambda archivo: rx.box(
                                                                rx.vstack(
                                                                    rx.cond(
                                                                        archivo["src"] != "",
                                                                        rx.image(
                                                                            src=archivo["src"],
                                                                            alt=archivo["name"],
                                                                            width="100%",
                                                                            max_height="150px",
                                                                            object_fit="cover",
                                                                            border_radius="md",
                                                                        ),
                                                                        rx.hstack(
                                                                            rx.icon("file", size=16, color="#10b981"),
                                                                            rx.text("Archivo no previsualizable (PDF/ZIP)", font_size="xs", color=subtext_color),
                                                                            spacing="2",
                                                                            align_items="center",
                                                                        ),
                                                                    ),
                                                                    rx.hstack(
                                                                        rx.icon("paperclip", size=16, color="#10b981"),
                                                                        rx.text(archivo["name"], font_size="sm", font_weight="semibold", color=rx.color_mode_cond(light="#065f46", dark="#6ee7b7")),
                                                                        rx.spacer(),
                                                                        rx.button(
                                                                            rx.icon("x", size=14),
                                                                            "Quitar",
                                                                            type="button",
                                                                            size="1",
                                                                            variant="soft",
                                                                            color_scheme="red",
                                                                            on_click=State.eliminar_documento_por_nombre(archivo["name"]),
                                                                        ),
                                                                        spacing="2",
                                                                        align_items="center",
                                                                        width="100%",
                                                                    ),
                                                                    spacing="2",
                                                                    align_items="start",
                                                                ),
                                                                width="100%",
                                                                p="2.5",
                                                                border_radius="lg",
                                                                bg=rx.color_mode_cond(light="rgba(236, 253, 245, 0.8)", dark="rgba(6, 78, 59, 0.25)"),
                                                                border=rx.color_mode_cond(light="1px solid #a7f3d0", dark="1px solid rgba(16, 185, 129, 0.4)"),
                                                            ),
                                                        ),
                                                        spacing="2",
                                                        width="100%",
                                                        mt="2",
                                                        align_items="stretch",
                                                    ),
                                                ),
                                                width="100%"
                                            ),
                                            
                                            rx.box(
                                                rx.checkbox(
                                                    "Acepto el tratamiento de mis datos personales para la gestión de esta solicitud conforme a la Ley 1581.",
                                                    checked=State.acepta_politica_solicitud, on_change=State.set_acepta_politica_solicitud, required=True, size="2", color_scheme="blue"
                                                ),
                                                mt="4", p="4", bg=rx.color_mode_cond(light="#f8fafc", dark="#1e293b"), border_radius="lg", width="100%"
                                            ),
                                            
                                            spacing="4", width="100%", align_items="start", p="6", bg=rx.color_mode_cond(light="rgba(255,255,255,0.4)", dark="rgba(15,23,42,0.3)"), border_radius="2xl"
                                        ),
                                        
                                        template_columns={"base": "1fr", "lg": "1fr 1fr"},
                                        gap="6", width="100%"
                                    ),
                                    
                                    rx.divider(margin_y="8", opacity="0.5"),
                                    
                                    # Botón de Radicación
                                    rx.center(
                                        rx.button(
                                            rx.icon("zap", size=20),
                                            "Radicar Solicitud Oficial",
                                            type="submit", color_scheme="blue", size="4", radius="full", padding_x="8",
                                            box_shadow="0 10px 15px -3px rgba(59, 130, 246, 0.4)",
                                            _hover={"transform": "scale(1.02)", "box_shadow": "0 20px 25px -5px rgba(59, 130, 246, 0.5)"}, transition="all 0.3s"
                                        ),
                                        width="100%"
                                    ),
                                    
                                    width="100%"
                                ),
                                on_submit=State.crear_solicitud, width="100%"
                            ),
                            p={"base": "6", "md": "10"}, bg=card_bg, backdrop_filter="blur(24px)", border=card_border, border_radius="3xl", box_shadow="0 25px 50px -12px rgba(0, 0, 0, 0.15)", width="100%", z_index="1"
                        ),
                        spacing="6", align_items="center", width="100%", max_width="1200px", padding_x={"base": "4", "md": "8"}, padding_y="12", margin_bottom="12"
                    ),
                    width="100%", min_height="90vh", position="relative", overflow="hidden", align_items="start"
                ),
                bg=rx.color_mode_cond(light="#f1f5f9", dark="#0f172a"), width="100%", min_height="100vh", style={"margin": "0"}
            ),
            access_denied_widget("Debe iniciar sesión para registrar una solicitud.")
        ),
        rx.center(rx.spinner(size="3", color="#3b82f6"), height="100vh", bg=rx.color_mode_cond(light="#f1f5f9", dark="#0f172a"))
    )


def consultar_estado_page() -> rx.Component:
    return rx.box(
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
                        rx.box(
                            rx.text(
                                State.consulta_mensaje,
                                color=rx.cond(
                                    State.consulta_mensaje.contains("encontrada") & ~State.consulta_mensaje.contains("No se encontró"),
                                    "green.500",
                                    "red.500"
                                ),
                                font_weight="semibold"
                            ),
                            p="3",
                            border_radius="lg",
                            bg=rx.color_mode_cond(light="#f8fafc", dark="rgba(30,41,59,0.45)"),
                            animation="flashMessage 5s ease forwards",
                            style={
                                "@keyframes flashMessage": {
                                    "0%": {"opacity": "0", "transform": "translateY(-4px)"},
                                    "10%": {"opacity": "1", "transform": "translateY(0px)"},
                                    "80%": {"opacity": "1", "transform": "translateY(0px)"},
                                    "100%": {"opacity": "0", "transform": "translateY(-4px)"},
                                }
                            },
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
    # Componentes de UI reusables
    def kpi_card(title: str, value: str, icon_name: str, color: str, bg_color: str):
        return rx.card(
            rx.hstack(
                rx.vstack(
                    rx.text(title, font_weight="medium", color=rx.color_mode_cond(light="gray.600", dark="gray.400"), font_size="sm", letter_spacing="0.02em"),
                    rx.heading(value, size="7", color=rx.color_mode_cond(light="black", dark="white"), font_weight="bold"),
                    align_items="start",
                    spacing="1"
                ),
                rx.spacer(),
                rx.box(
                    rx.icon(icon_name, size=24, color=color),
                    p="3",
                    bg=bg_color,
                    border_radius="xl"
                ),
                width="100%",
                align_items="center"
            ),
            p="5",
            bg=rx.color_mode_cond(light="#ffffff", dark="#1e293b"),
            box_shadow=rx.color_mode_cond(light="0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03)", dark="none"),
            border=rx.color_mode_cond(light="1px solid #f1f5f9", dark="1px solid #334155"),
            border_radius="2xl",
            width="100%"
        )

    def chart_card(title: str, chart_component, width="100%", extra_content=None):
        return rx.box(
            rx.vstack(
                rx.heading(title, size="5", color=rx.color_mode_cond(light="#1e293b", dark="#f8fafc"), font_weight="bold"),
                chart_component,
                extra_content if extra_content else rx.box(),
                spacing="4",
                align_items="center",
                width="100%"
            ),
            p="6",
            bg=rx.color_mode_cond(light="#ffffff", dark="#1e293b"),
            border=rx.color_mode_cond(light="1px solid #e2e8f0", dark="1px solid #334155"),
            border_radius="3xl",
            box_shadow=rx.color_mode_cond(light="0 4px 6px -1px rgba(0, 0, 0, 0.05)", dark="none"),
            width=width,
            _hover={"box_shadow": rx.color_mode_cond(light="0 10px 15px -3px rgba(0, 0, 0, 0.1)", dark="0 10px 15px -3px rgba(0, 0, 0, 0.5)"), "transform": "translateY(-2px)", "border_color": rx.color_mode_cond(light="#93c5fd", dark="#3b82f6")},
            transition="all 0.3s ease"
        )

    content = rx.box(
        navbar(),
        rx.center(
            rx.vstack(
                # Encabezado y Command Center
                rx.hstack(
                    rx.vstack(
                        rx.heading("Centro de Reportes", size="8", color=rx.color_mode_cond(light="#0f172a", dark="#f8fafc"), font_weight="bold", letter_spacing="-0.02em"),
                        rx.text("Análisis avanzado y métricas de solicitudes", color=rx.color_mode_cond(light="#64748b", dark="#94a3b8"), font_size="lg"),
                        align_items="start",
                        spacing="1"
                    ),
                    rx.spacer(),
                    # Barra de Filtros y Descarga
                    rx.box(
                        rx.hstack(
                            rx.hstack(
                                rx.icon("calendar", size=16, color=rx.color_mode_cond(light="#64748b", dark="#94a3b8")),
                                rx.select(
                                    ["Últimos 12 meses", "Últimos 6 meses", "Este año"],
                                    placeholder="Rango",
                                    variant="soft", radius="full", size="2"
                                ),
                                spacing="2", align_items="center"
                            ),
                            rx.divider(orientation="vertical", height="20px", border_color=rx.color_mode_cond(light="#e2e8f0", dark="#334155")),
                            rx.hstack(
                                rx.icon("filter", size=16, color=rx.color_mode_cond(light="#64748b", dark="#94a3b8")),
                                rx.select(
                                    ["Todos", "Petición", "Queja", "Reclamo", "Sugerencia"],
                                    placeholder="Tipo",
                                    value=State.filter_tipo_solicitud,
                                    on_change=State.set_filter_tipo_solicitud,
                                    variant="soft", radius="full", size="2"
                                ),
                                spacing="2", align_items="center"
                            ),
                            rx.divider(orientation="vertical", height="20px", border_color=rx.color_mode_cond(light="#e2e8f0", dark="#334155")),
                            rx.box(
                                rx.button(
                                    rx.icon("download", size=16),
                                    "Exportar",
                                    on_click=State.toggle_menu_descarga,
                                    color_scheme="blue",
                                    variant="solid",
                                    radius="full",
                                    box_shadow="0 4px 6px -1px rgba(59, 130, 246, 0.3)",
                                ),
                                rx.cond(
                                    State.mostrar_menu_descarga,
                                    rx.vstack(
                                        rx.button(rx.icon("file-spreadsheet", size=16), "Excel", on_click=State.descargar_excel_y_abrir, color_scheme="green", width="100%", size="2", variant="soft", justify="start"),
                                        rx.button(rx.icon("file-text", size=16), "CSV", on_click=State.descargar_csv_y_abrir, color_scheme="cyan", width="100%", size="2", variant="soft", justify="start"),
                                        spacing="2",
                                        position="absolute",
                                        top="120%",
                                        right="0",
                                        bg=rx.color_mode_cond(light="rgba(255, 255, 255, 0.9)", dark="rgba(30, 41, 59, 0.9)"),
                                        backdrop_filter="blur(12px)",
                                        border=rx.color_mode_cond(light="1px solid #e2e8f0", dark="1px solid #334155"),
                                        border_radius="xl",
                                        p="2",
                                        box_shadow="xl",
                                        z_index="10",
                                        width="140px"
                                    ),
                                    rx.box()
                                ),
                                position="relative"
                            ),
                            spacing="4",
                            align_items="center"
                        ),
                        bg=rx.color_mode_cond(light="rgba(248, 250, 252, 0.6)", dark="rgba(15, 23, 42, 0.4)"),
                        backdrop_filter="blur(16px)",
                        border=rx.color_mode_cond(light="1px solid rgba(226, 232, 240, 0.8)", dark="1px solid rgba(30, 41, 59, 0.8)"),
                        border_radius="full",
                        padding="2",
                        padding_x="5",
                        box_shadow=rx.color_mode_cond(light="0 4px 6px -1px rgba(0,0,0,0.05)", dark="0 4px 6px -1px rgba(0,0,0,0.5)")
                    ),
                    width="100%",
                    align_items="end",
                    flex_wrap="wrap"
                ),
                
                # Fila de KPIs (Top Row)
                rx.grid(
                    kpi_card("Total Solicitudes", State.numero_solicitudes, "layers", rx.color_mode_cond(light="#2563eb", dark="#60a5fa"), rx.color_mode_cond(light="#eff6ff", dark="rgba(96, 165, 250, 0.1)")),
                    kpi_card("Cerradas", State.kpi_cerradas_count, "circle-check", rx.color_mode_cond(light="#059669", dark="#34d399"), rx.color_mode_cond(light="#ecfdf5", dark="rgba(52, 211, 153, 0.1)")),
                    kpi_card("En Proceso", State.kpi_en_curso_count, "activity", rx.color_mode_cond(light="#ea580c", dark="#fb923c"), rx.color_mode_cond(light="#fff7ed", dark="rgba(251, 146, 60, 0.1)")),
                    kpi_card("Vencidas/Pendientes", State.kpi_pendientes_count, "triangle-alert", rx.color_mode_cond(light="#dc2626", dark="#f87171"), rx.color_mode_cond(light="#fef2f2", dark="rgba(248, 113, 113, 0.1)")),
                    columns={"base": "1", "sm": "2", "lg": "4"},
                    spacing="6",
                    width="100%",
                    margin_y="6"
                ),

                # Contenedor de Gráficas (Grid 2 Columnas)
                rx.grid(
                    # 1. Cumplimiento (Dona)
                    chart_card(
                        "Nivel de Cumplimiento",
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
                                inner_radius=65,
                                label=True,
                            ),
                            width="100%",
                            height=300,
                        ),
                        extra_content=rx.center(
                            rx.hstack(
                                rx.text(State.compliance_percentage, font_size="4xl", font_weight="bold", color="#10b981"),
                                rx.text("%", font_size="xl", font_weight="bold", color="#10b981"),
                            ),
                            margin_top="-150px",
                            margin_bottom="110px",
                            pointer_events="none"
                        )
                    ),

                    # 2. Tipos de Solicitud (Barras)
                    chart_card(
                        "Volumen por Tipo",
                        rc.bar_chart(
                            rc.x_axis(data_key="name"),
                            rc.y_axis(domain=[0, State.max_registros_tipo]),
                            rc.tooltip(),
                            rc.bar(data_key="cantidad", fill="#3b82f6", radius=[6, 6, 0, 0]),
                            data=State.data_grafica_tipo,
                            width="100%",
                            height=300,
                        )
                    ),

                    # 3. Tiempos de Respuesta (Línea)
                    chart_card(
                        "Tiempos Promedio de Respuesta",
                        rc.line_chart(
                            rc.x_axis(data_key="month"),
                            rc.y_axis(),
                            rc.tooltip(),
                            rc.line(type="monotone", data_key="dias", stroke="#8b5cf6", stroke_width=4, dot={"r": 5, "fill": "#8b5cf6", "stroke": "#ffffff", "strokeWidth": 2}),
                            data=State.monthly_response_times,
                            width="100%",
                            height=300,
                        ),
                        extra_content=rx.box(),
                    ),

                    # 4. Solicitudes por vencer (Barras semáforo)
                    chart_card(
                        "Estado de Vencimiento",
                        rx.box(
                            # Gráfico principal
                            rc.bar_chart(
                                rc.x_axis(data_key="name"),
                                rc.y_axis(),
                                rc.tooltip(),
                                rc.bar(
                                    rc.cell(fill="#ef4444"),
                                    rc.cell(fill="#f59e0b"),
                                    rc.cell(fill="#f59e0b"),
                                    rc.cell(fill="#10b981"),
                                    data_key="cantidad",
                                    radius=[6, 6, 0, 0]
                                ),
                                data=State.solicitudes_por_vencer_data,
                                width="100%",
                                height=300,
                            ),
                            # Capa superpuesta con botones invisibles sobre cada barra para capturar clicks
                            rx.hstack(
                                rx.box(width="25%", height="100%", cursor="pointer", on_click=lambda: State.abrir_vencimiento_modal("Vencidas")),
                                rx.box(width="25%", height="100%", cursor="pointer", on_click=lambda: State.abrir_vencimiento_modal("1-5 días")),
                                rx.box(width="25%", height="100%", cursor="pointer", on_click=lambda: State.abrir_vencimiento_modal("6-10 días")),
                                rx.box(width="25%", height="100%", cursor="pointer", on_click=lambda: State.abrir_vencimiento_modal(">10 días")),
                                position="absolute",
                                top="0",
                                left="10%",  # offset for y-axis
                                width="90%",
                                height="85%", # offset for x-axis
                                z_index="10",
                                opacity="0"
                            ),
                            position="relative",
                            width="100%"
                        ),
                        extra_content=rx.center(
                            rx.hstack(
                                rx.button("Vencidas", size="1", variant="soft", color_scheme="red", radius="full", on_click=lambda: State.abrir_vencimiento_modal("Vencidas")),
                                rx.button("1-5 días", size="1", variant="soft", color_scheme="orange", radius="full", on_click=lambda: State.abrir_vencimiento_modal("1-5 días")),
                                rx.button("6-10 días", size="1", variant="soft", color_scheme="yellow", radius="full", on_click=lambda: State.abrir_vencimiento_modal("6-10 días")),
                                rx.button(">10 días", size="1", variant="soft", color_scheme="green", radius="full", on_click=lambda: State.abrir_vencimiento_modal(">10 días")),
                                spacing="2",
                                flex_wrap="wrap",
                                justify_content="center"
                            ),
                            width="100%",
                            margin_top="2"
                        )
                    ),
                    columns={"base": "1", "lg": "2"},
                    spacing="6",
                    width="100%",
                ),

                # Volumen por Áreas Responsables (Lista detallada con filtro y scroll)
                rx.box(
                    rx.vstack(
                        rx.hstack(
                            rx.heading("Distribución por Área Responsable", size="5", color=rx.color_mode_cond(light="#1e293b", dark="#f8fafc"), font_weight="bold"),
                            rx.spacer(),
                            rx.input(
                                placeholder="Filtrar área...",
                                value=State.search_area_query,
                                on_change=State.set_search_area_query,
                                variant="surface",
                                radius="full",
                                size="2",
                                width="200px"
                            ),
                            width="100%",
                            align_items="center"
                        ),
                        rx.divider(margin_y="4", border_color=rx.color_mode_cond(light="#e2e8f0", dark="#334155")),
                        rx.box(
                            rx.vstack(
                                rx.foreach(
                                    State.top_areas,
                                    lambda row: rx.hstack(
                                        rx.icon("users", size=18, color=rx.color_mode_cond(light="#64748b", dark="#94a3b8")),
                                        rx.text(row.get('name'), font_weight="medium", font_size="md", color=rx.color_mode_cond(light="#334155", dark="#cbd5e1")),
                                        rx.spacer(),
                                        rx.badge(row.get('total'), color_scheme="blue", variant="surface", size="3", radius="full"),
                                        width="100%",
                                        padding_y="3",
                                        border_bottom=rx.color_mode_cond(light="1px solid #f1f5f9", dark="1px solid #1e293b"),
                                        align_items="center"
                                    ),
                                ),
                                spacing="0",
                                width="100%"
                            ),
                            max_height="320px",
                            overflow_y="auto",
                            width="100%",
                            padding_right="2"
                        )
                    ),
                    p="8",
                    bg=rx.color_mode_cond(light="#ffffff", dark="#1e293b"),
                    border=rx.color_mode_cond(light="1px solid #e2e8f0", dark="1px solid #334155"),
                    border_radius="3xl",
                    box_shadow=rx.color_mode_cond(light="0 4px 6px -1px rgba(0, 0, 0, 0.05)", dark="none"),
                    width="100%",
                    margin_top="6",
                    _hover={"box_shadow": rx.color_mode_cond(light="0 10px 15px -3px rgba(0, 0, 0, 0.1)", dark="0 10px 15px -3px rgba(0, 0, 0, 0.5)")},
                    transition="box-shadow 0.3s ease"
                ),

                spacing="6",
                width="100%",
                max_width="1400px",
                padding_y="8"
            ),
            width="100%",
        ),
        
        # Modal de Vencimiento de Solicitudes
        rx.cond(
            State.vencimiento_modal_abierto,
            rx.box(
                rx.vstack(
                    rx.box(
                        # Orbes Decorativos Translúcidos
                        rx.box(position="absolute", top="-40px", left="-20%", width="150px", height="150px", 
                               bg=rx.cond(State.rango_vencimiento_seleccionado == "Vencidas", "rgba(239, 68, 68, 0.6)", 
                                          rx.cond(State.rango_vencimiento_seleccionado == "1-5 días", "rgba(245, 158, 11, 0.6)", "rgba(16, 185, 129, 0.6)")), 
                               border_radius="full", filter="blur(40px)"),
                        
                        rx.hstack(
                            rx.box(
                                rx.icon("layers", color="white", size=28),
                                bg="linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%)",
                                p="3",
                                border_radius="2xl",
                                box_shadow="0 10px 25px -5px rgba(59, 130, 246, 0.5)",
                            ),
                            rx.vstack(
                                rx.heading(
                                    rx.cond(
                                        State.rango_vencimiento_seleccionado == "Vencidas",
                                        "Solicitudes Vencidas",
                                        rx.cond(
                                            State.rango_vencimiento_seleccionado == "1-5 días",
                                            "Críticas (1-5 días)",
                                            rx.cond(
                                                State.rango_vencimiento_seleccionado == "6-10 días",
                                                "Por Vencer (6-10 días)",
                                                "A Salvo (>10 días)"
                                            )
                                        )
                                    ),
                                    size="6", font_weight="900", background_image="linear-gradient(90deg, #ffffff, #e2e8f0)", background_clip="text", color="transparent"
                                ),
                                rx.hstack(
                                    rx.text(
                                        "Total:",
                                        color="rgba(255,255,255,0.9)",
                                        font_size="sm",
                                        font_weight="bold"
                                    ),
                                    rx.badge(
                                        State.solicitudes_vencimiento_filtradas.length(),
                                        color_scheme="blue",
                                        variant="solid",
                                        radius="full"
                                    ),
                                    rx.text(
                                        "solicitudes filtradas en este rango.",
                                        color="rgba(255,255,255,0.8)",
                                        font_size="sm",
                                        font_weight="medium"
                                    ),
                                    spacing="2",
                                    align_items="center"
                                ),
                                spacing="1"
                            ),
                            spacing="4",
                            align_items="center",
                            position="relative",
                            z_index="2",
                            width="100%"
                        ),
                        p="8",
                        bg="linear-gradient(135deg, #0f172a 0%, #1e293b 100%)",
                        border_bottom="1px solid rgba(255,255,255,0.05)",
                        border_top_left_radius="3xl",
                        border_top_right_radius="3xl",
                        position="relative",
                        overflow="hidden",
                        width="100%"
                    ),
                    
                    # Contenido / Tabla de Solicitudes
                    rx.box(
                        rx.cond(
                            State.solicitudes_vencimiento_filtradas,
                            rx.vstack(
                                rx.table.root(
                                    rx.table.header(
                                        rx.table.row(
                                            rx.table.column_header_cell("Radicado"),
                                            rx.table.column_header_cell("Tipo"),
                                            rx.table.column_header_cell("Asunto"),
                                            rx.table.column_header_cell("Área Responsable"),
                                            rx.table.column_header_cell("Días Restantes"),
                                            rx.table.column_header_cell("Acción"),
                                        )
                                    ),
                                    rx.table.body(
                                        rx.foreach(
                                            State.solicitudes_vencimiento_filtradas,
                                            lambda s: rx.table.row(
                                                rx.table.row_header_cell(
                                                    rx.badge(s.get("radicado"), color_scheme="blue", variant="surface", radius="full")
                                                ),
                                                rx.table.cell(s.get("tipo_solicitud")),
                                                rx.table.cell(s.get("asunto")),
                                                rx.table.cell(s.get("area_responsable")),
                                                rx.table.cell(
                                                    rx.hstack(
                                                        rx.box(
                                                            width="8px",
                                                            height="8px",
                                                            bg=s.get("semaforo_fill"),
                                                            border_radius="full"
                                                        ),
                                                        rx.text(
                                                            s.get("remaining_str", ""),
                                                            font_weight="semibold",
                                                            color=s.get("semaforo_fill")
                                                        ),
                                                        spacing="2",
                                                        align_items="center"
                                                    )
                                                ),
                                                rx.table.cell(
                                                    rx.button(
                                                        rx.icon("eye", size=16),
                                                        on_click=lambda: State.abrir_detalle_solicitud(s.get("id")),
                                                        variant="soft",
                                                        color_scheme="blue",
                                                        size="1",
                                                        radius="full"
                                                    )
                                                )
                                            )
                                        )
                                    ),
                                    width="100%",
                                    variant="ghost"
                                ),
                                spacing="4",
                                width="100%"
                            ),
                            # Estado Vacío
                            rx.center(
                                rx.vstack(
                                    rx.icon("inbox", size=48, color="gray"),
                                    rx.text("No se encontraron solicitudes pendientes en este rango.", font_weight="semibold", color="gray"),
                                    spacing="2",
                                    padding_y="8"
                                ),
                                width="100%"
                            )
                        ),
                        p="6",
                        max_height="400px",
                        overflow_y="auto",
                        width="100%",
                        bg=rx.color_mode_cond(light="rgba(255, 255, 255, 0.4)", dark="rgba(15, 23, 42, 0.4)")
                    ),
                    
                    # Botón de Cerrar
                    rx.box(
                        rx.button(
                            "Cerrar Ventana",
                            on_click=State.cerrar_vencimiento_modal,
                            bg="linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%)",
                            color="white",
                            size="3",
                            width="100%",
                            box_shadow="0 4px 14px 0 rgba(59,130,246,0.39)",
                            _hover={"transform": "translateY(-2px)", "box_shadow": "0 6px 20px rgba(59,130,246,0.5)"},
                            transition="all 0.2s"
                        ),
                        p="5",
                        border_top=rx.color_mode_cond(light="1px solid rgba(0,0,0,0.05)", dark="1px solid rgba(255,255,255,0.05)"),
                        bg=rx.color_mode_cond(light="rgba(248, 250, 252, 0.4)", dark="rgba(11, 17, 32, 0.4)"),
                        border_bottom_left_radius="3xl",
                        border_bottom_right_radius="3xl",
                        width="100%"
                    ),
                    spacing="0",
                ),
                p="0",
                border=rx.color_mode_cond(light="1px solid rgba(255,255,255,0.6)", dark="1px solid rgba(255,255,255,0.08)"),
                border_radius="3xl",
                bg=rx.color_mode_cond(light="rgba(255, 255, 255, 0.9)", dark="rgba(15, 23, 42, 0.8)"),
                backdrop_filter="blur(20px)",
                width="100%",
                max_width="850px",
                position="fixed",
                top="50%",
                left="50%",
                transform="translate(-50%, -50%)",
                z_index="1000",
                box_shadow=rx.color_mode_cond(light="0 25px 50px -12px rgba(0, 0, 0, 0.25), 0 0 0 1px rgba(0,0,0,0.05)", dark="0 25px 50px -12px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(255,255,255,0.1)")
            )
        ),
        
        # Modal de Detalles de la Solicitud Seleccionada
        rx.cond(
            State.detalle_solicitud_modal_abierto,
            rx.box(
                # Fondo oscuro semitransparente detrás del modal
                rx.box(
                    position="fixed",
                    top="0",
                    left="0",
                    width="100vw",
                    height="100vh",
                    bg="rgba(15, 23, 42, 0.75)",
                    backdrop_filter="blur(10px)",
                    z_index="1050",
                    on_click=State.cerrar_detalle_solicitud
                ),
                # Contenido del Modal de Detalles
                rx.box(
                    rx.vstack(
                        # Encabezado con Gradiente Premium
                        rx.box(
                            rx.vstack(
                                rx.hstack(
                                    rx.icon("info", size=24, color="#3b82f6"),
                                    rx.heading(
                                        f"Detalles de Solicitud: {State.solicitud_consultada.get('radicado', '')}",
                                        size="5",
                                        color="#ffffff"
                                    ),
                                    rx.spacer(),
                                    rx.button(
                                        rx.icon("x", size=20),
                                        on_click=State.cerrar_detalle_solicitud,
                                        variant="ghost",
                                        color="#ffffff",
                                        _hover={"bg": "rgba(255,255,255,0.1)"}
                                    ),
                                    width="100%",
                                    align_items="center"
                                ),
                                spacing="1",
                                align_items="start"
                            ),
                            p="6",
                            bg="linear-gradient(135deg, #0f172a 0%, #1e293b 100%)",
                            border_bottom="1px solid rgba(255,255,255,0.05)",
                            border_top_left_radius="3xl",
                            border_top_right_radius="3xl",
                            position="relative",
                            overflow="hidden",
                            width="100%"
                        ),
                        
                        # Cuerpo del Modal (Scrollable)
                        rx.vstack(
                            rx.grid(
                                rx.vstack(
                                    rx.text("Número de Radicado:", font_weight="bold", color=rx.color_mode_cond(light="#475569", dark="#94a3b8"), font_size="xs", text_transform="uppercase"),
                                    rx.text(State.solicitud_consultada.get("radicado", ""), color=rx.color_mode_cond(light="#0f172a", dark="#ffffff"), font_size="sm", font_weight="semibold")
                                ),
                                rx.vstack(
                                    rx.text("Tipo de Solicitud:", font_weight="bold", color=rx.color_mode_cond(light="#475569", dark="#94a3b8"), font_size="xs", text_transform="uppercase"),
                                    rx.text(State.solicitud_consultada.get("tipo_solicitud", ""), color=rx.color_mode_cond(light="#0f172a", dark="#ffffff"), font_size="sm", font_weight="semibold")
                                ),
                                rx.vstack(
                                    rx.text("Estado Actual:", font_weight="bold", color=rx.color_mode_cond(light="#475569", dark="#94a3b8"), font_size="xs", text_transform="uppercase"),
                                    rx.badge(
                                        State.solicitud_consultada.get("estado", ""),
                                        color_scheme=rx.cond(
                                            State.solicitud_consultada.get("estado") == "Radicada",
                                            "orange",
                                            rx.cond(
                                                State.solicitud_consultada.get("estado") == "Actualizada",
                                                "blue",
                                                "green"
                                            )
                                        ),
                                        radius="full",
                                        variant="solid"
                                    )
                                ),
                                rx.vstack(
                                    rx.text("Fecha de Radicación:", font_weight="bold", color=rx.color_mode_cond(light="#475569", dark="#94a3b8"), font_size="xs", text_transform="uppercase"),
                                    rx.text(State.solicitud_consultada.get("fecha", ""), color=rx.color_mode_cond(light="#0f172a", dark="#ffffff"), font_size="sm")
                                ),
                                rx.vstack(
                                    rx.text("Área Responsable:", font_weight="bold", color=rx.color_mode_cond(light="#475569", dark="#94a3b8"), font_size="xs", text_transform="uppercase"),
                                    rx.text(State.solicitud_consultada.get("area_responsable", "No asignada"), color=rx.color_mode_cond(light="#0f172a", dark="#ffffff"), font_size="sm")
                                ),
                                rx.vstack(
                                    rx.text("Creado Por:", font_weight="bold", color=rx.color_mode_cond(light="#475569", dark="#94a3b8"), font_size="xs", text_transform="uppercase"),
                                    rx.text(State.solicitud_consultada.get("creado_por", ""), color=rx.color_mode_cond(light="#0f172a", dark="#ffffff"), font_size="sm")
                                ),
                                template_columns={"base": "1fr", "sm": "repeat(2, 1fr)", "md": "repeat(3, 1fr)"},
                                gap="4",
                                width="100%",
                                p="4",
                                border_radius="2xl",
                                bg=rx.color_mode_cond(light="#f1f5f9", dark="rgba(255,255,255,0.02)"),
                                border="1px dashed rgba(128,128,128,0.2)"
                            ),
                            
                            rx.vstack(
                                rx.text("Asunto:", font_weight="bold", color=rx.color_mode_cond(light="#475569", dark="#94a3b8"), font_size="xs", text_transform="uppercase"),
                                rx.text(State.solicitud_consultada.get("asunto", ""), color=rx.color_mode_cond(light="#0f172a", dark="#ffffff"), font_weight="bold", font_size="md"),
                                width="100%",
                                align_items="start"
                            ),
                            
                            # Descripción
                            rx.vstack(
                                rx.text("Descripción Detallada:", font_weight="bold", color=rx.color_mode_cond(light="#475569", dark="#94a3b8"), font_size="xs", text_transform="uppercase"),
                                rx.box(
                                    rx.text(State.solicitud_consultada.get("descripcion", ""), color=rx.color_mode_cond(light="#1e293b", dark="#cbd5e1"), font_size="sm", white_space="pre-wrap"),
                                    p="4",
                                    border=rx.color_mode_cond(light="1px solid #cbd5e0", dark="1px solid rgba(255,255,255,0.08)"),
                                    border_radius="2xl",
                                    bg=rx.color_mode_cond(light="#f8fafc", dark="rgba(15,23,42,0.6)"),
                                    width="100%"
                                ),
                                width="100%",
                                align_items="start"
                            ),
                            
                            # Respuesta
                            rx.cond(
                                State.solicitud_consultada.get("respuesta"),
                                rx.vstack(
                                    rx.hstack(
                                        rx.icon("message_square_plus", size=18, color="#10b981"),
                                        rx.text("Respuesta del Funcionario:", font_weight="bold", color="#10b981", font_size="xs", text_transform="uppercase"),
                                        spacing="2"
                                    ),
                                    rx.box(
                                        rx.text(State.solicitud_consultada.get("respuesta", ""), color=rx.color_mode_cond(light="#14532d", dark="#a7f3d0"), font_size="sm", white_space="pre-wrap"),
                                        p="4",
                                        border="1px solid #10b981",
                                        border_radius="2xl",
                                        bg=rx.color_mode_cond(light="#f0fff4", dark="rgba(16,185,129,0.08)"),
                                        width="100%"
                                    ),
                                    width="100%",
                                    align_items="start"
                                )
                            ),
                            
                            # Adjuntos Ciudadano
                            rx.cond(
                                State.solicitud_consultada.get("documento_adjuntos"),
                                rx.vstack(
                                    rx.hstack(
                                        rx.icon("paperclip", size=16, color="#3b82f6"),
                                        rx.text("Documentos Adjuntos por Ciudadano:", font_weight="bold", color=rx.color_mode_cond(light="#475569", dark="#94a3b8"), font_size="xs", text_transform="uppercase"),
                                        spacing="2"
                                    ),
                                    rx.vstack(
                                        rx.foreach(
                                            State.solicitud_consultada_adjuntos,
                                            lambda doc: rx.link(
                                                rx.hstack(
                                                    rx.icon("file-text", size=14),
                                                    rx.text(doc["basename"], font_size="xs", font_weight="semibold"),
                                                    align_items="center",
                                                    spacing="1"
                                                ),
                                                href=doc["href"],
                                                color="#3b82f6",
                                                target="_blank",
                                                p="2",
                                                border_radius="lg",
                                                bg=rx.color_mode_cond(light="#eff6ff", dark="rgba(59,130,246,0.1)"),
                                                _hover={"bg": rx.color_mode_cond(light="#dbeafe", dark="rgba(59,130,246,0.2)")}
                                            )
                                        ),
                                        align_items="start",
                                        spacing="2",
                                        width="100%"
                                    ),
                                    width="100%",
                                    align_items="start"
                                )
                            ),
                            
                            p="6",
                            max_height="450px",
                            overflow_y="auto",
                            width="100%",
                            spacing="4"
                        ),
                        
                        # Botón de Cerrar del Modal Detalles
                        rx.box(
                            rx.button(
                                "Cerrar Detalles",
                                on_click=State.cerrar_detalle_solicitud,
                                bg="linear-gradient(135deg, #475569 0%, #334155 100%)",
                                color="#ffffff",
                                size="3",
                                width="100%",
                                box_shadow="0 4px 14px 0 rgba(100,116,139,0.3)",
                                _hover={"transform": "translateY(-2px)", "box_shadow": "0 6px 20px rgba(100,116,139,0.4)"},
                                transition="all 0.2s"
                            ),
                            p="5",
                            border_top=rx.color_mode_cond(light="1px solid rgba(0,0,0,0.05)", dark="1px solid rgba(255,255,255,0.05)"),
                            bg=rx.color_mode_cond(light="#f8fafc", dark="rgba(11, 17, 32, 0.4)"),
                            border_bottom_left_radius="3xl",
                            border_bottom_right_radius="3xl",
                            width="100%"
                        ),
                        spacing="0",
                    ),
                    p="0",
                    border=rx.color_mode_cond(light="1px solid #cbd5e1", dark="1px solid rgba(255,255,255,0.08)"),
                    border_radius="3xl",
                    bg=rx.color_mode_cond(light="#ffffff", dark="#111827"),
                    width="95%",
                    max_width="720px",
                    position="fixed",
                    top="50%",
                    left="50%",
                    transform="translate(-50%, -50%)",
                    z_index="1100",
                    box_shadow="0 30px 60px -15px rgba(0,0,0,0.5)"
                )
            )
        ),
        width="100%",
        min_height="100vh",
        bg=rx.color_mode_cond(light="#f8fafc", dark="#0f172a")
    )
    # Restringir acceso: solo funcionarios y administradores
    return rx.cond(
        State.es_autenticada & ((State.rol_usuario == "funcionario") | (State.rol_usuario == "administrador")),
        content,
        rx.box(
            navbar(),
            rx.center(
                access_denied_widget("Solo funcionarios autenticados pueden ver esta página."),
                size="3"
            )
        )
    )

def usuarios_page() -> rx.Component:
    return rx.cond(
        State.es_autenticada & (State.rol_usuario == "funcionario"),
        rx.box(
            navbar(),
            rx.box(
                rx.vstack(
                    rx.hstack(
                        rx.vstack(
                            rx.heading("Directorio de Personal", size="7", color=rx.color_mode_cond(light="#0f172a", dark="#f8fafc"), font_weight="bold", letter_spacing="-0.02em"),
                            rx.text("Gestión y control de cuentas de usuarios registrados", color=rx.color_mode_cond(light="#64748b", dark="#94a3b8"), font_size="md"),
                            align_items="start",
                            spacing="1"
                        ),
                        rx.spacer(),
                        rx.box(
                            rx.icon("users", size=24, color=rx.color_mode_cond(light="#2563eb", dark="#60a5fa")),
                            p="3",
                            bg=rx.color_mode_cond(light="#eff6ff", dark="rgba(96, 165, 250, 0.1)"),
                            border_radius="xl"
                        ),
                        width="100%",
                        align_items="center"
                    ),
                    
                    rx.divider(margin_y="4", border_color=rx.color_mode_cond(light="#e2e8f0", dark="#334155")),

                    rx.box(
                        rx.cond(
                            State.usuarios_registrados,
                            rx.vstack(
                                rx.table.root(
                                    rx.table.header(
                                        rx.table.row(
                                            rx.table.column_header_cell("Usuario"),
                                            rx.table.column_header_cell("Contacto"),
                                            rx.table.column_header_cell("Rol", align="center"),
                                            rx.table.column_header_cell("Registro"),
                                            rx.table.column_header_cell("Estado", align="center"),
                                            rx.table.column_header_cell("Acciones", align="center"),
                                        ),
                                    ),
                                    rx.table.body(
                                        rx.foreach(
                                            State.usuarios_registrados,
                                            lambda usuario: rx.table.row(
                                                rx.table.cell(
                                                    rx.hstack(
                                                        rx.avatar(fallback=rx.cond(usuario["rol"] == "funcionario", "FN", "CD"), size="3", radius="full", color_scheme=rx.cond(usuario["rol"] == "funcionario", "blue", "gray")),
                                                        rx.vstack(
                                                            rx.text(f"{usuario['nombres']} {usuario['apellidos']}", font_weight="semibold", font_size="sm", color=rx.color_mode_cond(light="#1e293b", dark="#f8fafc")),
                                                            rx.text(f"ID: {usuario['id']}", font_size="xs", color=rx.color_mode_cond(light="#64748b", dark="#94a3b8")),
                                                            spacing="0", align_items="start"
                                                        ),
                                                        spacing="3", align_items="center"
                                                    )
                                                ),
                                                rx.table.cell(
                                                    rx.hstack(
                                                        rx.icon("mail", size=14, color=rx.color_mode_cond(light="#64748b", dark="#94a3b8")),
                                                        rx.text(usuario["email"], font_size="sm", color=rx.color_mode_cond(light="#475569", dark="#cbd5e1")),
                                                        spacing="2", align_items="center"
                                                    )
                                                ),
                                                rx.table.cell(
                                                    rx.badge(
                                                        rx.cond(usuario["rol"] == "funcionario", rx.icon("shield", size=12), rx.icon("user", size=12)),
                                                        usuario["rol"],
                                                        color_scheme=rx.cond(usuario["rol"] == "funcionario", "blue", "gray"),
                                                        variant="soft",
                                                        radius="full",
                                                        size="2",
                                                    ),
                                                    align="center"
                                                ),
                                                rx.table.cell(rx.text(usuario["fecha_creacion"], font_size="sm", color=rx.color_mode_cond(light="#64748b", dark="#94a3b8"))),
                                                rx.table.cell(
                                                    rx.hstack(
                                                        rx.box(width="8px", height="8px", border_radius="full", bg=rx.cond(usuario["is_active"] == "True", "#10b981", rx.cond(usuario["is_active"], "#10b981", "#ef4444"))),
                                                        rx.text(rx.cond(usuario["is_active"] == "True", "Activo", rx.cond(usuario["is_active"], "Activo", "Inactivo")), font_size="sm", color=rx.color_mode_cond(light="#475569", dark="#cbd5e1")),
                                                        spacing="2", align_items="center", justify="center"
                                                    ),
                                                    align="center"
                                                ),
                                                rx.table.cell(
                                                    rx.cond(
                                                        usuario["rol"] == "funcionario",
                                                        rx.button(
                                                            "Degradar a ciudadano",
                                                            size="2",
                                                            variant="soft",
                                                            color_scheme="red",
                                                            on_click=State.degradar_funcionario_a_ciudadano(usuario["email"]),
                                                            is_disabled=State.email_actual.to_string().lower() == usuario["email"].to_string().lower(),
                                                        ),
                                                        rx.box(),
                                                    ),
                                                    align="center",
                                                ),
                                                align_items="center",
                                                _hover={"bg": rx.color_mode_cond(light="#f8fafc", dark="rgba(30, 41, 59, 0.5)")},
                                                transition="background 0.2s"
                                            )
                                        )
                                    ),
                                    width="100%",
                                    size="3",
                                    variant="surface"
                                ),
                                rx.hstack(
                                    rx.text(f"Total de registros: {State.usuarios_registrados_count}", font_weight="medium", color=rx.color_mode_cond(light="#64748b", dark="#94a3b8"), font_size="sm"),
                                    rx.spacer(),
                                    width="100%",
                                    padding_top="4"
                                ),
                                spacing="4",
                                width="100%"
                            ),
                            rx.vstack(
                                rx.icon("users", size=48, color=rx.color_mode_cond(light="#cbd5e1", dark="#475569")),
                                rx.text("No hay usuarios registrados en el sistema.", color=rx.color_mode_cond(light="#64748b", dark="#94a3b8"), font_size="lg", font_weight="medium"),
                                spacing="4",
                                padding_y="12",
                                align_items="center"
                            )
                        ),
                        p="6",
                        border=rx.color_mode_cond(light="1px solid #e2e8f0", dark="1px solid #334155"),
                        border_radius="2xl",
                        bg=rx.color_mode_cond(light="rgba(255, 255, 255, 0.8)", dark="rgba(15, 23, 42, 0.6)"),
                        backdrop_filter="blur(16px)",
                        box_shadow=rx.color_mode_cond(light="0 4px 6px -1px rgba(0, 0, 0, 0.05)", dark="0 10px 15px -3px rgba(0, 0, 0, 0.5)"),
                        width="100%",
                        overflow_x="auto"
                    ),
                    
                    spacing="6",
                    align_items="stretch",
                    width="100%"
                ),
                bg=rx.color_mode_cond(light="white", dark="#1a202c"),
                max_width="100%",
                p=rx.breakpoints(initial="4", md="6"),
                box_shadow="2xl",
                border_radius="3xl",
                width="100%",
                margin_y="4"
            ),
            width="100%",
            max_width="100%",
            p=rx.breakpoints(initial="2", md="3"),
            bg=rx.color_mode_cond(light="#f8fafc", dark="#0f172a"),
            min_height="100vh"
        ),
        rx.box(
            navbar(),
            rx.center(
                access_denied_widget("Solo funcionarios autenticados pueden ver esta página."),
                size="3"
            )
        )
    )


def cambiar_rol_page() -> rx.Component:
    return rx.cond(
        State.es_autenticada & (State.rol_usuario == "funcionario"),
        rx.box(
            navbar(),
            rx.center(
                rx.box(
                    # Glow de fondo moderno
                    rx.box(
                        position="absolute",
                        top="-120px",
                        left="-80px",
                        width="280px",
                        height="280px",
                        bg="rgba(37, 99, 235, 0.25)",
                        border_radius="full",
                        filter="blur(80px)",
                        z_index="0",
                    ),
                    rx.box(
                        position="absolute",
                        bottom="-140px",
                        right="-100px",
                        width="320px",
                        height="320px",
                        bg="rgba(14, 165, 233, 0.2)",
                        border_radius="full",
                        filter="blur(90px)",
                        z_index="0",
                    ),
                    rx.box(
                        rx.vstack(
                            rx.hstack(
                                rx.box(
                                    rx.icon("shield-check", size=28, color=rx.color_mode_cond(light="#1d4ed8", dark="#60a5fa")),
                                    p="3",
                                    border_radius="xl",
                                    bg=rx.color_mode_cond(light="#dbeafe", dark="rgba(59, 130, 246, 0.18)"),
                                ),
                                rx.vstack(
                                    rx.heading(
                                        "Promover ciudadano a funcionario",
                                        size="7",
                                        font_weight="bold",
                                        color=rx.color_mode_cond(light="#0f172a", dark="#f8fafc"),
                                    ),
                                    rx.text(
                                        "Gestiona privilegios con validación previa y confirmación explícita.",
                                        color=rx.color_mode_cond(light="#475569", dark="#94a3b8"),
                                        font_size="md",
                                    ),
                                    spacing="1",
                                    align_items="start",
                                ),
                                spacing="4",
                                align_items="center",
                                width="100%",
                            ),
                            rx.grid(
                                # Columna de contexto
                                rx.vstack(
                                    rx.box(
                                        rx.hstack(
                                            rx.icon("triangle-alert", size=16, color=rx.color_mode_cond(light="#b45309", dark="#fbbf24")),
                                            rx.text(
                                                "Esta acción otorga acceso a panel de gestión, reportes y actualización de solicitudes.",
                                                font_size="sm",
                                                color=rx.color_mode_cond(light="#92400e", dark="#fde68a"),
                                            ),
                                            spacing="2",
                                            align_items="start",
                                        ),
                                        p="4",
                                        border_radius="lg",
                                        bg=rx.color_mode_cond(light="#fffbeb", dark="rgba(245, 158, 11, 0.1)"),
                                        border=rx.color_mode_cond(light="1px solid #fde68a", dark="1px solid rgba(245, 158, 11, 0.25)"),
                                        width="100%",
                                    ),
                                    rx.box(
                                        rx.vstack(
                                            rx.text("Checklist previo", font_weight="bold", color=rx.color_mode_cond(light="#0f172a", dark="#e2e8f0")),
                                            rx.text("• Validar identidad del ciudadano", font_size="sm", color=rx.color_mode_cond(light="#475569", dark="#94a3b8")),
                                            rx.text("• Confirmar solicitud/autorización", font_size="sm", color=rx.color_mode_cond(light="#475569", dark="#94a3b8")),
                                            rx.text("• Verificar correo institucional", font_size="sm", color=rx.color_mode_cond(light="#475569", dark="#94a3b8")),
                                            spacing="1",
                                            align_items="start",
                                        ),
                                        p="4",
                                        border_radius="lg",
                                        bg=rx.color_mode_cond(light="rgba(241, 245, 249, 0.7)", dark="rgba(15, 23, 42, 0.4)"),
                                        border=rx.color_mode_cond(light="1px solid #e2e8f0", dark="1px solid #334155"),
                                        width="100%",
                                    ),
                                    spacing="4",
                                    align_items="start",
                                    width="100%",
                                ),
                                # Columna de acción
                                rx.vstack(
                                    rx.vstack(
                                        rx.text(
                                            "Correo electrónico del ciudadano",
                                            font_weight="semibold",
                                            font_size="sm",
                                            color=rx.color_mode_cond(light="#334155", dark="#cbd5e1"),
                                        ),
                                        rx.input(
                                            placeholder="usuario@ejemplo.com",
                                            value=State.cambiar_rol_email,
                                            on_change=State.set_cambiar_rol_email,
                                            width="100%",
                                            type="email",
                                            size="3",
                                            radius="large",
                                        ),
                                        spacing="2",
                                        width="100%",
                                    ),
                                    rx.checkbox(
                                        "Confirmo validación de identidad y autorización para promover este rol.",
                                        is_checked=State.confirmar_promocion_rol,
                                        on_change=State.set_confirmar_promocion_rol,
                                        color=rx.color_mode_cond(light="#334155", dark="#cbd5e1"),
                                        size="2",
                                    ),
                                    rx.hstack(
                                        rx.button(
                                            rx.icon("arrow-up-circle", size=20),
                                            "Confirmar promoción",
                                            on_click=State.cambiar_rol_ciudadano_a_funcionario,
                                            color_scheme="blue",
                                            size="3",
                                            radius="large",
                                            flex="1",
                                            is_disabled=(State.cambiar_rol_email == "") | (~State.confirmar_promocion_rol),
                                            _hover={"transform": "translateY(-1px)"},
                                            transition="all 0.2s",
                                        ),
                                        rx.button(
                                            rx.icon("rotate-ccw", size=16),
                                            "Limpiar",
                                            on_click=State.limpiar_form_promocion_rol,
                                            variant="soft",
                                            color_scheme="gray",
                                            size="3",
                                            radius="large",
                                        ),
                                        spacing="3",
                                        width="100%",
                                    ),
                                    rx.cond(
                                        State.cambiar_rol_mensaje != "",
                                        rx.box(
                                            rx.text(
                                                State.cambiar_rol_mensaje,
                                                color=rx.cond(
                                                    State.cambiar_rol_mensaje.contains("✅"),
                                                    "#059669",
                                                    "#dc2626",
                                                ),
                                                font_size="sm",
                                                white_space="pre-wrap",
                                            ),
                                            p="4",
                                            border_radius="lg",
                                            bg=rx.cond(
                                                State.cambiar_rol_mensaje.contains("✅"),
                                                rx.color_mode_cond(light="#ecfdf5", dark="rgba(16, 185, 129, 0.1)"),
                                                rx.color_mode_cond(light="#fef2f2", dark="rgba(239, 68, 68, 0.1)"),
                                            ),
                                            border=rx.cond(
                                                State.cambiar_rol_mensaje.contains("✅"),
                                                rx.color_mode_cond(light="1px solid #a7f3d0", dark="1px solid rgba(16, 185, 129, 0.2)"),
                                                rx.color_mode_cond(light="1px solid #fecaca", dark="1px solid rgba(239, 68, 68, 0.2)"),
                                            ),
                                            width="100%",
                                        ),
                                    ),
                                    spacing="4",
                                    align_items="start",
                                    width="100%",
                                ),
                                columns=rx.breakpoints(initial="1", md="2"),
                                spacing="6",
                                width="100%",
                            ),
                            spacing="6",
                            width="100%",
                            align_items="start",
                        ),
                        p=rx.breakpoints(initial="5", md="6"),
                        border_radius="24px",
                        bg=rx.color_mode_cond(light="rgba(255, 255, 255, 0.92)", dark="rgba(15, 23, 42, 0.82)"),
                        backdrop_filter="blur(18px)",
                        border=rx.color_mode_cond(light="1px solid rgba(226, 232, 240, 0.9)", dark="1px solid rgba(51, 65, 85, 0.9)"),
                        box_shadow=rx.color_mode_cond(light="0 20px 30px -12px rgba(15, 23, 42, 0.2)", dark="0 25px 50px -12px rgba(0, 0, 0, 0.75)"),
                        width="100%",
                        max_width="920px",
                        z_index="1",
                    ),
                    position="relative",
                    width="100%",
                    max_width="920px",
                ),
                width="100%",
                min_height="calc(100vh - 64px)",
                padding_x="6",
                padding_y=rx.breakpoints(initial="2", md="3"),
                display="flex",
                align_items="center",
                justify_content="center",
            ),
            bg=rx.color_mode_cond(light="#f1f5f9", dark="#0b1220"),
            min_height="100vh",
            width="100%"
        ),
        rx.box(
            navbar(),
            rx.center(
                access_denied_widget("Solo funcionarios autenticados pueden acceder a esta función."),
                size="3"
            )
        )
    )


def ayuda_funcionario_page() -> rx.Component:
    def acordeon_item(titulo: str, key: str, icono: str, contenido: rx.Component) -> rx.Component:
        abierto = State.ayuda_seccion_abierta == key
        return rx.box(
            rx.vstack(
                rx.button(
                    rx.hstack(
                        rx.hstack(
                            rx.box(
                                rx.icon(icono, size=18, color=rx.color_mode_cond(light="#2563eb", dark="#60a5fa")),
                                p="2",
                                bg=rx.color_mode_cond(light="#eff6ff", dark="rgba(96, 165, 250, 0.12)"),
                                border_radius="lg",
                            ),
                            rx.text(titulo, font_weight="bold", font_size="lg"),
                            spacing="3",
                            align_items="center",
                        ),
                        rx.spacer(),
                        rx.icon(rx.cond(abierto, "chevron_up", "chevron_down"), size=20),
                        width="100%",
                        align_items="center",
                    ),
                    on_click=State.toggle_ayuda_seccion(key),
                    variant="ghost",
                    width="100%",
                    justify="start",
                    p="4",
                ),
                rx.cond(
                    abierto,
                    rx.box(contenido, px="6", pb="6", width="100%"),
                    rx.box(),
                ),
                spacing="0",
                width="100%",
                align_items="start",
            ),
            bg=rx.color_mode_cond(light="rgba(255,255,255,0.95)", dark="rgba(30,41,59,0.9)"),
            border=rx.color_mode_cond(light="1px solid #dbeafe", dark="1px solid #334155"),
            border_radius="2xl",
            box_shadow=rx.color_mode_cond(light="0 10px 20px -12px rgba(0,0,0,0.12)", dark="0 10px 25px -15px rgba(0,0,0,0.7)"),
            width="100%",
        )

    hero = rx.box(
        rx.vstack(
            rx.hstack(
                rx.box(
                    rx.icon("circle_help", size=38, color="white"),
                    p="4",
                    bg="linear-gradient(135deg, #2563eb 0%, #7c3aed 100%)",
                    border_radius="2xl",
                    box_shadow="0 10px 25px -10px rgba(59,130,246,0.7)",
                ),
                rx.vstack(
                    rx.heading("Centro de Ayuda para Funcionarios", size="9", color="white", font_weight="bold"),
                    rx.text(
                        "Todo lo que necesitas para operar PQRS con rapidez, trazabilidad y calidad de servicio.",
                        color="rgba(255,255,255,0.9)",
                        font_size="lg",
                    ),
                    spacing="2",
                    align_items="start",
                ),
                spacing="4",
                width="100%",
                align_items="center",
            ),
            rx.grid(
                rx.box(
                    rx.text("Estado sugerido", font_size="sm", color="rgba(255,255,255,0.8)"),
                    rx.text("Radicada → En Proceso → Cerrada", font_weight="bold", color="white", font_size="lg"),
                ),
                rx.box(
                    rx.text("Tiempo de respuesta", font_size="sm", color="rgba(255,255,255,0.8)"),
                    rx.text("Métrica en días hábiles reales", font_weight="bold", color="white", font_size="lg"),
                ),
                rx.box(
                    rx.text("Objetivo", font_size="sm", color="rgba(255,255,255,0.8)"),
                    rx.text("Cerrar más rápido y mejor", font_weight="bold", color="white", font_size="lg"),
                ),
                columns={"base": "1", "md": "3"},
                spacing="4",
                width="100%",
            ),
            spacing="5",
            width="100%",
        ),
        p={"base": "6", "md": "8"},
        border_radius="3xl",
        bg="linear-gradient(120deg, #0f172a 0%, #1e3a8a 45%, #6d28d9 100%)",
        width="100%",
    )

    return rx.cond(
        State.es_autenticada & (State.rol_usuario == "funcionario"),
        rx.box(
            navbar(),
            rx.box(
                rx.box(
                    rx.vstack(
                        hero,
                        rx.vstack(
                        acordeon_item(
                            "1. Flujo recomendado de atención",
                            "estados",
                            "list_checks",
                            rx.vstack(
                                rx.text("Radicada: se recibió la solicitud y aún no ha sido gestionada.", font_size="lg"),
                                rx.text("En Proceso: ya existe análisis, contacto o trabajo activo sobre el caso.", font_size="lg"),
                                rx.text("Cerrada: se entregó respuesta final y, de ser necesario, adjuntos de soporte.", font_size="lg"),
                                rx.text("Consejo: evita cierres vacíos; documenta siempre la solución.", font_size="lg", font_weight="medium", color=rx.color_mode_cond(light="#475569", dark="#cbd5e1")),
                                spacing="2",
                                width="100%",
                                align_items="start",
                            ),
                        ),
                        acordeon_item(
                            "2. Respuestas y documentos adjuntos",
                            "adjuntos",
                            "paperclip",
                            rx.vstack(
                                rx.text("En 'Actualizar estado' redacta una respuesta clara y orientada al ciudadano.", font_size="lg"),
                                rx.text("Si adjuntas evidencia (PDF/imagen), el sistema la envía por correo al cerrar.", font_size="lg"),
                                rx.text("Nombra archivos de forma descriptiva para facilitar auditorías y seguimiento.", font_size="lg"),
                                spacing="2",
                                width="100%",
                                align_items="start",
                            ),
                        ),
                        acordeon_item(
                            "3. Reportes y lectura de métricas",
                            "reportes",
                            "chart_line",
                            rx.vstack(
                                rx.text("La gráfica de tiempos usa solicitudes cerradas con fecha real de respuesta.", font_size="lg"),
                                rx.text("Tooltip 'dias: X' significa promedio de días hábiles en esa fecha.", font_size="lg"),
                                rx.text("Usa filtros por tipo y exportaciones (Excel/CSV) para informes ejecutivos.", font_size="lg"),
                                spacing="2",
                                width="100%",
                                align_items="start",
                            ),
                        ),
                        acordeon_item(
                            "4. Administración de usuarios",
                            "usuarios",
                            "users",
                            rx.vstack(
                                rx.text("Consulta roles y estado de cuentas desde 'Ver Usuarios'.", font_size="lg"),
                                rx.text("Puedes degradar de funcionario a ciudadano cuando corresponda.", font_size="lg"),
                                rx.text("Por seguridad, no está permitido degradar tu propia cuenta.", font_size="lg"),
                                spacing="2",
                                width="100%",
                                align_items="start",
                            ),
                        ),
                        acordeon_item(
                            "5. Buenas prácticas operativas",
                            "buenas_practicas",
                            "shield_check",
                            rx.vstack(
                                rx.text("Prioriza vencidas y críticas con el semáforo de vencimientos.", font_size="lg"),
                                rx.text("Mantén respuestas concretas, respetuosas y con lenguaje ciudadano.", font_size="lg"),
                                rx.text("Antes de cerrar: valida ortografía, adjuntos y consistencia del estado.", font_size="lg"),
                                spacing="2",
                                width="100%",
                                align_items="start",
                            ),
                        ),
                        spacing="4",
                        width="100%",
                        ),
                        # Bloque de cierre para ocupar altura y mantener estética profesional
                        rx.box(
                            rx.grid(
                                rx.box(
                                    rx.text("SLA recomendado", font_size="sm", color=rx.color_mode_cond(light="#64748b", dark="#94a3b8")),
                                    rx.text("Responder en < 5 días hábiles", font_weight="bold", font_size="lg"),
                                    p="4",
                                    border_radius="xl",
                                    bg=rx.color_mode_cond(light="#f8fafc", dark="rgba(15,23,42,0.55)"),
                                    border=rx.color_mode_cond(light="1px solid #e2e8f0", dark="1px solid #334155"),
                                ),
                                rx.box(
                                    rx.text("Calidad de respuesta", font_size="sm", color=rx.color_mode_cond(light="#64748b", dark="#94a3b8")),
                                    rx.text("Clara, completa y verificable", font_weight="bold", font_size="lg"),
                                    p="4",
                                    border_radius="xl",
                                    bg=rx.color_mode_cond(light="#f8fafc", dark="rgba(15,23,42,0.55)"),
                                    border=rx.color_mode_cond(light="1px solid #e2e8f0", dark="1px solid #334155"),
                                ),
                                rx.box(
                                    rx.text("Seguimiento", font_size="sm", color=rx.color_mode_cond(light="#64748b", dark="#94a3b8")),
                                    rx.text("Revisar vencimientos cada día", font_weight="bold", font_size="lg"),
                                    p="4",
                                    border_radius="xl",
                                    bg=rx.color_mode_cond(light="#f8fafc", dark="rgba(15,23,42,0.55)"),
                                    border=rx.color_mode_cond(light="1px solid #e2e8f0", dark="1px solid #334155"),
                                ),
                                columns={"base": "1", "md": "3"},
                                spacing="4",
                                width="100%",
                            ),
                            width="100%",
                            margin_top="auto",
                            pt="6",
                        ),
                        spacing="6",
                        width="100%",
                        max_width="1650px",
                        min_height="calc(100vh - 130px)",
                        p={"base": "3", "md": "4"},
                    ),
                    width="100%",
                    bg=rx.color_mode_cond(light="rgba(255,255,255,0.7)", dark="rgba(15,23,42,0.45)"),
                    border=rx.color_mode_cond(light="1px solid #dbeafe", dark="1px solid #1e293b"),
                    border_radius="3xl",
                    box_shadow=rx.color_mode_cond(light="0 16px 40px -24px rgba(0,0,0,0.2)", dark="0 18px 45px -25px rgba(0,0,0,0.8)"),
                    margin_x={"base": "6px", "md": "14px"},
                ),
                width="100%",
                bg=rx.color_mode_cond(light="#f1f5f9", dark="#0f172a"),
                min_height="100vh",
                padding_top={"base": "6px", "md": "10px"},
                padding_bottom={"base": "12px", "md": "18px"},
            ),
        ),
        rx.box(
            navbar(),
            rx.center(access_denied_widget("Solo funcionarios autenticados pueden acceder a esta función."), size="3"),
        ),
    )

app = rx.App()
app.add_page(index, route="/", title="Inicio - Sistema PQRS")
app.add_page(registro_page, route="/registro", title="Registro de Ciudadano")
app.add_page(registro_funcionario_page, route="/registro-funcionario", title="Registro de Funcionario")
app.add_page(login_page, route="/login", title="Iniciar Sesión")
app.add_page(solicitudes_page, route="/solicitudes", title="Nueva Solicitud PQRS")
app.add_page(change_password_page, route="/cambiar-contrasena", title="Cambiar Contraseña")
app.add_page(dashboard, route="/dashboard", title="Panel de Ciudadano", on_load=State.cargar_solicitudes)
app.add_page(funcionario_dashboard, route="/dashboard-funcionario", title="Panel de Funcionario", on_load=State.cargar_datos_funcionario)
app.add_page(funcionario_cerradas_dashboard, route="/dashboard-funcionario-cerradas", title="Solicitudes Cerradas", on_load=State.cargar_datos_funcionario)
app.add_page(usuarios_page, route="/usuarios", title="Gestión de Usuarios", on_load=State.cargar_usuarios)
app.add_page(cambiar_rol_page, route="/cambiar-rol", title="Cambiar Rol de Usuario")
app.add_page(ayuda_funcionario_page, route="/ayuda-funcionario", title="Ayuda para Funcionarios")
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
    
