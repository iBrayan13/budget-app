"""Crea una cuenta de usuario. Pide la contraseña de forma oculta.

docker compose exec backend python -m scripts.create_user --email tu@correo.com --name "Tu nombre"
"""

import argparse

from app.cli import create_user


def main() -> None:
    parser = argparse.ArgumentParser(description="Crea una cuenta de usuario")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", default="")
    args = parser.parse_args()
    create_user(args.email, args.name)


if __name__ == "__main__":
    main()
