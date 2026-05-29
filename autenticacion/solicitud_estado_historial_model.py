from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime

class SolicitudEstadoHistorial(SQLModel, table=True):
    """Historial de cambios de estado de una solicitud PQRS."""
    id: Optional[int] = Field(default=None, primary_key=True)
    solicitud_id: int = Field(foreign_key="solicitud.id")
    estado_anterior: str
    estado_nuevo: str
    fecha_cambio: datetime = Field(default_factory=datetime.now)
    observaciones: Optional[str] = None
    documento_adjunto: Optional[str] = None
