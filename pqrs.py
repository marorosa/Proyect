from fastapi import FastAPI
import sqlite3
from datetime import datetime, date, timedelta
import random
from dateutil import parser
from typing import Dict, Any, Optional

app = FastAPI(title="PQRS Reportes")

# --- Configuración: adapta la ruta a tu archivo sqlite ---
SQLITE_DB = "reflex.db"


def parse_dt(v) -> Optional[datetime]:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v
    try:
        return parser.parse(v)
    except Exception:
        return None


def query_db(sql: str, params=()):
    conn = sqlite3.connect(SQLITE_DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(sql, params)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(r) for r in rows]


def load_holidays() -> set:
    """Intenta leer la tabla `festivos(fecha)` de la BD y devolver un set de date.
    Si la tabla no existe, devuelve un conjunto vacío.
    """
    try:
        rows = query_db("SELECT fecha FROM festivos")
    except Exception:
        return set()
    s = set()
    for r in rows:
        f = r.get("fecha")
        if not f:
            continue
        try:
            d = parser.parse(f).date()
            s.add(d)
        except Exception:
            continue
    return s


HOLIDAYS = load_holidays()


def is_business_day(d: date, holidays: set):
    return d.weekday() < 5 and d not in holidays


def business_days_between(start: date, end: date, holidays: set) -> int:
    if end < start:
        return 0
    days = 0
    cur = start
    while cur <= end:
        if is_business_day(cur, holidays):
            days += 1
        cur += timedelta(days=1)
    return days


def legal_days_for(tipo: str, detalle: Optional[str] = None) -> int:
    if not tipo:
        return 15
    t = tipo.lower()
    d = (detalle or "").lower()
    if "consulta" in d or t == "consulta":
        return 30
    if "inform" in d or "copia" in d or "informacion" in d:
        return 10
    if t in ("peticion", "petición", "queja", "reclamo", "sugerencia"):
        return 15
    return 15


def compute_remaining_and_color(row: Dict[str, Any], today: date, holidays: set):
    tipo = row.get("tipo_pqrs")
    detalle = row.get("tipo_detalle") or row.get("subtipo") or None
    legal = legal_days_for(tipo, detalle)
    fr = parse_dt(row.get("fecha_radicado"))
    if not fr:
        return {"remaining": None, "color": "unknown", "legal_days": legal}
    start = fr.date() + timedelta(days=1)
    ref = today
    if row.get("fecha_respuesta"):
        resp = parse_dt(row.get("fecha_respuesta"))
        if resp:
            ref = resp.date()
    used = business_days_between(start, ref, holidays)
    remaining = legal - used
    if remaining <= 0:
        color = "rojo"
    elif remaining <= 5:
        color = "amarillo"
    else:
        color = "verde"
    return {"remaining": remaining, "color": color, "legal_days": legal, "used_business_days": used}


@app.get("/api/semaforo")
def api_semaforo():
    today = date.today()
    HOL = load_holidays() or HOLIDAYS
    sql = """
        SELECT id_radicado, tipo_pqrs, estado, fecha_radicado, fecha_respuesta
        FROM solicitudes
        WHERE estado IN ('Radicada','En proceso')
        """
    rows = query_db(sql)
    counts = {"verde": 0, "amarillo": 0, "rojo": 0}
    items = []
    for r in rows:
        info = compute_remaining_and_color(r, today, HOL)
        c = info.get("color") or "unknown"
        if c in counts:
            counts[c] += 1
        items.append({
            "id_radicado": r.get("id_radicado"),
            "tipo_pqrs": r.get("tipo_pqrs"),
            "estado": r.get("estado"),
            "remaining": info.get("remaining"),
            "color": c,
            "legal_days": info.get("legal_days")
        })
    return {"counts": counts, "items": items, "total_active": len(rows)}


@app.get("/api/cumplimiento")
def api_cumplimiento():
    HOL = load_holidays() or HOLIDAYS
    sql = """
      SELECT id_radicado, tipo_pqrs, fecha_radicado, fecha_respuesta
      FROM solicitudes
      WHERE fecha_respuesta IS NOT NULL
        AND estado IN ('Respondida','Cerrada')
    """
    rows = query_db(sql)
    if not rows:
        return {"cumplimiento_pct": 0.0, "total_respondidas": 0, "respondidas_a_tiempo": 0, "monthly": []}
    total = 0
    on_time = 0
    monthly_bucket = {}
    for r in rows:
        total += 1
        fr = parse_dt(r.get("fecha_radicado"))
        frp = parse_dt(r.get("fecha_respuesta"))
        if not fr or not frp:
            continue
        start = fr.date() + timedelta(days=1)
        days = business_days_between(start, frp.date(), HOL)
        legal = legal_days_for(r.get("tipo_pqrs"), None)
        ok = days <= legal
        if ok:
            on_time += 1
        ym = frp.date().strftime("%Y-%m")
        b = monthly_bucket.setdefault(ym, {"total": 0, "on_time": 0})
        b["total"] += 1
        if ok:
            b["on_time"] += 1
    cumplimiento_pct = (on_time / total * 100) if total else 0.0
    monthly = [{"month": k, "total": v["total"], "on_time": v["on_time"], "pct": round((v["on_time"] / v["total"] * 100) if v["total"] else 0, 2)} for k, v in sorted(monthly_bucket.items())]
    return {"cumplimiento_pct": round(cumplimiento_pct, 2), "total_respondidas": total, "respondidas_a_tiempo": on_time, "monthly": monthly}


@app.get("/api/timeseries")
def api_timeseries(simulate: bool = False):
    """Return daily avg response times for last 30 days.
    If `simulate=true` is passed as a query param, any computed 0-day responses
    will be replaced with a random 1-5 day value to help testing visualization.
    """
    HOL = load_holidays() or HOLIDAYS
    # Return daily average response times for the last 30 days (inclusive).
    rows = query_db("SELECT id_radicado, tipo_pqrs, fecha_radicado, fecha_respuesta, estado FROM solicitudes WHERE fecha_respuesta IS NOT NULL")
    today = date.today()
    start_date = today - timedelta(days=29)

    # prepare buckets for each day in range
    day_buckets = {}
    for i in range(30):
        d = start_date + timedelta(days=i)
        key = d.strftime("%Y-%m-%d")
        day_buckets[key] = []

    for r in rows:
        try:
            fr = parse_dt(r.get("fecha_radicado"))
            frp = parse_dt(r.get("fecha_respuesta"))
            if not fr or not frp:
                continue
            resp_date = frp.date()
            if resp_date < start_date or resp_date > today:
                continue
            start = fr.date() + timedelta(days=1)
            dias = business_days_between(start, resp_date, HOL)
            # For testing: allow simulation of non-zero days when responses occurred same day
            if simulate and dias == 0:
                dias = random.randint(1, 5)
                print(f"DEBUG - api_timeseries: simulated dias={dias} for {r.get('id_radicado')}")
            key = resp_date.strftime("%Y-%m-%d")
            day_buckets.setdefault(key, []).append(dias)
        except Exception:
            continue

    series = []
    for i in range(30):
        d = start_date + timedelta(days=i)
        key = d.strftime("%Y-%m-%d")
        vals = day_buckets.get(key, [])
        avg = round(sum(vals) / len(vals), 2) if vals else 0.0
        label = d.strftime("%d %b")
        series.append({"date": key, "label": label, "avg_days": avg, "count": len(vals)})

    return {"series": series}
