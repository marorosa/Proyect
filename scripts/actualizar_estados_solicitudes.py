"""Actualiza los estados de las solicitudes según un mapeo definido.

Por seguridad el script corre en modo `--dry-run` por defecto (no modifica la DB).
Usar `--apply` para ejecutar los cambios.

Ejemplos:
  python scripts/actualizar_estados_solicitudes.py
  python scripts/actualizar_estados_solicitudes.py --apply
"""
from __future__ import annotations
import sys
from pathlib import Path
from datetime import datetime
import argparse
from sqlmodel import text

# Asegurar que la raíz del proyecto está en sys.path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from autenticacion import autenticacion

engine = autenticacion.engine


MAPPING = {
    "radicada": "Radicada",
    "asignada": "Asignada a Area",
    "en proceso": "En Gestion de Area",
    "en revisión": "En Gestion de Area",
    "en revision": "En Gestion de Area",
    "cerrada": "Cerrada",
}


def normalize(s: str) -> str:
    if s is None:
        return ""
    return " ".join(str(s).strip().split()).lower()


def gather_candidates(conn):
    keys = tuple(MAPPING.keys())
    # Construir lista para IN clause
    placeholders = ",".join([f":k{i}" for i in range(len(keys))])
    params = {f"k{i}": keys[i] for i in range(len(keys))}
    sql = text(f"SELECT id, COALESCE(estado,'') AS estado FROM solicitud WHERE lower(coalesce(estado,'')) IN ({placeholders})")
    result = conn.execute(sql, params)
    return result.fetchall()


def run(dry_run: bool = True):
    changes = []
    # Primero reunir candidatos usando una conexión de solo-lectura
    with engine.connect() as read_conn:
        rows = gather_candidates(read_conn)
        for id_, estado in rows:
            src_norm = normalize(estado)
            nuevo = MAPPING.get(src_norm)
            if not nuevo:
                continue
            if nuevo == (estado or ""):
                continue
            changes.append((id_, estado or "", nuevo))

        if not changes:
            print("No se encontraron estados para actualizar con el mapeo dado.")
            return

        print(f"Se encontrarón {len(changes)} cambios potenciales:")
        for id_, antes, despues in changes:
            print(f"- id={id_}: '{antes}' -> '{despues}'")

        if dry_run:
            print("\nModo dry-run: no se aplicarán cambios. Ejecuta con --apply para confirmar.")
            return

        # Aplicar cambios y registrar historial usando una transacción separada
        now = datetime.now()
        with engine.begin() as write_conn:
            for id_, antes, despues in changes:
                try:
                    write_conn.execute(
                        text("UPDATE solicitud SET estado = :nuevo WHERE id = :id"),
                        {"nuevo": despues, "id": id_},
                    )
                    write_conn.execute(
                        text(
                            "INSERT INTO solicitudestadohistorial (solicitud_id, estado_anterior, estado_nuevo, fecha_cambio) VALUES (:sid, :ant, :nue, :fecha)"
                        ),
                        {"sid": id_, "ant": antes, "nue": despues, "fecha": now},
                    )
                except Exception as e:
                    print(f"Error actualizando id={id_}: {e}")
                    raise

        print("Cambios aplicados correctamente.")


def main():
    parser = argparse.ArgumentParser(description="Actualizar estados de solicitudes según mapeo")
    parser.add_argument("--apply", action="store_true", help="Aplicar los cambios (por defecto dry-run)")
    args = parser.parse_args()
    run(dry_run=not args.apply)


if __name__ == "__main__":
    main()
