import time
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, StringConstraints
from sqlalchemy import ForeignKey, Integer, String, Text, select
from sqlalchemy.orm import Mapped, Session, mapped_column

if __package__ == "hr_services":
    from database import Base, User
else:
    from ..database import Base, User


class HRMessage(Base):
    __tablename__ = "hr_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    service: Mapped[str] = mapped_column(String(40))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[int] = mapped_column(Integer)


class SalaryMessageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=3000),
    ]


class SalaryMessageSent(BaseModel):
    id: int
    service: str
    created_at: datetime
    confirmation: str


class HRInboxMessage(BaseModel):
    id: int
    employee_id: int
    employee_name: str
    service: str
    message: str
    created_at: datetime


def create_salary_router(get_db, require_user, require_admin, require_csrf) -> APIRouter:
    router = APIRouter()

    @router.post(
        "/api/v1/hr/services/salary/messages",
        response_model=SalaryMessageSent,
        status_code=201,
        dependencies=[Depends(require_csrf)],
    )
    def send_salary_message(
        payload: SalaryMessageCreate,
        employee: User = Depends(require_user),
        db: Session = Depends(get_db),
    ):
        entry = HRMessage(
            employee_id=employee.id,
            service="salary",
            message=payload.message,
            created_at=int(time.time()),
        )
        db.add(entry)
        db.commit()

        return SalaryMessageSent(
            id=entry.id,
            service=entry.service,
            created_at=datetime.fromtimestamp(entry.created_at, tz=timezone.utc),
            confirmation="Your salary inquiry was sent to HR.",
        )

    @router.get(
        "/api/v1/admin/hr/messages",
        response_model=list[HRInboxMessage],
        dependencies=[Depends(require_admin)],
    )
    def get_hr_inbox(
        db: Session = Depends(get_db),
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
        before_id: Annotated[int | None, Query(gt=0)] = None,
    ):
        query = select(HRMessage, User.name).join(
            User, User.id == HRMessage.employee_id
        )
        if before_id is not None:
            query = query.where(HRMessage.id < before_id)

        rows = db.execute(query.order_by(HRMessage.id.desc()).limit(limit))
        return [
            HRInboxMessage(
                id=entry.id,
                employee_id=entry.employee_id,
                employee_name=employee_name,
                service=entry.service,
                message=entry.message,
                created_at=datetime.fromtimestamp(entry.created_at, tz=timezone.utc),
            )
            for entry, employee_name in rows
        ]

    return router