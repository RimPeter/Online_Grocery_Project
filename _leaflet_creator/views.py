from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseServerError
from django.shortcuts import render, redirect
from urllib.parse import urlparse, quote_plus
from io import BytesIO
import base64

from django.template.loader import get_template
from django.conf import settings
from django.contrib.staticfiles import finders
from xhtml2pdf import pisa

# Lazy import of WeasyPrint to avoid noisy import errors at startup on systems
# where native libraries (cairo/pango/etc.) are not available.
def _get_weasy():
    try:  # pragma: no cover
        from weasyprint import HTML as WPHTML, CSS as WPCSS  # type: ignore
        return WPHTML, WPCSS
    except Exception:
        return None, None
import os



def index(request):
    return HttpResponse("Leaflet Creator app is installed")


def dl_leaflet(request):
    return render(
        request,
        "_leaflet_creator/DL_size_leaflet.html",
        {"pdf": False},
    )


def _ensure_scheme(url: str) -> str:
    try:
        parsed = urlparse(url)
        if not parsed.scheme:
            return f"https://{url}"
        return url
    except Exception:
        return url


def qr_svg(request):
    site = request.GET.get("site", "").strip()
    if not site:
        return HttpResponseBadRequest("Missing site parameter")

    site = _ensure_scheme(site)

    try:
        import segno  # type: ignore
    except Exception:
        # Fallback: redirect to a public QR API so the browser fetches it directly.
        # Note: relies on client internet access.
        api = f"https://api.qrserver.com/v1/create-qr-code/?size=240x240&data={quote_plus(site)}"
        return redirect(api)

    try:
        qr = segno.make(site)
        buf = BytesIO()
        qr.save(buf, kind="svg", scale=3)
        return HttpResponse(buf.getvalue(), content_type="image/svg+xml")
    except Exception as exc:
        return HttpResponseServerError(f"Failed to generate QR: {exc}")


def _static_link_callback(uri, rel):
    """Resolve static and media URIs to absolute system paths for xhtml2pdf.

    Handles:
    - data: URIs (pass through)
    - http(s) URLs (pass through)
    - STATIC_URL-prefixed paths resolved via staticfiles finders
    - Bare or leading-slash paths resolved via finders, with safe fallback
    """
    if not uri:
        return uri

    # Allow embedded data URIs and remote URLs
    if uri.startswith("data:") or uri.startswith("http://") or uri.startswith("https://"):
        return uri

    # Normalize Windows backslashes early
    norm_uri = uri.replace("\\", "/")

    # Strip domain if present and keep path portion
    # e.g., http://example/static/... already handled above

    # Resolve STATIC_URL-prefixed assets
    static_url = settings.STATIC_URL or "/static/"
    if norm_uri.startswith(static_url):
        subpath = norm_uri[len(static_url):]
        found = finders.find(subpath)
        if found:
            return found

    # Try without a leading slash
    subpath = norm_uri.lstrip("/")
    found = finders.find(subpath)
    if found:
        return found

    # Fallback: join to BASE_DIR (best-effort)
    fallback = os.path.join(str(settings.BASE_DIR), subpath)
    return fallback


def _choose_renderer():
    """Return 'weasyprint' if available and configured, otherwise 'xhtml2pdf'."""
    mode = getattr(settings, 'LEAFLET_PDF_RENDERER', 'auto')
    mode = (mode or 'auto').lower()
    if mode == 'weasyprint':
        WPHTML, WPCSS = _get_weasy()
        return 'weasyprint' if WPHTML is not None and WPCSS is not None else 'xhtml2pdf'
    if mode == 'xhtml2pdf':
        return 'xhtml2pdf'
    # auto
    WPHTML, WPCSS = _get_weasy()
    return 'weasyprint' if WPHTML is not None and WPCSS is not None else 'xhtml2pdf'


def dl_leaflet_pdf(request):
    """Render the DL leaflet as a downloadable PDF, embedding the QR image."""
    site = request.GET.get("site", "").strip()
    site = _ensure_scheme(site) if site else ""

    qr_data_uri = None
    if site:
        try:
            import segno  # type: ignore
            qr = segno.make(site)
            buf = BytesIO()
            qr.save(buf, kind="png", scale=6)
            b64 = base64.b64encode(buf.getvalue()).decode("ascii")
            qr_data_uri = f"data:image/png;base64,{b64}"
        except Exception:
            # Fallback placeholder if QR can't be generated locally
            placeholder = (
                "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAAACXBIWXMAAAsSAAALEgHS3X78AAABcUlEQVR4nO3aMU7DQBAG4a8mJ8p+"
                "r4XwZyX1y6fQbJx0C1qF+E1J6v6g3v5aB0L2w7m4w2gHc8m6j0g9Hf7kYkSIkSIkSIkSIkSIkSIv8m8k1m1u8Q4KpG6QnZ9m2DgqkZjg"
                "i9wzv1h9u2H7g8g9m8Hq9w0g8g9m8Hq9w0g8g9m8Hq9w0g8g9m8Hq9w0g8g9m8Hq9w0g8g9m8Hq9w0XXz8j2z0mQkSZIkSZIkSZIkSZI"
                "kSfIu7Qe8JY4s7X2q8X8pX9y4A6y4c8xgLJNDfR4y7zj7v0Z3J0O4W6f8R3QeQWw9wqgQ7i9xgYQ3i9wYIQ3i9wYIQ3i9wYIQ3mC2b2v9"
                "r7r9g0mQkSZIkSZIkSZIkSZIkSW4B0tK0k2b+2a0AAAAASUVORK5CYII="
            )
            qr_data_uri = f"data:image/png;base64,{placeholder}"

    template = get_template("_leaflet_creator/DL_size_leaflet.html")
    context = {"pdf": True, "qr_data_uri": qr_data_uri, "request": request}
    html = template.render(context)

    # Prefer WeasyPrint if chosen/available for CSS parity
    if _choose_renderer() == 'weasyprint':
        try:
            WPHTML, WPCSS = _get_weasy()
            css_path = finders.find("css/leaflet.css")
            stylesheets = [WPCSS(filename=css_path)] if css_path else None
            pdf_bytes = WPHTML(string=html, base_url=str(settings.BASE_DIR)).write_pdf(stylesheets=stylesheets)
            response = HttpResponse(pdf_bytes, content_type="application/pdf")
            response["Content-Disposition"] = "attachment; filename=leaflet-dl.pdf"
            return response
        except Exception:
            pass  # fall back to xhtml2pdf

    # Fallback to xhtml2pdf
    pdf_io = BytesIO()
    pisa.CreatePDF(html, dest=pdf_io, link_callback=_static_link_callback)
    response = HttpResponse(pdf_io.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = "attachment; filename=leaflet-dl.pdf"
    return response


def leaflet_status(request):
    """Simple status page showing which PDF renderer is configured and available."""
    configured = getattr(settings, 'LEAFLET_PDF_RENDERER', 'auto')
    # Only probe WeasyPrint availability when not explicitly forced to xhtml2pdf
    weasy_available = False
    if str(configured).lower() != 'xhtml2pdf':
        WPHTML, WPCSS = _get_weasy()
        weasy_available = WPHTML is not None and WPCSS is not None
    active = _choose_renderer()
    body = (
        f"Configured: {configured}\n"
        f"WeasyPrint available: {weasy_available}\n"
        f"Active renderer: {active}\n"
    )
    return HttpResponse(body, content_type='text/plain')


# dl_leaflet_jpg feature removed per request
