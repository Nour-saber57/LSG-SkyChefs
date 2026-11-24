from contextlib import asynccontextmanager
import hashlib
import re
import secrets
import time
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from pwdlib import PasswordHash

from sqlalchemy import (
    ForeignKey,
    Integer,
    String,
    create_engine,
    delete,
    inspect,
    select,
    update,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import (
    Mapped,
    Session,
    mapped_column,
    sessionmaker,
)

from starlette.middleware.trustedhost import TrustedHostMiddleware
if __package__ == "login":
    from database import Base, User
    from hr_services.HrLetter import create_hr_letter_router
    from hr_services.holidays import create_holidays_router
    from hr_services.salary import create_salary_router
    from insurance.insuranceRequest import create_insurance_router
else:
    from ..database import Base, User
    from ..hr_services.HrLetter import create_hr_letter_router
    from ..hr_services.holidays import create_holidays_router
    from ..hr_services.salary import create_salary_router
    from ..insurance.insuranceRequest import create_insurance_router

# --------------------------------------------------
# Configuration
# --------------------------------------------------

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        extra="ignore",
    )

    database_url: str = "sqlite:///./skychef.db"
    cookie_secure: bool = True

    frontend_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

    allowed_hosts: list[str] = [
        "localhost",
        "127.0.0.1",
    ]

    session_hours: int = Field(
        default=8,
        ge=1,
        le=24,
    )


# --------------------------------------------------
# Database models
# --------------------------------------------------


class LoginSession(Base):
    __tablename__ = "login_sessions"

    token_hash: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        index=True,
    )

    csrf_hash: Mapped[str] = mapped_column(String(64))

    expires_at: Mapped[int] = mapped_column(
        Integer,
        index=True,
    )


class LoginLimit(Base):
    __tablename__ = "login_limits"

    key: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
    )

    hits: Mapped[int] = mapped_column(Integer)

    expires_at: Mapped[int] = mapped_column(
        Integer,
        index=True,
    )


def initialize_database(engine):
    with engine.begin() as connection:
        Base.metadata.create_all(connection)
        if connection.dialect.name == "sqlite":
            create_view = "CREATE VIEW IF NOT EXISTS"
            existing_views = ()
        else:
            create_view = "CREATE VIEW"
            existing_views = inspect(connection).get_view_names()

        # The users table owns the role and keeps each identity unique.
        for view, role in (("admin_emails", "admin"), ("employee_emails", "user")):
            if view not in existing_views:
                connection.exec_driver_sql(
                    f"{create_view} {view} AS "
                    "SELECT identity AS email, name, active FROM users "
                    f"WHERE role = '{role}' AND identity LIKE '%@%'"
                )


# --------------------------------------------------
# Request / response schemas
# --------------------------------------------------

class Credentials(BaseModel):
    # Reject fields such as a client-supplied role.
    model_config = ConfigDict(extra="forbid")

    identity: str = Field(
        min_length=1,
        max_length=254,
        validation_alias=AliasChoices("identity", "email"),
    )

    password: SecretStr = Field(
        min_length=1,
        max_length=1024,
    )


class PublicUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    identity: str
    name: str
    role: str


class LoginResult(BaseModel):
    user: PublicUser
    redirect_to: str
    csrf_token: str


class AccountCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    identity: str = Field(
        min_length=1,
        max_length=254,
        validation_alias=AliasChoices("identity", "email"),
    )
    name: str = Field(min_length=1, max_length=150)
    password: SecretStr = Field(min_length=12, max_length=1024)


# --------------------------------------------------
# Security utilities
# --------------------------------------------------

passwords = PasswordHash.recommended()

# Used when an account does not exist, so password
# verification still runs.
DUMMY_HASH = passwords.hash(
    secrets.token_urlsafe(32)
)

COOKIE_NAME = "skychef_session"


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def normalize_work_email(value: str) -> str:
    email = value.strip().casefold()
    if len(email) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@.]+(?:\.[^\s@.]+)+", email):
        raise ValueError("Provide a valid work email.")
    return email


LOGIN_PAGE = """<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SkyChef sign in</title>
<style>
  body { max-width: 26rem; margin: 12vh auto; padding: 0 1rem;
         font: 1rem system-ui, sans-serif; color: #172536; background: #f5f7fa; }
  main { padding: 2rem; background: white; border: 1px solid #d6dde5; border-radius: 1rem; }
  h1 { margin-top: 0; }
  #login { display: grid; gap: 0.5rem; }
  input, button { font: inherit; padding: 0.65rem; border-radius: 0.4rem; }
  input { border: 1px solid #687b90; margin-bottom: 0.5rem; }
  button { color: white; background: #173f66; border: 0; cursor: pointer; }
  #login-error { color: #9c2832; }
  #login-error:empty { display: none; }
</style>
<main>
  <h1>Sign in to SkyChef</h1>
  <form id="login" method="post">
    <label for="identity">Work email or employee ID</label>
    <input id="identity" name="identity" autocomplete="username" maxlength="254" required>
    <label for="password">Password</label>
    <input id="password" name="password" type="password" autocomplete="current-password"
           maxlength="1024" required>
    <button type="submit">Sign in</button>
    <p id="login-error" role="alert"></p>
  </form>
</main>
<script>
  const form = document.querySelector('#login');
  const button = form.querySelector('button');
  const error = document.querySelector('#login-error');
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    button.disabled = true;
    error.textContent = '';
    try {
      const response = await fetch('/api/v1/auth/login', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(Object.fromEntries(new FormData(form)))
      });
      if (response.ok) {
        const { redirect_to } = await response.json();
        window.location.assign(redirect_to);
        return;
      }
      error.textContent = response.status === 429
        ? 'Too many sign-in attempts. Try again later.'
        : 'Unable to sign in. Check your email or employee ID and password.';
    } catch {
      error.textContent = 'Unable to reach SkyChef. Try again.';
    } finally {
      button.disabled = false;
    }
  });
</script>
</html>"""


# --------------------------------------------------
# Application factory
# --------------------------------------------------

def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    frontend_dir = Path(__file__).resolve().parents[2] / "frontend"

    connect_args = {}
    database_url = settings.database_url

    if database_url.startswith("sqlite:///./"):
        database_file = (
            Path(__file__).resolve().parents[1]
            / database_url.removeprefix("sqlite:///./")
        )
        database_url = f"sqlite:///{database_file.as_posix()}"

    if database_url.startswith("sqlite"):
        connect_args = {
            "check_same_thread": False
        }

    engine = create_engine(
        database_url,
        connect_args=connect_args,
        pool_pre_ping=True,
    )

    session_factory = sessionmaker(
        engine,
        expire_on_commit=False,
    )

    @asynccontextmanager
    async def lifespan(app):
        # Suitable for this starter.
        # Introduce migrations before production.
        initialize_database(engine)

        yield

        engine.dispose()

    app = FastAPI(
        title="SkyChef Authentication API",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.state.session_factory = session_factory
    app.state.settings = settings
    app.mount(
        "/assets",
        StaticFiles(directory=frontend_dir),
        name="assets",
    )

    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.allowed_hosts,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.frontend_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=[
            "Content-Type",
            "X-CSRF-Token",
        ],
    )

    # --------------------------------------------------
    # Request protections
    # --------------------------------------------------

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        origin = request.headers.get("origin")

        if (
            request.method not in {"GET", "HEAD", "OPTIONS"}
            and origin
            and origin not in settings.frontend_origins
        ):
            return JSONResponse(
                {"detail": "Origin not allowed"},
                status_code=403,
            )

        response = await call_next(request)

        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"

        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # Do not echo submitted passwords in errors.
        errors = [
            {
                "loc": list(error["loc"]),
                "msg": error["msg"],
                "type": error["type"],
            }
            for error in exc.errors()
        ]

        return JSONResponse(
            {"detail": errors},
            status_code=422,
        )

    # --------------------------------------------------
    # Dependencies
    # --------------------------------------------------

    def get_db():
        with session_factory() as db:
            yield db

    def get_current_session(
        request: Request,
        db: Session = Depends(get_db),
    ):
        token = request.cookies.get(COOKIE_NAME)

        login_session = (
            db.get(LoginSession, digest(token))
            if token
            else None
        )

        user = (
            db.get(User, login_session.user_id)
            if login_session
            else None
        )

        if (
            not login_session
            or login_session.expires_at <= int(time.time())
            or not user
            or not user.active
            or user.role not in {"admin", "user"}
        ):
            raise HTTPException(
                status_code=401,
                detail="Sign in required",
            )

        return login_session, user

    def get_current_user(
        auth=Depends(get_current_session),
    ):
        return auth[1]

    def require_admin(
        user: User = Depends(get_current_user),
    ):
        if user.role != "admin":
            raise HTTPException(
                status_code=403,
                detail="Admin access required",
            )

        return user

    def require_user(
        user: User = Depends(get_current_user),
    ):
        if user.role != "user":
            raise HTTPException(
                status_code=403,
                detail="Employee access required",
            )

        return user

    def require_csrf(request: Request, auth=Depends(get_current_session)):
        token = request.headers.get("X-CSRF-Token", "")
        if not token or not secrets.compare_digest(digest(token), auth[0].csrf_hash):
            raise HTTPException(status_code=403, detail="Invalid CSRF token")
        return auth

    app.include_router(
        create_salary_router(
            get_db=get_db,
            require_user=require_user,
            require_admin=require_admin,
            require_csrf=require_csrf,
        )
    )
    app.include_router(
        create_hr_letter_router(
            get_db=get_db,
            require_user=require_user,
            require_csrf=require_csrf,
        )
    )
    app.include_router(
        create_holidays_router(
            get_db=get_db,
            require_user=require_user,
            require_admin=require_admin,
            require_csrf=require_csrf,
        )
    )
    app.include_router(
        create_insurance_router(
            get_db=get_db,
            require_user=require_user,
            require_admin=require_admin,
            require_csrf=require_csrf,
        )
    )

    # --------------------------------------------------
    # Login throttling
    # --------------------------------------------------

    def check_rate_limit(
        db: Session,
        key: str,
        maximum: int,
        period: int,
    ):
        now = int(time.time())

        bucket = digest(
            f"{key}:{now // period}"
        )

        result = db.execute(
            update(LoginLimit)
            .where(LoginLimit.key == bucket)
            .values(hits=LoginLimit.hits + 1)
        )

        if not result.rowcount:
            db.add(
                LoginLimit(
                    key=bucket,
                    hits=1,
                    expires_at=(now // period + 1) * period,
                )
            )

            try:
                db.commit()

            except IntegrityError:
                db.rollback()

                db.execute(
                    update(LoginLimit)
                    .where(LoginLimit.key == bucket)
                    .values(hits=LoginLimit.hits + 1)
                )

        db.commit()

        item = db.get(LoginLimit, bucket)

        if item.hits > maximum:
            retry_after = max(
                1,
                item.expires_at - now,
            )

            raise HTTPException(
                status_code=429,
                detail="Too many sign-in attempts. Try again later.",
                headers={
                    "Retry-After": str(retry_after)
                },
            )

    # --------------------------------------------------
    # Shared login logic
    # --------------------------------------------------

    def perform_login(
        payload: Credentials,
        request: Request,
        response: Response,
        db: Session,
        expected_role: str | None,
    ):
        identity = payload.identity.strip().casefold()

        ip = (
            request.client.host
            if request.client
            else "unknown"
        )

        check_rate_limit(
            db,
            key=f"ip:{ip}",
            maximum=30,
            period=60,
        )

        check_rate_limit(
            db,
            key=f"identity:{identity}",
            maximum=10,
            period=900,
        )

        user = db.scalar(
            select(User).where(
                User.identity == identity
            )
        )

        stored_hash = (
            user.password_hash
            if user
            else DUMMY_HASH
        )

        valid_password = passwords.verify(
            payload.password.get_secret_value(),
            stored_hash,
        )

        if (
            not valid_password
            or not user
            or not user.active
            or user.role not in {"admin", "user"}
            or (
                expected_role
                and user.role != expected_role
            )
        ):
            raise HTTPException(
                status_code=401,
                detail="Invalid credentials or account access",
            )

        now = int(time.time())

        # Replace any current session.
        old_token = request.cookies.get(COOKIE_NAME)

        if old_token:
            db.execute(
                delete(LoginSession).where(
                    LoginSession.token_hash == digest(old_token)
                )
            )

        # Remove expired records.
        db.execute(
            delete(LoginSession).where(
                LoginSession.expires_at <= now
            )
        )

        db.execute(
            delete(LoginLimit).where(
                LoginLimit.expires_at <= now
            )
        )

        token = secrets.token_urlsafe(32)
        csrf_token = secrets.token_urlsafe(32)

        lifetime = settings.session_hours * 3600

        db.add(
            LoginSession(
                token_hash=digest(token),
                user_id=user.id,
                csrf_hash=digest(csrf_token),
                expires_at=now + lifetime,
            )
        )

        db.commit()

        response.set_cookie(
            key=COOKIE_NAME,
            value=token,
            max_age=lifetime,
            httponly=True,
            secure=settings.cookie_secure,
            samesite="lax",
            path="/",
        )

        destination = (
            "/admin/dashboard"
            if user.role == "admin"
            else "/dashboard"
        )

        return LoginResult(
            user=PublicUser.model_validate(user),
            redirect_to=destination,
            csrf_token=csrf_token,
        )

    # --------------------------------------------------
    # Login endpoints
    # --------------------------------------------------

    @app.post(
        "/api/v1/auth/register",
        response_model=PublicUser,
        status_code=201,
        dependencies=[Depends(require_admin), Depends(require_csrf)],
    )
    def register_account(
        payload: AccountCreate,
        db: Session = Depends(get_db),
    ):
        try:
            identity = normalize_work_email(payload.identity)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        name = payload.name.strip()

        if not name:
            raise HTTPException(
                status_code=422,
                detail="Name is required",
            )

        existing_user = db.scalar(
            select(User).where(User.identity == identity)
        )

        if existing_user:
            raise HTTPException(
                status_code=409,
                detail="Account already exists",
            )

        user = User(
            identity=identity,
            name=name,
            role="user",
            password_hash=passwords.hash(
                payload.password.get_secret_value()
            ),
            active=True,
        )

        db.add(user)

        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=409,
                detail="Account already exists",
            )

        db.refresh(user)
        return user

    @app.post(
        "/api/v1/auth/user/login",
        response_model=LoginResult,
    )
    def user_login(
        payload: Credentials,
        request: Request,
        response: Response,
        db: Session = Depends(get_db),
    ):
        return perform_login(
            payload,
            request,
            response,
            db,
            expected_role="user",
        )

    @app.post(
        "/api/v1/auth/admin/login",
        response_model=LoginResult,
    )
    def admin_login(
        payload: Credentials,
        request: Request,
        response: Response,
        db: Session = Depends(get_db),
    ):
        return perform_login(
            payload,
            request,
            response,
            db,
            expected_role="admin",
        )

    @app.post(
        "/api/v1/auth/login",
        response_model=LoginResult,
    )
    def shared_login(
        payload: Credentials,
        request: Request,
        response: Response,
        db: Session = Depends(get_db),
    ):
        return perform_login(
            payload,
            request,
            response,
            db,
            expected_role=None,
        )

    # --------------------------------------------------
    # Current account
    # --------------------------------------------------

    @app.get(
        "/api/v1/me",
        response_model=PublicUser,
    )
    def me(
        user: User = Depends(get_current_user),
    ):
        return user

    # --------------------------------------------------
    # CSRF token
    # --------------------------------------------------

    @app.get("/api/v1/auth/csrf")
    def refresh_csrf(
        auth=Depends(get_current_session),
        db: Session = Depends(get_db),
    ):
        token = secrets.token_urlsafe(32)

        db.execute(
            update(LoginSession)
            .where(
                LoginSession.token_hash == auth[0].token_hash
            )
            .values(
                csrf_hash=digest(token)
            )
        )

        db.commit()

        return {
            "csrf_token": token
        }

    # --------------------------------------------------
    # Logout
    # --------------------------------------------------

    @app.post(
        "/api/v1/auth/logout",
        status_code=204,
    )
    def logout(
        response: Response,
        auth=Depends(require_csrf),
        db: Session = Depends(get_db),
    ):
        db.execute(
            delete(LoginSession).where(
                LoginSession.token_hash == auth[0].token_hash
            )
        )

        db.commit()

        response.delete_cookie(
            key=COOKIE_NAME,
            path="/",
            secure=settings.cookie_secure,
            httponly=True,
            samesite="lax",
        )

    # --------------------------------------------------
    # Protected route examples
    # --------------------------------------------------

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def sign_in_page():
        return FileResponse(frontend_dir / "index.html")

    def workspace_page():
        return FileResponse(frontend_dir / "workspace.html")

    @app.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
    def employee_dashboard_page(user: User = Depends(require_user)):
        return workspace_page()

    @app.get("/hr-services", response_class=HTMLResponse, include_in_schema=False)
    def hr_services_page(user: User = Depends(require_user)):
        return workspace_page()

    @app.get("/hr-services/salary", response_class=HTMLResponse, include_in_schema=False)
    def salary_page(user: User = Depends(require_user)):
        return workspace_page()

    @app.get("/hr-services/hr-letter", response_class=HTMLResponse, include_in_schema=False)
    def hr_letter_page(user: User = Depends(require_user)):
        return workspace_page()

    @app.get("/hr-services/holidays", response_class=HTMLResponse, include_in_schema=False)
    def holidays_page(user: User = Depends(require_user)):
        return workspace_page()

    @app.get("/hr-services/insurance", response_class=HTMLResponse, include_in_schema=False)
    def insurance_page(user: User = Depends(require_user)):
        return workspace_page()

    @app.get("/admin/dashboard", response_class=HTMLResponse, include_in_schema=False)
    def admin_dashboard_page(user: User = Depends(require_admin)):
        return workspace_page()

    @app.get("/admin/hr-inbox", response_class=HTMLResponse, include_in_schema=False)
    def admin_hr_inbox_page(user: User = Depends(require_admin)):
        return workspace_page()

    @app.get("/admin/holiday-requests", response_class=HTMLResponse, include_in_schema=False)
    def admin_holiday_requests_page(user: User = Depends(require_admin)):
        return workspace_page()

    @app.get("/admin/insurance-requests", response_class=HTMLResponse, include_in_schema=False)
    def admin_insurance_requests_page(user: User = Depends(require_admin)):
        return workspace_page()

    @app.get("/api/v1/admin/dashboard")
    def admin_dashboard(
        user: User = Depends(require_admin),
    ):
        return {
            "message": "Admin authentication verified",
            "name": user.name,
        }

    @app.get("/api/v1/user/dashboard")
    def user_dashboard(
        user: User = Depends(require_user),
    ):
        return {
            "message": "Employee authentication verified",
            "name": user.name,
        }

    @app.get("/health")
    def health():
        return {
            "status": "ok"
        }

    return app


app = create_app()
