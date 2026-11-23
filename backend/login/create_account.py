import argparse
from getpass import getpass

from sqlalchemy.exc import IntegrityError

try:
    from .main import (
        Settings,
        User,
        create_app,
        initialize_database,
        normalize_work_email,
        passwords,
    )
except ImportError:
    from main import (
        Settings,
        User,
        create_app,
        initialize_database,
        normalize_work_email,
        passwords,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Create a SkyChef account."
    )

    identities = parser.add_mutually_exclusive_group(required=True)
    identities.add_argument("--email", help="Work email")
    identities.add_argument(
        "--identity",
        help="Existing CLI option for an employee ID or work email",
    )

    parser.add_argument(
        "--name",
        required=True,
    )

    parser.add_argument(
        "--role",
        required=True,
        choices=["employee", "admin", "user"],
    )

    args = parser.parse_args()

    if args.email is not None:
        try:
            identity = normalize_work_email(args.email)
        except ValueError as error:
            parser.error(str(error))
    else:
        identity = args.identity.strip().casefold()

    role = "user" if args.role == "employee" else args.role
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

    initialize_database(factory.kw["bind"])

    with factory() as db:
        user = User(
            identity=identity,
            name=name,
            role=role,
            password_hash=passwords.hash(password),
            active=True,
        )

        db.add(user)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            parser.error("Account already exists.")

    print("Account created successfully.")


if __name__ == "__main__":
    main()
