"""Sistema de Gestión de PQRS para Empresas Públicas - Sprint 1: Registro de Ciudadanos"""
import re
import datetime
from datetime import datetime
import bcrypt
import base64
import uuid
<<<<<<< HEAD
import reflex as rx
from .usuario_model import Usuario
from sqlmodel import select
=======
import os
import reflex as rx
from .usuario_model import Usuario, Solicitud
from sqlmodel import select, SQLModel, create_engine
>>>>>>> e2b305b84823c9d11bb994642ecae2240d4e6dcb
from rxconfig import config
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
# Carpeta donde se guardarán los archivos subidos por los usuarios
<<<<<<< HEAD
UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")
from typing import List, Dict

# Cargar variables de entorno
load_dotenv()
=======
UPLOAD_DIR = os.path.join(os.getcwd(), "assets", "uploads")
from typing import List, Dict, Any

# Cargar variables de entorno
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///reflex.db")
engine = create_engine(DATABASE_URL, echo=False)
SQLModel.metadata.create_all(engine)
>>>>>>> e2b305b84823c9d11bb994642ecae2240d4e6dcb

def tiene_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
def confirmar_contraseña(contraseña: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(contraseña.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False
def validar_correo(correo: str) -> bool:
    return bool(re.fullmatch(r"[^@]+@[^@]+\.[^@]+", correo))
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


def enviar_correo_bienvenida(email_destinatario: str, email_usuario: str):
    """Envía un correo de bienvenida con las credenciales de acceso"""
    try:
        # Obtener credenciales del archivo .env
        email_sender = os.getenv("EMAIL_SENDER")
        email_password = os.getenv("EMAIL_PASSWORD")
        smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        empresa_nombre = os.getenv("EMPRESA_NOMBRE", "Sistema de Gestión de PQRS")
        
        # Validar que existan credenciales
        if not email_sender or not email_password:
            print("⚠️ Advertencia: Credenciales de correo no configuradas en .env")
            return False
        
        # Crear mensaje
        mensaje = MIMEMultipart("alternative")
        mensaje["Subject"] = f"¡Bienvenido a {empresa_nombre}!"
        mensaje["From"] = email_sender
        mensaje["To"] = email_destinatario
        
        # Contenido del correo en HTML
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
<<<<<<< HEAD
                
=======
                    
>>>>>>> e2b305b84823c9d11bb994642ecae2240d4e6dcb
                    <hr style="border: 1px solid #ddd; margin: 20px 0;">
                    <p style="color: #666; font-size: 14px;"><strong>Recuerda:</strong> Nunca compartas tu contraseña con terceros. El equipo de soporte nunca te pedirá tu contraseña.</p>
                    <p style="color: #666; font-size: 14px;">Si tienes preguntas o problemas, contacta a nuestro equipo de soporte.</p>
                    <p style="text-align: center; color: #999; font-size: 12px; margin-top: 30px;">© 2026 {empresa_nombre}. Todos los derechos reservados.</p>
                </div>
            </body>
        </html>
        """
        
        # Adjuntar el contenido
        parte_html = MIMEText(html, "html")
        mensaje.attach(parte_html)
        
        # Enviar correo
        with smtplib.SMTP(smtp_server, smtp_port) as servidor:
            servidor.starttls()
            servidor.login(email_sender, email_password)
            servidor.sendmail(email_sender, email_destinatario, mensaje.as_string())
        
        print(f"✅ Correo enviado exitosamente a {email_destinatario}")
        return True
    
    except Exception as e:
        print(f"❌ Error al enviar correo: {str(e)}")
        return False


# quitar prints de prueba

class State(rx.State):
    "En esta clase se define el estado de la aplicación, es decir, las variables que se van a usar en la aplicación y sus valores iniciales."
    contraseña: str = ""
    confirmar_contraseña: str = ""
    correo: str = ""
    # Campos adicionales para registro extendido
    tipo_identificacion: str = ""
    numero_identificacion: str = ""
    nombres: str = ""
    apellidos: str = ""
    genero: str = ""
    direccion: str = ""
    telefono: str = ""
    departamento: str = ""
    ciudad: str = ""
    # Estados de validación UX
    correo_validado: bool = False
    numero_identificacion_valid: bool = False
    nombres_valid: bool = False
    apellidos_valid: bool = False
    telefono_valid: bool = False
    departamento_valid: bool = False
    ciudad_valid: bool = False
    # Habeas data / autorizaciones
    acepta_notificaciones: bool = False
    acepta_politica_datos: bool = False
    # Para el formulario de solicitudes
    acepta_politica_solicitud: bool = False
    tipo_solicitud: str = ""
    asunto: str = ""
    descripcion: str = ""
    ubicacion: str = ""
    documento: str = ""
    documento_nombre: str = ""
    descripcion_len: int = 0
    solicitudes: List[Dict] = []
    editar_solicitud_id: int = 0
    solicitud_mensaje: str = ""
    
    error_de_registro: str = ""
    succes: str = ""
    error_de_contraseña: str = ""
    succes2: str = ""
    
    id_usuario: int = 0
    es_autentica: bool = False
<<<<<<< HEAD
=======
    email_actual: str = ""
    rol_usuario: str = ""
    email_actual: str = ""
>>>>>>> e2b305b84823c9d11bb994642ecae2240d4e6dcb
    show_password: bool = False
    # Campos para cambiar contraseña
    current_password: str = ""
    new_password: str = ""
    confirm_new_password: str = ""
    change_pw_message: str = ""
    
    def borrar_mensajes_de_estado(self):
        self.error_de_registro = ""
        self.succes = ""
        self.error_de_contraseña = ""
        self.succes2 = ""
        
    def validacion_de_entradas(self, require_strong_pw: bool = True) -> bool:
        if not validar_correo(self.correo):
            self.error_de_registro = "Correo no válido."
            return False
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
<<<<<<< HEAD
        
=======
        return ok
>>>>>>> e2b305b84823c9d11bb994642ecae2240d4e6dcb

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
        self.validar_campo_simple("departamento")

    def set_and_validate_ciudad(self, val: str):
        self.ciudad = val
        self.validar_campo_simple("ciudad")

    def set_descripcion(self, val: str):
        # Guardar descripción y longitud para el contador de caracteres
        self.descripcion = val if val is not None else ""
        # Limitar a 1000 caracteres en la UI
        if len(self.descripcion) > 1000:
            self.descripcion = self.descripcion[:1000]
        self.descripcion_len = len(self.descripcion)

    def set_documento(self, val):
        # Valida y guarda nombre/valor del documento enviado desde el input file
        # Valores posibles: dict con 'name' y 'content', o string (ruta/data URL)
        self.documento = val
        try:
            if isinstance(val, dict) and "name" in val:
                self.documento_nombre = val.get("name", "")
            elif isinstance(val, str):
                # puede ser data URL o ruta; mostrar solo la parte final
                self.documento_nombre = os.path.basename(val)
            else:
                self.documento_nombre = ""
        except Exception:
            self.documento_nombre = ""
<<<<<<< HEAD
=======

    def _solicitud_a_dict(self, solicitud: Solicitud) -> Dict[str, Any]:
        return {
            "id": solicitud.id,
            "radicado": solicitud.radicado,
            "tipo_solicitud": solicitud.tipo_solicitud,
            "asunto": solicitud.asunto,
            "descripcion": solicitud.descripcion,
            "ubicacion": solicitud.ubicacion,
            "documento": solicitud.documento,
            "documento_basename": solicitud.documento_basename,
            "estado": solicitud.estado,
            "fecha": solicitud.fecha.strftime("%Y-%m-%d %H:%M") if isinstance(solicitud.fecha, datetime) else str(solicitud.fecha),
            "creado_por": solicitud.creado_por,
            "usuario_id": solicitud.usuario_id,
        }

    def cargar_solicitudes(self):
        try:
            with rx.session() as session:
                query = select(Solicitud).order_by(Solicitud.id)
                if self.rol_usuario == "ciudadano" and self.email_actual:
                    query = query.where(Solicitud.creado_por == self.email_actual)
                solicitudes_obj = session.exec(query).all()
                self.solicitudes = [self._solicitud_a_dict(s) for s in solicitudes_obj]
        except Exception as e:
            print(f"Error cargando solicitudes: {e}")
            self.solicitudes = []

>>>>>>> e2b305b84823c9d11bb994642ecae2240d4e6dcb
    def signup(self):
        self.borrar_mensajes_de_estado()
        if not self.validacion_de_entradas():
            return
        # Validaciones adicionales para registro extendido
        required_fields = ["nombres", "apellidos", "tipo_identificacion", "numero_identificacion"]
        for f in required_fields:
            if not getattr(self, f, ""):
                self.error_de_registro = "Completa los campos obligatorios de información personal."
                return
        if not self.acepta_politica_datos or not self.acepta_notificaciones:
            self.error_de_registro = "Debes aceptar la política de datos y recibir notificaciones para registrarte."
            return
        with rx.session() as session:
            existing_user = session.exec(select(Usuario).where(Usuario.email == self.correo)).first()
            if existing_user:
                self.error_de_registro = "El correo ya está registrado."
                return
            hashed = tiene_password(self.contraseña)
            nuevo_usuario = Usuario(
                email=self.correo,
                Contraseña=hashed,
                rol="ciudadano",
                is_active=True,
                Fecha_de_creacion=datetime.now(),
                tipo_identificacion=self.tipo_identificacion,
                numero_identificacion=self.numero_identificacion,
                nombres=self.nombres,
                apellidos=self.apellidos,
                genero=self.genero,
                direccion=self.direccion,
                telefono=self.telefono,
                departamento=self.departamento,
                ciudad=self.ciudad,
            )
            session.add(nuevo_usuario)
            session.commit()
            print(f"Usuario registrado: {self.correo}")
            # Enviar correo de bienvenida
            enviar_correo_bienvenida(self.correo, self.correo)
<<<<<<< HEAD
            self.succes = "Registro exitoso. Revisa tu correo para confirmar. Ahora puedes iniciar sesión."
=======
            self.succes = "Registro exitoso. Revisa tu correo para confirmar. Ahora el funcionario puede iniciar sesión."
>>>>>>> e2b305b84823c9d11bb994642ecae2240d4e6dcb
            self.error_de_registro = ""
            self.contraseña = ""
            self.confirmar_contraseña = ""
            self.show_password = False
<<<<<<< HEAD
=======

    def signup_funcionario(self):
        self.borrar_mensajes_de_estado()
        if not self.es_autentica or self.rol_usuario != "funcionario":
            self.error_de_registro = "Solo los funcionarios autenticados pueden registrar nuevos funcionarios."
            return
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
        with rx.session() as session:
            existing_user = session.exec(select(Usuario).where(Usuario.email == self.correo)).first()
            if existing_user:
                self.error_de_registro = "El correo ya está registrado."
                return
            hashed = tiene_password(self.contraseña)
            nuevo_usuario = Usuario(
                email=self.correo,
                Contraseña=hashed,
                rol="funcionario",
                is_active=True,
                Fecha_de_creacion=datetime.now(),
                tipo_identificacion=self.tipo_identificacion,
                numero_identificacion=self.numero_identificacion,
                nombres=self.nombres,
                apellidos=self.apellidos,
                genero=self.genero,
                direccion=self.direccion,
                telefono=self.telefono,
                departamento=self.departamento,
                ciudad=self.ciudad,
            )
            session.add(nuevo_usuario)
            session.commit()
            print(f"Funcionario registrado: {self.correo}")
            enviar_correo_bienvenida(self.correo, self.correo)
            self.succes = "Funcionario registrado con éxito. Ahora puede iniciar sesión con su correo institucional."
            self.error_de_registro = ""
            self.contraseña = ""
            self.confirmar_contraseña = ""
            self.show_password = False

>>>>>>> e2b305b84823c9d11bb994642ecae2240d4e6dcb
    def login(self):
        self.borrar_mensajes_de_estado()
        if not self.validacion_de_entradas(require_strong_pw=False):
            self.succes2 = ""
            return
        with rx.session() as session:
            user = session.exec(select(Usuario).where(Usuario.email == self.correo)).first()
            pw_ok = False
            try:
                pw_ok = confirmar_contraseña(self.contraseña, user.Contraseña) if user else False
            except Exception as e:
                print(f"Error comprobando contraseña: {e}")
            print(f"Login attempt for: {self.correo}, success: {pw_ok}")
            if not user or not pw_ok:
                self.error_de_contraseña = "Correo o contraseña incorrectos."
                self.succes2 = ""
                return
            if not user.is_active:
                self.error_de_contraseña = "La cuenta no está activa."
                self.succes2 = ""
                return
            self.id_usuario = user.id
<<<<<<< HEAD
            self.es_autentica = True
            self.succes2 = "Inicio de sesión exitoso."
=======
            self.rol_usuario = user.rol
            self.email_actual = user.email
            self.es_autentica = True
            self.cargar_solicitudes()
            self.succes2 = f"Inicio de sesión exitoso. Redirigiendo al {'dashboard de funcionario' if user.rol == 'funcionario' else 'dashboard de ciudadano'}..."
>>>>>>> e2b305b84823c9d11bb994642ecae2240d4e6dcb
            self.error_de_contraseña = ""
            self.contraseña = ""
            self.confirmar_contraseña = ""
            self.show_password = False
<<<<<<< HEAD
            return rx.redirect("/solicitudes")
=======
            if user.rol == "funcionario":
                return rx.redirect("/dashboard-funcionario")
            return rx.redirect("/dashboard")
>>>>>>> e2b305b84823c9d11bb994642ecae2240d4e6dcb
    def logout(self):
        "cerrar sesion de usuario"
        self.id_usuario = 0
        self.correo = ""
        self.contraseña = ""
        self.confirmar_contraseña = ""
<<<<<<< HEAD
=======
        self.rol_usuario = ""
        self.email_actual = ""
>>>>>>> e2b305b84823c9d11bb994642ecae2240d4e6dcb
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
        with rx.session() as session:
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

<<<<<<< HEAD
    def limpiar_formulario_solicitud(self):
=======
    def limpiar_formulario_solicitud(self, keep_message: bool = False):
>>>>>>> e2b305b84823c9d11bb994642ecae2240d4e6dcb
        self.tipo_solicitud = ""
        self.asunto = ""
        self.descripcion = ""
        self.ubicacion = ""
        self.documento = ""
<<<<<<< HEAD
        self.editar_solicitud_id = 0
        self.solicitud_mensaje = ""
=======
        self.documento_nombre = ""
        self.descripcion_len = 0
        self.editar_solicitud_id = 0
        self.acepta_politica_solicitud = False
        if not keep_message:
            self.solicitud_mensaje = ""
>>>>>>> e2b305b84823c9d11bb994642ecae2240d4e6dcb

    def crear_solicitud(self):
        self.solicitud_mensaje = ""
        if not self.tipo_solicitud or not self.asunto or not self.descripcion:
            self.solicitud_mensaje = "Completa los campos obligatorios antes de enviar."
            return
        # Verificar aceptación de política de tratamiento de datos
        if not self.acepta_politica_solicitud:
            self.solicitud_mensaje = "Debes aceptar la Política de Tratamiento de Datos Personales antes de enviar."
            return
<<<<<<< HEAD
        if self.editar_solicitud_id:
            for solicitud in self.solicitudes:
                if solicitud["id"] == self.editar_solicitud_id:
                    solicitud.update({
                        "tipo_solicitud": self.tipo_solicitud,
                        "asunto": self.asunto,
                        "descripcion": self.descripcion,
                        "ubicacion": self.ubicacion,
                        "documento": self.documento,
                        "estado": "Actualizada",
                    })
                    self.solicitud_mensaje = "Solicitud actualizada con éxito."
                    break
            self.editar_solicitud_id = 0
        else:
            nuevo_id = max([s["id"] for s in self.solicitudes], default=0) + 1
            # Procesar y guardar el archivo adjunto si viene en self.documento
            documento_guardado = ""
            if self.documento:
                try:
                    os.makedirs(UPLOAD_DIR, exist_ok=True)
                    # Caso: data URL (base64)
                    if isinstance(self.documento, str) and self.documento.startswith("data:"):
                        header, b64 = self.documento.split(",", 1)
                        mime = header.split(";")[0].split(":")[1] if ":" in header else ""
                        ext = mime.split("/")[-1] if "/" in mime else "bin"
                        saved_name = f"adjunto_{uuid.uuid4().hex}.{ext}"
                        path = os.path.join(UPLOAD_DIR, saved_name)
                        with open(path, "wb") as f:
                            f.write(base64.b64decode(b64))
                        documento_guardado = path
                    # Caso: objeto con 'content' y 'name'
                    elif isinstance(self.documento, dict) and "content" in self.documento:
                        content = self.documento.get("content")
                        name = self.documento.get("name", f"adjunto_{uuid.uuid4().hex}")
                        if isinstance(content, str) and content.startswith("data:"):
                            _, b64 = content.split(",", 1)
                            data = base64.b64decode(b64)
                        else:
                            data = base64.b64decode(content)
                        path = os.path.join(UPLOAD_DIR, name)
                        with open(path, "wb") as f:
                            f.write(data)
                        documento_guardado = path
                    else:
                        # Si viene solo el nombre o ruta, lo conservamos tal cual
                        documento_guardado = str(self.documento)
                except Exception as e:
                    self.solicitud_mensaje = f"Error guardando documento: {e}"
                    return

            self.solicitudes.append({
                "id": nuevo_id,
                "tipo_solicitud": self.tipo_solicitud,
                "asunto": self.asunto,
                "descripcion": self.descripcion,
                "ubicacion": self.ubicacion,
                "documento": documento_guardado,
                "estado": "Radicada",
                "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
            })
            self.solicitud_mensaje = "Solicitud registrada correctamente."
        self.limpiar_formulario_solicitud()

    def editar_solicitud(self, solicitud_id: int):
        solicitud = next((s for s in self.solicitudes if s["id"] == solicitud_id), None)
        if solicitud:
            self.editar_solicitud_id = solicitud_id
            self.tipo_solicitud = solicitud["tipo_solicitud"]
            self.asunto = solicitud["asunto"]
            self.descripcion = solicitud["descripcion"]
            self.ubicacion = solicitud["ubicacion"]
            self.documento = solicitud["documento"]
            self.solicitud_mensaje = "Editando solicitud. Actualiza los campos y guarda cambios."
=======

        documento_guardado = ""
        if self.documento:
            try:
                os.makedirs(UPLOAD_DIR, exist_ok=True)
                # Caso: data URL (base64)
                if isinstance(self.documento, str) and self.documento.startswith("data:"):
                    header, b64 = self.documento.split(",", 1)
                    mime = header.split(";")[0].split(":")[1] if ":" in header else ""
                    ext = mime.split("/")[-1] if "/" in mime else "bin"
                    saved_name = f"adjunto_{uuid.uuid4().hex}.{ext}"
                    path = os.path.join(UPLOAD_DIR, saved_name)
                    with open(path, "wb") as f:
                        f.write(base64.b64decode(b64))
                    documento_guardado = path
                # Caso: objeto con 'content' y 'name'
                elif isinstance(self.documento, dict) and "content" in self.documento:
                    content = self.documento.get("content")
                    name = self.documento.get("name", f"adjunto_{uuid.uuid4().hex}")
                    if isinstance(content, str) and content.startswith("data:"):
                        _, b64 = content.split(",", 1)
                        data = base64.b64decode(b64)
                    else:
                        data = base64.b64decode(content)
                    path = os.path.join(UPLOAD_DIR, name)
                    with open(path, "wb") as f:
                        f.write(data)
                    documento_guardado = path
                else:
                    # Si viene solo el nombre o ruta, lo conservamos tal cual
                    documento_guardado = str(self.documento)
            except Exception as e:
                self.solicitud_mensaje = f"Error guardando documento: {e}"
                return

        if self.editar_solicitud_id:
            try:
                with rx.session() as session:
                    solicitud_obj = session.get(Solicitud, self.editar_solicitud_id)
                    if not solicitud_obj:
                        self.solicitud_mensaje = "Solicitud no encontrada para editar."
                        return
                    solicitud_obj.tipo_solicitud = self.tipo_solicitud
                    solicitud_obj.asunto = self.asunto
                    solicitud_obj.descripcion = self.descripcion
                    solicitud_obj.ubicacion = self.ubicacion or None
                    if documento_guardado:
                        solicitud_obj.documento = documento_guardado
                        solicitud_obj.documento_basename = os.path.basename(documento_guardado)
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
                solicitud_obj = Solicitud(
                    radicado=f"PQRS-{datetime.now().year}-{uuid.uuid4().hex[:8]}",
                    tipo_solicitud=self.tipo_solicitud,
                    asunto=self.asunto,
                    descripcion=self.descripcion,
                    ubicacion=self.ubicacion or None,
                    documento=documento_guardado or None,
                    documento_basename=os.path.basename(documento_guardado) if documento_guardado else None,
                    estado="Radicada",
                    fecha=datetime.now(),
                    creado_por=self.email_actual or self.correo,
                    usuario_id=self.id_usuario if self.id_usuario else None,
                )
                session.add(solicitud_obj)
                session.commit()
            self.solicitud_mensaje = "Solicitud registrada correctamente."
            self.limpiar_formulario_solicitud(keep_message=True)
            self.cargar_solicitudes()
        except Exception as e:
            self.solicitud_mensaje = f"Error guardando solicitud: {e}"

    def signup_funcionario(self):
        self.borrar_mensajes_de_estado()
        if not self.validacion_de_entradas():
            return
        # Validaciones adicionales para registro de funcionario
        required_fields = ["nombres", "apellidos", "tipo_identificacion", "numero_identificacion"]
        for f in required_fields:
            if not getattr(self, f, ""):
                self.error_de_registro = "Completa los campos obligatorios de información personal."
                return
        if not self.acepta_politica_datos or not self.acepta_notificaciones:
            self.error_de_registro = "Debes aceptar la política de datos y recibir notificaciones para registrarte."
            return
        with rx.session() as session:
            existing_user = session.exec(select(Usuario).where(Usuario.email == self.correo)).first()
            if existing_user:
                self.error_de_registro = "El correo ya está registrado."
                return
            hashed = tiene_password(self.contraseña)
            nuevo_funcionario = Usuario(
                email=self.correo,
                Contraseña=hashed,
                rol="funcionario",
                is_active=True,
                Fecha_de_creacion=datetime.now(),
                tipo_identificacion=self.tipo_identificacion,
                numero_identificacion=self.numero_identificacion,
                nombres=self.nombres,
                apellidos=self.apellidos,
                genero=self.genero,
                direccion=self.direccion,
                telefono=self.telefono,
                departamento=self.departamento,
                ciudad=self.ciudad,
            )
            session.add(nuevo_funcionario)
            session.commit()
            print(f"Funcionario registrado: {self.correo}")
            enviar_correo_bienvenida(self.correo, self.correo)
            self.succes = "Funcionario registrado con éxito. Ahora puede iniciar sesión con su correo institucional."
            self.error_de_registro = ""
            self.contraseña = ""
            self.confirmar_contraseña = ""
            self.show_password = False

    def editar_solicitud(self, solicitud_id: int):
        try:
            with rx.session() as session:
                solicitud_obj = session.get(Solicitud, solicitud_id)
                if solicitud_obj:
                    self.editar_solicitud_id = solicitud_id
                    self.tipo_solicitud = solicitud_obj.tipo_solicitud
                    self.asunto = solicitud_obj.asunto
                    self.descripcion = solicitud_obj.descripcion
                    self.ubicacion = solicitud_obj.ubicacion or ""
                    self.documento = solicitud_obj.documento or ""
                    self.solicitud_mensaje = "Editando solicitud. Actualiza los campos y guarda cambios."
                else:
                    self.solicitud_mensaje = "Solicitud no encontrada."
        except Exception as e:
            self.solicitud_mensaje = f"Error cargando solicitud: {e}"
>>>>>>> e2b305b84823c9d11bb994642ecae2240d4e6dcb

    def eliminar_solicitud(self, solicitud_id: int):
        self.solicitudes = [s for s in self.solicitudes if s["id"] != solicitud_id]
        self.solicitud_mensaje = "Solicitud eliminada correctamente."

    """The app state."""


def auth_card(title: str, on_submit, show_confirm: bool = False) -> rx.Component:
<<<<<<< HEAD
    # 1. Definimos variables de color dinámicas
    bg_card = rx.color_mode_cond(light="#f5f5f5", dark="#1a202c")
    text_main = rx.color_mode_cond(light="black", dark="white")
    input_bg = rx.color_mode_cond(light="white", dark="#2d3748")
    input_text = rx.color_mode_cond(light="black", dark="white")
    placeholder_color = rx.color_mode_cond(light="#718096", dark="#a0aec0")

=======
    # Si show_confirm es True, renderizamos el formulario extendido para registro
    if show_confirm:
        return rx.card(
            rx.form(
                rx.vstack(
                    rx.heading(title, size="7", color="black", margin_bottom="1em"),
                    # Grid de 2 columnas para campos personales
                    rx.grid(
                        # Responsive grid: 3 columnas en pantallas anchas
                        rx.vstack(rx.text("Tipo de Identificación", font_weight="semibold"), rx.select(["Cédula", "Pasaporte", "Tarjeta de Identidad"], placeholder="Selecciona", value=State.tipo_identificacion, on_change=State.set_tipo_identificacion, bg="white", border="1px solid #cbd5e1", border_radius="md")),
                        rx.vstack(rx.text([rx.text("Número de Identificación "), rx.text("*", color="orange.500")]), rx.hstack(rx.input(placeholder="Número de Identificación", value=State.numero_identificacion, on_change=State.set_and_validate_numero_identificacion, bg="white", border="1px solid #cbd5e1", border_radius="md"), rx.cond(State.numero_identificacion_valid, rx.image(src="/check-green.svg", height="16px", ml="2"), rx.text("")))),
                        rx.vstack(rx.text([rx.text("Nombres "), rx.text("*", color="orange.500")]), rx.hstack(rx.input(placeholder="Nombres", value=State.nombres, on_change=State.set_and_validate_nombres, bg="white", border="1px solid #cbd5e1", border_radius="md"), rx.cond(State.nombres_valid, rx.image(src="/check-green.svg", height="16px", ml="2"), rx.text("")))),
                        rx.vstack(rx.text([rx.text("Apellidos "), rx.text("*", color="orange.500")]), rx.hstack(rx.input(placeholder="Apellidos", value=State.apellidos, on_change=State.set_and_validate_apellidos, bg="white", border="1px solid #cbd5e1", border_radius="md"), rx.cond(State.apellidos_valid, rx.image(src="/check-green.svg", height="16px", ml="2"), rx.text("")))),
                        rx.vstack(rx.text("Género"), rx.select(["Femenino", "Masculino", "Otro", "Prefiero no decirlo"], placeholder="Selecciona", value=State.genero, on_change=State.set_genero, bg="white", border="1px solid #cbd5e1", border_radius="md")),
                        rx.vstack(rx.text("Teléfono"), rx.hstack(rx.input(placeholder="Teléfono", value=State.telefono, on_change=State.set_and_validate_telefono, bg="white", border="1px solid #cbd5e1", border_radius="md"), rx.cond(State.telefono_valid, rx.image(src="/check-green.svg", height="16px", ml="2"), rx.text("")))),
                        rx.vstack(rx.text("Departamento"), rx.hstack(rx.input(placeholder="Departamento", value=State.departamento, on_change=State.set_and_validate_departamento, bg="white", border="1px solid #cbd5e1", border_radius="md"), rx.cond(State.departamento_valid, rx.image(src="/check-green.svg", height="16px", ml="2"), rx.text("")))),
                        rx.vstack(rx.text("Ciudad"), rx.hstack(rx.input(placeholder="Ciudad", value=State.ciudad, on_change=State.set_and_validate_ciudad, bg="white", border="1px solid #cbd5e1", border_radius="md"), rx.cond(State.ciudad_valid, rx.image(src="/check-green.svg", height="16px", ml="2"), rx.text("")))),
                        rx.box(
                            rx.vstack(
                                rx.text([rx.text("Dirección "), rx.text("*", color="orange.500")]),
                                rx.input(
                                    placeholder="Dirección",
                                    value=State.direccion,
                                    on_change=State.set_direccion,
                                    bg="white",
                                    border="1px solid #cbd5e1",
                                    border_radius="md",
                                ),
                            ),
                            grid_column="1 / -1",
                        ),
                        rx.box(
                            rx.hstack(
                                rx.input(
                                    placeholder="Correo electrónico",
                                    type="email",
                                    value=State.correo,
                                    on_change=State.set_correo,
                                    bg="white",
                                    border="1px solid #cbd5e1",
                                    border_radius="md",
                                ),
                                rx.button("Validar", on_click=State.validar_correo_accion, color_scheme="blue", size="2", ml="2"),
                                rx.cond(State.correo_validado, rx.image(src="/check-green.svg", height="16px", ml="2"), rx.text("")),
                            ),
                            grid_column="1 / -1",
                        ),
                        rx.box(
                            rx.vstack(
                                rx.text([rx.text("Contraseña "), rx.text("*", color="orange.500")]),
                                rx.hstack(
                                    rx.cond(
                                        State.show_password,
                                        rx.input(
                                            placeholder="Contraseña",
                                            type="text",
                                            value=State.contraseña,
                                            on_change=State.set_contraseña,
                                            bg="white",
                                            border="1px solid #cbd5e1",
                                            border_radius="md",
                                        ),
                                        rx.input(
                                            placeholder="Contraseña",
                                            type="password",
                                            value=State.contraseña,
                                            on_change=State.set_contraseña,
                                            bg="white",
                                            border="1px solid #cbd5e1",
                                            border_radius="md",
                                        ),
                                    ),
                                    rx.button(
                                        rx.cond(State.show_password, "🙈", "👁"),
                                        on_click=State.toggle_show_password,
                                        variant="ghost",
                                        size="2",
                                        ml="2",
                                    ),
                                ),
                            ),
                            grid_column="1 / -1",
                        ),
                        rx.box(
                            rx.cond(
                                show_confirm,
                                rx.vstack(
                                    rx.text([rx.text("Confirmar Contraseña "), rx.text("*", color="orange.500")]),
                                    rx.input(
                                        placeholder="Confirmar Contraseña",
                                        type="password",
                                        value=State.confirmar_contraseña,
                                        on_change=State.set_confirmar_contraseña,
                                        bg="white",
                                        border="1px solid #cbd5e1",
                                        border_radius="md",
                                    ),
                                ),
                            ),
                            grid_column="1 / -1",
                        ),
                        template_columns="repeat(3, 1fr)",
                        gap="4",
                    ),

                    # Sección legal y checkboxes
                    rx.vstack(
                        rx.checkbox("Acepto recibir notificaciones por correo", is_checked=State.acepta_notificaciones, on_change=State.set_acepta_notificaciones),
                        rx.checkbox(rx.link("He leído y acepto la Política de Protección de Datos", href="/politica-privacidad", color="blue"), is_checked=State.acepta_politica_datos, on_change=State.set_acepta_politica_datos),
                        spacing="3",
                        padding_top="4"
                    ),

                    rx.text(State.error_de_registro, color="red.500", font_size="sm", font_weight="bold"),
                    rx.text(State.succes, color="green.500", font_size="sm", font_weight="bold"),

                    rx.hstack(rx.button(title, type="submit", color_scheme="blue", size="4", width="220px"), rx.link("¿No tienes una cuenta? Registrate", href="/login", margin_left="4"), spacing="4", justify="start"),

                    spacing="4",
                    align_items="stretch"
                ),
                on_submit=on_submit
            ),
            p="8",
            max_width="1100px",
            box_shadow="2xl",
            border_radius="2xl",
            bg="white",
            _dark={"bg": "gray.800"}
        )

    # Si no es registro extendido, renderizamos la forma simple (login)
>>>>>>> e2b305b84823c9d11bb994642ecae2240d4e6dcb
    return rx.card(
        rx.vstack(
            rx.heading(
                title, 
                size="7", 
<<<<<<< HEAD
                color=text_main, 
                margin_bottom="1em"
            ),
            
            # --- INPUT DE CORREO ---
=======
                color="black", 
                margin_bottom="1em"
            ),
            
            # Input de Correo
>>>>>>> e2b305b84823c9d11bb994642ecae2240d4e6dcb
            rx.input(
                placeholder="Correo electrónico",
                type="email",
                value=State.correo,
                on_change=State.set_correo,
<<<<<<< HEAD
                bg=input_bg,
                color=input_text,
                border="1px solid #718096",
                _placeholder={"color": placeholder_color},
=======
                bg="white",
                color="black",
                border="1px solid #718096",
                _placeholder={
                    "color": "#718096",
                    "opacity": "1"
                },
>>>>>>> e2b305b84823c9d11bb994642ecae2240d4e6dcb
                width="100%",
                border_radius="md",
            ),

<<<<<<< HEAD
            # --- INPUT DE CONTRASEÑA CON OJO ---
            rx.hstack(
                rx.input(
                    type=rx.cond(State.show_password, "text", "password"),
                    placeholder="Contraseña",
                    value=State.contraseña, 
                    on_change=State.set_contraseña, 
                    bg=input_bg, 
                    color=input_text,
                    _placeholder={"color": placeholder_color}, 
                    width="100%",
                    border_radius="md"
                ),
                rx.button(
                    rx.cond(State.show_password, "🙈", "👁"),
                    on_click=State.toggle_show_password,
                    variant="ghost",
                ),
                width="100%",
            ),
            
            # --- CONFIRMAR CONTRASEÑA (SOLO REGISTRO) ---
            rx.cond(
                show_confirm,
                rx.vstack(
                    rx.input(
                        placeholder="Confirmar contraseña", 
                        type="password", 
                        value=State.confirmar_contraseña, 
                        on_change=State.set_confirmar_contraseña, 
                        bg=input_bg,
                        color=input_text,
                        border="1px solid #718096",
                        _placeholder={"color": placeholder_color},
                        width="100%", 
                        border_radius="md"
                    ),
                    # Validación visual inmediata
                    rx.cond(
                        (State.contraseña != State.confirmar_contraseña) & (State.confirmar_contraseña != ""),
                        rx.text("Las contraseñas no coinciden.", color="red.500", font_size="xs"),
                    ),
                    width="100%",
                )
            ),
            
            # --- MENSAJES DE ESTADO (IMPORTANTE) ---
            # Aquí es donde aparecerá "Este correo ya está registrado"
            rx.cond(
                State.error_de_registro != "",
                rx.text(State.error_de_registro, color="red.500", font_size="sm", font_weight="bold", text_align="center"),
            ),
            rx.cond(
                State.succes != "",
                rx.text(State.succes, color="green.500", font_size="sm", font_weight="bold", text_align="center"),
            ),
            
            # --- BOTÓN DE ACCIÓN ---
=======
            # Input de Contraseña
            rx.hstack(
                rx.cond(
                    State.show_password,
                    rx.input(
                        placeholder="Contraseña", 
                        type="text", 
                        value=State.contraseña, 
                        on_change=State.set_contraseña, 
                        bg="white",
                        color="black",
                        border="1px solid #718096",
                        _placeholder={"color": "#718096"},
                        width="100%", 
                        border_radius="md"
                    ),
                    rx.input(
                        placeholder="Contraseña", 
                        type="password", 
                        value=State.contraseña, 
                        on_change=State.set_contraseña, 
                        bg="white",
                        color="black",
                        border="1px solid #718096",
                        _placeholder={"color": "#718096"},
                        width="100%", 
                        border_radius="md"
                    )
                ),
                rx.button(
                    rx.cond(
                        State.show_password,
                        "🙈",
                        "👁"
                    ),
                    on_click=State.toggle_show_password,
                    variant="ghost",
                    size="2",
                    ml="2"
                ),
                width="100%",
                align="center"
            ),
            
            # Confirmar Contraseña (Condicional)
            rx.cond(
                show_confirm,
                rx.input(
                    placeholder="Confirmar contraseña", 
                    type="password", 
                    value=State.confirmar_contraseña, 
                    on_change=State.set_confirmar_contraseña, 
                    bg="white",
                    color="black",
                    border="1px solid #718096",
                    _placeholder={"color": "#718096"},
                    width="100%", 
                    border_radius="md"
                )
            ),
            # Aviso inmediato si las contraseñas no coinciden
            rx.cond(
                show_confirm & (State.contraseña != State.confirmar_contraseña) & ((State.contraseña != "") | (State.confirmar_contraseña != "")),
                rx.text("Las contraseñas no coinciden.", color="red.500", font_size="sm", font_weight="bold")
            ),
            
            # Mensajes de estado con colores legibles
            rx.text(State.error_de_registro, color="red.500", font_size="sm", font_weight="bold"),
            rx.text(State.succes, color="green.500", font_size="sm", font_weight="bold"),
            
>>>>>>> e2b305b84823c9d11bb994642ecae2240d4e6dcb
            rx.button(
                title, 
                on_click=on_submit, 
                width="100%", 
                color_scheme="blue", 
                size="4",
                margin_top="1em"
            ),
            
<<<<<<< HEAD
            # --- ENLACE DINÁMICO ---
            rx.link(
                rx.cond(show_confirm, "¿Ya tienes una cuenta? Inicia sesión", "¿No tienes cuenta? Regístrate"),
                href=rx.cond(show_confirm, "/login", "/registro"),
                margin_top="0.5em",
                color=rx.color_mode_cond(light="blue.600", dark="blue.300"),
                font_size="sm"
            ),
            
            spacing="4",
            align_items="center",
        ),
        p="12",
        max_width="640px",
        box_shadow="2xl",
        border_radius="2xl",
        bg=bg_card
=======
            rx.link("¿No tienes cuenta? Regístrate", href="/registro", margin_top="0.5em"),
            spacing="4",
            align_items="center",
        ),
        p="8",
        max_width="450px",
        box_shadow="2xl",
        border_radius="2xl",
        bg="white",
        _dark={"bg": "gray.800"}
>>>>>>> e2b305b84823c9d11bb994642ecae2240d4e6dcb
    )


def navbar() -> rx.Component:
<<<<<<< HEAD
    nav_bg = rx.color_mode_cond(light="white", dark="#0f172a")
    nav_text = rx.color_mode_cond(light="blue.700", dark="blue.200")
    nav_border = rx.color_mode_cond(light="#e6eef8", dark="#1e293b")

    return rx.hstack(
        rx.link("Inicio", href="/", font_weight="bold", color=nav_text, text_decoration="none"),
        rx.link("Nueva Solicitud", href="/solicitudes", font_weight="bold", color=nav_text, text_decoration="none"),
        rx.link("Registro de Ciudadano", href="/registro", font_weight="bold", color=nav_text, text_decoration="none"),
        rx.cond(
            State.es_autentica,
            rx.link("Cambiar Contraseña", href="/cambiar-contrasena", font_weight="bold", color=nav_text, text_decoration="none"),
            rx.fragment()
        ),
        rx.link("Iniciar Sesión", href="/login", font_weight="bold", color=nav_text, text_decoration="none"),
        spacing="6",
        padding="12px 20px",
        width="100%",
        justify="center",
        bg=nav_bg,
        box_shadow="sm",
        border_bottom=f"1px solid {nav_border}",
        position="sticky",
        top="0",
        z_index="10",
    )

def header() -> rx.Component:
    return rx.vstack(
        utility_bar(),
        navbar(),
        spacing="0",
        width="100%",
    )


def solicitudes_page() -> rx.Component:
    # Colores dinámicos para el fondo y textos
    bg_page = rx.color_mode_cond(light="#f8fafc", dark="#0f172a")
    text_main = rx.color_mode_cond(light="black", dark="white")
    card_bg = rx.color_mode_cond(light="white", dark="#1a202c")

    # TODO el contenido debe estar dentro de este rx.box
    return rx.box(
        utility_bar(), # Tu función con los colores dinámicos que definiste
        navbar(),
        rx.center(
            rx.cond(
                State.es_autentica,
                # Bloque 1: Usuario autenticado (El Formulario)
                rx.card(
                    rx.vstack(
                        rx.heading("Nueva Solicitud PQRS", size="8", color=text_main),
                        
                        rx.button("Enviar Solicitud", color_scheme="blue", width="100%"),
                    ),
                    bg=card_bg,
                    p="12",
                    border_radius="2xl",
                    max_width="640px",
                ),
                # Bloque 2: Acceso denegado (Sustituye al rx.container suelto)
                rx.card(
                    rx.vstack(
                        rx.heading("Acceso Denegado", size="8", color="red.500"),
                        rx.text("Necesitas iniciar sesión para crear una solicitud.", color=text_main),
                        rx.link(rx.button("Ir al Login", color_scheme="blue"), href="/login"),
                        spacing="4",
                        align_items="center"
                    ),
                    bg=card_bg,
                    p="10",
                    border_radius="2xl",
                )
            ),
            min_height="80vh",
            padding_y="4em",
        ),
        footer(),
        brand_footer(),
        bg=bg_page,
        min_height="100vh",
=======
    # Barra de navegación principal con utility bar encima
    return rx.vstack(
        utility_bar(),
        rx.hstack(
            rx.link("Inicio", href="/", font_weight="bold", color_scheme="blue", text_decoration="none", _hover={"color":"gray.100"}),
            rx.link("Nueva Solicitud", href="/solicitudes", font_weight="bold", color_scheme="blue", text_decoration="none", _hover={"color":"gray.100"}),
            rx.link("Registro de Ciudadano", href="/registro", font_weight="bold", color_scheme="blue", text_decoration="none", _hover={"color":"gray.100"}),
            rx.cond(
                State.es_autentica & (State.rol_usuario == "funcionario"),
                rx.link("Registrar Funcionario", href="/registro-funcionario", font_weight="bold", color_scheme="blue", text_decoration="none", _hover={"color":"gray.100"}),
                rx.text("")
            ),
            rx.cond(
                State.es_autentica & (State.rol_usuario == "funcionario"),
                rx.link("Dashboard Funcionario", href="/dashboard-funcionario", font_weight="bold", color_scheme="blue", text_decoration="none", _hover={"color":"gray.100"}),
                rx.text("")
            ),
            rx.cond(
                State.es_autentica & (State.rol_usuario != "funcionario"),
                rx.link("Mi Dashboard", href="/dashboard", font_weight="bold", color_scheme="blue", text_decoration="none", _hover={"color":"gray.100"}),
                rx.text("")
            ),
            rx.cond(State.es_autentica, rx.link("Cambiar Contraseña", href="/cambiar-contrasena", font_weight="bold", color_scheme="blue", text_decoration="none", _hover={"color":"gray.100"}), rx.text("")),
            rx.cond(
                State.es_autentica,
                rx.button("Cerrar Sesión", on_click=State.logout, color_scheme="red", size="4"),
                rx.link("Iniciar Sesión", href="/login", font_weight="bold", color_scheme="blue", text_decoration="none", _hover={"color":"gray.100"})
            ),
            spacing="6",
            padding="12px",
            width="100%",
            justify="center",
            bg="white",
            _dark={"bg": "gray.900", "borderColor": "gray.700"},
            box_shadow="md",
            border_bottom="1px solid #e6eef8",
            position="sticky",
            top="0",
            z_index="sticky"
        )
    )


def utility_bar() -> rx.Component:
    """Barra superior delgada con logo GOV.CO, accesibilidad y enlaces de sesión."""
    return rx.hstack(
        rx.image(src="/govco_logo.svg", alt="GOV.CO", height="28px"),
        rx.spacer(),
        rx.hstack(
            rx.link("Opciones de Accesibilidad", href="#", font_size="sm", color="white"),
            rx.text("|", color="white"),
            rx.link("Inicia sesión", href="/login", font_size="sm", color="white"),
            rx.text(" "),
            rx.link("Regístrate", href="/registro", font_size="sm", color="white"),
            spacing="3",
            align_items="center"
        ),
        padding_x="16px",
        padding_y="6px",
        bg="blue.600",
        border_bottom="1px solid rgba(0,0,0,0.08)",
        width="100%",
        align_items="center"
>>>>>>> e2b305b84823c9d11bb994642ecae2240d4e6dcb
    )


def index() -> rx.Component:
<<<<<<< HEAD
    bg_page = rx.color_mode_cond(light="#f8fafc", dark="#0f172a")
    hero_overlay = rx.color_mode_cond(
        light="linear-gradient(90deg, rgba(15,23,42,0.82) 0%, rgba(30,64,175,0.58) 45%, rgba(255,255,255,0.10) 100%)",
        dark="linear-gradient(90deg, rgba(2,6,23,0.88) 0%, rgba(30,41,59,0.72) 50%, rgba(15,23,42,0.35) 100%)"
    )
    text_white = "white"
    text_soft = rx.color_mode_cond(light="rgba(255,255,255,0.92)", dark="rgba(255,255,255,0.85)")
    card_bg = rx.color_mode_cond(light="rgba(255,255,255,0.96)", dark="rgba(15,23,42,0.82)")
    card_border = rx.color_mode_cond(light="1px solid rgba(255,255,255,0.45)", dark="1px solid rgba(255,255,255,0.12)")
    section_title = rx.color_mode_cond(light="#0f172a", dark="white")
    section_text = rx.color_mode_cond(light="#475569", dark="#cbd5e1")

    return rx.box(
    rx.color_mode.button(position="top-right"),
    header(),


        # HERO PRINCIPAL
        rx.box(
            rx.box(
                rx.container(
                    rx.hstack(
                        # Columna izquierda
                        rx.vstack(
                            rx.box(
                                rx.text(
                                    "Plataforma oficial de atención ciudadana",
                                    color="white",
                                    font_size="sm",
                                    font_weight="medium",
                                ),
                                bg="rgba(255,255,255,0.16)",
                                padding_x="12px",
                                padding_y="6px",
                                border_radius="full",
                            ),
                            rx.heading(
                                "Atención PQRS - Enlace 1755",
                                size="8",
                                color=text_white,
                                line_height="1.1",
                            ),
                            rx.text(
                                "Radica, consulta y gestiona tus Peticiones, Quejas, Reclamos y Sugerencias de forma clara, rápida y segura.",
                                color=text_soft,
                                font_size="lg",
                                max_width="620px",
                            ),
                            rx.hstack(
                                rx.link(
                                    rx.button(
                                        "Radicar PQRS",
                                        color_scheme="blue",
                                        size="4",
                                        width="200px",
                                    ),
                                    href="/solicitudes",
                                ),
                                rx.link(
                                    rx.button(
                                        "Consultar estado",
                                        variant="outline",
                                        size="4",
                                        width="200px",
                                        color="white",
                                        border="1px solid white",
                                        _hover={"bg": "rgba(255,255,255,0.08)"},
                                    ),
                                    href="/consultar-estado",
                                ),
                                spacing="4",
                                flex_wrap="wrap",
                            ),
                            spacing="5",
                            align_items="start",
                            width="100%",
                            max_width="700px",
                        ),

                        # Columna derecha
                        rx.card(
                            rx.vstack(
                                rx.heading("Accesos rápidos", size="5", color=section_title),
                                rx.link(rx.button("Registrarme", width="100%", color_scheme="blue"), href="/registro", width="100%"),
                                rx.link(rx.button("Iniciar sesión", width="100%", variant="soft"), href="/login", width="100%"),
                                rx.link(rx.button("Nueva solicitud", width="100%", variant="outline"), href="/solicitudes", width="100%"),
                                rx.text(
                                    "Disponible para ciudadanos que deseen registrar y hacer seguimiento a sus solicitudes.",
                                    color=section_text,
                                    font_size="sm",
                                ),
                                spacing="4",
                                align_items="stretch",
                                width="100%",
                            ),
                            bg=card_bg,
                            border=card_border,
                            box_shadow="2xl",
                            border_radius="2xl",
                            p="6",
                            width="100%",
                            max_width="340px",
                        ),
                        justify="between",
                        align_items="center",
                        spacing="8",
                        width="100%",
                        flex_wrap="wrap",
                    ),
                    max_width="1200px",
                    padding_x="6",
                    padding_y="16",
                ),
                style={
                    "backgroundImage": f"{hero_overlay}, url('/Gemini_Generated_Image_ouyornouyornouyo.png')",
                    "backgroundSize": "cover",
                    "backgroundPosition": "center",
                    "backgroundRepeat": "no-repeat",
                },
                width="100%",
                min_height="430px",
            ),
            width="100%",
        ),

        # ACCIONES RÁPIDAS
        rx.container(
            rx.vstack(
                rx.vstack(
                    rx.heading("¿Qué deseas hacer hoy?", size="7", color=section_title),
                    rx.text(
                        "Accede rápidamente a los servicios principales del sistema.",
                        color=section_text,
                        font_size="md",
                    ),
                    spacing="2",
                    align_items="center",
                ),

                rx.hstack(
                    quick_action_card(
                        "Radicar PQRS",
                        "Crea una nueva petición, queja, reclamo o sugerencia.",
                        "Ir al formulario",
                        "/solicitudes",
                        "blue",
                    ),
                    quick_action_card(
                        "Consultar estado",
                        "Revisa el avance y respuesta de tus solicitudes.",
                        "Consultar",
                        "/consultar-estado",
                        "cyan",
                    ),
                    quick_action_card(
                        "Registro ciudadano",
                        "Crea tu cuenta para gestionar trámites de forma segura.",
                        "Registrarme",
                        "/registro",
                        "green",
                    ),
                    quick_action_card(
                        "Iniciar sesión",
                        "Accede a tu cuenta y continúa tus gestiones.",
                        "Entrar",
                        "/login",
                        "gray",
                    ),
                    spacing="5",
                    justify="center",
                    width="100%",
                    flex_wrap="wrap",
                ),

                spacing="8",
                align_items="center",
                width="100%",
            ),
            max_width="1200px",
            padding_y="12",
            padding_x="6",
        ),

        # SECCIÓN INFORMATIVA
        rx.container(
            rx.vstack(
                rx.vstack(
                    rx.heading("Atención clara y transparente para la ciudadanía", size="7", color=section_title),
                    rx.text(
                        "Este portal facilita la recepción, gestión y seguimiento de solicitudes ciudadanas de manera organizada y accesible.",
                        color=section_text,
                        text_align="center",
                        max_width="850px",
                    ),
                    spacing="3",
                    align_items="center",
                ),

                rx.hstack(
                    info_card("Canal seguro", "Tus datos y solicitudes se gestionan en un entorno controlado."),
                    info_card("Trazabilidad", "Cada solicitud puede registrarse y consultarse con mayor claridad."),
                    info_card("Atención oportuna", "El sistema está pensado para mejorar tiempos y experiencia ciudadana."),
                    spacing="5",
                    width="100%",
                    justify="center",
                    flex_wrap="wrap",
                ),
                spacing="8",
                width="100%",
                align_items="center",
            ),
            max_width="1200px",
            padding_y="4",
            padding_x="6",
        ),

        # DEFINICIONES PQRS
        rx.container(
            rx.vstack(
                rx.heading("¿Qué significa PQRS?", size="7", color=section_title),
                rx.hstack(
                    pqrs_badge("Petición", "Solicitud respetuosa de información o actuación por parte de la entidad.", "#2563eb"),
                    pqrs_badge("Queja", "Manifestación de inconformidad por la conducta o atención recibida.", "#f59e0b"),
                    pqrs_badge("Reclamo", "Expresión de inconformidad por una prestación deficiente o incumplimiento.", "#ef4444"),
                    pqrs_badge("Sugerencia", "Propuesta o recomendación para mejorar la atención o el servicio.", "#10b981"),
                    spacing="5",
                    width="100%",
                    justify="center",
                    flex_wrap="wrap",
                ),
                spacing="6",
                align_items="center",
                width="100%",
            ),
            max_width="1200px",
            padding_y="12",
            padding_x="6",
        ),

        footer(),
        brand_footer(),
        bg=bg_page,
        width="100%",
        min_height="100vh",
    )


# Función auxiliar para no repetir código en las definiciones
def definition_item(label, desc):
    return rx.hstack(
        rx.text(label, font_weight="bold", color=rx.color_mode_cond(light="blue.800", dark="blue.300")), 
        rx.text(desc, color=rx.color_mode_cond(light="gray.700", dark="gray.400")),
        align_items="start"
=======
    return rx.vstack(
        rx.color_mode.button(position="top-right"),

        # Header y banner de ancho completo
        rx.fragment(
            navbar(), # Barra superior (ya definida para 100% ancho)
            # Hero principal usando imagen de assets (full-width banner)
            rx.box(
                # inner centered container so text aligns with main content
                rx.container(
                    rx.vstack(
                        rx.heading("Atención PQRS - Enlace 1755", size="7", color="blue.600", style={"textShadow": "none"}),
                        rx.text("Atención PQRS - Enlace 1755", color="blue.600", font_size="sm", style={"textShadow": "none"}),
                        spacing="2",
                        align_items="flex-start"
                    ),
                    max_width="900px",
                    padding_x="6",
                    padding_y="2",
                    margin_x="auto"
                ),
                width="100%",
                min_height="220px",
                style={
                    "backgroundImage": "linear-gradient(rgba(0,0,0,0.15), rgba(0,0,0,0.15)), url('/Gemini_Generated_Image_ouyornouyornouyo.png')",
                    "backgroundSize": "cover",
                    "backgroundPosition": "center",
                    "backgroundRepeat": "no-repeat",
                    "color": "inherit"
                },
                text_align="left"
            )
        ),

        # Contenido principal centrado y con ancho limitado para legibilidad
        rx.container(
            rx.center(
                rx.vstack(
                    rx.container(
                        rx.vstack(
                            rx.heading("La Universidad del Valle te da la bienvenida al portal de gestión Enlace 1755", size="5", color="black"),
                            rx.text(
                                "Para nosotros es fundamental brindarte una atención transparente, oportuna y adecuada. Antes de registrar tu solicitud, por favor ten en cuenta los siguientes conceptos para clasificarla correctamente:",
                                color="gray.700",
                                font_size="md",
                                text_align="left"
                            ),
                            # Lista de definiciones
                            rx.vstack(
                                rx.hstack(rx.text("Petición:", font_weight="bold"), rx.text("Es el derecho de solicitar información, documentos o consultar sobre las actuaciones de la entidad.")),
                                rx.hstack(rx.text("Queja:", font_weight="bold"), rx.text("Manifestación de inconformidad frente a la conducta o actuar irregular de un funcionario.")),
                                rx.hstack(rx.text("Reclamo:", font_weight="bold"), rx.text("Manifestación por prestación deficiente de un servicio o incumplimiento de una obligación.")),
                                rx.hstack(rx.text("Sugerencia:", font_weight="bold"), rx.text("Recomendación o idea para mejorar servicios, procesos o atención de la institución.")),
                                spacing="3",
                                align_items="start"
                            ),
                            spacing="6",
                            align_items="stretch"
                        ),
                        max_width="900px",
                        padding="6",
                        bg="white",
                        border_radius="md",
                        box_shadow="sm"
                    ),

                    # Botones de acción principales
                    rx.hstack(
                        rx.link(rx.button("Radicar PQRS", color_scheme="blue", size="4", width="220px"), href="/solicitudes"),
                        rx.link(rx.button("Consultar Solicitud", color_scheme="gray", size="4", width="220px"), href="/consultar-estado"),
                        spacing="5",
                        align_items="center",
                        justify="center"
                    ),

                    spacing="8",
                    align_items="center"
                ),
                min_height="64vh",
                width="100%",
                padding_top="10",
                padding_bottom="10",
                background="transparent"
            ),
            # container props: keep it visually centered but allow full-width header above
            padding_x="6"
        ),

        footer(),
        brand_footer()
>>>>>>> e2b305b84823c9d11bb994642ecae2240d4e6dcb
    )


def footer() -> rx.Component:
<<<<<<< HEAD
    # Definimos colores dinámicos para el texto y encabezados
    header_color = rx.color_mode_cond(light="black", dark="white")
    text_color = rx.color_mode_cond(light="gray.700", dark="gray.400")
    link_color = rx.color_mode_cond(light="blue.600", dark="blue.300")
    bg_color = rx.color_mode_cond(light="#f7fafc", dark="#111827")

=======
>>>>>>> e2b305b84823c9d11bb994642ecae2240d4e6dcb
    return rx.container(
        rx.hstack(
            # Columna 1: Información de la Entidad
            rx.vstack(
<<<<<<< HEAD
                rx.heading("Información de la Entidad", size="6", color=header_color), # Dinámico
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
            # Repite la lógica de color para las demás columnas (Servicio al Ciudadano, etc.)
            spacing="9",
            align_items="start",
=======
                rx.heading("Información de la Entidad", size="6", color="black"),
                rx.text("Sede Principal: Calle 10 # 5-20, Cali, Valle del Cauca"),
                rx.text("Código Postal: 760001"),
                rx.text("PBX: (+57) 602 XXX XXXX"),
                rx.link("Correo institucional: atencionalciudadano@empresa.gov.co", href="mailto:atencionalciudadano@empresa.gov.co"),
                rx.link("Sitio web principal: www.empresa.gov.co", href="http://www.empresa.gov.co", target="_blank"),
                rx.text("Horario de atención presencial: Lunes a Viernes, 7:30 a.m. - 12:00 p.m. y 2:00 p.m. - 5:30 p.m.")
            ),

            # Columna 2: Servicio al Ciudadano
            rx.vstack(
                rx.heading("Servicio al Ciudadano", size="6", color="black"),
                rx.link("Radicar solicitud PQRS (HU4)", href="/solicitudes"),
                rx.link("Consultar estado de solicitud (HU11)", href="/consultar-estado"),
                rx.link("Preguntas Frecuentes (FAQ)", href="/faq"),
                rx.link("Tiempos de respuesta (Ley 1755 de 2015)", href="/tiempos-respuesta"),
                rx.link("Notificaciones por aviso y judiciales", href="/notificaciones"),
                rx.link("Política de privacidad y protección de datos", href="/politica-privacidad"),
                rx.link("Manual de usuario (Enlace 1755)", href="/manual-1755")
            ),

            # Columna 3: Contacto Directo y Redes
            rx.vstack(
                rx.heading("Contacto Directo y Redes", size="6", color="black"),
                rx.text("Recepción de correspondencia física: Lunes a viernes, 8:00 a.m. a 4:00 p.m."),
                rx.text("Línea gratuita nacional: 01 8000 91XXXX"),
                rx.hstack(
                    rx.link("Facebook", href="https://facebook.com", target="_blank"),
                    rx.link("X/Twitter", href="https://twitter.com", target="_blank"),
                    rx.link("YouTube", href="https://youtube.com", target="_blank"),
                    rx.link("LinkedIn", href="https://linkedin.com", target="_blank"),
                    spacing="4"
                ),
                rx.text("Sistema gestionado por: Enlace 1755 (Versión 1.0)", font_size="sm")
            ),

                        spacing="9",
                        align_items="start"
>>>>>>> e2b305b84823c9d11bb994642ecae2240d4e6dcb
        ),
        width="100%",
        padding_top="24px",
        padding_bottom="24px",
<<<<<<< HEAD
        bg=bg_color, # Fondo dinámico
        border_top=rx.color_mode_cond(light="1px solid #e2e8f0", dark="1px solid #2d3748"),
        justify="center",
    )
def quick_action_card(title: str, desc: str, button_text: str, href: str, accent: str = "blue") -> rx.Component:
    card_bg = rx.color_mode_cond(light="white", dark="#1e293b")
    text_main = rx.color_mode_cond(light="#0f172a", dark="white")
    text_sec = rx.color_mode_cond(light="#475569", dark="#cbd5e1")
    border_color = rx.color_mode_cond(light="#e2e8f0", dark="#334155")

    return rx.card(
        rx.vstack(
            rx.heading(title, size="5", color=text_main),
            rx.text(desc, color=text_sec, font_size="sm"),
            rx.link(
                rx.button(button_text, color_scheme=accent, width="100%"),
                href=href,
                width="100%",
            ),
            spacing="4",
            align_items="start",
            width="100%",
        ),
        bg=card_bg,
        border=f"1px solid {border_color}",
        box_shadow="lg",
        border_radius="xl",
        p="6",
        width="100%",
        max_width="260px",
    )


def info_card(title: str, desc: str) -> rx.Component:
    bg = rx.color_mode_cond(light="white", dark="#1e293b")
    text_main = rx.color_mode_cond(light="#0f172a", dark="white")
    text_sec = rx.color_mode_cond(light="#475569", dark="#cbd5e1")
    border_color = rx.color_mode_cond(light="#e2e8f0", dark="#334155")

    return rx.card(
        rx.vstack(
            rx.text(title, font_weight="bold", color=text_main, font_size="md"),
            rx.text(desc, color=text_sec, font_size="sm"),
            spacing="2",
            align_items="start",
        ),
        bg=bg,
        border=f"1px solid {border_color}",
        border_radius="lg",
        p="5",
        width="100%",
        box_shadow="sm",
    )


def pqrs_badge(title: str, desc: str, color: str) -> rx.Component:
    card_bg = rx.color_mode_cond(light="white", dark="#1e293b")
    text_main = rx.color_mode_cond(light="#0f172a", dark="white")
    text_sec = rx.color_mode_cond(light="#475569", dark="#cbd5e1")
    border_color = rx.color_mode_cond(light="#e2e8f0", dark="#334155")

    return rx.card(
        rx.vstack(
            rx.box(
                rx.text(title, color="white", font_weight="bold", font_size="sm"),
                bg=color,
                padding_x="12px",
                padding_y="6px",
                border_radius="full",
            ),
            rx.text(desc, color=text_sec, font_size="sm"),
            spacing="3",
            align_items="start",
        ),
        bg=card_bg,
        border=f"1px solid {border_color}",
        border_radius="xl",
        p="5",
        width="100%",
        box_shadow="sm",
=======
        bg="#f7fafc",
        _dark={"bg": "gray.900", "borderColor": "gray.700"},
        border_top="1px solid #e2e8f0",
        justify="center"
>>>>>>> e2b305b84823c9d11bb994642ecae2240d4e6dcb
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
<<<<<<< HEAD
        bg="#ffffff",
=======
        bg="white",
        _dark={"bg": "gray.900", "borderColor": "gray.700"},
>>>>>>> e2b305b84823c9d11bb994642ecae2240d4e6dcb
        border_top="1px solid #e2e8f0"
    )

def registro_page() -> rx.Component:
    return rx.container(
<<<<<<< HEAD
        header(),
        rx.center(
            rx.box(
                auth_card("Registrarme", State.signup, show_confirm=True),
                width="100%",
                max_width="450px",  # Un poco más ancho para igualar diseño
                # Añadimos margen arriba y abajo para separarlo de los bordes
                margin_top="5em", 
                margin_bottom="5em",
            ),
            # Aumentamos esto para que el área de centrado sea más amplia
            min_height="80vh", 
        ),
        footer(), # Asegúrate de incluir el footer si lo tienes
    )

=======
        navbar(),
        rx.center(
            # Llamamos a auth_card con la función de signup y pidiendo confirmación
            auth_card("Registrarme como Ciudadano", State.signup, show_confirm=True),
            min_height="8vh"
        )
    )


def registro_funcionario_page() -> rx.Component:
    return rx.cond(
        State.es_autentica & (State.rol_usuario == "funcionario"),
        rx.container(
            navbar(),
            rx.center(
                auth_card("Registrar Funcionario", State.signup_funcionario, show_confirm=True),
                min_height="8vh"
            )
        ),
        rx.container(
            navbar(),
            rx.center(
                rx.vstack(
                    rx.heading("Acceso Denegado", size="8", color="red.500"),
                    rx.text("Solo los funcionarios autenticados pueden registrar nuevos funcionarios."),
                    rx.link(rx.button("Ir al Login", color_scheme="blue"), href="/login"),
                    spacing="4",
                    align_items="center"
                ),
                min_height="84vh"
            )
        )
    )


>>>>>>> e2b305b84823c9d11bb994642ecae2240d4e6dcb
def change_password_page() -> rx.Component:
    return rx.container(
        navbar(),
        rx.center(
            rx.card(
                rx.vstack(
                    rx.heading("Cambiar Contraseña", size="7", color="black"),
                    rx.input(placeholder="Contraseña actual", type="password", value=State.current_password, on_change=State.set_current_password, width="100%"),
                    rx.input(placeholder="Nueva contraseña", type="password", value=State.new_password, on_change=State.set_new_password, width="100%"),
                    rx.input(placeholder="Confirmar nueva contraseña", type="password", value=State.confirm_new_password, on_change=State.set_confirm_new_password, width="100%"),
                    rx.button("Cambiar contraseña", on_click=State.change_password, color_scheme="blue", width="100%"),
                    rx.text(State.change_pw_message, color="green.500", font_size="sm")
                ),
                p="8",
<<<<<<< HEAD
                max_width="420px"
=======
                max_width="560px"
>>>>>>> e2b305b84823c9d11bb994642ecae2240d4e6dcb
            ),
            min_height="84vh"
        )
    )

def login_page() -> rx.Component:
    return rx.container(
<<<<<<< HEAD
        header(),
        rx.center(
            rx.vstack(
                rx.box(
                    auth_card("Iniciar Sesión", State.login, show_confirm=False),
                    width="100%",
                    max_width="620px",  # <-- controla el ancho aquí
                ),
=======
        navbar(),
        rx.center(
            rx.vstack(
                # Llamamos a auth_card. Nota: en tu código llamaste 'usuario' a la función de login
                auth_card("Iniciar Sesión", State.login,  show_confirm=False),
                # Enlace para ir a cambiar contraseña (visible siempre debajo del login)
>>>>>>> e2b305b84823c9d11bb994642ecae2240d4e6dcb
                rx.link("¿Olvidaste tu contraseña?", href="/cambiar-contrasena", color_scheme="blue"),
                spacing="4",
                align_items="center"
            ),
            min_height="85vh"
        )
    )

<<<<<<< HEAD
def dashboard() -> rx.Component:
    return rx.cond(
        State.es_autentica,
=======
def politica_privacidad_page() -> rx.Component:
    return rx.container(
        navbar(),
        rx.center(
            rx.box(
                rx.vstack(
                    rx.heading("Política de Privacidad y Protección de Datos", size="6", color="black"),
                    rx.text(
                        "En esta plataforma tratamos tus datos con responsabilidad, transparencia y seguridad. "
                        "Tu información personal se usa únicamente para gestionar solicitudes PQRS y mejorar el servicio.",
                        color="gray.700",
                        font_size="md"
                    ),
                    rx.text(
                        "Al enviar una solicitud aceptas la Política de Tratamiento de Datos Personales y los términos de uso de la plataforma.",
                        color="gray.700",
                        font_size="md"
                    ),
                    rx.heading("Datos recolectados", size="7", color="black"),
                    rx.text("Correo electrónico, identificación, nombre, apellidos, teléfono y datos de ubicación para poder gestionar la solicitud."),
                    rx.heading("Finalidad", size="7", color="black"),
                    rx.text("Usar tus datos para contactar al ciudadano, radicar la solicitud en el sistema y generar trazabilidad de atención."),
                    rx.heading("Derechos", size="7", color="black"),
                    rx.text("Puedes solicitar corrección o eliminación de tus datos conforme a la normativa vigente de protección de datos personales."),
                    rx.link("Volver al inicio", href="/", color_scheme="blue", font_weight="bold"),
                    spacing="4",
                    align_items="flex-start"
                ),
                p="8",
                max_width="840px",
                border_radius="2xl",
                bg="white",
                _dark={"bg": "gray.800"}
            ),
            min_height="84vh"
        )
    )

def dashboard() -> rx.Component:
    return rx.cond(
        State.es_autentica & (State.rol_usuario == "ciudadano"),
>>>>>>> e2b305b84823c9d11bb994642ecae2240d4e6dcb
        rx.container(
            navbar(),
            rx.center(
                rx.card(
                    rx.vstack(
                        rx.heading("Panel de Ciudadano", size="8", color="black"),
                        rx.text("¡Bienvenido! Aquí podrás gestionar tus Peticiones, Quejas, Reclamos y Sugerencias.", color="gray.600"),
                        rx.text("Funcionalidad completa próximamente en próximos sprints.", color="gray.500"),
                        rx.button("Cerrar Sesión", on_click=State.logout, color_scheme="red", width="100%"),
                        spacing="4",
                        align_items="center"
                    ),
                    max_width="640px",
                    p="10",
                    box_shadow="2xl",
                    border_radius="2xl"
                ),
                min_height="84vh"
            )
        ),
        rx.container(
            navbar(),
            rx.center(
                rx.vstack(
                    rx.heading("Acceso Denegado", size="8", color="red.500"),
<<<<<<< HEAD
                    rx.text("Necesitas iniciar sesión para acceder a esta página."),
=======
                    rx.text("Esta página es solo para ciudadanos. Si eres funcionario, ve a tu dashboard.", color="gray.600"),
                    rx.link(rx.button("Ir al Dashboard Funcionario", color_scheme="blue"), href="/dashboard-funcionario"),
                    rx.link(rx.button("Ir al Login", color_scheme="gray"), href="/login"),
                    spacing="4",
                    align_items="center"
                ),
                min_height="84vh"
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
                    rx.heading("Panel de Funcionario", size="8", color="black"),
                    rx.text("Bienvenido, funcionario. Esta es tu página principal donde puedes revisar todas las peticiones.", color="gray.600"),
                    rx.text("Usa el menú superior para navegar: 'Nueva Solicitud' para crear peticiones, 'Registrar Funcionario' para añadir nuevos funcionarios.", color="gray.500"),
                    rx.box(
                        rx.vstack(
                            rx.cond(
                                State.solicitudes,
                                rx.vstack(
                                    rx.foreach(
                                        State.solicitudes,
                                        lambda solicitud: rx.box(
                                            rx.vstack(
                                                rx.heading(f"Radicado: {solicitud['radicado']} - {solicitud['tipo_solicitud']}", size="6", color="black"),
                                                rx.text(f"Asunto: {solicitud['asunto']}", color="gray.700"),
                                                rx.text(f"Descripción: {solicitud['descripcion']}", color="gray.700"),
                                                rx.text(f"Creado por: {solicitud.get('creado_por', 'Desconocido')}", color="gray.600"),
                                                rx.text(
                                                    "Ubicación: ",
                                                    rx.cond(
                                                        solicitud["ubicacion"],
                                                        solicitud["ubicacion"],
                                                        "No especificada"
                                                    ),
                                                    color="gray.600"
                                                ),
                                                rx.text(f"Estado: {solicitud['estado']}", color="gray.600"),
                                                rx.text(f"Fecha: {solicitud['fecha']}", color="gray.600"),
                                                rx.cond(
                                                    solicitud["documento"],
                                                    rx.hstack(
                                                        rx.text("Documento: ", color="gray.600"),
                                                        rx.link(
                                                            solicitud["documento_basename"],
                                                            href=f"/uploads/{solicitud['documento_basename']}",
                                                            color="blue.600",
                                                            target="_blank"
                                                        )
                                                    ),
                                                    rx.text("Documento: No adjunto", color="gray.600")
                                                ),
                                                spacing="2",
                                                align_items="start"
                                            ),
                                            p="4",
                                            border="1px solid #e2e8f0",
                                            border_radius="lg",
                                            bg="white",
                                            _dark={"bg": "gray.800", "borderColor": "gray.700"},
                                            width="100%"
                                        )
                                    ),
                                    spacing="4"
                                ),
                                rx.text("No hay solicitudes registradas aún.", color="gray.600", font_size="md")
                            ),
                            spacing="4"
                        ),
                        width="100%"
                    ),
                    rx.button("Cerrar Sesión", on_click=State.logout, color_scheme="red", width="100%"),
                    spacing="6",
                    align_items="stretch"
                ),
                min_height="84vh"
            )
        ),
        rx.container(
            navbar(),
            rx.center(
                rx.vstack(
                    rx.heading("Acceso Denegado", size="8", color="red.500"),
                    rx.text("Solo los funcionarios autenticados pueden acceder a esta página."),
>>>>>>> e2b305b84823c9d11bb994642ecae2240d4e6dcb
                    rx.link(rx.button("Ir al Login", color_scheme="blue"), href="/login"),
                    spacing="4",
                    align_items="center"
                ),
                min_height="84vh"
            )
        )
    )


<<<<<<< HEAD
# --- REEMPLAZA TUS FUNCIONES DE PÁGINA CON ESTAS ---

def utility_bar() -> rx.Component:
    """Barra superior delgada con logo GOV.CO, accesibilidad y enlaces de sesión."""
    
    # Definimos el color del texto: azul oscuro en modo claro, blanco en modo oscuro
    text_color = rx.color_mode_cond(light="blue.800", dark="white")
    
    # Definimos el color de fondo: gris muy claro en modo claro, azul en modo oscuro
    bar_bg = rx.color_mode_cond(light="gray.100", dark="blue.600")

    return rx.hstack(
        rx.image(src="/govco_logo.svg", alt="GOV.CO", height="28px"),
        rx.spacer(),
        rx.hstack(
            rx.link(
                "Opciones de Accesibilidad", 
                href="#", 
                font_size="sm", 
                color=text_color
            ),
            rx.text("|", color=text_color),
            rx.link(
                "Inicia sesión", 
                href="/login", 
                font_size="sm", 
                color=text_color
            ),
            rx.text(" ", color=text_color),
            rx.link(
                "Regístrate", 
                href="/registro", 
                font_size="sm", 
                color=text_color
            ),
            spacing="3",
            align_items="center"
        ),
        padding_x="16px",
        padding_y="6px",
        bg=bar_bg,
        border_bottom="1px solid rgba(0,0,0,0.08)",
        width="100%",
        align_items="center"
    )

def footer() -> rx.Component:
    # Definimos los colores dinámicos
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

def solicitudes_page() -> rx.Component:
    # 1. Definimos variables de color dinámicas
    text_main = rx.color_mode_cond(light="black", dark="white")
    text_sec = rx.color_mode_cond(light="gray.600", dark="gray.400")
    input_bg = rx.color_mode_cond(light="white", dark="#2d3748")
    card_bg = rx.color_mode_cond(light="white", dark="#1a202c")
    # Color para la zona de adjuntar archivos
    dropzone_bg = rx.color_mode_cond(light="#f8fbff", dark="rgba(255,255,255,0.05)")
    dropzone_border = rx.color_mode_cond(light="#cfe7ff", dark="#4a5568")

    return rx.box(
        rx.cond(
            State.es_autentica,
            rx.vstack(
                header(),
                rx.center(
                    rx.card(
                        rx.vstack(
                            rx.heading("Nueva Solicitud PQRS", size="8", color=text_main),
                            rx.text("Completa el formulario para radicar tu Petición, Queja, Reclamo o Sugerencia.", color=text_sec),
                            
                            rx.form(
                                rx.vstack(
                                    # Tipo de solicitud
                                    rx.vstack(
                                        rx.hstack(
                                            rx.text("Tipo de Solicitud ", font_weight="semibold", color=text_main),
                                            rx.text("*", color="orange.500")
                                        ),
                                        rx.select(
                                            ["Petición", "Queja", "Reclamo", "Sugerencia"], 
                                            placeholder="Selecciona el tipo", 
                                            value=State.tipo_solicitud, 
                                            on_change=State.set_tipo_solicitud, 
                                            required=True,
                                            bg=input_bg,
                                            color=text_main
                                        ),
                                        align_items="start", width="100%"
                                    ),

                                    # Asunto
                                    rx.vstack(
                                        rx.hstack(
                                            rx.text("Asunto ", font_weight="semibold", color=text_main),
                                            rx.text("*", color="orange.500")
                                        ),
                                        rx.input(
                                            placeholder="Asunto", 
                                            value=State.asunto, 
                                            on_change=State.set_asunto, 
                                            required=True, 
                                            bg=input_bg, 
                                            color=text_main,
                                            border=f"1px solid {rx.color_mode_cond(light='#cbd5e1', dark='#4a5568')}"
                                        ),
                                        align_items="start", width="100%"
                                    ),

                                    # Descripción
                                    rx.vstack(
                                        rx.hstack(
                                            rx.text("Descripción detallada ", font_weight="semibold", color=text_main),
                                            rx.text("*", color="orange.500")
                                        ),
                                        rx.text_area(
                                            placeholder="Detalles de tu solicitud...", 
                                            value=State.descripcion, 
                                            on_change=State.set_descripcion, 
                                            required=True, 
                                            rows="4",
                                            bg=input_bg,
                                            color=text_main,
                                            style={"border": f"1px solid {rx.color_mode_cond(light='#cbd5e1', dark='#4a5568')}", "borderRadius": "8px"}
                                        ),
                                        rx.hstack(
                                            rx.spacer(), 
                                            rx.text(State.descripcion_len, font_size="sm", color=text_sec), 
                                            rx.text(" / 1000 caracteres", font_size="sm", color=text_sec)
                                        ),
                                        align_items="stretch", width="100%"
                                    ),

                                    # Archivo adjunto adaptable
                                    rx.vstack(
                                        rx.text("Documento adjunto (opcional)", font_weight="semibold", color=text_main),
                                        rx.box(
                                            rx.hstack(
                                                rx.image(src="/clip-icon.svg", alt="Adjuntar", height="20px"),
                                                rx.text("Arrastra archivos aquí o haz clic", color=text_sec),
                                                rx.spacer(),
                                                rx.text(State.documento_nombre, font_size="sm", color=text_sec)
                                            ),
                                            rx.input(type="file", on_change=State.set_documento, style={"position": "absolute", "inset": "0", "width": "100%", "height": "100%", "opacity": 0, "cursor": "pointer"}),
                                            position="relative",
                                            padding="4",
                                            border=f"2px dashed {dropzone_border}",
                                            border_radius="8px",
                                            bg=dropzone_bg,
                                            width="100%",
                                        ),
                                        align_items="start", width="100%"
                                    ),

                                    rx.checkbox(
                                        rx.text("Acepto la Política de Datos", color=text_main), 
                                        is_checked=State.acepta_politica_solicitud, 
                                        on_change=State.set_acepta_politica_solicitud
                                    ),
                                    rx.button("Enviar Solicitud", on_click=State.crear_solicitud, color_scheme="blue", width="100%"),
                                    
                                    spacing="4",
                                    align_items="stretch"
                                ),
                            ),
                            spacing="4",
                            align_items="center"
                        ),
                        bg=card_bg,
                        max_width="640px",
                        p="10",
                        box_shadow="2xl",
                        border_radius="2xl"
                    ),
                    padding_y="4em",
                    min_height="85vh"
                ),
                spacing="0"
            ),
            # Caso Acceso Denegado
            rx.vstack(
                navbar(),
                rx.center(
                    rx.vstack(
                        rx.heading("Acceso Denegado", size="8", color="red.500"),
                        rx.text("Necesitas iniciar sesión para crear una solicitud.", color=text_main),
                        rx.link(rx.button("Ir al Login", color_scheme="blue"), href="/login"),
                        spacing="4",
                        align_items="center"
                    ),
                    min_height="85vh"
                ),
                spacing="0"
            )
        ),
        bg=rx.color_mode_cond(light="#f8fafc", dark="#0f172a"),
        min_height="100vh"
=======
def solicitudes_page() -> rx.Component:
    return rx.cond(
        State.es_autentica,
        rx.container(
            navbar(),
            rx.center(
                rx.card(
                    rx.vstack(
                        rx.heading("Nueva Solicitud PQRS", size="8", color="black"),
                        rx.text("Completa el formulario para radicar tu Petición, Queja, Reclamo o Sugerencia.", color="gray.600"),
                        rx.form(
                            rx.vstack(
                                # Tipo de solicitud (label + select)
                                rx.vstack(
                                    rx.text([rx.text("Tipo de Solicitud ", font_weight="semibold"), rx.text("*", color="orange.500")], align_items="flex-start"),
                                    rx.select(["Petición", "Queja", "Reclamo", "Sugerencia"], placeholder="Selecciona el tipo de solicitud", value=State.tipo_solicitud, on_change=State.set_tipo_solicitud, required=True),
                                ),

                                # Asunto (label + input)
                                rx.vstack(
                                    rx.text([rx.text("Asunto ", font_weight="semibold"), rx.text("*", color="orange.500")]),
                                    rx.input(placeholder="Asunto", value=State.asunto, on_change=State.set_asunto, required=True, bg="white", border="1px solid #cbd5e1", border_radius="md"),
                                ),

                                # Descripción detallada (label + textarea + contador)
                                rx.vstack(
                                    rx.text([rx.text("Descripción detallada ", font_weight="semibold"), rx.text("*", color="orange.500")]),
                                    rx.text_area(placeholder="Escribe aquí los detalles de tu solicitud...", value=State.descripcion, on_change=State.set_descripcion, required=True, rows="4", max_length=1000, style={"resize": "vertical", "minHeight": "120px", "border": "1px solid #cbd5e1", "borderRadius": "8px", "padding": "8px"}, _dark={"bg": "gray.700", "color": "white", "borderColor": "gray.600"}),
                                    rx.hstack(rx.spacer(), rx.text(State.descripcion_len, font_size="sm", color="gray.600"), rx.text(" / 1000 caracteres", font_size="sm", color="gray.600")),
                                ),
                                rx.input(
                                    placeholder="Ubicación (opcional)",
                                    value=State.ubicacion,
                                    on_change=State.set_ubicacion
                                ),

                                # Archivo adjunto: zona arrastrar y soltar moderna
                                rx.vstack(
                                    rx.text("Documento adjunto (opcional)", font_weight="semibold"),
                                    rx.box(
                                        rx.hstack(
                                            rx.image(src="/clip-icon.svg", alt="Adjuntar", height="20px"),
                                            rx.text("Arrastra y suelta tus archivos aquí o haz clic para explorar", color="gray.600"),
                                            rx.spacer(),
                                            rx.text(State.documento_nombre, font_size="sm", color="gray.500")
                                        ),
                                        rx.input(type="file", accept="*/*", on_change=State.set_documento, style={"position": "absolute", "inset": "0", "width": "100%", "height": "100%", "opacity": 0, "cursor": "pointer"}),
                                        position="relative",
                                        padding="4",
                                        border="2px dashed #cfe7ff",
                                        border_radius="8px",
                                        bg="#f8fbff",
                                        _dark={"bg": "gray.700", "borderColor": "gray.600"},
                                        width="100%",
                                    )
                                ),
                                rx.checkbox(rx.link("He leído y acepto la Política de Tratamiento de Datos Personales", href="/politica-privacidad", color="blue"), is_checked=State.acepta_politica_solicitud, on_change=State.set_acepta_politica_solicitud),
                                rx.button("Enviar Solicitud", on_click=State.crear_solicitud, color_scheme="blue", width="100%", is_disabled=~State.acepta_politica_solicitud),
                                rx.cond(
                                    State.solicitud_mensaje,
                                    rx.text(State.solicitud_mensaje, color=rx.cond(State.solicitud_mensaje.contains("éxito"), "green.500", "red.500"))
                                ),
                                rx.cond(
                                    State.solicitudes,
                                    rx.vstack(
                                        rx.heading("Solicitudes registradas", size="6", color="black"),

                                        rx.foreach(
                                            State.solicitudes,
                                            lambda solicitud: rx.box(
                                                rx.vstack(
                                                    rx.text(f"#{solicitud['id']} - {solicitud['tipo_solicitud']}", font_weight="bold"),
                                                    rx.text(f"Asunto: {solicitud['asunto']}"),
                                                    rx.text(f"Descripción: {solicitud['descripcion']}"),
                                                    rx.text(f"Creado por: {solicitud.get('creado_por', 'Desconocido')}"),
                                                    rx.text(
                                                        "Ubicación: ",
                                                        rx.cond(
                                                            solicitud["ubicacion"],
                                                            solicitud["ubicacion"],
                                                            "No especificada"
                                                        )
                                                    ),
                                                    rx.text(f"Estado: {solicitud['estado']}"),
                                                    rx.text(f"Fecha: {solicitud['fecha']}"),
                                                ),
                                                p="4",
                                                border="1px solid #e2e8f0",
                                                border_radius="lg",
                                                bg="white",
                                                _dark={"bg": "gray.800", "borderColor": "gray.700"},
                                                width="100%"
                                            )
                                        ),

                                        spacing="3",
                                        width="100%"
                                    )
                                ),
                                spacing="4",
                                align_items="stretch"
                            ),
                            on_submit=State.crear_solicitud
                        ),
                        spacing="4",
                        align_items="center"
                    ),
                    max_width="640px",
                    p="10",
                    box_shadow="2xl",
                    border_radius="2xl"
                ),
                min_height="84vh"
            )
        ),
        rx.container(
            navbar(),
            rx.center(
                rx.vstack(
                    rx.heading("Acceso Denegado", size="8", color="red.500"),
                    rx.text("Necesitas iniciar sesión para crear una solicitud."),
                    rx.link(rx.button("Ir al Login", color_scheme="blue"), href="/login"),
                    spacing="4",
                    align_items="center"
                ),
                min_height="84vh"
            )
        )
>>>>>>> e2b305b84823c9d11bb994642ecae2240d4e6dcb
    )


app = rx.App()
app.add_page(index, route="/", title="Inicio - Sistema PQRS")
app.add_page(registro_page, route="/registro", title="Registro de Ciudadano")
<<<<<<< HEAD
app.add_page(login_page, route="/login", title="Iniciar Sesión")
app.add_page(solicitudes_page, route="/solicitudes", title="Nueva Solicitud PQRS")
app.add_page(change_password_page, route="/cambiar-contrasena", title="Cambiar Contraseña")
app.add_page(dashboard, route="/dashboard", title="Panel de Ciudadano") 
=======
app.add_page(registro_funcionario_page, route="/registro-funcionario", title="Registro de Funcionario")
app.add_page(login_page, route="/login", title="Iniciar Sesión")
app.add_page(solicitudes_page, route="/solicitudes", title="Nueva Solicitud PQRS")
app.add_page(change_password_page, route="/cambiar-contrasena", title="Cambiar Contraseña")
app.add_page(dashboard, route="/dashboard", title="Panel de Ciudadano")
app.add_page(funcionario_dashboard, route="/dashboard-funcionario", title="Panel de Funcionario")
app.add_page(politica_privacidad_page, route="/politica-privacidad", title="Política de Privacidad")
>>>>>>> e2b305b84823c9d11bb994642ecae2240d4e6dcb
