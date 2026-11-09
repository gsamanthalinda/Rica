BRAND = "RICA"
PRIMARY = "#062464"
BG = "#f3f6fb"
CARD = "#ffffff"
TEXT = "#0f172a"
MUTED = "#64748b"
BORDER = "#e2e8f0"


def render_email(
    *,
    title: str,
    greeting: str | None = None,
    paragraphs: list[str],
    button_text: str | None = None,
    button_url: str | None = None,
    footer_lines: list[str] | None = None,
) -> str:
    para_html = "".join(
        f'<p style="margin:0 0 16px 0;font-size:16px;line-height:1.6;color:{TEXT};">{p}</p>'
        for p in paragraphs
    )
    greeting_html = (
        f'<p style="margin:0 0 16px 0;font-size:16px;line-height:1.6;color:{TEXT};font-weight:600;">{greeting}</p>'
        if greeting
        else ""
    )
    button_html = ""
    if button_text and button_url:
        button_html = (
            f'<table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin:24px 0;">'
            f'<tr><td align="left">'
            f'<a href="{button_url}" style="display:inline-block;padding:14px 28px;background:{PRIMARY};color:#ffffff;'
            f'font-size:16px;font-weight:600;text-decoration:none;border-radius:10px;">{button_text}</a>'
            f"</td></tr></table>"
        )
    footer_html = ""
    if footer_lines:
        footer_html = (
            f'<div style="border-top:1px solid {BORDER};margin-top:32px;padding-top:20px;">'
            + "".join(
                f'<p style="margin:0 0 8px 0;font-size:13px;line-height:1.5;color:{MUTED};">{line}</p>'
                for line in footer_lines
            )
            + "</div>"
        )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
</head>
<body style="margin:0;padding:0;background:{BG};font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:{BG};padding:40px 16px;">
<tr><td align="center">
<table role="presentation" width="600" cellspacing="0" cellpadding="0" border="0" style="max-width:600px;width:100%;background:{CARD};border-radius:16px;overflow:hidden;box-shadow:0 8px 30px rgba(15,23,42,0.08);">
<tr><td style="background:{PRIMARY};padding:32px 40px;text-align:center;">
<span style="font-size:26px;font-weight:700;letter-spacing:1px;color:#ffffff;">{BRAND}</span>
</td></tr>
<tr><td style="padding:40px 40px 32px 40px;">
<h1 style="margin:0 0 20px 0;font-size:24px;font-weight:700;color:{TEXT};line-height:1.3;">{title}</h1>
{greeting_html}
{para_html}
{button_html}
{footer_html}
</td></tr>
</table>
<p style="margin:24px 0 0 0;font-size:12px;color:{MUTED};text-align:center;">&copy; {BRAND}</p>
</td></tr>
</table>
</body>
</html>"""
