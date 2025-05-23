from django.shortcuts import render, get_object_or_404, redirect
from collections import defaultdict
from .models import All_Products
from django.conf import settings
from django.contrib import messages
import json
import os
from django.db.models import Q
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from _orders.models import Order, OrderItem
from _catalog.models import All_Products
from django.contrib.auth.decorators import login_required



def home(request):
    return render(request, '_catalog/home.html')

def product_detail(request, pk):
    product = get_object_or_404(All_Products, pk=pk)
    return render(request, '_catalog/product_detail.html', {'product': product})

def product_list(request):
    # Load JSON file
    category_file = os.path.join(settings.BASE_DIR, 'category_structure.json')
    with open(category_file, 'r', encoding='utf-8') as f:
        category_data = json.load(f)

    # Extract Level 1 and Level 2 categories
    level1_to_level2 = defaultdict(list)
    for level1, level2_list in category_data.items():
        for level2_dict in level2_list:
            for level2 in level2_dict.keys():
                if level2 not in level1_to_level2[level1]:
                    level1_to_level2[level1].append(level2)

    # Product filtering logic
    query = request.GET.get('q', '').strip()
    products = All_Products.objects.filter(ga_product_id__endswith="1")  # Filter products ending with '1'
    products = products.exclude(image_url='/img/products/no-image.png')  # Exclude products with no image
    products = products.order_by('id')
    if query:
        products = products.filter(
           Q(main_category__icontains=query) |
           Q(sub_category__icontains=query) |
           Q(sub_subcategory__icontains=query)
           )

    # Pagination setup
    paginator = Paginator(products, 12)  # Show 12 products per page
    page_number = request.GET.get('page')

    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        page_obj = paginator.page(1)
    except EmptyPage:
        # If page is out of range, deliver last page of results.
        page_obj = paginator.page(paginator.num_pages)

    context = {
        'products': page_obj,  # Pass paginated products to the template
        'level1_to_level2': dict(level1_to_level2),  # Pass Level 1 to Level 2 mapping
        'page_obj': page_obj,  # Pass page object for pagination controls
        'query': query,  # Pass current query to maintain search in pagination links
    }
    return render(request, '_catalog/product.html', context)

@login_required
def cart_view(request):
    """
    Displays the shopping cart and associates it with a pending Order.
    Also, synchronizes the pending order items with the session cart.
    """
    # Get the cart from session (or use an empty dict if not found)
    cart = request.session.get('cart', {})

    # Fetch all pending orders for the user, ordered by newest first.
    pending_orders = Order.objects.filter(user=request.user, status='pending').order_by('-created_at')
    if pending_orders.exists():
        order = pending_orders.first()  # Use the latest pending order.
        created_new = False
        # Delete any older pending orders.
        if pending_orders.count() > 1:
            pending_orders.exclude(pk=order.pk).delete()
    else:
        # If no pending order exists, create a new one.
        order = Order.objects.create(user=request.user, status='pending')
        created_new = True

    # Build cart items and calculate the total price from session data.
    cart_items = []
    total_price = 0
    products_by_id = {}
    if cart:
        product_ids = list(cart.keys())
        products = All_Products.objects.filter(pk__in=product_ids)
        products_by_id = {str(p.pk): p for p in products}
        for pid, quantity in cart.items():
            product = products_by_id.get(str(pid))
            if product:
                item_total = product.price * quantity
                total_price += item_total
                cart_items.append({
                    'product': product,
                    'quantity': quantity,
                    'item_total': item_total,
                })

    # Synchronize the pending order with the session cart.
    # Remove any existing order items...
    order.items.all().delete()
    # ...and recreate them from the current cart.
    for pid, quantity in cart.items():
        product = products_by_id.get(str(pid))
        if product:
            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=quantity,
                price=product.price
            )

    context = {
        'cart_items': cart_items,
        'total_price': total_price,
        'order': order,  # This order now has updated OrderItems.
        'created_new': created_new,
    }
    return render(request, '_catalog/cart.html', context)

def add_to_cart(request, product_id):
    cart = request.session.get('cart', {})
    
    if product_id in cart:
        cart[product_id] += 1
        messages.success(request, "Quantity updated in cart.")
    else:
        cart[product_id] = 1
        messages.success(request, "Product added to cart.")
        
    request.session['cart'] = cart
    return redirect('product_list')

def update_cart(request):
    """
    Updates the cart: remove an item or change its quantity.
    """
    if request.method == 'POST':
        product_id = request.POST.get('product_id')
        action = request.POST.get('action')  # 'remove' or 'update'
        cart = request.session.get('cart', {})

        if action == 'remove':
            # Remove the item from cart
            if product_id in cart:
                del cart[product_id]
                messages.success(request, "Item removed from your cart.")

        elif action == 'update':
            # Change the quantity (only if it's valid and > 0)
            new_quantity = request.POST.get('quantity')
            if new_quantity is not None:
                new_quantity = int(new_quantity)
                if new_quantity > 0:
                    cart[product_id] = new_quantity
                    messages.success(request, "Item quantity updated.")
                    
                else:
                    # If 0 or negative, remove the item from the cart
                    if product_id in cart:
                        del cart[product_id]
                        messages.success(request, "Item removed from your cart.")

        # Save the updated cart back to the session
        request.session['cart'] = cart

    return redirect('cart_view')

def load_more_products(request):
    page_number = request.GET.get('page', 1)
    query = request.GET.get('q', '').strip()

    # Start with the same base queryset:
    products_qs = All_Products.objects.filter(ga_product_id__endswith="1")
    products_qs = products_qs.exclude(image_url='/img/products/no-image.png')
    products_qs = products_qs.order_by('id')   # same ordering
    print(products_qs.count()) 

    # Same filter condition:
    if query:
        products_qs = products_qs.filter(
            Q(main_category__icontains=query) |
            Q(sub_category__icontains=query) |
            Q(sub_subcategory__icontains=query)
            )

    paginator = Paginator(products_qs, 8)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        '_catalog/partial_products.html',
        {
            'page_obj': page_obj,  # or 'products': page_obj
            'products': page_obj   # so partial can loop & also check page_obj.has_next
        }
    )



