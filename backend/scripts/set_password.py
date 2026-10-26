"""Cambia la contraseña de un usuario. Pide la nueva contraseña de forma oculta.

docker compose exec backend python -m scripts.set_password --email tu@correo.com
"""

import argparse

from app.cli import set_password


def main() -> None:
    parser = argparse.ArgumentParser(description="Cambia la contraseña de un usuario")
    parser.add_argument("--email", required=True)
    args = parser.parse_args()
    set_password(args.email)


if __name__ == "__main__":
    main()
