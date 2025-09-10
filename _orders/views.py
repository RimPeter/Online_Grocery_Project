from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from .models import Order, OrderItem
from _catalog.models import All_Products
from django.contrib import messages
from _accounts.models import Address
from io import BytesIO
from django.http import HttpResponse
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

@login_required
def order_history_view(request):
    orders = Order.objects.filter(user=request.user,
                                  status__in= ('paid', 'processed', 'delivered')
                                  ).order_by('-created_at')
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
    if request.method == 'POST':
        delivery_date = request.POST.get('delivery_date')
        delivery_time = request.POST.get('delivery_time')
        if delivery_date and delivery_time:
            order.delivery_date = delivery_date
            order.delivery_time = delivery_time
            order.save()

            messages.success(request, f"Delivery slot saved for Order #{order.id}!")
            return redirect('order_summery', order_id=order.id)
        else:
            messages.error(request, "Please provide both a valid delivery date and time.")
            return render(request, '_orders/delivery_slots.html', {'order': order})

    return render(request, '_orders/delivery_slots.html', {'order': order})

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

    # Optional: only allow invoices for paid orders
    if order.status != 'paid':
        messages.error(request, "Invoice is available after payment.")
        return redirect('order_summery', order_id=order.id)

    order_items = order.items.select_related('product').all()
    for item in order_items:
        item.subtotal = item.price * item.quantity
    total = sum(i.subtotal for i in order_items)

    # If you show addresses on the invoice, pick default/fallback:
    default_address = None
    try:
        from _accounts.models import Address
        qs = Address.objects.filter(user=request.user)
        default_address = qs.filter(is_default=True).first() or qs.first()
    except Exception:
        pass

    return render(
        request,
        '_orders/invoice_page.html',
        {'order': order, 'order_items': order_items, 'total': total, 'default_address': default_address}
    )


@login_required
def invoice_pdf_view(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)

    # Optional: only allow invoices for paid orders
    # if order.status != 'paid':
    #     messages.error(request, "Invoice is available after payment.")
    #     return redirect('invoice_page', order_id=order.id)

    order_items = order.items.select_related('product').all()
    for item in order_items:
        item.subtotal = item.price * item.quantity
    total = sum(i.subtotal for i in order_items)

    # Pull default/fallback address
    default_address = None
    try:
        from _accounts.models import Address
        qs = Address.objects.filter(user=request.user)
        default_address = qs.filter(is_default=True).first() or qs.first()
    except Exception:
        pass

    # Build PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=36, leftMargin=36, topMargin=48, bottomMargin=36
    )
    styles = getSampleStyleSheet()
    elements = []

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
        data.append([
            it.product.name,
            str(it.quantity),
            f"£{it.price}",
            f"£{it.subtotal}",
        ])

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
    elements.append(Paragraph(f"<b>Total:</b> £{total}", styles['Heading3']))

    # Delivery slot (optional)
    if order.delivery_date or order.delivery_time:
        slot = []
        if order.delivery_date:
            slot.append(order.delivery_date.strftime("%Y-%m-%d"))
        if order.delivery_time:
            slot.append(order.delivery_time.strftime("%H:%M"))
        elements.append(Spacer(1, 6))
        elements.append(Paragraph(f"<b>Delivery:</b> {' '.join(slot)}", styles['Normal']))

    doc.build(elements)
    pdf = buffer.getvalue()
    buffer.close()

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="invoice-{order.id}.pdf"'
    return response


