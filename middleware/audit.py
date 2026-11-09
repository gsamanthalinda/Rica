import os
from datetime import datetime, timezone
from typing import Callable

from fastapi import FastAPI, Request


def add_audit_logging(app: FastAPI):
    if os.getenv("TESTING") == "1":
        return

    from database import get_db

    @app.middleware("http")
    async def audit_middleware(request: Request, call_next: Callable):
        response = await call_next(request)

        from models import AuditLog

        action = f"{request.method} {request.url.path}"
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")

        db = next(get_db())
        try:
            user_id = None
            auth_header = request.headers.get("authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
                try:
                    from core.auth import decode_token

                    payload = decode_token(token)
                    user_id = payload.get("user_id")
                except Exception:
                    pass

            audit = AuditLog(
                user_id=user_id,
                action=action,
                resource=request.url.path,
                ip_address=client_ip,
                user_agent=user_agent,
                timestamp=datetime.now(timezone.utc),
            )
            db.add(audit)
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

        return response
