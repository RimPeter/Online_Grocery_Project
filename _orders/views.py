from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from .models import Order, OrderItem
from _catalog.models import All_Products
from django.contrib import messages

@login_required
def order_history_view(request):
    orders = Order.objects.filter(user=request.user,
                                  status='paid'
                                  ).order_by('-created_at')
    return render(request, '_orders/order_history.html', {'orders': orders})

@login_required
def order_summery_view(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    order_items = order.items.select_related('product').all()

    if not order_items:
        print("DEBUG: No order items found for order", order_id) 
           
    # Calculate subtotal for each item and total order price
    for item in order_items:
        item.subtotal = item.price * item.quantity
    total = sum(item.subtotal for item in order_items)
    
    context = {
        'order': order,
        'order_items': order_items,
        'total': total,
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

