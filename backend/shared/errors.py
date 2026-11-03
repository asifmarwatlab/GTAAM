"""Common error types and the handlers that turn them into clean JSON replies."""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    status_code = 400
    code = "app_error"

    def __init__(self, message: str, *, code: str | None = None, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code


class BadRequest(AppError):
    status_code, code = 400, "bad_request"


class NotFound(AppError):
    status_code, code = 404, "not_found"


class Conflict(AppError):
    status_code, code = 409, "conflict"


class NotAvailable(AppError):
    status_code, code = 501, "not_available"


def _reply(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": code, "message": message})


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError):
        return _reply(exc.status_code, exc.code, exc.message)

    @app.exception_handler(FileNotFoundError)
    async def _missing_file(_: Request, exc: FileNotFoundError):
        return _reply(404, "file_not_found", str(exc))

    @app.exception_handler(ImportError)
    async def _missing_dep(_: Request, exc: ImportError):
        return _reply(501, "dependency_missing", str(exc))

    @app.exception_handler(ValueError)
    async def _value_error(_: Request, exc: ValueError):
        # core/ raises plain ValueError for bad input (e.g. "DEMs do not overlap")
        return _reply(400, "invalid_value", str(exc))
