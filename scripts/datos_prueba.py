from datetime import datetime, timedelta, timezone
import random
import sys
import uuid

sys.path.insert(0, "/app")

from sqlmodel import Session, select

from autenticacion.autenticacion import engine
from autenticacion.usuario_model import Usuario, Solicitud


CANTIDAD = 50
USUARIO_ID = 1
PREFIJO = "TEST-PQRS-"


TIPOS = [
    "Petición",
    "Queja",
    "Reclamo",
    "Sugerencia",
    "Consulta",
]

AREAS = [
    "Atención al ciudadano",
    "Servicios Públicos",
    "Secretaría de Educación",
    "Secretaría de Salud",
    "Planeación",
    "Hacienda",
]

ASUNTOS = [
    "Solicitud de información",
    "Inconformidad con el servicio",
    "Solicitud de atención",
    "Reporte de situación",
    "Solicitud de respuesta",
    "Consulta sobre trámite",
    "Reclamo por demora",
    "Sugerencia de mejora",
]

UBICACIONES = [
    "Buenaventura - Comuna 1",
    "Buenaventura - Comuna 2",
    "Buenaventura - Comuna 3",
    "Buenaventura - Comuna 4",
    "Buenaventura - Comuna 5",
    "Buenaventura - Comuna 6",
    "Buenaventura - Comuna 7",
    "Buenaventura - Comuna 8",
    "Buenaventura - Comuna 9",
    "Buenaventura - Comuna 10",
    "Buenaventura - Comuna 11",
    "Buenaventura - Comuna 12",
]

DESCRIPCIONES = [
    "El ciudadano solicita información relacionada con el trámite y requiere orientación.",
    "Se presenta una inconformidad con el servicio recibido y se solicita revisión del caso.",
    "El ciudadano solicita una respuesta formal sobre la situación reportada.",
    "Se reporta una situación que requiere atención por parte del área responsable.",
    "Se solicita información sobre los procedimientos y requisitos correspondientes.",
    "El ciudadano requiere seguimiento al trámite realizado y solicita información sobre su estado.",
    "Se presenta una solicitud relacionada con la prestación de un servicio público.",
    "El ciudadano propone una mejora para facilitar la atención y los trámites.",
]

RESPUESTAS = [
    "La solicitud fue revisada por el área responsable y se emitió respuesta al ciudadano.",
    "Después de revisar el caso, se informa al ciudadano sobre las acciones realizadas.",
    "El área responsable analizó la solicitud y dio respuesta conforme al procedimiento establecido.",
    "Se realizó la revisión correspondiente y se notificó la respuesta al ciudadano.",
]


def obtener_solicitudes_prueba(session):
    return session.exec(
        select(Solicitud).where(
            Solicitud.radicado.startswith(PREFIJO)
        )
    ).all()


def crear():
    with Session(engine) as session:

        usuario = session.get(Usuario, USUARIO_ID)

        if not usuario:
            print(f"ERROR: No existe el usuario con ID {USUARIO_ID}.")
            return

        existentes = obtener_solicitudes_prueba(session)

        if existentes:
            print()
            print("Ya existen datos de prueba.")
            print(f"Solicitudes encontradas: {len(existentes)}")
            print()
            print("Si deseas crear un nuevo conjunto de datos:")
            print("  python /app/scripts/datos_prueba.py eliminar")
            print("  python /app/scripts/datos_prueba.py crear")
            print()
            return

        ahora = datetime.now(timezone.utc)

        # Distribución controlada:
        # 15 Radicadas
        # 15 En proceso
        # 10 Respondidas
        # 10 Cerradas
        estados = (
            ["Radicada"] * 15
            + ["En proceso"] * 15
            + ["Respondida"] * 10
            + ["Cerrada"] * 10
        )

        random.shuffle(estados)

        creadas = 0

        for i, estado in enumerate(estados, start=1):

            tipo = random.choice(TIPOS)

            # Las solicitudes abiertas pueden tener diferentes edades.
            if estado in ["Radicada", "En proceso"]:
                dias_atras = random.randint(1, 120)

            # Las solicitudes respondidas/cerradas deben tener
            # suficiente antigüedad para que la respuesta no quede
            # en el futuro.
            else:
                dias_atras = random.randint(20, 120)

            fecha = ahora - timedelta(days=dias_atras)

            respuesta = None
            fecha_respuesta = None

            if estado in ["Respondida", "Cerrada"]:

                dias_respuesta = random.randint(1, min(20, dias_atras))

                fecha_respuesta = fecha + timedelta(
                    days=dias_respuesta
                )

                respuesta = random.choice(RESPUESTAS)

            # UUID corto para garantizar que el radicado sea único
            identificador = uuid.uuid4().hex[:8].upper()

            radicado = (
                f"{PREFIJO}"
                f"{fecha.strftime('%Y%m%d')}-"
                f"{i:04d}-"
                f"{identificador}"
            )

            solicitud = Solicitud(
                radicado=radicado,
                tipo_solicitud=tipo,
                asunto=random.choice(ASUNTOS),
                descripcion=random.choice(DESCRIPCIONES),
                ubicacion=random.choice(UBICACIONES),
                area_responsable=random.choice(AREAS),
                estado=estado,
                respuesta=respuesta,
                fecha=fecha,
                fecha_respuesta=fecha_respuesta,
                creado_por=usuario.email,
                usuario_id=usuario.id,
            )

            session.add(solicitud)
            creadas += 1

        session.commit()

        print()
        print("======================================")
        print("     DATOS DE PRUEBA CREADOS")
        print("======================================")
        print(f"Solicitudes creadas : {creadas}")
        print(f"Usuario asociado    : {usuario.email}")
        print(f"Radicados           : {PREFIJO}...")
        print()
        print("Distribución:")
        print("  Radicada           : 15")
        print("  En proceso         : 15")
        print("  Respondida         : 10")
        print("  Cerrada            : 10")
        print("======================================")


def listar():
    with Session(engine) as session:

        solicitudes = obtener_solicitudes_prueba(session)

        print()
        print("======================================")
        print("       DATOS DE PRUEBA")
        print("======================================")
        print(f"Total: {len(solicitudes)}")
        print()

        for s in solicitudes:
            print(
                f"{s.id} | "
                f"{s.radicado} | "
                f"{s.tipo_solicitud} | "
                f"{s.estado} | "
                f"{s.area_responsable}"
            )

        print("======================================")


def eliminar():
    with Session(engine) as session:

        solicitudes = obtener_solicitudes_prueba(session)

        if not solicitudes:
            print("No hay datos de prueba para eliminar.")
            return

        cantidad = len(solicitudes)

        for solicitud in solicitudes:
            session.delete(solicitud)

        session.commit()

        print()
        print("======================================")
        print("       DATOS DE PRUEBA ELIMINADOS")
        print("======================================")
        print(f"Solicitudes eliminadas: {cantidad}")
        print("Los demás datos NO fueron modificados.")
        print("======================================")


def mostrar_ayuda():
    print()
    print("Uso:")
    print()
    print("  crear")
    print("      Crea 50 solicitudes de prueba.")
    print()
    print("  listar")
    print("      Muestra las solicitudes de prueba.")
    print()
    print("  eliminar")
    print("      Elimina solamente las solicitudes")
    print("      cuyo radicado comienza por TEST-PQRS-.")
    print()


if __name__ == "__main__":

    if len(sys.argv) < 2:
        mostrar_ayuda()
        sys.exit(0)

    comando = sys.argv[1].lower()

    if comando == "crear":
        crear()

    elif comando == "listar":
        listar()

    elif comando == "eliminar":
        eliminar()

    else:
        mostrar_ayuda()