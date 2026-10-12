"""HTTP layer. Thin on purpose: every route calls one method on ``Dreamlog``."""

from __future__ import annotations

import logging
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, FastAPI, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import JSONResponse

from .audio import AudioDecodeError
from .config import Settings, get_settings
from .illustrate.palette import mood_colours
from .models import AtlasOut, DeletedOut, EntryOut, GraphOut, MonthOut, PrivacyOut, SearchOut, SeedStatus, TextIn
from .service import Dreamlog, NotFound, build_services

log = logging.getLogger("dreamlog")

MAX_UPLOAD_BYTES = 30 * 1024 * 1024
DISCLAIMER = (
    "Dreamlog reports patterns only. It counts which symbols recur and which appear together. "
    "It does not interpret dreams and it is not medical or psychological advice."
)
_SUFFIX = {
    "audio/webm": ".webm", "audio/ogg": ".ogg", "audio/mp4": ".m4a", "audio/x-m4a": ".m4a", "audio/aac": ".aac",
    "audio/mpeg": ".mp3", "audio/wav": ".wav", "audio/x-wav": ".wav", "audio/aiff": ".aiff", "video/webm": ".webm",
}  # fmt: skip
_PRIVATE = "private, max-age=31536000, immutable"


def create_app(settings: Settings | None = None, *, warm: bool = True) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        core = Dreamlog(build_services(settings))
        app.state.core = core
        app.state.ready = not warm

        def load() -> None:
            try:
                core.warm()
            except Exception:
                log.exception("could not load the models; the first recording will retry")
            app.state.ready = True

        if warm:
            threading.Thread(target=load, name="warm", daemon=True).start()
        yield
        core.s.db.close()

    app = FastAPI(title="Dreamlog", version="0.1.0", lifespan=lifespan)
    api = APIRouter(prefix="/api")

    def core(request: Request) -> Dreamlog:
        return request.app.state.core  # type: ignore[no-any-return]

    @app.exception_handler(NotFound)
    async def not_found(_request: Request, _exc: NotFound) -> JSONResponse:
        return JSONResponse({"detail": "not found"}, status_code=404)

    @app.exception_handler(ValueError)
    async def bad_request(_request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=400)

    @api.get("/health")
    def health(request: Request) -> dict[str, object]:
        return {"status": "ok", "models_ready": bool(request.app.state.ready)}

    @api.get("/meta")
    def meta() -> dict[str, object]:
        return {"disclaimer": DISCLAIMER, "moods": mood_colours()}

    @api.post("/entries/audio", response_model=EntryOut, status_code=201)
    def create_from_audio(request: Request, file: Annotated[UploadFile, File()]) -> EntryOut:
        data = file.file.read(MAX_UPLOAD_BYTES + 1)
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "recording is larger than 30 MB")
        if not data:
            raise HTTPException(400, "the recording is empty")
        kind = (file.content_type or "").split(";")[0].strip().lower()
        suffix = _SUFFIX.get(kind) or Path(file.filename or "").suffix.lower() or ".webm"
        try:
            return core(request).create_from_audio(data, suffix)
        except AudioDecodeError as exc:
            raise HTTPException(400, str(exc)) from exc

    @api.post("/entries", response_model=EntryOut, status_code=201)
    def create_from_text(request: Request, body: TextIn) -> EntryOut:
        return core(request).create_from_text(body.text, created_at=body.created_at)

    @api.get("/entries", response_model=list[EntryOut])
    def list_entries(request: Request, symbol: int | None = None) -> list[EntryOut]:
        return core(request).list_entries(symbol)

    @api.get("/entries/{entry_id}", response_model=EntryOut)
    def get_entry(request: Request, entry_id: UUID) -> EntryOut:
        return core(request).get_entry(entry_id)

    @api.put("/entries/{entry_id}", response_model=EntryOut)
    def update_entry(request: Request, entry_id: UUID, body: TextIn) -> EntryOut:
        return core(request).update_entry(entry_id, body.text)

    @api.delete("/entries/{entry_id}", status_code=204)
    def delete_entry(request: Request, entry_id: UUID) -> Response:
        core(request).delete_entry(entry_id)
        return Response(status_code=204)

    @api.get("/entries/{entry_id}/image")
    def entry_image(request: Request, entry_id: UUID, size: str = "full") -> Response:
        data = core(request).entry_image(entry_id, thumb=size == "thumb")
        return Response(data, media_type="image/webp", headers={"Cache-Control": _PRIVATE})

    @api.get("/graph", response_model=GraphOut)
    def graph(request: Request) -> GraphOut:
        return core(request).graph()

    @api.get("/search", response_model=SearchOut)
    def search(request: Request, q: Annotated[str, Query(min_length=1, max_length=200)]) -> SearchOut:
        return core(request).search(q)

    @api.get("/months", response_model=list[MonthOut])
    def months(request: Request) -> list[MonthOut]:
        return core(request).months()

    @api.get("/atlas/{month}", response_model=AtlasOut)
    def atlas(request: Request, month: str) -> AtlasOut:
        return core(request).atlas(month)

    @api.get("/atlas/{month}/image")
    def atlas_image(request: Request, month: str, format: str = "webp", download: bool = False) -> Response:
        fmt = "png" if format == "png" else "webp"
        data = core(request).atlas_image(month, fmt)
        headers = {"Cache-Control": _PRIVATE}
        if download:
            headers["Content-Disposition"] = f'attachment; filename="dream-atlas-{month}.{fmt}"'
        return Response(data, media_type=f"image/{fmt}", headers=headers)

    @api.get("/privacy", response_model=PrivacyOut)
    def privacy(request: Request) -> PrivacyOut:
        return core(request).privacy()

    @api.get("/export")
    def export(request: Request) -> Response:
        data = core(request).export_zip()
        return Response(
            data,
            media_type="application/zip",
            headers={"Content-Disposition": 'attachment; filename="dreamlog-export.zip"', "Cache-Control": "no-store"},
        )

    @api.delete("/all", response_model=DeletedOut)
    def delete_all(request: Request, confirm: str = "") -> DeletedOut:
        if confirm != "delete-everything":
            raise HTTPException(400, "pass confirm=delete-everything")
        return core(request).delete_all()

    @api.post("/fixtures/load", response_model=SeedStatus, status_code=202)
    def load_fixtures(request: Request) -> SeedStatus:
        return core(request).start_seed()

    @api.get("/fixtures/status", response_model=SeedStatus)
    def fixtures_status(request: Request) -> SeedStatus:
        return core(request).seed_status()

    app.include_router(api)
    return app


app = create_app()
