from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from ..database import PiHealthRow, SensorReadingRow


def create_router(engine: Engine, templates: Jinja2Templates) -> APIRouter:
    router = APIRouter()

    @router.get("/", response_class=HTMLResponse)
    def overview(request: Request) -> Response:
        with Session(engine) as session:
            readings = (
                session.execute(
                    select(SensorReadingRow)
                    .order_by(desc(SensorReadingRow.timestamp))
                    .limit(50)
                )
                .scalars()
                .all()
            )
            health = session.execute(
                select(PiHealthRow).order_by(desc(PiHealthRow.timestamp)).limit(1)
            ).scalar_one_or_none()
        return templates.TemplateResponse(
            request,
            "overview.html",
            {"readings": readings, "health": health},
        )

    @router.get("/api/temperatures")
    def api_temperatures() -> list[dict[str, object]]:
        with Session(engine) as session:
            rows = (
                session.execute(
                    select(SensorReadingRow)
                    .order_by(desc(SensorReadingRow.timestamp))
                    .limit(50)
                )
                .scalars()
                .all()
            )
        return [
            {
                "sensor_id": r.sensor_id,
                "sensor_name": r.sensor_name,
                "temperature_c": r.temperature_c,
                "temperature_f": r.temperature_f,
                "read_quality": r.read_quality,
                "timestamp": r.timestamp.isoformat() if r.timestamp else None,
            }
            for r in rows
        ]

    @router.get("/api/health")
    def api_health() -> dict[str, object]:
        with Session(engine) as session:
            row = session.execute(
                select(PiHealthRow).order_by(desc(PiHealthRow.timestamp)).limit(1)
            ).scalar_one_or_none()
        if row is None:
            return {}
        return {
            "cpu_temp_c": row.cpu_temp_c,
            "cpu_percent": row.cpu_percent,
            "memory_percent": row.memory_percent,
            "disk_percent": row.disk_percent,
            "timestamp": row.timestamp.isoformat() if row.timestamp else None,
        }

    return router
