# Instalación e Inicio del Proyecto

## Información del proyecto

Este repositorio contiene un sistema de gestión de PQRS (Peticiones, Quejas, Reclamos y Sugerencias) desarrollado con Reflex y Python.

El objetivo principal es permitir el registro de ciudadanos, la autenticación de usuarios, el envío de notificaciones por correo y la gestión de solicitudes a través de una interfaz web.

### Características clave

- Registro e inicio de sesión de usuarios.
- Gestión de roles básicos (ciudadanos y funcionarios).
- Envío de correos SMTP configurables.
- Base de datos local SQLite (`reflex.db`).
- Migraciones con Alembic.
- Frontend basado en Reflex UI y módulos de Node.js.

### Estructura básica relevante

- `requirements.txt`: dependencias Python.
- `package.json`: dependencias frontend.
- `rxconfig.py`: configuración de Reflex.
- `alembic/`: migraciones de base de datos.
- `autenticacion/`: lógica de usuario y modelos.
- `.env`: variables de entorno.

## 1. Requisitos previos

- Windows 10/11
- Python 3.11 o superior
- Node.js 18 o superior (para dependencias de frontend si se requiere)
- Git opcional

## 2. Preparar el entorno de Python

1. Abrir terminal en la carpeta del proyecto:
   - `c:\Users\HinojosaDev\Downloads\ADA\Sft1\APP\Proyect`

2. Crear el entorno virtual (si no existe):
   - PowerShell:
     ```powershell
     python -m venv .venv
     ```

3. Activar el entorno virtual:
   - PowerShell:
     ```powershell
     .venv\Scripts\Activate.ps1
     ```
   - CMD:
     ```cmd
     .venv\Scripts\activate.bat
     ```

4. Actualizar pip y luego instalar las dependencias Python:
   ```powershell
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

## 3. Preparar dependencias de frontend (opcional)

Este proyecto incluye un `package.json` en la raíz del proyecto, por lo que si necesita instalar o actualizar módulos de frontend, ejecute:

```powershell
npm install
```

> Nota: si ya existe una carpeta `node_modules`, este paso no es obligatorio, pero es recomendable cuando se trabaja en un equipo o después de clonar el repositorio.

## 4. Configurar variables de entorno

Copiar `.env` si existe un ejemplo o crear uno nuevo con las siguientes variables mínimas:

```env
EMAIL_SENDER=tu-correo@example.com
EMAIL_PASSWORD=tu-password-o-app-password
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
EMPRESA_NOMBRE=Nombre de la empresa
APP_URL=http://localhost:3000
```

> Asegúrate de usar una contraseña de aplicación cuando trabajes con Gmail.

## 5. Inicializar la base de datos

Si es un proyecto nuevo o si necesitas aplicar migraciones, ejecuta:

```powershell
alembic upgrade head
```

Si la base de datos ya está presente (`reflex.db`), puedes omitir este paso.

## 6. Ejecutar el proyecto

Con el entorno virtual activo, ejecutar:

```powershell
reflex run
```

Si el comando `reflex` no se encuentra, prueba:

```powershell
python -m reflex run
```

## 7. Acceder a la aplicación

Abrir el navegador y visitar:

```text
http://localhost:3000
```

## 8. Comandos útiles

- Activar entorno virtual:
  - `.\.venv\Scripts\Activate.ps1`
- Instalar dependencias Python:
  - `pip install -r requirements.txt`
- Instalar dependencias Node:
  - `npm install`
- Ejecutar la aplicación:
  - `reflex run`
- Ejecutar migraciones de base de datos:
  - `alembic upgrade head`

## 9. Verificación rápida

1. Verifica que el entorno virtual está activo.
2. Confirma instalación de paquetes Python sin errores.
3. Asegúrate de que `.env` está configurado correctamente.
4. Ejecuta `reflex run` y abre `http://localhost:3000`.

## 10. Comandos de desarrollo

- Iniciar la aplicación:
  - `reflex run`
- Ejecutar con Python si `reflex` no está en PATH:
  - `python -m reflex run`
- Instalar librerías Python:
  - `pip install -r requirements.txt`
- Instalar dependencias de frontend:
  - `npm install`
- Aplicar migraciones de base de datos:
  - `alembic upgrade head`
- Volver a crear el entorno virtual (limpio):
  - `python -m venv .venv`
  - `.venv\Scripts\Activate.ps1`
  - `pip install -r requirements.txt`

## 11. Scripts útiles para crear datos de prueba y administrar usuarios

Ejecuta estos comandos desde la raíz del proyecto con el entorno virtual activo.

- Crear un funcionario administrador inicial:
  - `python scripts/create_funcionario_initial.py`
- Crear un funcionario nuevo con parámetros:
  - `python scripts/create_funcionario.py admin2@empresa.com MiContraseña123! "Nombres" "Apellidos" --identificacion 123456 --tipo-identificacion CC --telefono 3001234567 --direccion "Calle 1 #2-3" --departamento Antioquia --ciudad Medellín`
- Crear varios ciudadanos de ejemplo:
  - `python scripts/crear_ciudadanos_ejemplo.py`
- Crear solicitudes de ejemplo (requiere ciudadanos existentes):
  - `python scripts/crear_solicitudes_ejemplo.py`
- Crear solicitudes adicionales de ejemplo:
  - `python scripts/crear_solicitudes_adicionales.py`
- Listar usuarios en la base de datos:
  - `python scripts/check_users.py`
- Restablecer contraseña de un usuario existente:
  - `python scripts/reset_password.py usuario@ejemplo.com NuevaContraseña123!`
- Reintentar el envío de correos fallidos:
  - `python scripts/retry_failed_emails.py`

## 12. Solución de problemas comunes

- `python` no reconocido:
  - Verifica la instalación de Python y agrega `python` al PATH.
- `pip` no reconocido:
  - Usa `python -m pip install -r requirements.txt`.
- `reflex` no encontrado:
  - Verifica que está instalado en el entorno virtual.
  - Usa `python -m reflex run`.
- Error de SMTP o correo:
  - Revisa `EMAIL_SENDER`, `EMAIL_PASSWORD`, `SMTP_SERVER` y `SMTP_PORT`.
  - Si usas Gmail, crea una contraseña de aplicación.

---

## Resumen rápido

1. Activar entorno virtual
2. `pip install -r requirements.txt`
3. Configurar `.env`
4. `alembic upgrade head` (si es necesario)
5. `reflex run`
6. Abrir `http://localhost:3000`
