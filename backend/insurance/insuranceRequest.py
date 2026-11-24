import time
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, StringConstraints
from sqlalchemy import ForeignKey, Integer, String, Text, select
from sqlalchemy.orm import Mapped, Session, mapped_column

if __package__ == "insurance":
    from database import Base, User
else:
    from ..database import Base, User


class InsuranceRequest(Base):
    __tablename__ = "insurance_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    employee_code: Mapped[str] = mapped_column(String(50))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[int] = mapped_column(Integer)


class InsuranceRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    employee_code: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=50),
    ]
    message: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=3000),
    ]


class InsuranceRequestSent(BaseModel):
    id: int
    created_at: datetime
    confirmation: str


class AdminInsuranceRequest(BaseModel):
    id: int
    employee_id: int
    employee_name: str
    employee_code: str
    message: str
    created_at: datetime


def create_insurance_router(get_db, require_user, require_admin, require_csrf) -> APIRouter:
    router = APIRouter()

    @router.post(
        "/api/v1/hr/services/insurance/requests",
        response_model=InsuranceRequestSent,
        status_code=201,
        dependencies=[Depends(require_csrf)],
    )
    def create_insurance_request(
        payload: InsuranceRequestCreate,
        employee: User = Depends(require_user),
        db: Session = Depends(get_db),
    ):
        entry = InsuranceRequest(
            employee_id=employee.id,
            employee_code=payload.employee_code,
            message=payload.message,
            created_at=int(time.time()),
        )
        db.add(entry)
        db.commit()

        return InsuranceRequestSent(
            id=entry.id,
            created_at=datetime.fromtimestamp(entry.created_at, tz=timezone.utc),
            confirmation="Your insurance request has been submitted.",
        )

    @router.get(
        "/api/v1/admin/hr/insurance-requests",
        response_model=list[AdminInsuranceRequest],
        dependencies=[Depends(require_admin)],
    )
    def get_insurance_requests(
        db: Session = Depends(get_db),
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
        before_id: Annotated[int | None, Query(gt=0)] = None,
    ):
        query = select(InsuranceRequest, User.name).join(
            User, User.id == InsuranceRequest.employee_id
        )
        if before_id is not None:
            query = query.where(InsuranceRequest.id < before_id)

        rows = db.execute(query.order_by(InsuranceRequest.id.desc()).limit(limit))
        return [
            AdminInsuranceRequest(
                id=entry.id,
                employee_id=entry.employee_id,
                employee_name=employee_name,
                employee_code=entry.employee_code,
                message=entry.message,
                created_at=datetime.fromtimestamp(entry.created_at, tz=timezone.utc),
            )
            for entry, employee_name in rows
        ]

    return router