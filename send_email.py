# =============================================================================
# GROWTH OPPORTUNITY ENGINE
# send_email.py
#
# Envia por e-mail:
# - report.pdf
# - opportunities.csv
#
# Credenciais lidas por variáveis de ambiente / GitHub Secrets.
# =============================================================================

from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from pathlib import Path


PROJECT_NAME = "GROWTH OPPORTUNITY ENGINE"

BASE_DIR = Path(__file__).resolve().parent

REPORT_FILE = BASE_DIR / "output" / "report.pdf"

OPPORTUNITIES_FILE = (
    BASE_DIR
    / "output"
    / "opportunities.csv"
)


def get_required_env(name: str) -> str:
    value = os.getenv(name)

    if not value:
        raise RuntimeError(
            f"Variável de ambiente ausente: {name}"
        )

    return value


def attach_file(
    message: EmailMessage,
    file_path: Path,
):
    if not file_path.exists():
        print(
            f"⚠️ Arquivo não encontrado: "
            f"{file_path}"
        )
        return

    suffix = file_path.suffix.lower()

    if suffix == ".pdf":
        maintype = "application"
        subtype = "pdf"

    elif suffix == ".csv":
        maintype = "text"
        subtype = "csv"

    else:
        maintype = "application"
        subtype = "octet-stream"

    data = file_path.read_bytes()

    message.add_attachment(
        data,
        maintype=maintype,
        subtype=subtype,
        filename=file_path.name,
    )


def send_email():
    smtp_host = os.getenv(
        "SMTP_HOST",
        "smtp.gmail.com",
    )

    smtp_port = int(
        os.getenv(
            "SMTP_PORT",
            "587",
        )
    )

    smtp_user = get_required_env(
        "SMTP_USER"
    )

    smtp_password = get_required_env(
        "SMTP_PASSWORD"
    )

    email_to = get_required_env(
        "EMAIL_TO"
    )

    message = EmailMessage()

    message["Subject"] = (
        "Growth Opportunity Engine | "
        "Relatório Diário"
    )

    message["From"] = smtp_user
    message["To"] = email_to

    message.set_content(
        """
GROWTH OPPORTUNITY ENGINE

A execução foi concluída.

Arquivos anexados:
- report.pdf
- opportunities.csv

O relatório contém as classificações:
- ENTRADA FORTE
- ENTRADA PARCIAL
- AGUARDAR

Este material é gerado automaticamente pelo
Growth Opportunity Engine.

Resultados históricos não garantem resultados futuros.
""".strip()
    )

    attach_file(
        message,
        REPORT_FILE,
    )

    attach_file(
        message,
        OPPORTUNITIES_FILE,
    )

    print("=" * 80)
    print(PROJECT_NAME)
    print("ENVIO DE E-MAIL")
    print("=" * 80)

    print(
        f"Servidor: {smtp_host}:{smtp_port}"
    )

    print(
        f"Destinatário: {email_to}"
    )

    with smtplib.SMTP(
        smtp_host,
        smtp_port,
        timeout=30,
    ) as server:

        server.ehlo()

        server.starttls()

        server.ehlo()

        server.login(
            smtp_user,
            smtp_password,
        )

        server.send_message(
            message
        )

    print("✅ E-mail enviado com sucesso.")
    print("=" * 80)


if __name__ == "__main__":
    send_email()
