from django.shortcuts import render, get_object_or_404, redirect
from collections import defaultdict
from .models import All_Products
from django.conf import settings
from django.contrib import messages
import json
import os
from django.db.models import Q
from django.db.models.functions import Lower, Trim
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from _orders.models import Order, OrderItem
from django.contrib.auth.decorators import login_required
from pathlib import Path
from django.urls import reverse
from decimal import Decimal
from django.utils.http import url_has_allowed_host_and_scheme


def home(request):
    # Build dynamic Category shortcuts from all categories and subcategories
    subcats = []
    try:
        qs = (
            All_Products.objects
            .exclude(image_url__isnull=True)
            .exclude(image_url='')
            .exclude(image_url='/img/products/no-image.png')
            .order_by('sub_category', 'sub_subcategory', 'id')
        )
        seen = set()
        for p in qs:
            l1 = (p.sub_category or '').strip() or 'Other'
            l2 = (p.sub_subcategory or '').strip() or 'Other'
            key = (l1.casefold(), l2.casefold())
            if key in seen:
                continue
            seen.add(key)
            subcats.append({
                'name': l2,
                'image_url': p.image_url,
                'l1': l1,
                'l2': l2,
            })
        # Sort by parent then child for tidy grouping
        subcats.sort(key=lambda x: (x['l1'].casefold(), x['name'].casefold()))
    except Exception:
        subcats = []

    return render(request, '_catalog/home_new.html', {
        'subcats': subcats,
    })

def _load_category_json():
    """Load category JSON from whichever app path exists.
    Tries `_catalog/management/commands/` first, then `_product_management/...`.
    Returns an empty dict if not found to avoid 500s.
    """
    candidates = [
        Path(settings.BASE_DIR)
        / "_catalog"
        / "management"
        / "commands"
        / "product_category.json",
        Path(settings.BASE_DIR)
        / "_product_management"
        / "management"
        / "commands"
        / "product_category.json",
    ]
    for p in candidates:
        try:
            if p.exists():
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            # If a candidate exists but can't be read/parsed, try the next.
            continue
    return {}

def product_detail(request, pk):
    product = get_object_or_404(All_Products, pk=pk)
    return render(request, '_catalog/product_detail.html', {'product': product})

def product_list(request):
    # Load category JSON (supports multiple candidate locations)
    raw = _load_category_json()

    # Optional helper (kept even if we don't use URLs in UI)
    def pick_best_url(url_or_list):
        if isinstance(url_or_list, list):
            for pref in ("s=200", "s=100"):
                for u in url_or_list:
                    if f"?{pref}" in u or f"&{pref}" in u:
                        return u
            return url_or_list[-1]
        return url_or_list

    # Build tree and suggestion lists
    category_tree = {}
    for level1 in sorted(raw.keys(), key=str.casefold):
        node = raw[level1]
        if isinstance(node, dict):
            sub = {}
            for level2 in sorted(node.keys(), key=str.casefold):
                sub[level2] = pick_best_url(node[level2])
            category_tree[level1] = sub
        else:
            category_tree[level1] = pick_best_url(node)

    level1_names = sorted(category_tree.keys(), key=str.casefold)
    level2_names = []
    for node in category_tree.values():
        if isinstance(node, dict):
            level2_names.extend(node.keys())
    level2_names = sorted(set(level2_names), key=str.casefold)

    # Filters
    query = request.GET.get('q', '').strip()
    l1 = request.GET.get('l1', '').strip()
    l2 = request.GET.get('l2', '').strip()

    # Show all products; handle placeholder images in template
    products = All_Products.objects.all().order_by('id')

    if l2:
        # Normalize DB fields with Trim+Lower to avoid mismatch on stray spaces/case
        l1n = l1.strip().lower()
        l2n = l2.strip().lower()
        products = (
            products
            .annotate(l1_norm=Lower(Trim('sub_category')), l2_norm=Lower(Trim('sub_subcategory')))
            .filter(l1_norm=l1n, l2_norm=l2n)
        )
    elif l1:
        l1n = l1.strip().lower()
        products = (
            products
            .annotate(l1_norm=Lower(Trim('sub_category')))
            .filter(l1_norm=l1n)
        )
    elif query:
        q_ci = query.casefold()
        if q_ci in {n.casefold() for n in level2_names}:
            qn = query.strip().lower()
            products = (
                products
                .annotate(l2_norm=Lower(Trim('sub_subcategory')))
                .filter(l2_norm=qn)
            )
        elif q_ci in {n.casefold() for n in level1_names}:
            qn = query.strip().lower()
            products = (
                products
                .annotate(l1_norm=Lower(Trim('sub_category')))
                .filter(l1_norm=qn)
            )
        else:
            products = products.filter(
                Q(name__icontains=query) |
                Q(main_category__icontains=query) |
                Q(sub_category__icontains=query) |
                Q(sub_subcategory__icontains=query)
            )
    elif l2:
        products = products.filter(sub_category__iexact=l1, sub_subcategory__iexact=l2)
    elif l1:
        products = products.filter(sub_category__iexact=l1)
    # Pagination
    paginator = Paginator(products, 24)
    page_number = request.GET.get('page')
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    # Build context ONCE (after page_obj exists)
    context = {
        'products': page_obj,
        'page_obj': page_obj,
        'query': query,
        'category_tree': category_tree,
        'level1_names': level1_names,
        'level2_names': level2_names,
    }

    # Add recent purchased items from the user's last 3 non-pending orders
    if request.user.is_authenticated:
        try:
            recent_orders = (
                Order.objects
                .filter(user=request.user, status__in=['paid', 'processed', 'delivered'])
                .order_by('-created_at')[:3]
            )
            seen = set()
            recent_items = []
            for order in recent_orders:
                for it in order.items.select_related('product').all():
                    pid = it.product_id
                    if pid in seen or not it.product:
                        continue
                    seen.add(pid)
                    recent_items.append({
                        'product_id': pid,
                        'name': it.product.name,
                        'quantity': it.quantity,
                        'image_url': it.product.image_url or '',
                    })
            context['recent_purchased_items'] = recent_items
        except Exception:
            context['recent_purchased_items'] = []

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
    total_price = Decimal('0.00')
    products_by_id = {}
    if cart:
        product_ids = list(cart.keys())
        products = All_Products.objects.filter(pk__in=product_ids)
        products_by_id = {str(p.pk): p for p in products}
        for pid, quantity in cart.items():
            product = products_by_id.get(str(pid))
            if product:
                # ensure Decimal math
                item_price = Decimal(str(product.price))
                qty = int(quantity)
                item_total = item_price * qty
                total_price += item_total
                cart_items.append({
                    'product': product,
                    'quantity': qty,
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

    # Fixed delivery charge applied on cart totals display
    delivery_charge = Decimal('1.50') if cart_items else Decimal('0.00')
    grand_total = (total_price + delivery_charge).quantize(Decimal('0.01'))

    context = {
        'cart_items': cart_items,
        'total_price': total_price.quantize(Decimal('0.01')),
        'delivery_charge': delivery_charge,
        'grand_total': grand_total,
        'order': order,  # This order now has updated OrderItems.
        'created_new': created_new,
    }
    return render(request, '_catalog/cart.html', context)

def add_to_cart(request, product_id):
    cart = request.session.get('cart', {})

    # Always store keys as strings in the session cart
    pid = str(product_id)

    # Read quantity from the form, default to 1
    qty_str = request.POST.get('quantity', '1')
    try:
        qty = max(1, int(qty_str))
    except (TypeError, ValueError):
        qty = 1

    # Add or increment
    current = int(cart.get(pid, 0))
    cart[pid] = current + qty

    # Save back to session
    request.session['cart'] = cart

    # Feedback
    if current:
        msg_qty = qty
        messages.success(request, f"Added {msg_qty} more to cart.")
    else:
        messages.success(request, "Product added to cart.")

    # Redirect back where the user came from (or product list as fallback)
    return_to = request.POST.get('return_to') or request.META.get('HTTP_REFERER') or reverse('product_list')
    if not url_has_allowed_host_and_scheme(return_to, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return_to = reverse('product_list')
    return redirect(return_to)

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

        elif action == 'clear':
            # Remove all items from the cart
            cart = {}
            messages.success(request, "All items removed from your cart.")

        # Save the updated cart back to the session
        request.session['cart'] = cart

    return redirect('cart_view')

def load_more_products(request):
    page_number = request.GET.get('page', 1)
    query = request.GET.get('q', '').strip()
    l1 = request.GET.get('l1', '').strip()
    l2 = request.GET.get('l2', '').strip()

    # Show all products; handle placeholder images in template
    products_qs = All_Products.objects.all().order_by('id')

    # Rebuild the category name sets (or refactor into a helper if you prefer)
    raw = _load_category_json()
    level1_names, level2_names = set(), set()
    for k, node in raw.items():
        level1_names.add(k)
        if isinstance(node, dict):
            level2_names.update(node.keys())

    if l2:
        l1n = l1.strip().lower()
        l2n = l2.strip().lower()
        products_qs = (
            products_qs
            .annotate(l1_norm=Lower(Trim('sub_category')), l2_norm=Lower(Trim('sub_subcategory')))
            .filter(l1_norm=l1n, l2_norm=l2n)
        )
    elif l1:
        l1n = l1.strip().lower()
        products_qs = (
            products_qs
            .annotate(l1_norm=Lower(Trim('sub_category')))
            .filter(l1_norm=l1n)
        )
    elif query:
        q_ci = query.casefold()
        if q_ci in {n.casefold() for n in level2_names}:
            qn = query.strip().lower()
            products_qs = (
                products_qs
                .annotate(l2_norm=Lower(Trim('sub_subcategory')))
                .filter(l2_norm=qn)
            )
        elif q_ci in {n.casefold() for n in level1_names}:
            qn = query.strip().lower()
            products_qs = (
                products_qs
                .annotate(l1_norm=Lower(Trim('sub_category')))
                .filter(l1_norm=qn)
            )
        else:
            products_qs = products_qs.filter(
                Q(name__icontains=query) |
                Q(main_category__icontains=query) |
                Q(sub_category__icontains=query) |
                Q(sub_subcategory__icontains=query)
            )
    elif l2:
        l1n = l1.strip().lower()
        l2n = l2.strip().lower()
        products_qs = (
            products_qs
            .annotate(l1_norm=Lower(Trim('sub_category')), l2_norm=Lower(Trim('sub_subcategory')))
            .filter(l1_norm=l1n, l2_norm=l2n)
        )
    elif l1:
        l1n = l1.strip().lower()
        products_qs = (
            products_qs
            .annotate(l1_norm=Lower(Trim('sub_category')))
            .filter(l1_norm=l1n)
        )
        
    paginator = Paginator(products_qs, 8)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        '_catalog/partial_products.html',
        {'page_obj': page_obj, 'products': page_obj}
    )


