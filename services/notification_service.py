from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage

import streamlit as st

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


def send_account_password_email(email: str, display_name: str, username: str, temp_password: str) -> tuple[bool, str]:
    host = smtp_config_value("host")
    port = int(smtp_config_value("port", "587"))
    smtp_user = smtp_config_value("user")
    smtp_password = smtp_config_value("password")
    sender = smtp_config_value("from", smtp_user)
    use_tls = smtp_config_value("starttls", "1").strip().lower() not in {"0", "false", "no"}
    verify_ssl = smtp_config_value("verify_ssl", "1").strip().lower() not in {"0", "false", "no"}
    if not host or not sender:
        return False, "Service email non configure cote serveur."
    msg = EmailMessage()
    msg["Subject"] = "Votre compte BTS Energy Management"
    msg["From"] = sender
    msg["To"] = email
    msg.set_content(
        "\n".join(
            [
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
        )
    )
    try:
        with smtplib.SMTP(host, port, timeout=20) as server:
            if use_tls:
                context = ssl.create_default_context()
                if not verify_ssl:
                    context.check_hostname = False
                    context.verify_mode = ssl.CERT_NONE
                server.starttls(context=context)
            if smtp_user:
                server.login(smtp_user, smtp_password)
            server.send_message(msg)
    except Exception as exc:
        return False, f"Email non envoye: {exc}"
    return True, "Email envoye."


def save_smtp_config(host: str, port: int, user: str, password: str, sender: str, starttls: bool) -> dict:
    return {
        "smtp_host": host.strip(),
        "smtp_port": str(int(port)),
        "smtp_user": user.strip(),
        "smtp_from": sender.strip(),
        "smtp_starttls": "1" if starttls else "0",
    }
