from datetime import datetime
from typing import Optional
import reflex as rx
from sqlmodel import Field

class Usuario(rx.Model, table=True):
    "Esta es la tabla de usuario en la base de datos"
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    Contraseña: str
    rol: str = "ciudadano"  # Roles: ciudadano, funcionario, administrador
    is_active: bool = True
    Fecha_de_creacion: datetime = Field(default_factory=datetime.now)
    # Campos adicionales del registro ampliado
    tipo_identificacion: Optional[str] = None
    numero_identificacion: Optional[str] = None
    nombres: Optional[str] = None
    apellidos: Optional[str] = None
    genero: Optional[str] = None
    direccion: Optional[str] = None
    telefono: Optional[str] = None
    departamento: Optional[str] = None
    ciudad: Optional[str] = None
    etnia: Optional[str] = None
    persona_vulnerable: Optional[str] = None
    acepta_notificaciones: bool = False
    acepta_politica_datos: bool = False

class Solicitud(rx.Model, table=True):
    "Tabla de solicitudes PQRS"
    id: Optional[int] = Field(default=None, primary_key=True)
    radicado: str
    tipo_solicitud: str
    asunto: str
    descripcion: str
    ubicacion: Optional[str] = None
    documento: Optional[str] = None
    documento_basename: Optional[str] = None
    area_responsable: Optional[str] = None
    persona_vulnerable: Optional[str] = None
    estado: str = "Radicada"
    respuesta: Optional[str] = None
    fecha: datetime = Field(default_factory=datetime.now)
    fecha_respuesta: Optional[datetime] = None
    creado_por: Optional[str] = None
    usuario_id: Optional[int] = Field(default=None, foreign_key="usuario.id")
    calificacion_servicio: Optional[int] = None
    fecha_consulta_ciudadano: Optional[datetime] = None
    