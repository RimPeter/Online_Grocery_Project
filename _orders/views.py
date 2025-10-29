from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from .models import Order, OrderItem
from _accounts.models import Address, Company   
from _catalog.models import All_Products
from decimal import Decimal
from datetime import date, timedelta
from django.contrib import messages
from io import BytesIO
from django.conf import settings
from django.core.mail import EmailMessage
from reportlab.platypus import Image
from django.http import HttpResponse
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from django.urls import reverse

# Statuses that permit invoice access/download/email
ALLOWED_INVOICE_STATUSES = ('paid', 'processed', 'delivered')

@login_required
def order_history_view(request):
    orders = (
        Order.objects
        .filter(
            user=request.user,
            status__in=('paid', 'processed', 'delivered')
        )
        .prefetch_related('items__product')
        .order_by('-created_at')
    )
    return render(request, '_orders/order_history.html', {'orders': orders})

@login_required
def order_summery_view(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    order_items = order.items.select_related('product').all()

    # Calculate per-item subtotal and total
    for item in order_items:
        item.subtotal = item.price * item.quantity
    total = sum(item.subtotal for item in order_items)

    # Get the user's default address (fallback to first if none marked default)
    addresses = Address.objects.filter(user=request.user)
    if not addresses.exists():
        messages.error(request, "Please add a delivery address before checking out.")
        return redirect('manage_addresses')
    default_address = addresses.filter(is_default=True).first() or addresses.first()

    context = {
        'order': order,
        'order_items': order_items,
        'total': total,
        'default_address': default_address, 
    }
    return render(request, '_orders/order_summery.html', context)

@login_required
def delivery_slots_view(request):
    order_id = request.GET.get('order_id')

    # Enforce minimum order total before allowing checkout
    try:
        MIN_ORDER_TOTAL = Decimal('40.00')
    except Exception:
        MIN_ORDER_TOTAL = Decimal('40.00')

    # Compute current cart total from session
    cart = request.session.get('cart', {})
    total_price = Decimal('0.00')
    if cart:
        product_ids = list(cart.keys())
        products = All_Products.objects.filter(pk__in=product_ids)
        price_by_id = {str(p.pk): Decimal(str(p.price)) for p in products}
        for pid, qty in cart.items():
            price = price_by_id.get(str(pid))
            if price is not None:
                try:
                    q = int(qty)
                except (TypeError, ValueError):
                    q = 0
                total_price += price * q

    if total_price < MIN_ORDER_TOTAL:
        shortfall = (MIN_ORDER_TOTAL - total_price).quantize(Decimal('0.01'))
        messages.error(
            request,
            f"Minimum order is £{MIN_ORDER_TOTAL:.2f}. Add £{shortfall:.2f} more to proceed."
        )
        return redirect('cart_view')

    # Try to get an order by ID, or get the latest pending order
    if order_id:
        try:
            order = Order.objects.get(id=order_id, user=request.user)
        except Order.DoesNotExist:
            messages.error(request, "That order does not exist or is not yours.")
            return redirect('cart_view')
    else:
        try:
            order = Order.objects.filter(user=request.user, status='pending').latest('created_at')
        except Order.DoesNotExist:
            order = None

    # If order is missing or has no order items, create one from the session cart
    if not order or order.items.count() == 0:
        cart = request.session.get('cart', {})
        if not cart:
            messages.error(request, "Your cart is empty. Please add items before checking out.")
            return redirect('cart_view')

        total_price = 0
        product_ids = list(cart.keys())
        products = All_Products.objects.filter(pk__in=product_ids)
        for product in products:
            quantity = cart[str(product.pk)]
            total_price += product.price * quantity

        order = Order.objects.create(
            user=request.user,
            total=total_price,
            status='pending'
        )

        for product in products:
            quantity = cart[str(product.pk)]
            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=quantity,
                price=product.price
            )

    # Now proceed with delivery slot selection
    # Compute max date constraint (today + 14 days)
    today = date.today()
    max_date = today + timedelta(days=14)
    max_date_str = max_date.strftime('%Y-%m-%d')

    if request.method == 'POST':
        delivery_date_str = request.POST.get('delivery_date')
        delivery_time = request.POST.get('delivery_time')
        if delivery_date_str and delivery_time:
            try:
                # Parse and validate date range
                year, month, day = map(int, delivery_date_str.split('-'))
                dd = date(year, month, day)
            except Exception:
                dd = None

            if not dd:
                messages.error(request, "Invalid delivery date format.")
            elif dd < today:
                messages.error(request, "Delivery date cannot be in the past.")
            elif dd > max_date:
                messages.error(request, "Delivery date cannot be more than 2 weeks from today.")
            else:
                # Save using validated values
                order.delivery_date = dd
                order.delivery_time = delivery_time
                order.save()

                messages.success(request, f"Delivery slot saved for Order #{order.id}!")
                return redirect('order_summery', order_id=order.id)

        if not delivery_date_str or not delivery_time:
            messages.error(request, "Please provide both a valid delivery date and time.")
        return render(request, '_orders/delivery_slots.html', {'order': order, 'max_date': max_date_str})

    return render(request, '_orders/delivery_slots.html', {'order': order, 'max_date': max_date_str})

@login_required
def delete_order_view(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    if request.method == 'POST':
        # Make sure only the owner can delete
        order.delete()
        messages.success(request, f"Order #{order_id} has been deleted.")
        return redirect('order_history')
    else:
        messages.error(request, "Invalid request method.")
        return redirect('order_history')

@login_required
def pending_order_view(request):
    """
    Displays the 'pending' order details before the user selects a delivery slot.
    """
    # Try retrieving an existing pending order for this user
    try:
        order = Order.objects.get(user=request.user, status='pending')
    except Order.DoesNotExist:
        messages.error(request, "You have no pending order.")
        return redirect('cart_view')  # or wherever makes sense

    # Fetch related order items (assuming you have an OrderItem model)
    order_items = order.items.select_related('product').all()

    # Calculate totals or retrieve from your model logic
    total = sum(item.price * item.quantity for item in order_items)

    # Pass order and items to the template
    context = {
        'order': order,
        'order_items': order_items,
        'total': total,
    }
    return render(request, '_orders/pending_order.html', context)

@login_required
def invoice_page_view(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)

    # Only allow invoices for paid/processed/delivered orders
    if order.status not in ALLOWED_INVOICE_STATUSES:
        messages.error(request, "Invoice is available after payment.")
        return redirect('order_summery', order_id=order.id)

    order_items = order.items.select_related('product').all()
    for item in order_items:
        item.subtotal = item.price * item.quantity
    total = sum(i.subtotal for i in order_items)

    # If you show addresses on the invoice, pick default/fallback:
    default_address = Address.objects.filter(user=request.user).order_by('-is_default').first()
    company = getattr(Company, "get_default", None)
    company = company() if callable(company) else Company.objects.filter(is_default=True).first() or Company.objects.first()

    
    try:
        company = Company.get_default()
    except Exception:
        company = Company.objects.filter(is_default=True).first() or Company.objects.first()


    return render(
        request,
        '_orders/invoice_page.html',
        {'order': order, 
         'order_items': order_items, 
         'total': total, 
         'default_address': default_address,
         'company': company
        }
    )

@login_required
def invoice_pdf_view(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)

    if order.status not in ALLOWED_INVOICE_STATUSES:
        messages.error(request, "Invoice is available after payment.")
        return redirect('order_summery', order_id=order.id)

    pdf_bytes = _build_invoice_pdf_bytes(request, order)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="invoice-{order.id}.pdf"'
    return response

@login_required
def email_invoice_view(request, order_id):
    if request.method != 'POST':
        messages.error(request, "Invalid request method.")
        return redirect('invoice_page', order_id=order_id)

    order = get_object_or_404(Order, id=order_id, user=request.user)
    if order.status not in ALLOWED_INVOICE_STATUSES:
        messages.error(request, "Invoice can be emailed after payment.")
        return redirect('order_summery', order_id=order.id)

    try:
        pdf_bytes = _build_invoice_pdf_bytes(request, order)
        subject = f"Your Invoice #{order.id}"
        body = (
            f"Hi {request.user.get_full_name() or request.user.username},\n\n"
            f"Attached is your invoice #{order.id}.\n\nThanks for your order!"
        )
        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[request.user.email],
        )
        email.attach(f"invoice-{order.id}.pdf", pdf_bytes, "application/pdf")
        email.send(fail_silently=False)
        messages.success(request, "Invoice emailed to you.")
    except Exception as e:
        messages.error(request, f"Could not email the invoice: {e}")

    return redirect('invoice_page', order_id=order.id)


@login_required
def _build_invoice_pdf_bytes(request, order):
    """Return PDF bytes for the given order (same content as invoice_pdf_view)."""
    order_items = order.items.select_related('product').all()
    for item in order_items:
        item.subtotal = item.price * item.quantity
    total = sum(i.subtotal for i in order_items)

    default_address = Address.objects.filter(user=request.user).order_by('-is_default').first()

    try:
        company = Company.get_default()
    except Exception:
        company = Company.objects.filter(is_default=True).first() or Company.objects.first()

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=48, bottomMargin=36
    )
    styles = getSampleStyleSheet()
    elements = []

    # Company block
    if company:
        if getattr(company, "logo", None) and hasattr(company.logo, "path"):
            try:
                elements.append(Image(company.logo.path, width=120, height=40))
                elements.append(Spacer(1, 6))
            except Exception:
                pass
        elements.append(Paragraph(company.legal_name or company.name, styles['Heading2']))

        addr_line_1 = company.address_line1
        if company.address_line2:
            addr_line_1 += f", {company.address_line2}"
        city_line = company.city
        if company.region:
            city_line += f", {company.region}"
        city_line += f" {company.postal_code}, {company.country}"
        elements.append(Paragraph(addr_line_1, styles['Normal']))
        elements.append(Paragraph(city_line, styles['Normal']))

        meta_bits = []
        if company.vat_number: meta_bits.append(f"VAT: {company.vat_number}")
        if company.company_number: meta_bits.append(f"Company No: {company.company_number}")
        if meta_bits:
            elements.append(Paragraph(" · ".join(meta_bits), styles['Normal']))

        contact_bits = []
        if company.email: contact_bits.append(company.email)
        if company.phone: contact_bits.append(company.phone)
        if company.website: contact_bits.append(company.website)
        if contact_bits:
            elements.append(Paragraph(" · ".join(contact_bits), styles['Normal']))
        elements.append(Spacer(1, 12))

    # Header
    elements.append(Paragraph(f"Invoice #{order.id}", styles['Title']))
    elements.append(Paragraph(order.created_at.strftime("%Y-%m-%d %H:%M"), styles['Normal']))
    elements.append(Spacer(1, 12))

    # Customer / Address
    elements.append(Paragraph(f"<b>Customer:</b> {request.user.get_full_name() or request.user.username}", styles['Normal']))
    elements.append(Paragraph(f"<b>Email:</b> {request.user.email}", styles['Normal']))
    if default_address:
        addr_lines = f"{default_address.street_address}"
        if default_address.apartment:
            addr_lines += f", {default_address.apartment}"
        addr_lines += f"<br/>{default_address.city}, {default_address.postal_code}"
        elements.append(Paragraph(f"<b>Address:</b><br/>{addr_lines}", styles['Normal']))
    elements.append(Spacer(1, 12))

    # Items table
    data = [["Item", "Qty", "Price", "Subtotal"]]
    for it in order_items:
        data.append([it.product.name, str(it.quantity), f"£{it.price:.2f}", f"£{it.subtotal:.2f}"])

    table = Table(data, colWidths=[260, 60, 80, 80])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('TEXTCOLOR', (0,0), (-1,0), colors.black),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('ALIGN', (1,1), (-1,-1), 'RIGHT'),
        ('ALIGN', (0,0), (0,-1), 'LEFT'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('TOPPADDING', (0,0), (-1,0), 6),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 12))

    # Totals
    total_val = sum(getattr(i, "subtotal", i.price * i.quantity) for i in order_items)
    elements.append(Paragraph(f"<b>Total:</b> £{total_val:.2f}", styles['Heading3']))

    # Delivery slot
    if order.delivery_date or order.delivery_time:
        slot = []
        if order.delivery_date: slot.append(order.delivery_date.strftime("%Y-%m-%d"))
        if order.delivery_time: slot.append(order.delivery_time.strftime("%H:%M"))
        elements.append(Spacer(1, 6))
        elements.append(Paragraph(f"<b>Delivery:</b> {' '.join(slot)}", styles['Normal']))

    # Footer
    try:
        company = Company.get_default()
    except Exception:
        company = Company.objects.filter(is_default=True).first() or Company.objects.first()
    if company and company.invoice_footer:
        elements.append(Spacer(1, 18))
        elements.append(Paragraph(company.invoice_footer.replace("\n", "<br/>"), styles['Normal']))

    doc.build(elements)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf


@login_required
def reorder_order_view(request, order_id):
    """Add all items from a past order back into the session cart."""
    if request.method != 'POST':
        messages.error(request, "Invalid request method.")
        return redirect('order_history')

    order = get_object_or_404(Order, id=order_id, user=request.user)

    cart = request.session.get('cart', {})
    added_count = 0
    for item in order.items.select_related('product'):
        pid = str(item.product_id)
        current = int(cart.get(pid, 0))
        try:
            qty = int(item.quantity)
        except (TypeError, ValueError):
            qty = 1
        cart[pid] = current + max(1, qty)
        added_count += 1

    request.session['cart'] = cart

    if added_count:
        messages.success(request, f"Added {added_count} item(s) from Order #{order.id} to your cart.")
    else:
        messages.info(request, "No items to reorder from that order.")

    # redirect back to history by default
    return_to = request.POST.get('return_to') or reverse('order_history')
    return redirect(return_to)


