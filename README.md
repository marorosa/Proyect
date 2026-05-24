# Sistema de Gestión de PQRS para Empresas Públicas

## Descripción del Proyecto
Este proyecto implementa un sistema web de gestión de PQRS (Peticiones, Quejas, Reclamos y Sugerencias) para empresas públicas, desarrollado bajo el marco SCRUM. El objetivo es digitalizar y mejorar el proceso de atención al ciudadano, garantizando transparencia, eficiencia y cumplimiento normativo.

## Metodología SCRUM
- **Product Owner:** [Nombre]
- **Scrum Master:** [Nombre]
- **Equipo de Desarrollo:** [Nombres]

## Sprints Planificados
1. **Sprint 1: Registro de Ciudadanos** (Actual)
   - Historia de Usuario: Como ciudadano, quiero registrarme en el sistema para poder enviar solicitudes oficiales.
   - Funcionalidades: Registro y login básico para ciudadanos.

2. **Sprint 2: Gestión de PQRS**
   - Registro de solicitudes, asignación automática de radicado.

3. **Sprint 3: Seguimiento y Notificaciones**
   - Consulta de estado, notificaciones por email.

4. **Sprint 4: Panel de Administración**
   - Gestión de solicitudes por funcionarios.

5. **Sprint 5: Reportes y Estadísticas**
   - Generación de reportes y cumplimiento normativo.

## Tecnologías Utilizadas
- **Framework:** Reflex (Python)
- **Base de Datos:** SQLModel (SQLite/PostgreSQL)
- **Autenticación:** bcrypt
- **Frontend:** Reflex UI Components
- **Envío de Correos:** smtplib con python-dotenv

## Instalación y Ejecución
1. Instalar dependencias: `pip install -r requirements.txt`
2. Configurar variables de entorno en `.env`
3. Ejecutar la aplicación: `reflex run`
4. Acceder en: http://localhost:3000

## Estructura del Proyecto y Documentación de Archivos

### 📁 Archivos Principales

#### 1. `autenticacion.py` - Archivo Principal de la Aplicación
**Ubicación:** `autenticacion/autenticacion.py`  
**Función:** Contiene toda la lógica de la aplicación web, incluyendo:
- **Funciones de Utilidad:**
  - `tiene_password()`: Hashea contraseñas usando bcrypt para seguridad.
  - `confirmar_contraseña()`: Verifica contraseñas hasheadas.
  - `validar_correo()`: Valida formato de correos electrónicos con expresiones regulares.
  - `cantida_minima_contraseña()`: Valida requisitos de contraseña (8+ caracteres, mayúsculas, minúsculas, números, especiales).
  - `enviar_correo_bienvenida()`: Envía correos HTML de bienvenida usando SMTP.

- **Clase State:** Maneja el estado de la aplicación con variables reactivas:
  - `correo`, `contraseña`, `confirmar_contraseña`: Campos del formulario.
  - `error_de_registro`, `succes`, `error_de_contraseña`, `succes2`: Mensajes de estado.
  - `id_usuario`, `es_autentica`: Estado de autenticación.
  - Métodos: `signup()`, `login()`, `logout()` para gestión de usuarios.

- **Componentes de UI:**
  - `navbar()`: Barra de navegación con enlaces a Inicio, Registro, Login.
  - `auth_card()`: Tarjeta reutilizable para formularios de autenticación.
  - `index()`: Página de inicio con bienvenida.
  - `registro_page()`: Página de registro de ciudadanos.
  - `login_page()`: Página de inicio de sesión.
  - `dashboard()`: Panel protegido para ciudadanos autenticados.

- **Configuración de Rutas:** Define las páginas disponibles en la aplicación.

#### 2. `usuario_model.py` - Modelo de Datos de Usuario
**Ubicación:** `autenticacion/usuario_model.py`  
**Función:** Define la estructura de la tabla de usuarios en la base de datos usando SQLModel:
- **Campos:**
  - `id`: Identificador único (clave primaria).
  - `email`: Correo electrónico único e indexado.
  - `Contraseña`: Contraseña hasheada.
  - `rol`: Rol del usuario (ciudadano, funcionario, administrador).
  - `is_active`: Estado de activación de la cuenta.
  - `Fecha_de_creacion`: Timestamp de creación del usuario.

- **Herencia:** Extiende `rx.Model` para integración con Reflex y `table=True` para crear tabla SQL.

#### 3. `rxconfig.py` - Configuración de Reflex
**Ubicación:** `rxconfig.py`  
**Función:** Archivo de configuración generado por Reflex que contiene:
- Configuración de la aplicación (nombre, tema, etc.).
- Configuración de base de datos.
- Configuración de rutas y páginas.

#### 4. `.env` - Variables de Entorno
**Ubicación:** `.env`  
**Función:** Archivo de configuración segura que contiene:
- `EMAIL_SENDER`: Correo electrónico remitente para envío de correos.
- `EMAIL_PASSWORD`: Contraseña de aplicación de Gmail.
- `SMTP_SERVER`: Servidor SMTP (smtp.gmail.com).
- `SMTP_PORT`: Puerto SMTP (587).
- `EMPRESA_NOMBRE`: Nombre de la empresa para personalización.

### 📁 Sistema de Migraciones de Base de Datos

#### 5. `alembic/` - Directorio de Migraciones
**Ubicación:** `alembic/`  
**Función:** Sistema de migraciones de base de datos usando Alembic:
- `alembic.ini`: Configuración de Alembic (conexión a BD, rutas).
- `env.py`: Script de entorno para ejecutar migraciones.
- `script.py.mako`: Plantilla para generar scripts de migración.
- `versions/`: Directorio con archivos de migración específicos.
  - `ff383e22d5c3_.py`: Migración inicial que crea la tabla `usuario`.

### 📁 Archivos de Configuración y Dependencias

#### 6. `requirements.txt` - Dependencias del Proyecto
**Ubicación:** `requirements.txt`  
**Función:** Lista todas las dependencias Python necesarias:
- `reflex`: Framework principal.
- `bcrypt`: Para hashing de contraseñas.
- `python-dotenv`: Para cargar variables de entorno.
- `sqlmodel`: Para modelos de base de datos.
- Otras dependencias del sistema.

#### 7. `pyproject.toml` - Configuración del Proyecto
**Ubicación:** `pyproject.toml`  
**Función:** Archivo de configuración moderno de Python que define:
- Metadatos del proyecto (nombre, versión, autores).
- Dependencias y dependencias de desarrollo.
- Configuración de herramientas (linting, testing).

#### 8. `README.md` - Documentación del Proyecto
**Ubicación:** `README.md` (este archivo)  
**Función:** Documentación principal del proyecto con:
- Descripción general.
- Instrucciones de instalación.
- Estructura del proyecto.
- Tecnologías utilizadas.
- Próximos pasos.

### 📁 Archivos Generados por Reflex

#### 9. `web/` - Directorio del Frontend
**Ubicación:** `web/`  
**Función:** Contiene el código frontend generado por Reflex:
- `src/`: Código fuente React/TypeScript.
- `public/`: Archivos estáticos.
- `package.json`: Dependencias de Node.js.

#### 10. `env/` - Entorno Virtual de Python
**Ubicación:** `env/`  
**Función:** Entorno virtual de Python que contiene:
- `pyvenv.cfg`: Configuración del entorno virtual.
- `Lib/site-packages/`: Paquetes instalados.
- `Scripts/`: Ejecutables (python, pip, etc.).

## Funcionalidades Implementadas (Sprint 1)

### 🔐 Autenticación y Autorización
- **Registro de Ciudadanos:** Formulario con validación de email y contraseña fuerte.
- **Inicio de Sesión:** Autenticación con email y contraseña.
- **Hashing Seguro:** Uso de bcrypt para almacenar contraseñas.
- **Gestión de Sesiones:** Estado reactivo para mantener autenticación.

### 📧 Sistema de Notificaciones
- **Correo de Bienvenida:** Envío automático de correo HTML al registrarse.
- **Plantilla Personalizada:** Diseño profesional con datos del usuario.
- **Configuración SMTP:** Integración con Gmail usando credenciales seguras.

### 🎨 Interfaz de Usuario
- **Diseño Responsivo:** Compatible con dispositivos móviles y desktop.
- **Navegación Intuitiva:** Barra de navegación fija con enlaces claros.
- **Validación en Tiempo Real:** Mensajes de error y éxito inmediatos.
- **Estilos Modernos:** Uso de colores, sombras y gradientes.

### 🗄️ Base de Datos
- **Modelo Relacional:** Tabla de usuarios con integridad referencial.
- **Migraciones Automáticas:** Sistema de versionado de esquema de BD.
- **ORM Integrado:** SQLModel para consultas seguras.

## Requisitos Funcionales Cumplidos
- ✅ Gestión de usuarios con roles (Ciudadano, Funcionario, Administrador)
- ✅ Registro seguro con validación de datos
- ✅ Inicio de sesión con autenticación
- ✅ Envío de notificaciones por correo
- ✅ Interfaz web intuitiva y accesible
- ✅ Cumplimiento con estándares de seguridad

## Próximos Pasos
- **Sprint 2:** Implementar modelo y formulario para PQRS
- **Sprint 3:** Sistema de seguimiento y notificaciones avanzadas
- **Sprint 4:** Panel de administración para funcionarios
- **Sprint 5:** Módulos de reportes y estadísticas

## Conclusión
Este proyecto representa el primer paso hacia la digitalización completa del proceso de atención al ciudadano en empresas públicas. La implementación del Sprint 1 establece una base sólida para el desarrollo de funcionalidades más avanzadas, garantizando seguridad, usabilidad y escalabilidad del sistema.
- Implementar módulos adicionales según sprints.
- Integrar notificaciones por email.
- Desplegar en producción.