"""
Cria (ou promove) um usuário administrador.

Uso: uv run python -m src.scripts.create_admin
     (lê ADMIN_NAME, ADMIN_EMAIL e ADMIN_PASSWORD do ambiente; ou pergunta no terminal)
"""

import getpass
import os

from src.auth.permissions import ROLE_ADMIN
from src.auth.service import create_user, get_user_by_email
from src.database import SessionLocal


def main() -> None:
    name = os.getenv("ADMIN_NAME") or input("Nome: ").strip()
    email = os.getenv("ADMIN_EMAIL") or input("E-mail: ").strip()
    password = os.getenv("ADMIN_PASSWORD") or getpass.getpass("Senha (mín. 8): ")

    if len(password) < 8:
        raise SystemExit("A senha precisa ter ao menos 8 caracteres.")

    with SessionLocal() as session:
        existing = get_user_by_email(email, session)
        if existing:
            existing.role = ROLE_ADMIN
            session.commit()
            print(f"Usuário {existing.email} promovido a admin.")
            return

        user = create_user(name, email, password, session, role=ROLE_ADMIN)
        print(f"Admin {user.email} criado.")


if __name__ == "__main__":
    main()
