"""Build and send the DAGs alert email — problems only.

Works straight off the in-memory `results` list check_all() already produced
for the current run — no separate storage, no DB, nothing accumulated across
runs. As a result, while a DAG stays broken, an email goes out on every cron
cycle that still sees it broken (no dedup/throttling yet — add it later if
the alert volume during an incident turns out to be a problem).
"""
import html
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

log = logging.getLogger("pysmoke-test.dags.alert")

# Same palette as the web UI (frontend/src/style/global.css :root), so the
# email reads as the same product rather than a bare script dump.
_BRAND_DEEP = "#03291A"
_BRAND = "#00915A"
_KO = "#D63C3C"
_KO_WASH = "#FBEAEA"
_WARN = "#C9861D"
_WARN_WASH = "#FCF1E0"
_INK = "#0B2A1D"
_INK_DIM = "#55645C"
_BORDER = "#DCE4DD"
_SURFACE_ALT = "#EAF0EB"
_BG = "#F4F6F3"
_SANS = "'Segoe UI', Arial, sans-serif"
_MONO = "Menlo, Consolas, monospace"


def _is_problem(row):
    return not row["ok"]


def _reason(row):
    if row["error"]:
        return f"Erreur : {row['error']}"
    if row["delayed"]:
        return "Bloqué en file d'attente au-delà du seuil toléré"
    return f"Dernier run en échec (état = {row['state']})"


def _badge_html(row):
    if row["delayed"]:
        color, bg, label = _WARN, _WARN_WASH, "RETARD"
    else:
        color, bg, label = _KO, _KO_WASH, "ÉCHEC"
    return (
        f'<span style="display:inline-block;padding:3px 11px;border-radius:999px;'
        f'font:600 11px {_SANS};letter-spacing:.03em;color:{color};background:{bg};">'
        f'{label}</span>'
    )


def _group_by_instance(problems):
    by_instance = {}
    for r in problems:
        by_instance.setdefault((r["business_line"], r["url"]), []).append(r)
    return by_instance


def _build_text(problems, by_instance, generated_at):
    lines = [f"{len(problems)} DAG issue(s) detected — {generated_at}", ""]
    for business_line, url in sorted(by_instance):
        rows = sorted(by_instance[(business_line, url)], key=lambda r: r["dag_id"] or "")
        lines.append(f"{business_line.upper()} — {url}")
        for r in rows:
            reason = "stuck queued too long" if r["delayed"] else f"state={r['state']}"
            if r["error"]:
                reason = f"error: {r['error']}"
            lines.append(f"  - {r['dag_id']}: {reason}")
        lines.append("")
    return "\n".join(lines)


def _instance_block_html(business_line, url, rows):
    dag_rows = "".join(
        f'''<tr>
          <td width="220" style="padding:11px 14px 11px 20px;border-top:1px solid {_BORDER};font:500 13px {_MONO};color:{_INK};">
            {html.escape(r["dag_id"] or "")}
          </td>
          <td width="70" style="padding:11px 10px;border-top:1px solid {_BORDER};text-align:center;white-space:nowrap;">
            {_badge_html(r)}
          </td>
          <td style="padding:11px 20px 11px 0;border-top:1px solid {_BORDER};font:400 12.5px {_SANS};color:{_INK_DIM};">
            {html.escape(_reason(r))}
          </td>
        </tr>'''
        for r in rows
    )
    return f'''<tr><td style="padding:0 0 16px 0;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
             style="border:1px solid {_BORDER};border-radius:8px;overflow:hidden;">
        <tr>
          <td colspan="3" style="background:{_SURFACE_ALT};padding:12px 20px;">
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td style="padding-right:12px;font:700 13px {_SANS};color:{_INK};text-transform:uppercase;letter-spacing:.04em;">
                  {html.escape(business_line.upper())}
                  <span style="font-family:{_MONO};font-size:12px;color:{_INK_DIM};font-weight:400;text-transform:none;letter-spacing:0;margin-left:10px;">
                    {html.escape(url)}
                  </span>
                </td>
                <td width="120" style="text-align:right;font:600 12px {_SANS};color:{_KO};white-space:nowrap;">
                  {len(rows)} problème{"s" if len(rows) > 1 else ""}
                </td>
              </tr>
            </table>
          </td>
        </tr>
        {dag_rows}
      </table>
    </td></tr>'''


def _build_html(problems, by_instance, generated_at):
    blocks = "".join(
        _instance_block_html(business_line, url, sorted(by_instance[(business_line, url)], key=lambda r: r["dag_id"] or ""))
        for business_line, url in sorted(by_instance)
    )
    plural = "s" if len(problems) > 1 else ""
    return f'''<!DOCTYPE html>
<html lang="fr">
<body style="margin:0;padding:0;background:{_BG};">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{_BG};padding:24px 0;">
    <tr><td align="center">
      <table role="presentation" width="600" cellpadding="0" cellspacing="0"
             style="background:#FFFFFF;border-radius:10px;overflow:hidden;">
        <tr>
          <td style="background:{_BRAND_DEEP};padding:26px 28px;">
            <div style="font:700 12px {_SANS};color:{_BRAND};text-transform:uppercase;letter-spacing:.08em;">
              Datahub v2 &middot; Surveillance des DAGs
            </div>
            <div style="font:600 21px Georgia,serif;color:#FFFFFF;margin-top:8px;">
              {len(problems)} problème{plural} détecté{plural}
            </div>
            <div style="font:400 12px {_SANS};color:#8FC7A9;margin-top:6px;">
              {html.escape(generated_at)}
            </div>
          </td>
        </tr>
        <tr>
          <td style="padding:22px 22px 4px 22px;">
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
              {blocks}
            </table>
          </td>
        </tr>
        <tr>
          <td style="padding:14px 28px 24px 28px;border-top:1px solid {_BORDER};">
            <div style="font:400 11.5px {_SANS};color:{_INK_DIM};line-height:1.5;">
              Alerte générée automatiquement par Datahub v2 — ne pas répondre à cet email.
              Le tableau de bord affiche l'ensemble des DAGs, y compris ceux en succès.
            </div>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>'''


def build_email(results, generated_at):
    """Return (subject, text_body, html_body), or (None, None, None) if nothing to report."""
    problems = [r for r in results if _is_problem(r)]
    if not problems:
        return None, None, None

    by_instance = _group_by_instance(problems)
    subject = f"[Datahub v2] {len(problems)} problème(s) DAG détecté(s)"
    text_body = _build_text(problems, by_instance, generated_at)
    html_body = _build_html(problems, by_instance, generated_at)
    return subject, text_body, html_body


def send_email(smtp_host, smtp_port, email_from, email_to, subject, text_body, html_body,
               smtp_username="", smtp_password="", use_tls=False, debug=False):
    if not smtp_host or not email_to:
        log.warning("EMAIL_ENABLED is set but SMTP_HOST/EMAIL_TO is missing, skipping send")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = email_from
    msg["To"] = ", ".join(email_to)
    # Plain text first, HTML second — clients render the last part they understand.
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

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
