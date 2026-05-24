import argparse
import sqlite3
import bcrypt


def main():
    parser = argparse.ArgumentParser(description="Crear un usuario funcionario en la base de datos reflex.db")
    parser.add_argument("email", help="Correo del funcionario")
    parser.add_argument("password", help="Contraseña del funcionario")
    parser.add_argument("nombres", help="Nombres del funcionario")
    parser.add_argument("apellidos", help="Apellidos del funcionario")
    parser.add_argument("--identificacion", default="", help="Número de identificación")
    parser.add_argument("--tipo-identificacion", default="", help="Tipo de identificación")
    parser.add_argument("--telefono", default="", help="Teléfono")
    parser.add_argument("--direccion", default="", help="Dirección")
    parser.add_argument("--departamento", default="", help="Departamento")
    parser.add_argument("--ciudad", default="", help="Ciudad")
    parser.add_argument("--db", default="reflex.db", help="Ruta del archivo SQLite de la aplicación")
    args = parser.parse_args()

    hashed = bcrypt.hashpw(args.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    conn = sqlite3.connect(args.db)
    cur = conn.cursor()

    try:
        cur.execute("SELECT id FROM usuario WHERE email = ?", (args.email,))
        if cur.fetchone():
            print(f"ERROR: Ya existe un usuario con el correo {args.email}")
            return

        cur.execute(
            "INSERT INTO usuario (email, Contraseña, rol, is_active, Fecha_de_creacion, tipo_identificacion, numero_identificacion, nombres, apellidos, genero, direccion, telefono, departamento, ciudad) VALUES (?, ?, ?, ?, datetime('now'), ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                args.email,
                hashed,
                "funcionario",
                1,
                args.tipo_identificacion,
                args.identificacion,
                args.nombres,
                args.apellidos,
                None,
                args.direccion,
                args.telefono,
                args.departamento,
                args.ciudad,
            ),
        )
        conn.commit()
        print(f"Funcionario creado correctamente: {args.email}")
        print("Ahora puedes iniciar sesión en /login con ese correo y contraseña.")
    except sqlite3.Error as e:
        print("Error en la base de datos:", e)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
