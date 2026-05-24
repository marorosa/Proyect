import sqlite3
conn = sqlite3.connect("reflex.db")
cursor = conn.cursor()
cursor.execute("PRAGMA table_info(usuario)")
columnas = cursor.fetchall()
print("\n--- ESTRUCTURA DE LA TABLA USUARIO ---")
for col in columnas:
    print(f"ID: {col[0]} | Nombre: {col[1]} | Tipo: {col[2]}")
conn.close()
