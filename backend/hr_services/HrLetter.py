import time
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, StringConstraints
from sqlalchemy.orm import Session

if __package__ == "hr_services":
    from database import User
    from hr_services.salary import HRMessage
else:
    from ..database import User
    from .salary import HRMessage


class HRLetterRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=3000),
    ]


class HRLetterRequestSent(BaseModel):
    id: int
    service: str
    created_at: datetime
    confirmation: str


def create_hr_letter_router(get_db, require_user, require_csrf) -> APIRouter:
    router = APIRouter()

    @router.post(
        "/api/v1/hr/services/hr-letter/requests",
        response_model=HRLetterRequestSent,
        status_code=201,
        dependencies=[Depends(require_csrf)],
    )
    def create_hr_letter_request(
        payload: HRLetterRequestCreate,
        employee: User = Depends(require_user),
        db: Session = Depends(get_db),
    ):
        entry = HRMessage(
            employee_id=employee.id,
            service="hr_letter",
            message=payload.message,
            created_at=int(time.time()),
        )
        db.add(entry)
        db.commit()

        return HRLetterRequestSent(
            id=entry.id,
            service=entry.service,
            created_at=datetime.fromtimestamp(entry.created_at, tz=timezone.utc),
            confirmation="Your HR Letter request was sent to HR.",
        )

    return router