from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.exceptions import register_exception_handlers
from middleware.audit import add_audit_logging
from middleware.rate_limit import add_rate_limiting
from routers import processing_stage, scenario_results, value_calculation
from routers.activation import router as activation_router
from routers.auth import router as auth_router
from routers.batch_history import router as batch_history_router
from routers.decision_support import router as decision_support_router
from routers.email_mfa import router as email_mfa_router
from routers.mfa import router as mfa_router
from routers.mineral_batch import router as mineral_batch_router
from routers.password_reset import router as password_reset_router
from routers.scenarios import router as scenario_router
from routers.users import router as users_router

app = FastAPI(title="Rica", version="0.1.0")

_allowed_origins = [
    o.strip() for o in (settings.cors_origins or "").split(",") if o.strip()
] or ["http://localhost:3000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_origin_regex=None,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "Origin"],
    expose_headers=[],
    max_age=600,
)

register_exception_handlers(app)

add_rate_limiting(app)
add_audit_logging(app)

app.include_router(processing_stage.router)
app.include_router(scenario_results.router)
app.include_router(value_calculation.router, prefix="/values")
app.include_router(scenario_router)
app.include_router(mineral_batch_router)
app.include_router(batch_history_router)
app.include_router(decision_support_router)
app.include_router(users_router)
app.include_router(auth_router)
app.include_router(activation_router)
app.include_router(mfa_router)
app.include_router(email_mfa_router)
app.include_router(password_reset_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
