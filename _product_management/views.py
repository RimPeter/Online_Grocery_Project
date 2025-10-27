from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseServerError
from django.shortcuts import render, redirect, get_object_or_404
from urllib.parse import urlparse, quote_plus
from io import BytesIO
import base64

from django.template.loader import get_template
from django.conf import settings
from django.contrib.staticfiles import finders
from xhtml2pdf import pisa
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Sum, F, DecimalField, Value
from django.db.models.functions import Coalesce, Cast
from datetime import date, timedelta
from django.views.decorators.http import require_http_methods
import threading
from _catalog.models import All_Products
from _orders.models import Order, OrderItem
from django.contrib import messages

# Lazy import of WeasyPrint to avoid noisy import errors at startup on systems
# where native libraries (cairo/pango/etc.) are not available.
def _get_weasy():
    # Attempt to import WeasyPrint quietly; if native deps are missing,
    # the import may print guidance to stderr — suppress that in 'auto' mode.
    try:  # pragma: no cover
        import contextlib, io as _io
        buf = _io.StringIO()
        with contextlib.redirect_stderr(buf):
            from weasyprint import HTML as WPHTML, CSS as WPCSS  # type: ignore
        return WPHTML, WPCSS
    except Exception:
        return None, None
import os

"""PDF rendering helpers using Playwright (Chromium).

We replace WeasyPrint with Playwright for HTML -> PDF rendering. We keep
xhtml2pdf as a fallback so existing flows continue to work when Chromium
is not available in the runtime environment.
"""

def _has_playwright() -> bool:
    try:
        from playwright.sync_api import sync_playwright  # type: ignore  # noqa: F401
        return True
    except Exception:
        return False


def _inline_css(html: str, css_subpath: str) -> str:
    """Inline a static CSS file into the document <head>.

    Looks up the CSS via staticfiles finders using the subpath relative to
    STATIC_ROOT (e.g., 'css/leaflet.css'). If not found, returns the HTML
    unchanged.
    """
    try:
        css_path = finders.find(css_subpath)
        if not css_path:
            return html
        with open(css_path, 'r', encoding='utf-8') as fh:
            css = fh.read()
        inject = f"\n<style>{css}</style>\n"
        lower = html.lower()
        pos = lower.find('<head>')
        if pos != -1:
            insert_at = pos + len('<head>')
            return html[:insert_at] + inject + html[insert_at:]
        pos = lower.find('</head>')
        if pos != -1:
            return html[:pos] + inject + html[pos:]
        return inject + html
    except Exception:
        return html


def _render_pdf_playwright(html: str, request) -> bytes:
    """Render HTML to PDF using Playwright/Chromium.

    - Inlines key CSS for reliable print styling.
    - Adds a <base> tag so relative URLs (e.g., /static/...) resolve.
    - Prints backgrounds and removes margins to allow full-bleed designs.
    """
    from playwright.sync_api import sync_playwright  # type: ignore

    # Inline primary CSS files used by our templates
    if 'DL_size_leaflet' in html:
        html = _inline_css(html, 'css/leaflet.css')
    if 'Items To Order' in html or 'items-to-order' in html:
        html = _inline_css(html, 'css/main.css')

    # Ensure relative URLs resolve (static, images)
    try:
        base_href = request.build_absolute_uri('/')
    except Exception:
        base_href = '/'
    base_tag = f"<base href=\"{base_href}\">\n"
    lower = html.lower()
    pos = lower.find('<head>')
    if pos != -1:
        insert_at = pos + len('<head>')
        html = html[:insert_at] + base_tag + html[insert_at:]
    else:
        pos = lower.find('</head>')
        if pos != -1:
            html = html[:pos] + base_tag + html[pos:]
        else:
            html = base_tag + html

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.set_content(html, wait_until='networkidle')
        pdf_bytes = page.pdf(
            print_background=True,
            prefer_css_page_size=True,
        )
        context.close()
        browser.close()
        return pdf_bytes


# Backstop: ensure any lingering calls to _get_weasy() don't try to import.
def _get_weasy():  # pragma: no cover
    return None, None



def index(request):
    return HttpResponse("Product Management app is installed")


def dl_leaflet(request):
    # Choose QR image kind to mirror PDF renderer capabilities for visual parity
    active_renderer = _choose_renderer()
    qr_kind = "svg" if active_renderer == "playwright" else "png"
    return render(
        request,
        "_product_management/DL_size_leaflet.html",
        {"pdf": False, "qr_kind": qr_kind},
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
    kind = request.GET.get("kind", "svg").strip().lower() or "svg"

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
        if kind == "png":
            qr.save(buf, kind="png", scale=6)
            return HttpResponse(buf.getvalue(), content_type="image/png")
        else:
            qr.save(buf, kind="svg", scale=6)
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
    """Return 'playwright' if available/configured, otherwise 'xhtml2pdf'."""
    mode = getattr(settings, 'LEAFLET_PDF_RENDERER', 'auto')
    mode = (mode or 'auto').lower()
    # Back-compat: treat legacy 'weasyprint' as 'playwright'
    if mode == 'weasyprint':
        mode = 'playwright'
    if mode == 'playwright':
        return 'playwright' if _has_playwright() else 'xhtml2pdf'
    if mode == 'xhtml2pdf':
        return 'xhtml2pdf'
    # auto
    return 'playwright' if _has_playwright() else 'xhtml2pdf'


def dl_leaflet_pdf(request):
    """Render the DL leaflet as a downloadable PDF, embedding the QR image."""
    site = request.GET.get("site", "").strip()
    site = _ensure_scheme(site) if site else ""

    qr_data_uri = None
    active_renderer = _choose_renderer()
    if site:
        try:
            import segno  # type: ignore
            qr = segno.make(site)
            if active_renderer == "playwright":
                # Embed SVG for better fidelity
                buf = BytesIO()
                qr.save(buf, kind="svg", scale=3)
                b64 = base64.b64encode(buf.getvalue()).decode("ascii")
                qr_data_uri = f"data:image/svg+xml;base64,{b64}"
            else:
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

    template = get_template("_product_management/DL_size_leaflet.html")
    context = {"pdf": True, "qr_data_uri": qr_data_uri, "request": request}
    html = template.render(context)

    # Prefer Playwright if available for best CSS fidelity
    if active_renderer == 'playwright':
        try:
            pdf_bytes = _render_pdf_playwright(html, request)
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
    pw_available = _has_playwright() if str(configured).lower() != 'xhtml2pdf' else False
    active = _choose_renderer()
    body = (
        f"Configured: {configured}\n"
        f"Playwright available: {pw_available}\n"
        f"Active renderer: {active}\n"
    )
    return HttpResponse(body, content_type='text/plain')


# dl_leaflet_jpg feature removed per request


@staff_member_required
def active_orders(request):
    active_statuses = ('pending', 'paid', 'processed')
    dec = DecimalField(max_digits=12, decimal_places=2)
    amount_expr = F('items__price') * Cast('items__quantity', output_field=dec)
    orders = (
        Order.objects
        .filter(status__in=active_statuses)
        .select_related('user')
        .prefetch_related('items__product', 'user__addresses')
        .annotate(
            items_count=Count('items'),
            computed_total=Coalesce(Sum(amount_expr), Value(0, output_field=dec))
        )
        .order_by('-created_at')
    )
    return render(request, '_product_management/active_orders.html', {'orders': orders})


@staff_member_required
def completed_orders(request):
    dec = DecimalField(max_digits=12, decimal_places=2)
    amount_expr = F('items__price') * Cast('items__quantity', output_field=dec)
    orders = (
        Order.objects
        .filter(status='delivered')
        .select_related('user')
        .prefetch_related('items__product')
        .annotate(
            items_count=Count('items'),
            computed_total=Coalesce(Sum(amount_expr), Value(0, output_field=dec))
        )
        .order_by('-created_at')
    )
    return render(request, '_product_management/completed_orders.html', {'orders': orders})


@staff_member_required
def mark_order_completed(request, order_id: int):
    if request.method != 'POST':
        return HttpResponseBadRequest('Invalid method')

    order = get_object_or_404(Order, id=order_id)
    if order.status in ('pending', 'paid', 'processed'):
        order.status = 'delivered'
        order.save(update_fields=['status'])
        messages.success(request, f'Order #{order.id} marked as completed.')
    else:
        messages.info(request, f'Order #{order.id} is already {order.get_status_display().lower()}.')

    return redirect('_product_management:active_orders')


@staff_member_required
def mark_all_orders_completed(request):
    if request.method != 'POST':
        return HttpResponseBadRequest('Invalid method')

    active_statuses = ('pending', 'paid', 'processed')
    qs = Order.objects.filter(status__in=active_statuses)
    updated = qs.update(status='delivered')
    if updated:
        messages.success(request, f'Marked {updated} order(s) as completed.')
    else:
        messages.info(request, 'No active orders to complete.')
    return redirect('_product_management:active_orders')


@staff_member_required
def mark_order_active(request, order_id: int):
    if request.method != 'POST':
        return HttpResponseBadRequest('Invalid method')

    order = get_object_or_404(Order, id=order_id)
    if order.status == 'delivered':
        order.status = 'processed'
        order.save(update_fields=['status'])
        messages.success(request, f'Order #{order.id} moved back to Active.')
    else:
        messages.info(request, f'Order #{order.id} is {order.get_status_display().lower()}, not completed.')

    return redirect('_product_management:completed_orders')


@staff_member_required
def items_to_order(request):
    active_statuses = ('pending', 'paid', 'processed')
    items = (
        OrderItem.objects
        .filter(order__status__in=active_statuses)
        .values(
            'product_id',
            'product__name',
            'product__sku',
            'product__variant',
        )
        .annotate(
            total_qty=Sum('quantity'),
            orders_count=Count('order', distinct=True),
        )
        .order_by('product__name')
    )
    context = { 'items': items }
    return render(request, '_product_management/items_to_order.html', context)


@staff_member_required
def items_to_order_pdf(request):
    """Generate a PDF of the aggregated items to order (active orders only)."""
    active_statuses = ('pending', 'paid', 'processed')
    items = (
        OrderItem.objects
        .filter(order__status__in=active_statuses)
        .values(
            'product_id',
            'product__name',
            'product__sku',
            'product__variant',
        )
        .annotate(
            total_qty=Sum('quantity'),
            orders_count=Count('order', distinct=True),
        )
        .order_by('product__name')
    )

    template = get_template('_product_management/items_to_order_pdf.html')
    html = template.render({'items': items})

    if _choose_renderer() == 'playwright':
        try:
            pdf_bytes = _render_pdf_playwright(html, request)
            resp = HttpResponse(pdf_bytes, content_type='application/pdf')
            resp['Content-Disposition'] = 'attachment; filename=items-to-order.pdf'
            return resp
        except Exception:
            pass

    # Fallback to xhtml2pdf
    out = BytesIO()
    pisa.CreatePDF(html, dest=out, link_callback=_static_link_callback)
    resp = HttpResponse(out.getvalue(), content_type='application/pdf')
    resp['Content-Disposition'] = 'attachment; filename=items-to-order.pdf'
    return resp


@staff_member_required
def set_delivery_slot(request, order_id: int):
    order = get_object_or_404(Order.objects.select_related('user'), id=order_id)
    today = date.today()
    max_date = today + timedelta(days=14)
    max_date_str = max_date.strftime('%Y-%m-%d')

    if request.method == 'POST':
        delivery_date_str = request.POST.get('delivery_date')
        delivery_time = request.POST.get('delivery_time')

        if not delivery_date_str or not delivery_time:
            messages.error(request, 'Please provide both a delivery date and time.')
        else:
            try:
                y, m, d = map(int, delivery_date_str.split('-'))
                dd = date(y, m, d)
            except Exception:
                dd = None
            if not dd:
                messages.error(request, 'Invalid delivery date.')
            elif dd < today:
                messages.error(request, 'Delivery date cannot be in the past.')
            elif dd > max_date:
                messages.error(request, 'Delivery date cannot be more than 2 weeks from today.')
            else:
                order.delivery_date = dd
                order.delivery_time = delivery_time
                order.save(update_fields=['delivery_date', 'delivery_time'])
                messages.success(request, f'Delivery slot saved for Order #{order.id}.')
                return redirect('_product_management:active_orders')

    return render(
        request,
        '_product_management/set_delivery_slot.html',
        {'order': order, 'max_date': max_date_str}
    )


@staff_member_required
@require_http_methods(["GET", "POST"])
def commands(request):
    """Simple admin page to trigger management commands like datajob.

    Runs datajob in a background thread so the request does not block.
    """
    product_count = All_Products.objects.count()

    if request.method == 'POST':
        action = request.POST.get('action') or 'datajob'

        if action == 'datajob':
            run_all = bool(request.POST.get('all'))
            run_scrape = bool(request.POST.get('scrape')) or run_all
            if request.POST.get('no_scrape'):
                run_scrape = False
            run_variants = bool(request.POST.get('variants')) or run_all
            run_vat = bool(request.POST.get('vat')) or run_all
            run_home = bool(request.POST.get('home_subcats')) or run_all
            variants_limit = int(request.POST.get('variants_limit') or 0)
            variants_dry = bool(request.POST.get('variants_dry_run'))
            home_active = not bool(request.POST.get('home_inactive'))
            verbosity = int(request.POST.get('verbosity') or 1)

            def _run_datajob():
                try:
                    from django.core.management import call_command
                    call_command(
                        'datajob',
                        **{
                            'all': run_all,
                            'scrape': (not run_all and run_scrape),
                            'no_scrape': (not run_all and not run_scrape and bool(request.POST.get('no_scrape'))),
                            'variants': (not run_all and run_variants),
                            'variants_limit': variants_limit,
                            'variants_dry_run': variants_dry,
                            'vat': (not run_all and run_vat),
                            'home_subcats': (not run_all and run_home),
                            'home_inactive': (not home_active),
                            'verbosity': verbosity,
                        }
                    )
                except Exception:
                    # Intentionally swallow to avoid crashing the thread; errors will appear in server logs
                    pass

            threading.Thread(target=_run_datajob, daemon=True).start()
            messages.success(request, 'Data job started in background. Refresh later to see results.')
            return redirect('_product_management:commands')

        elif action == 'clear_all_products':
            # Extra safety: only superusers may execute
            if not request.user.is_superuser:
                messages.error(request, 'Only superusers may clear all products.')
                return redirect('_product_management:commands')

            ack = bool(request.POST.get('ack'))
            phrase = (request.POST.get('confirm_phrase') or '').strip()
            count_match = (request.POST.get('confirm_count') or '').strip()
            expected_phrase = 'DELETE ALL PRODUCTS'
            expected_count = str(product_count)

            if not ack or phrase != expected_phrase or count_match != expected_count:
                messages.error(request, 'Confirmation failed. Please follow the exact steps to proceed.')
                return redirect('_product_management:commands')

            def _run_clear():
                try:
                    from django.core.management import call_command
                    call_command('clear_all_products', verbosity=1)
                except Exception:
                    pass

            threading.Thread(target=_run_clear, daemon=True).start()
            messages.success(request, 'Clear all products started. This is destructive; check logs for progress.')
            return redirect('_product_management:commands')

    return render(request, '_product_management/commands.html', {'product_count': product_count})
