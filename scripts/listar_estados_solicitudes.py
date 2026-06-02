"""Lista los estados distintos de las solicitudes y su conteo.
Ejecutar desde la raíz del proyecto con el entorno virtual activo:

python scripts/listar_estados_solicitudes.py
"""
from sqlmodel import text
import sys
from pathlib import Path

# Asegurar que la raíz del proyecto está en sys.path para poder importar el paquete `autenticacion`
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from autenticacion import autenticacion

engine = autenticacion.engine

with engine.connect() as conn:
    result = conn.execute(text(
        "SELECT COALESCE(estado,'') AS estado, COUNT(*) AS cantidad FROM solicitud GROUP BY estado ORDER BY cantidad DESC"
    ))
    rows = result.fetchall()

if not rows:
    print("No se encontraron solicitudes en la base de datos.")
else:
    print("Estados actuales en la tabla 'solicitud':")
    for estado, cantidad in rows:
        print(f"- {estado!s} : {cantidad}")
