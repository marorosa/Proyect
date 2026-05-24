import sqlite3
conn = sqlite3.connect('reflex.db')
cursor = conn.cursor()
cursor.execute('SELECT name FROM sqlite_master WHERE type="table";')
tables = cursor.fetchall()
print('Tablas en la base de datos:')
for table in tables:
    print(f'- {table[0]}')
if 'solicitud' in [t[0] for t in tables]:
    cursor.execute('PRAGMA table_info(solicitud);')
    columns = cursor.fetchall()
    print('Columnas de la tabla solicitud:')
    for col in columns:
        print(f'  {col[1]}: {col[2]}')
conn.close()