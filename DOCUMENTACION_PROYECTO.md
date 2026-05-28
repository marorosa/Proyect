# Documentación del Proyecto PQRS

## Nivel de Cumplimiento

El porcentaje del Nivel de Cumplimiento (el número grande que aparece en el centro de la gráfica de dona) se calcula con una fórmula muy directa y transparente.

Actualmente, el sistema hace esta matemática:

1. **Toma el Total:** Cuenta todas las solicitudes que existen (o que estén filtradas en el dashboard). En tu caso, son 139 solicitudes totales.
2. **Identifica las Cerradas:** Cuenta cuántas de esas solicitudes están en un estado que indique finalización (específicamente lee las que dicen Cerrada, Resuelta, Respondida o Finalizada). En tu caso, son 23.
3. **Calcula el Porcentaje:** Divide las cerradas entre el total y lo multiplica por 100.
   * `(23 / 139) * 100 = 16.54%`

---

## Gráfica de Tiempos Promedio de Respuesta

La gráfica de "Tiempos Promedio de Respuesta" (ubicada en el dashboard de reportes) muestra la eficiencia histórica del equipo al resolver las solicitudes ciudadanas a lo largo de los últimos 30 días.

### ¿Qué representa esta gráfica?
El eje vertical (Y) representa la **cantidad de días hábiles** que tomó cerrar o responder una solicitud.
El eje horizontal (X) representa los **días del mes** (los últimos 30 días calendario consecutivos).

### ¿Cómo y cuándo se mueve la gráfica?
La gráfica es 100% dinámica, sin simulaciones, y se calcula en tiempo real con base en el rendimiento puro de los funcionarios:

1. **Condición para aparecer en la gráfica:**
   Una solicitud *solo* alimenta esta gráfica cuando un funcionario la pasa a un estado de cierre definitivo (estado `Respondida`, `Cerrada`, `Finalizada` o `Resuelta`). Las solicitudes que siguen "En Proceso" o "Asignadas" no generan puntos aquí, pues aún no tienen un tiempo de respuesta final.

2. **Cálculo del Tiempo de Respuesta (Días Hábiles):**
   En el momento exacto en que se cierra una solicitud, el sistema hace una resta entre la `fecha_radicado` (creación original) y la `fecha_respuesta` (cierre). 
   El sistema está diseñado para contar únicamente **días hábiles** descartando por completo los fines de semana.

3. **Promedio Diario:**
   Es común que en un solo día se cierren múltiples PQRS. Si hoy se cierran 3 solicitudes (una que tardó 2 días, otra 4 días y otra 6 días), el sistema promedia esos tiempos: `(2 + 4 + 6) / 3 = 4.0 días`.
   En ese caso, el punto del día de hoy en la gráfica se ubicará exactamente en la altura del `4.0`.

4. **El Movimiento Diario (Subidas y Bajadas):**
   * **Picos Altos (Sube):** La gráfica se dispara hacia arriba en aquellos días donde los funcionarios cerraron solicitudes muy "viejas" o atrasadas (que acumularon muchos días hábiles de demora).
   * **Valle/Línea Plana en Cero (Baja):** La gráfica baja a `0` si los funcionarios son ultra-eficientes. Si un ciudadano radica una solicitud hoy y el funcionario la responde y cierra hoy mismo, el tiempo de demora es de `0` días hábiles.
   * **Días sin Actividad:** Si en un día específico del mes no se cerró *ninguna* solicitud, el valor de ese día caerá a `0`, indicando que no hubo tiempos de demora registrados porque no hubo respuestas.

## Envío de correos con SMTP

Todo el flujo de notificaciones usa **SMTP** (`notificaciones.enviar_correo_smtp`).

1. **SMTP** — variables `EMAIL_SENDER`, `EMAIL_PASSWORD`, `SMTP_SERVER`, `SMTP_PORT`.
2. **Log local** — si falla, el mensaje se escribe en `failed_emails.log`.

### Reintento de correos fallidos
- `python scripts/retry_failed_emails.py` reenvía los correos pendientes por SMTP.

### Variables de entorno
| Variable | Descripción |
|----------|-------------|
| `EMAIL_SENDER` | Dirección de envío. |
| `EMAIL_PASSWORD` | Contraseña o app password (Gmail). |
| `SMTP_SERVER` | Servidor SMTP (ej. `smtp.gmail.com`). |
| `SMTP_PORT` | Puerto SMTP (ej. `587`). |
| `EMPRESA_NOMBRE` | Nombre en las plantillas. |
| `APP_URL` | URL pública de la app (ej. `https://pqrs.tudominio.gov.co`). Si no está o es `localhost`, los archivos se envían **adjuntos** en el correo en lugar de un enlace. |

Esta documentación está ahora disponible en **DOCUMENTACION_PROYECTO.md**.