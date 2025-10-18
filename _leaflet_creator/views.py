from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseServerError
from django.shortcuts import render, redirect
from urllib.parse import urlparse, quote_plus
from io import BytesIO


def index(request):
    return HttpResponse("Leaflet Creator app is installed")


def dl_leaflet(request):
    return render(request, "_leaflet_creator/DL_size_leaflet.html")


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
