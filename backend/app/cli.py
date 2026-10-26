"""Admin commands. There is no public sign-up: users are created from here.

python -m app.cli create-user --email tu@correo.com --name "Brayan"
"""

import argparse
import getpass
import sys

from sqlalchemy import func, select

from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models import User

MIN_PASSWORD_LENGTH = 12


def _read_password() -> str:
    password = getpass.getpass("Contraseña: ")
    if len(password) < MIN_PASSWORD_LENGTH:
        sys.exit(f"La contraseña debe tener al menos {MIN_PASSWORD_LENGTH} caracteres.")
    if password != getpass.getpass("Repite la contraseña: "):
        sys.exit("Las contraseñas no coinciden.")
    return password


def create_user(email: str, name: str) -> None:
    with SessionLocal() as db:
        if db.scalar(select(User).where(func.lower(User.email) == email.lower())):
            sys.exit(f"Ya existe un usuario con el correo {email}.")
        db.add(
            User(
                email=email.lower(), full_name=name, hashed_password=hash_password(_read_password())
            )
        )
        db.commit()
    print(f"Usuario {email} creado.")


def set_password(email: str) -> None:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(func.lower(User.email) == email.lower()))
        if user is None:
            sys.exit(f"No existe el usuario {email}.")
        user.hashed_password = hash_password(_read_password())
        db.commit()
    print(f"Contraseña de {email} actualizada.")


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create-user")
    create.add_argument("--email", required=True)
    create.add_argument("--name", default="")

    passwd = sub.add_parser("set-password")
    passwd.add_argument("--email", required=True)

    args = parser.parse_args()
    if args.command == "create-user":
        create_user(args.email, args.name)
    else:
        set_password(args.email)


if __name__ == "__main__":
    main()
