from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage

import streamlit as st

SMTP_TIMEOUT_SECONDS = 20
FALSE_VALUES = {"0", "false", "no", "off"}


def smtp_config_value(key: str, default: str = "") -> str:
    env_names = {
        "host": "BTS_SMTP_HOST",
        "port": "BTS_SMTP_PORT",
        "user": "BTS_SMTP_USER",
        "password": "BTS_SMTP_PASSWORD",
        "from": "BTS_SMTP_FROM",
        "starttls": "BTS_SMTP_STARTTLS",
        "verify_ssl": "BTS_SMTP_VERIFY_SSL",
    }
    env_value = os.getenv(env_names.get(key, ""), "").strip()
    if env_value:
        return env_value
    try:
        smtp_secrets = st.secrets.get("smtp", {})
        return str(smtp_secrets.get(key, default)).strip()
    except Exception:
        return default


def _smtp_port() -> int:
    try:
        return int(smtp_config_value("port", "587"))
    except ValueError:
        return 587


def _is_enabled(key: str, default: str = "1") -> bool:
    return smtp_config_value(key, default).strip().lower() not in FALSE_VALUES


def _send_email(
    to_email: str,
    subject: str,
    body_lines: list[str],
    missing_message: str,
) -> tuple[bool, str]:
    host = smtp_config_value("host")
    smtp_user = smtp_config_value("user")
    smtp_password = smtp_config_value("password")
    sender = smtp_config_value("from", smtp_user)

    if not host or not sender:
        return False, missing_message

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to_email
    msg.set_content("\n".join(body_lines))

    try:
        with smtplib.SMTP(host, _smtp_port(), timeout=SMTP_TIMEOUT_SECONDS) as server:
            if _is_enabled("starttls"):
                context = ssl.create_default_context()
                if not _is_enabled("verify_ssl"):
                    context.check_hostname = False
                    context.verify_mode = ssl.CERT_NONE
                server.starttls(context=context)
            if smtp_user:
                server.login(smtp_user, smtp_password)
            server.send_message(msg)
    except Exception as exc:
        return False, f"Email non envoye: {exc}"

    return True, "Email envoye."


def send_account_password_email(
    email: str,
    display_name: str,
    username: str,
    temp_password: str,
) -> tuple[bool, str]:
    body = [
        f"Bonjour {display_name or username},",
        "",
        "Voici vos informations d'acces BTS Energy Management.",
        f"Identifiant: {username}",
        f"Mot de passe temporaire: {temp_password}",
        "",
        "A la prochaine connexion, l'application vous demandera de modifier ce mot de passe.",
        "",
        "Tunisie Telecom - BTS Energy Management System",
    ]
    return _send_email(
        email,
        "Votre compte BTS Energy Management",
        body,
        "Service email non configure cote serveur.",
    )


def send_account_status_email(
    email: str,
    display_name: str,
    username: str,
    is_active: bool,
) -> tuple[bool, str]:
    status_text = "active" if is_active else "desactive"
    body = [
        f"Bonjour {display_name or username},",
        "",
        f"Le statut de votre compte BTS Energy Management (identifiant: {username}) a ete mis a jour.",
        f"Votre compte est desormais : {status_text.upper()}.",
        "",
    ]

    if is_active:
        body.append("Vous pouvez desormais vous connecter au tableau de bord.")
    else:
        body.append(
            "Votre acces a l'application a ete suspendu. "
            "Veuillez contacter un administrateur pour plus d'informations."
        )

    body.extend(["", "Tunisie Telecom - BTS Energy Management System"])
    return _send_email(
        email,
        f"Statut de votre compte BTS EMS : {status_text.capitalize()}",
        body,
        "Service email non configure.",
    )


def send_account_deletion_email(email: str, display_name: str, username: str) -> tuple[bool, str]:
    body = [
        f"Bonjour {display_name or username},",
        "",
        f"Votre compte BTS Energy Management (identifiant: {username}) a ete supprime par un administrateur.",
        "Vous n'avez plus acces au systeme.",
        "",
        "Tunisie Telecom - BTS Energy Management System",
    ]
    return _send_email(email, "Suppression de votre compte BTS EMS", body, "Service email non configure.")
