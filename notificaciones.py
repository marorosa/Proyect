"""
Módulo de notificaciones para PQRS vía SMTP.
Maneja el envío de correos para diferentes estados de solicitudes.
"""

import os
import logging
import smtplib
import mimetypes
from pathlib import Path
from typing import Dict, Optional, List, Tuple
from datetime import datetime
from email import encoders
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from urllib.parse import quote
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('notificaciones.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

EMAIL_SENDER = os.getenv("EMAIL_SENDER", "enlacepqrs1755@gmail.com")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
EMPRESA_NOMBRE = os.getenv("EMPRESA_NOMBRE", "Sistema de PQRS")


def get_app_base_url() -> str:
    """URL pública de la app (sin barra final). Vacía si no está configurada o es localhost."""
    base = os.getenv("APP_URL", "").strip().rstrip("/")
    if not base:
        return ""
    lower = base.lower()
    if "localhost" in lower or "127.0.0.1" in lower:
        return ""
    return base


def url_descarga_publica(nombre_archivo: str) -> Optional[str]:
    """Enlace de descarga solo si APP_URL apunta a un servidor accesible desde internet."""
    base = get_app_base_url()
    if not base:
        return None
    return f"{base}/assets/uploads/{quote(nombre_archivo)}"


def formatear_nota_documento(
    nombre_archivo: str,
    ruta_local: Optional[str] = None,
) -> Tuple[str, List[str]]:
    """
    Texto para el cuerpo del correo y rutas de archivos a adjuntar por SMTP.
    Si no hay URL pública, el archivo va adjunto al correo.
    """
    adjuntos: List[str] = []
    if ruta_local:
        ruta = str(Path(ruta_local))
        if os.path.isfile(ruta):
            adjuntos.append(os.path.abspath(ruta))
        else:
            candidato = Path(__file__).resolve().parent / "assets" / "uploads" / Path(ruta).name
            if candidato.is_file():
                adjuntos.append(str(candidato.resolve()))

    lineas = [f"\n\nDocumento adjunto: {nombre_archivo}"]
    url = url_descarga_publica(nombre_archivo)
    if url:
        lineas.append(f"Descarga: {url}")
    elif adjuntos:
        lineas.append(
            "El archivo va incluido como adjunto en este correo; "
            "ábrelo desde Gmail, Outlook u otro cliente de correo."
        )
    else:
        lineas.append(
            "No se pudo adjuntar el archivo automáticamente. "
            "Consulta el estado de tu solicitud en el portal web."
        )
    return "\n".join(lineas), adjuntos


def _adjuntar_archivos(mensaje: MIMEMultipart, rutas: List[str]) -> None:
    for ruta in rutas:
        path = Path(ruta)
        if not path.is_file():
            continue
        mime_type, _ = mimetypes.guess_type(str(path))
        maintype, subtype = (mime_type or "application/octet-stream").split("/", 1)
        with open(path, "rb") as archivo:
            parte = MIMEBase(maintype, subtype)
            parte.set_payload(archivo.read())
        encoders.encode_base64(parte)
        parte.add_header(
            "Content-Disposition",
            "attachment",
            filename=path.name,
        )
        mensaje.attach(parte)


def enviar_correo_smtp(
    destinatario: str,
    asunto: str,
    html: str,
    adjuntos: Optional[List[str]] = None,
) -> bool:
    """Envía un correo HTML por SMTP. Opcionalmente adjunta archivos del disco."""
    if not EMAIL_PASSWORD:
        logger.error("EMAIL_PASSWORD no configurada; no se puede enviar por SMTP.")
        return False
    try:
        mensaje = MIMEMultipart("mixed")
        mensaje["From"] = EMAIL_SENDER
        mensaje["To"] = destinatario
        mensaje["Subject"] = asunto
        cuerpo = MIMEMultipart("alternative")
        cuerpo.attach(MIMEText(html, "html"))
        mensaje.attach(cuerpo)
        if adjuntos:
            _adjuntar_archivos(mensaje, adjuntos)
            logger.info("Adjuntos al correo: %s", adjuntos)
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=30) as servidor:
            servidor.starttls()
            servidor.login(EMAIL_SENDER, EMAIL_PASSWORD)
            servidor.sendmail(EMAIL_SENDER, destinatario, mensaje.as_string())
        return True
    except smtplib.SMTPAuthenticationError as e:
        logger.error("Credenciales SMTP incorrectas: %s", e)
        return False
    except Exception as e:
        logger.error("Error SMTP enviando a %s: %s", destinatario, e)
        return False


# ========== BASE HTML COMPARTIDA ==========

def _base_email(contenido_inner: str, color_header: str = "#4f46e5") -> str:
    """Envuelve el contenido en la plantilla base moderna."""
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{EMPRESA_NOMBRE}</title>
</head>
<body style="margin:0;padding:0;background-color:#f1f5f9;font-family:'Segoe UI',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f1f5f9;padding:40px 20px;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">

          <!-- HEADER -->
          <tr>
            <td style="background:linear-gradient(135deg,{color_header} 0%,#312e81 100%);
                       border-radius:16px 16px 0 0;padding:40px 40px 30px;text-align:center;">
              <div style="display:inline-block;background:rgba(255,255,255,0.15);
                          border-radius:50%;width:56px;height:56px;line-height:56px;
                          font-size:28px;margin-bottom:16px;">📋</div>
              <h1 style="margin:0;color:#ffffff;font-size:24px;font-weight:700;
                         letter-spacing:-0.5px;">{EMPRESA_NOMBRE}</h1>
              <p style="margin:6px 0 0;color:rgba(255,255,255,0.75);font-size:13px;">
                Sistema de Gestión de PQRS
              </p>
            </td>
          </tr>

          <!-- BODY -->
          <tr>
            <td style="background:#ffffff;padding:40px;border-left:1px solid #e2e8f0;
                       border-right:1px solid #e2e8f0;">
              {contenido_inner}
            </td>
          </tr>

          <!-- FOOTER -->
          <tr>
            <td style="background:#f8fafc;border:1px solid #e2e8f0;
                       border-radius:0 0 16px 16px;padding:24px 40px;text-align:center;">
              <p style="margin:0;color:#94a3b8;font-size:12px;line-height:1.6;">
                Este es un mensaje automático de <strong>{EMPRESA_NOMBRE}</strong>.<br>
                Por favor no responda a este correo.
              </p>
              <p style="margin:12px 0 0;color:#cbd5e1;font-size:11px;">
                © {datetime.now().year} {EMPRESA_NOMBRE} · Todos los derechos reservados
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def _badge(texto: str, color_bg: str, color_text: str) -> str:
    return (f'<span style="display:inline-block;background:{color_bg};color:{color_text};'
            f'padding:4px 12px;border-radius:99px;font-size:12px;font-weight:600;">'
            f'{texto}</span>')


def _info_row(icono: str, label: str, valor: str) -> str:
    return f"""
    <tr>
      <td style="padding:10px 0;border-bottom:1px solid #f1f5f9;vertical-align:top;width:40%;">
        <span style="font-size:14px;">{icono}</span>
        <span style="color:#64748b;font-size:13px;margin-left:6px;">{label}</span>
      </td>
      <td style="padding:10px 0;border-bottom:1px solid #f1f5f9;vertical-align:top;">
        <span style="color:#1e293b;font-size:14px;font-weight:600;">{valor}</span>
      </td>
    </tr>"""


# ========== PLANTILLAS ==========

def template_solicitud_creada(
    nombre_solicitante: str,
    numero_solicitud: str,
    tipo_pqrs: str,
    fecha_creacion: str,
    fecha_vencimiento: str
) -> str:
    """Plantilla moderna para notificar creación de solicitud."""

    tipo_icons = {"Petición": "📩", "Queja": "😤", "Reclamo": "⚖️", "Sugerencia": "💡"}
    icono_tipo = tipo_icons.get(tipo_pqrs, "📋")

    contenido = f"""
    <p style="margin:0 0 8px;color:#64748b;font-size:14px;">Hola,</p>
    <h2 style="margin:0 0 4px;color:#1e293b;font-size:22px;font-weight:700;">
      {nombre_solicitante}
    </h2>
    <p style="margin:0 0 28px;color:#475569;font-size:15px;line-height:1.6;">
      Tu solicitud ha sido <strong style="color:#10b981;">radicada exitosamente</strong>
      en el sistema. A continuación el resumen:
    </p>

    <!-- Card radicado -->
    <div style="background:linear-gradient(135deg,#f0fdf4,#dcfce7);border:1px solid #bbf7d0;
                border-radius:12px;padding:24px;text-align:center;margin-bottom:28px;">
      <p style="margin:0 0 4px;color:#166534;font-size:12px;font-weight:600;text-transform:uppercase;
                letter-spacing:1px;">Número de Radicado</p>
      <p style="margin:0;color:#15803d;font-size:28px;font-weight:800;letter-spacing:2px;">
        {numero_solicitud}
      </p>
    </div>

    <!-- Detalles -->
    <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:28px;">
      {_info_row(icono_tipo, "Tipo de solicitud", tipo_pqrs)}
      {_info_row("📅", "Fecha de radicación", fecha_creacion)}
      {_info_row("⏰", "Fecha límite de respuesta", fecha_vencimiento)}
    </table>

    <!-- Aviso -->
    <div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:10px;
                padding:16px 20px;margin-bottom:28px;">
      <p style="margin:0;color:#1d4ed8;font-size:13px;line-height:1.6;">
        💡 <strong>¿Cómo hacer seguimiento?</strong><br>
        Usa el número de radicado <strong>{numero_solicitud}</strong> en el portal para
        consultar el estado de tu solicitud en cualquier momento.
      </p>
    </div>

    <p style="margin:0;color:#64748b;font-size:13px;line-height:1.6;">
      Resolveremos tu solicitud en el menor tiempo posible dentro de los plazos establecidos.
      Gracias por usar nuestros servicios.
    </p>
    """
    return _base_email(contenido, color_header="#059669")


def template_cambio_estado(
    nombre_solicitante: str,
    numero_solicitud: str,
    estado_anterior: str,
    estado_nuevo: str,
    fecha_cambio: str,
    observaciones: Optional[str] = None,
    area_asignada: Optional[str] = None,
) -> str:
    """Plantilla moderna para notificar cambio de estado."""

    estado_colores = {
        "Radicada":    ("#dbeafe", "#1d4ed8"),
        "En Proceso":  ("#fef3c7", "#b45309"),
        "Asignada":    ("#ede9fe", "#6d28d9"),
        "En Revisión": ("#fce7f3", "#be185d"),
        "Cerrada":     ("#d1fae5", "#065f46"),
        "Resuelta":    ("#d1fae5", "#065f46"),
        "Finalizada":  ("#d1fae5", "#065f46"),
    }
    bg_nuevo, fg_nuevo = estado_colores.get(estado_nuevo, ("#f1f5f9", "#334155"))
    bg_ant,   fg_ant   = estado_colores.get(estado_anterior, ("#f1f5f9", "#64748b"))

    obs_bloque = ""
    if observaciones:
        obs_bloque = f"""
        <div style="background:#f8fafc;border-left:4px solid #4f46e5;border-radius:0 10px 10px 0;
                    padding:16px 20px;margin:20px 0;">
          <p style="margin:0 0 4px;color:#4f46e5;font-size:11px;font-weight:700;
                    text-transform:uppercase;letter-spacing:1px;">Observaciones</p>
          <p style="margin:0;color:#334155;font-size:14px;line-height:1.6;">{observaciones}</p>
        </div>"""

    area_bloque = ""
    if area_asignada:
        area_bloque = f"""
        <div style="background:linear-gradient(135deg,#fffbeb,#fef3c7);border:1px solid #fde68a;
                    border-left:4px solid #f59e0b;border-radius:0 10px 10px 0;
                    padding:16px 20px;margin:16px 0;">
          <p style="margin:0 0 4px;color:#b45309;font-size:11px;font-weight:700;
                    text-transform:uppercase;letter-spacing:1px;">🏢 Área Asignada</p>
          <p style="margin:0;color:#92400e;font-size:15px;font-weight:700;">{area_asignada}</p>
        </div>"""

    contenido = f"""
    <p style="margin:0 0 8px;color:#64748b;font-size:14px;">Hola,</p>
    <h2 style="margin:0 0 4px;color:#1e293b;font-size:22px;font-weight:700;">
      {nombre_solicitante}
    </h2>
    <p style="margin:0 0 28px;color:#475569;font-size:15px;line-height:1.6;">
      Tu solicitud <strong style="color:#4f46e5;">#{numero_solicitud}</strong>
      ha tenido una actualización de estado.
    </p>

    <!-- Cambio de estado visual -->
    <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;
                padding:24px;margin-bottom:28px;text-align:center;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          <td align="center" width="40%">
            <p style="margin:0 0 8px;color:#94a3b8;font-size:11px;font-weight:600;
                      text-transform:uppercase;letter-spacing:1px;">Estado anterior</p>
            <span style="display:inline-block;background:{bg_ant};color:{fg_ant};
                         padding:8px 16px;border-radius:99px;font-size:13px;font-weight:600;">
              {estado_anterior}
            </span>
          </td>
          <td align="center" width="20%">
            <span style="color:#cbd5e1;font-size:24px;">→</span>
          </td>
          <td align="center" width="40%">
            <p style="margin:0 0 8px;color:#94a3b8;font-size:11px;font-weight:600;
                      text-transform:uppercase;letter-spacing:1px;">Estado nuevo</p>
            <span style="display:inline-block;background:{bg_nuevo};color:{fg_nuevo};
                         padding:8px 16px;border-radius:99px;font-size:13px;font-weight:700;">
              {estado_nuevo}
            </span>
          </td>
        </tr>
      </table>
    </div>

    <!-- Detalles -->
    <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:8px;">
      {_info_row("🔖", "Radicado", numero_solicitud)}
      {_info_row("🕐", "Fecha de cambio", fecha_cambio)}
    </table>

    {area_bloque}

    {obs_bloque}

    <p style="margin:20px 0 0;color:#64748b;font-size:13px;line-height:1.6;">
      Continuaremos actualizándote sobre el avance de tu solicitud.
    </p>
    """
    return _base_email(contenido, color_header="#4f46e5")


def template_respuesta_final(
    nombre_solicitante: str,
    numero_solicitud: str,
    tipo_pqrs: str,
    fecha_respuesta: str,
    descripcion_respuesta: str
) -> str:
    """Plantilla moderna para notificar respuesta final."""

    contenido = f"""
    <p style="margin:0 0 8px;color:#64748b;font-size:14px;">Hola,</p>
    <h2 style="margin:0 0 4px;color:#1e293b;font-size:22px;font-weight:700;">
      {nombre_solicitante}
    </h2>
    <p style="margin:0 0 28px;color:#475569;font-size:15px;line-height:1.6;">
      Nos complace informarte que tu <strong>{tipo_pqrs}</strong> ha sido
      <strong style="color:#059669;">resuelta satisfactoriamente</strong>.
    </p>

    <!-- Banner resuelto -->
    <div style="background:linear-gradient(135deg,#059669,#047857);border-radius:12px;
                padding:20px 24px;text-align:center;margin-bottom:28px;">
      <span style="font-size:32px;">✅</span>
      <p style="margin:8px 0 0;color:#ffffff;font-size:16px;font-weight:700;">
        Solicitud Resuelta
      </p>
      <p style="margin:4px 0 0;color:rgba(255,255,255,0.8);font-size:13px;">
        Radicado: <strong>{numero_solicitud}</strong>
      </p>
    </div>

    <!-- Detalles -->
    <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:24px;">
      {_info_row("📋", "Tipo de solicitud", tipo_pqrs)}
      {_info_row("📅", "Fecha de respuesta", fecha_respuesta)}
    </table>

    <!-- Respuesta -->
    <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:12px;
                padding:20px 24px;margin-bottom:28px;">
      <p style="margin:0 0 12px;color:#166534;font-size:12px;font-weight:700;
                text-transform:uppercase;letter-spacing:1px;">📝 Respuesta oficial</p>
      <p style="margin:0;color:#1e293b;font-size:14px;line-height:1.7;
                white-space:pre-wrap;">{descripcion_respuesta}</p>
    </div>

    <div style="background:#fffbeb;border:1px solid #fde68a;border-radius:10px;
                padding:14px 18px;">
      <p style="margin:0;color:#92400e;font-size:13px;line-height:1.6;">
        💬 Si tienes alguna aclaración o no estás conforme con la respuesta,
        comunícate con nosotros a través del portal web.
      </p>
    </div>
    """
    return _base_email(contenido, color_header="#059669")


# ========== FUNCIONES DE ENVÍO ==========

def enviar_correo(
    destinatarios: List[str],
    asunto: str,
    html: str,
    nombre_evento: str = "general",
    adjuntos: Optional[List[str]] = None,
) -> Dict:
    """Envía correos HTML a una lista de destinatarios por SMTP."""
    try:
        if not destinatarios:
            logger.warning("[%s] No hay destinatarios para enviar el correo", nombre_evento)
            return {"success": False, "error": "No destinatarios"}

        resultados = []
        for correo in destinatarios:
            if enviar_correo_smtp(correo, asunto, html, adjuntos=adjuntos):
                logger.info("[%s] Correo enviado a %s (SMTP)", nombre_evento, correo)
                resultados.append({"correo": correo, "exito": True})
            else:
                logger.error("[%s] Error enviando a %s", nombre_evento, correo)
                resultados.append({
                    "correo": correo,
                    "exito": False,
                    "error": "Fallo SMTP",
                })

        exitosos = sum(1 for r in resultados if r["exito"])
        return {
            "success": exitosos > 0,
            "resultados": resultados,
            "total": len(resultados),
            "exitosos": exitosos,
        }

    except Exception as e:
        logger.error("[%s] Error general en envío: %s", nombre_evento, e)
        return {"success": False, "error": str(e)}


def notificar_solicitud_creada(
    nombre_solicitante: str,
    correo_solicitante: str,
    numero_solicitud: str,
    tipo_pqrs: str,
    fecha_creacion: str,
    fecha_vencimiento: str,
    correos_adicionales: Optional[List[str]] = None
) -> Dict:
    """Notifica cuando se crea una nueva solicitud."""
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
        f"✅ Solicitud {numero_solicitud} Radicada — {EMPRESA_NOMBRE}",
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
    correos_adicionales: Optional[List[str]] = None,
    adjuntos: Optional[List[str]] = None,
    area_asignada: Optional[str] = None,
) -> Dict:
    """Notifica cuando cambia el estado de una solicitud."""
    destinatarios = [correo_solicitante]
    if correos_adicionales:
        destinatarios.extend(correos_adicionales)

    html = template_cambio_estado(
        nombre_solicitante,
        numero_solicitud,
        estado_anterior,
        estado_nuevo,
        fecha_cambio,
        observaciones,
        area_asignada,
    )

    return enviar_correo(
        destinatarios,
        f"🔄 Actualización Solicitud {numero_solicitud} — {estado_nuevo}",
        html,
        "cambio_estado",
        adjuntos=adjuntos,
    )


def notificar_respuesta_final(
    nombre_solicitante: str,
    correo_solicitante: str,
    numero_solicitud: str,
    tipo_pqrs: str,
    fecha_respuesta: str,
    descripcion_respuesta: str,
    correos_adicionales: Optional[List[str]] = None,
    adjuntos: Optional[List[str]] = None,
) -> Dict:
    """Notifica cuando se envía la respuesta final de una solicitud."""
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
        f"📬 Respuesta a su Solicitud {numero_solicitud} — {EMPRESA_NOMBRE}",
        html,
        "respuesta_final",
        adjuntos=adjuntos,
    )


# ========== FUNCIÓN DE PRUEBA ==========

def enviar_correo_prueba(correo_destino: str) -> Dict:
    """Envía un correo de prueba para validar la configuración."""

    contenido = f"""
    <div style="text-align:center;margin-bottom:28px;">
      <span style="font-size:48px;">🚀</span>
      <h2 style="margin:16px 0 8px;color:#1e293b;font-size:22px;font-weight:700;">
        ¡Configuración exitosa!
      </h2>
      <p style="margin:0;color:#64748b;font-size:15px;">
        El sistema de notificaciones por correo está funcionando correctamente.
      </p>
    </div>

    <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:12px;
                padding:20px 24px;margin-bottom:24px;">
      <table width="100%" cellpadding="0" cellspacing="0">
        {_info_row("✅", "Estado", "Operativo")}
        {_info_row("📡", "Servicio", "SMTP")}
        {_info_row("🕐", "Timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))}
        {_info_row("📬", "Destinatario", correo_destino)}
      </table>
    </div>

    <div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:10px;
                padding:16px 20px;">
      <p style="margin:0;color:#1d4ed8;font-size:13px;line-height:1.6;">
        💡 Si recibes este correo, los correos automáticos del sistema PQRS
        llegarán correctamente a los ciudadanos.
      </p>
    </div>
    """
    html = _base_email(contenido, color_header="#7c3aed")

    return enviar_correo(
        [correo_destino],
        "🧪 Correo de Prueba — Sistema PQRS",
        html,
        "prueba"
    )


if __name__ == "__main__":
    print("Módulo de notificaciones cargado correctamente.")
    print(f"SMTP configurado: {bool(EMAIL_PASSWORD)}")
    print(f"Email desde: {EMAIL_SENDER}")
