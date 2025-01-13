from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from .models import Order
from django.contrib import messages

@login_required
def order_history_view(request):
    orders = Order.objects.filter(user=request.user, status='paid').order_by('-created_at')
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

@login_required
def delivery_slots_view(request):
    order_id = request.GET.get('order_id')

    if order_id:
        try:
            order = Order.objects.get(id=order_id, user=request.user)
        except Order.DoesNotExist:
            messages.error(request, "That order does not exist or is not yours.")
            return redirect('cart_view')
    else:
        try:
            order = Order.objects.filter(user=request.user).latest('created_at')
        except Order.DoesNotExist:
            messages.error(request, "No pending orders found.")
            return redirect('cart_view')

    if request.method == 'POST':
        delivery_date = request.POST.get('delivery_date')
        delivery_time = request.POST.get('delivery_time')
        if delivery_date and delivery_time:
            order.delivery_date = delivery_date
            order.delivery_time = delivery_time
            order.save()

            messages.success(request, f"Delivery slot saved for Order #{order.id}!")
            return redirect('checkout')
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



