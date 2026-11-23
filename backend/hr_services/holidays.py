import time
from datetime import date, datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator
from sqlalchemy import Date, ForeignKey, Integer, Text, select
from sqlalchemy.orm import Mapped, Session, mapped_column

if __package__ == "hr_services":
    from database import Base, User
else:
    from ..database import Base, User


class HolidayRequest(Base):
    __tablename__ = "holiday_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[int] = mapped_column(Integer)


class HolidayRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_date: date
    end_date: date
    reason: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=3000),
    ]

    @model_validator(mode="after")
    def validate_date_range(self):
        if self.end_date < self.start_date:
            raise ValueError("The end date must be on or after the start date.")
        return self


class HolidayRequestSent(BaseModel):
    id: int
    start_date: date
    end_date: date
    created_at: datetime
    confirmation: str


class AdminHolidayRequest(BaseModel):
    id: int
    employee_id: int
    employee_name: str
    start_date: date
    end_date: date
    reason: str
    created_at: datetime


def create_holidays_router(get_db, require_user, require_admin, require_csrf) -> APIRouter:
    router = APIRouter()

    @router.post(
        "/api/v1/hr/services/holidays/requests",
        response_model=HolidayRequestSent,
        status_code=201,
        dependencies=[Depends(require_csrf)],
    )
    def create_holiday_request(
        payload: HolidayRequestCreate,
        employee: User = Depends(require_user),
        db: Session = Depends(get_db),
    ):
        entry = HolidayRequest(
            employee_id=employee.id,
            start_date=payload.start_date,
            end_date=payload.end_date,
            reason=payload.reason,
            created_at=int(time.time()),
        )
        db.add(entry)
        db.commit()

        return HolidayRequestSent(
            id=entry.id,
            start_date=entry.start_date,
            end_date=entry.end_date,
            created_at=datetime.fromtimestamp(entry.created_at, tz=timezone.utc),
            confirmation="Your holiday request was sent to HR.",
        )

    @router.get(
        "/api/v1/admin/hr/holiday-requests",
        response_model=list[AdminHolidayRequest],
        dependencies=[Depends(require_admin)],
    )
    def get_holiday_requests(
        db: Session = Depends(get_db),
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
        before_id: Annotated[int | None, Query(gt=0)] = None,
    ):
        query = select(HolidayRequest, User.name).join(
            User, User.id == HolidayRequest.employee_id
        )
        if before_id is not None:
            query = query.where(HolidayRequest.id < before_id)

        rows = db.execute(query.order_by(HolidayRequest.id.desc()).limit(limit))
        return [
            AdminHolidayRequest(
                id=entry.id,
                employee_id=entry.employee_id,
                employee_name=employee_name,
                start_date=entry.start_date,
                end_date=entry.end_date,
                reason=entry.reason,
                created_at=datetime.fromtimestamp(entry.created_at, tz=timezone.utc),
            )
            for entry, employee_name in rows
        ]

    return router