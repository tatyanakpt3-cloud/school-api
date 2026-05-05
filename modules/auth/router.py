from fastapi import APIRouter, Request, Response
import psycopg2.extras
from core.db import db, now_msk
from core.auth import require_auth, get_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/check")
def check(request: Request):
    user = require_auth(request)
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE school_auth_tokens SET last_login=%s WHERE token=%s",
                (now_msk(), get_token(request)),
            )
    return {"ok": True, "role": user["role"], "name": user["name"],
            "ref_id": user["ref_id"]}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("school_token")
    return {"ok": True}
