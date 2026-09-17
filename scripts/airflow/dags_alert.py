"""Build and send the DAGs alert email — problems only.

Works straight off the in-memory `results` list check_all() already produced
for the current run — no separate storage, no DB, nothing accumulated across
runs. As a result, while a DAG stays broken, an email goes out on every cron
cycle that still sees it broken (no dedup/throttling yet — add it later if
the alert volume during an incident turns out to be a problem).
"""
import logging
import smtplib
from email.mime.text import MIMEText

log = logging.getLogger("pysmoke-test.dags.alert")


def _is_problem(row):
    return not row["ok"]


def build_email(results, generated_at):
    """Return (subject, body), or (None, None) if there's nothing to report."""
    problems = [r for r in results if _is_problem(r)]
    if not problems:
        return None, None

    by_instance = {}
    for r in problems:
        by_instance.setdefault((r["business_line"], r["url"]), []).append(r)

    lines = [f"{len(problems)} DAG issue(s) detected — {generated_at}", ""]
    for (business_line, url) in sorted(by_instance):
        rows = by_instance[(business_line, url)]
        lines.append(f"{business_line.upper()} — {url}")
        for r in sorted(rows, key=lambda r: r["dag_id"] or ""):
            reason = "stuck queued too long" if r["delayed"] else f"state={r['state']}"
            if r["error"]:
                reason = f"error: {r['error']}"
            lines.append(f"  - {r['dag_id']}: {reason}")
        lines.append("")

    subject = f"[Datahub v2] {len(problems)} DAG issue(s) detected"
    return subject, "\n".join(lines)


def send_email(smtp_host, smtp_port, email_from, email_to, subject, body,
                smtp_username="", smtp_password="", use_tls=False, debug=False):
    if not smtp_host or not email_to:
        log.warning("EMAIL_ENABLED is set but SMTP_HOST/EMAIL_TO is missing, skipping send")
        return

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = email_from
    msg["To"] = ", ".join(email_to)

    with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as smtp:
        if debug:
            smtp.set_debuglevel(2)
        if use_tls:
            smtp.starttls()
        if smtp_username:
            smtp.login(smtp_username, smtp_password)
        # sendmail() only raises if the server refuses the whole transaction —
        # a per-recipient refusal comes back in this dict instead, silently,
        # so it has to be checked explicitly.
        refused = smtp.sendmail(email_from, email_to, msg.as_string())

    if refused:
        log.warning("SMTP server refused some recipients: %s", refused)
    else:
        log.info("Sent alert email to %s: %s", email_to, subject)
