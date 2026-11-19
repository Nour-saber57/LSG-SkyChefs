import argparse
from getpass import getpass

from sqlalchemy import select

try:
    from .main import (
        Base,
        Settings,
        User,
        create_app,
        passwords,
    )
except ImportError:
    from main import (
        Base,
        Settings,
        User,
        create_app,
        passwords,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Create a SkyChef account."
    )

    parser.add_argument(
        "--identity",
        required=True,
        help="Employee ID or work email",
    )

    parser.add_argument(
        "--name",
        required=True,
    )

    parser.add_argument(
        "--role",
        required=True,
        choices=["user", "admin"],
    )

    args = parser.parse_args()

    identity = args.identity.strip().casefold()
    name = args.name.strip()

    if not identity or len(identity) > 254:
        parser.error("Provide a valid employee ID or email.")

    if not name or len(name) > 150:
        parser.error("Provide a valid name.")

    password = getpass(
        "New password (at least 12 characters): "
    )

    confirmation = getpass("Confirm password: ")

    if not 12 <= len(password) <= 1024:
        parser.error(
            "Password must contain 12–1024 characters."
        )

    if password != confirmation:
        parser.error("Passwords do not match.")

    application = create_app(Settings())

    factory = application.state.session_factory

    Base.metadata.create_all(
        factory.kw["bind"]
    )

    with factory() as db:
        existing_user = db.scalar(
            select(User).where(
                User.identity == identity
            )
        )

        if existing_user:
            parser.error("Account already exists.")

        user = User(
            identity=identity,
            name=name,
            role=args.role,
            password_hash=passwords.hash(password),
            active=True,
        )

        db.add(user)
        db.commit()

    print("Account created successfully.")


if __name__ == "__main__":
    main()