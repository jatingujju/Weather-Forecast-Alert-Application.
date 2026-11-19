"""
notify.py - OPTIONAL email notifications.

Safe by default: if the email settings are missing from .env, nothing is
sent and the program only shows what WOULD have been sent (a "dry run").
The same alert is not sent twice within 12 hours (simple de-duplication).
"""
import smtplib
import ssl
from email.message import EmailMessage

import pandas as pd

from src import config
from src.alerts import SEVERITY_RANK

LOG_PATH = config.OUTPUT_DIR / "alert_log.csv"


def smtp_settings():
    """Email settings from the environment, or None if something is missing."""
    s = {"host": config.get_setting("SMTP_HOST"),
         "port": int(config.get_setting("SMTP_PORT", "587")),
         "user": config.get_setting("SMTP_USER"),
         "password": config.get_setting("SMTP_PASSWORD"),
         "to": config.get_setting("ALERT_EMAIL_TO")}
    return s if all([s["host"], s["user"], s["password"], s["to"]]) else None


def build_email(alerts, sender, recipient):
    """Create the email message (does not send it)."""
    critical = sum(1 for a in alerts if a.severity == "critical")
    msg = EmailMessage()
    msg["Subject"] = f"Weather alerts: {len(alerts)} alert(s), {critical} critical"
    msg["From"], msg["To"] = sender, recipient
    lines = ["Weather alerts from your Weather Forecast & Alert Application", ""]
    for city in dict.fromkeys(a.city for a in alerts):
        lines.append(city)
        lines += [f"  [{a.severity.upper()}] {a.title}: {a.message}" for a in alerts if a.city == city]
        lines.append("")
    msg.set_content("\n".join(lines))
    return msg


def filter_new(alerts, log_path=LOG_PATH, hours=12, now=None):
    """Drop alerts (same city + type) that were already sent in the last `hours`."""
    now = now or pd.Timestamp.now()
    if not log_path.exists():
        return list(alerts)
    log = pd.read_csv(log_path, parse_dates=["sent_at"])
    recent = log[log["sent_at"] >= now - pd.Timedelta(hours=hours)]
    seen = set(zip(recent["city"], recent["category"]))
    return [a for a in alerts if (a.city, a.category) not in seen]


def record_sent(alerts, log_path=LOG_PATH, now=None):
    now = now or pd.Timestamp.now()
    new = pd.DataFrame([{"city": a.city, "category": a.category, "sent_at": now} for a in alerts])
    if log_path.exists():
        new = pd.concat([pd.read_csv(log_path), new], ignore_index=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    new.to_csv(log_path, index=False)


def send_alerts(alerts, min_severity="warning", log_path=LOG_PATH, now=None, smtp_factory=smtplib.SMTP):
    """
    Email the alerts. Returns a short status message for the terminal.
    Only 'min_severity' and above are sent (info alerts are too noisy).
    """
    wanted = [a for a in alerts if SEVERITY_RANK[a.severity] >= SEVERITY_RANK[min_severity]]
    wanted = filter_new(wanted, log_path, now=now)
    if not wanted:
        return "No new warning/critical alerts to send."

    settings = smtp_settings()
    if settings is None:
        msg = build_email(wanted, "weather@example.com", "you@example.com")
        return (f"[DRY RUN] Email settings not found in .env - nothing sent. "
                f"Would send: '{msg['Subject']}'.")
    msg = build_email(wanted, settings["user"], settings["to"])
    try:
        with smtp_factory(settings["host"], settings["port"], timeout=20) as server:
            server.starttls(context=ssl.create_default_context())
            server.login(settings["user"], settings["password"])
            server.send_message(msg)
    except (smtplib.SMTPException, OSError) as error:
        # never print the password; the error type is enough to debug
        return f"Email failed ({type(error).__name__}). Check SMTP settings in .env."
    record_sent(wanted, log_path, now=now)
    return f"Email sent to {settings['to']} with {len(wanted)} alert(s)."
