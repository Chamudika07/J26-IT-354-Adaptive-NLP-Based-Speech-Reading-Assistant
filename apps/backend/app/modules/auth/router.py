"""Only the four approved authentication endpoints; no account administration."""

from fastapi import APIRouter, Response

from app.modules.auth import service
from app.modules.auth.dependencies import Authenticated, Database, RuntimeSettings
from app.modules.auth.schemas import LoginRequest, MeResponse, RefreshRequest, TokenResponse

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest, response: Response, db: Database, settings: RuntimeSettings
) -> TokenResponse:
    response.headers["Cache-Control"] = "no-store"
    return service.login(db, settings, payload.login_handle, payload.password.get_secret_value())


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    payload: RefreshRequest, response: Response, db: Database, settings: RuntimeSettings
) -> TokenResponse:
    response.headers["Cache-Control"] = "no-store"
    return service.refresh(db, settings, payload.refresh_token.get_secret_value())


@router.post("/logout", status_code=204)
def logout(payload: RefreshRequest, db: Database) -> Response:
    service.logout(db, payload.refresh_token.get_secret_value())
    return Response(status_code=204, headers={"Cache-Control": "no-store"})


@router.get("/me", response_model=MeResponse)
def me(principal: Authenticated, response: Response) -> MeResponse:
    response.headers["Cache-Control"] = "no-store"
    return MeResponse(
        user_id=principal.user_id,
        login_handle=principal.login_handle,
        status=principal.status,
        roles=sorted(principal.roles),
    )
