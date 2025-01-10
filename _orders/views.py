from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from .models import Order
from django.contrib import messages

@login_required
def order_history_view(request):
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    return render(request, '_orders/order_history.html', {'orders': orders})

@login_required
def order_detail_view(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    order_items = order.items.select_related('product').all()
    
    for item in order_items:
        item.subtotal = item.price * item.quantity
        
    context = {
        'order': order,
        'order_items': order_items,
    }
    return render(request, '_orders/order_detail.html', context)

def delivery_slots_view(request):
    # For now, just render a template that shows available slots
    return render(request, '_scheduling/delivery_slots.html')

@login_required
def delivery_slots_view(request):
    """
    Allows user to pick date/time for their delivery, 
    then saves it to their Order (which we assume is 
    created or pending).
    """
    # Typically, you'd have logic to find or create the 
    # "current/pending" Order. 
    # For demo, let's grab the most recent pending order:
    try:
        order = Order.objects.filter(user=request.user).latest('created_at')
    except Order.DoesNotExist:
        messages.error(request, "No pending orders found.")
        return redirect('cart_view')  # or wherever makes sense

    if request.method == 'POST':
        delivery_date = request.POST.get('delivery_date')
        delivery_time = request.POST.get('delivery_time')

        # Validate data is present (basic check)
        if not delivery_date or not delivery_time:
            messages.error(request, "Please select both date and time.")
            return render(request, '_orders/delivery_slots.html')

        # Save to your Order model (assuming you have fields for these)
        order.delivery_date = delivery_date
        order.delivery_time = delivery_time
        order.save()

        messages.success(request, "Delivery slot saved!")
        # After saving, you might redirect to your checkout or payment page:
        return redirect('checkout')

    # GET request: just show the form
    return render(request, '_orders/delivery_slots.html')

