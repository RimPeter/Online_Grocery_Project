from django.shortcuts import render, get_object_or_404, redirect
from collections import defaultdict
from .models import All_Products, HomeCategoryTile, HomeValuePillar
from django.conf import settings
from django.contrib import messages
import json
import os
from django.db import connection
from django.db.models import Q, F, Value, DecimalField, ExpressionWrapper, Case, When
from django.db.models.functions import Lower, Trim, Greatest, Coalesce
from django.db.utils import DatabaseError
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import JsonResponse, Http404, HttpResponseForbidden
from django.views.decorators.http import require_GET, require_POST
from _orders.models import Order, OrderItem
from django.contrib.auth.decorators import login_required
from pathlib import Path
from django.urls import reverse
from decimal import Decimal, InvalidOperation
from django.utils.http import url_has_allowed_host_and_scheme

try:
    from django.contrib.postgres.search import TrigramSimilarity
except ImportError:  # pragma: no cover - postgres not available in dev
    TrigramSimilarity = None


DEFAULT_HOME_PILLARS = [
    {
        'key': 'speed',
        'title': 'Next-day windows',
        'subtitle': 'Pick a delivery time that fits your schedule',
        'sort_order': 10,
    },
    {
        'key': 'selection',
        'title': 'Great local selection',
        'subtitle': 'From fresh produce to daily essentials',
        'sort_order': 20,
    },
    {
        'key': 'reorders',
        'title': 'Easy reorders',
        'subtitle': 'Save time with your recent items and favorites',
        'sort_order': 30,
    },
]

def _normalize_category_value(value):
    value = (value or '').strip()
    return value or 'Other'


def _auto_home_tiles():
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
            l1 = _normalize_category_value(p.sub_category)
            l2 = _normalize_category_value(p.sub_subcategory)
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
        subcats.sort(key=lambda x: (x['l1'].casefold(), x['name'].casefold()))
    except Exception:
        subcats = []
    return subcats


def _home_value_pillars():
    try:
        pillars = list(HomeValuePillar.objects.order_by('sort_order', 'id'))
    except Exception:
        pillars = []
    if pillars:
        return [
            {
                'title': pillar.title,
                'subtitle': pillar.subtitle,
            }
            for pillar in pillars
        ]
    return [
        {
            'title': default['title'],
            'subtitle': default['subtitle'],
        }
        for default in DEFAULT_HOME_PILLARS
    ]


def _group_home_tiles(subcats):
    if not subcats:
        return []
    grouped = defaultdict(list)
    for tile in subcats:
        grouped[tile['l1']].append(tile)
    category_groups = []
    for l1 in sorted(grouped.keys(), key=str.casefold):
        items = grouped[l1]
        items.sort(key=lambda x: x['name'].casefold())
        category_groups.append({'l1': l1, 'label': l1, 'items': items})
    return category_groups


def _manual_home_groups(auto_tiles):
    try:
        tiles = list(
            HomeCategoryTile.objects
            .filter(is_active=True)
            .order_by('sort_order', 'id')
        )
    except Exception:
        return []
    if not tiles:
        return []

    grouped_auto = defaultdict(list)
    for tile in auto_tiles:
        grouped_auto[tile['l1']].append(tile)

    manual_groups = []
    for tile in tiles:
        l1 = _normalize_category_value(tile.l1)
        children = grouped_auto.get(l1)
        if not children:
            continue
        label = (tile.display_name or '').strip() or l1
        manual_groups.append({
            'l1': l1,
            'label': label,
            'items': children,
        })
    return manual_groups


def home(request):
    auto_tiles = _auto_home_tiles()
    manual_groups = _manual_home_groups(auto_tiles)
    value_pillars = _home_value_pillars()
    if manual_groups:
        category_groups = manual_groups
        subcats = [tile for group in manual_groups for tile in group['items']]
        using_manual = True
    else:
        subcats = auto_tiles
        category_groups = _group_home_tiles(subcats)
        using_manual = False

    return render(request, '_catalog/home_new.html', {
        'subcats': subcats,
        'category_groups': category_groups,
        'home_tiles_are_manual': using_manual,
        'value_pillars': value_pillars,
    })

def _ensure_rsp(product):
    """Ensure RSP is set for display.

    If DB did not provide an RSP (None or 0), compute as price * 1.3.
    Mutates only the in-memory instance for rendering.
    """
    try:
        if not product:
            return product
        cur = getattr(product, 'rsp', None)
        if cur is None or Decimal(str(cur)) == Decimal('0'):
            price = getattr(product, 'price', None)
            if price is not None:
                product.rsp = (Decimal(str(price)) * Decimal('1.30')).quantize(Decimal('0.01'))
    except Exception:
        pass
    return product

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

def _pick_best_url(url_or_list):
    if isinstance(url_or_list, list):
        for pref in ("s=200", "s=100"):
            for u in url_or_list:
                if f"?{pref}" in u or f"&{pref}" in u:
                    return u
        return url_or_list[-1]
    return url_or_list

def _category_metadata():
    """
    Returns (category_tree, level1_names, level2_names, level2_map)
    category_tree mirrors the JSON but with deterministic ordering and best-fit URLs.
    level2_map is a dict of {level1: [level2,...]} to help client-side filtering.
    """
    raw = _load_category_json() or {}
    category_tree = {}
    level1_names = []
    level2_names = set()
    level2_map = {}

    for level1 in sorted(raw.keys(), key=str.casefold):
        node = raw[level1]
        if isinstance(node, dict):
            ordered = {}
            for level2 in sorted(node.keys(), key=str.casefold):
                ordered[level2] = _pick_best_url(node[level2])
                level2_names.add(level2)
            category_tree[level1] = ordered
            level2_map[level1] = list(ordered.keys())
        else:
            category_tree[level1] = _pick_best_url(node)
            level2_map[level1] = []
        level1_names.append(level1)

    return category_tree, level1_names, sorted(level2_names, key=str.casefold), level2_map

def _apply_category_filters(queryset, l1, l2):
    """
    Shared helper to filter a queryset by level-1/level-2 names with trimmed/casefold logic.
    """
    if l2:
        l2n = l2.strip().lower()
        annotations = {
            'l2_norm': Lower(Trim('sub_subcategory')),
        }
        filters = {'l2_norm': l2n}
        if l1:
            l1n = l1.strip().lower()
            annotations['l1_norm'] = Lower(Trim('sub_category'))
            filters['l1_norm'] = l1n
        return queryset.annotate(**annotations).filter(**filters)
    if l1:
        l1n = l1.strip().lower()
        return (
            queryset
            .annotate(l1_norm=Lower(Trim('sub_category')))
            .filter(l1_norm=l1n)
        )
    return queryset

def product_detail(request, pk):
    product = get_object_or_404(All_Products, pk=pk)
    # Fallback RSP if missing for display and hiding logic
    _ensure_rsp(product)
    # Hide products that are not meant for customers (superusers can still see them)
    if not request.user.is_superuser and not getattr(product, 'is_visible_to_customers', True):
        raise Http404("Product not available")
    # Hide items with unit RSP over £50
    try:
        rsp_val = Decimal(str(product.rsp)) if product.rsp is not None else None
    except Exception:
        rsp_val = None
    if rsp_val is not None and rsp_val > Decimal('50.00'):
        raise Http404("Product not available")
    return render(request, '_catalog/product_detail.html', {'product': product})

def product_list(request):
    category_tree, level1_names, level2_names, level2_map = _category_metadata()

    # Inputs
    query = (request.GET.get('q') or '').strip()
    l1 = (request.GET.get('l1') or '').strip()
    l2 = (request.GET.get('l2') or '').strip()

    # Superusers see all products; customers see only visible ones
    if request.user.is_superuser:
        products = All_Products.objects.all()
    else:
        products = All_Products.objects.filter(is_visible_to_customers=True)

    # ---- 1) Apply category filters first (AND) ----
    l1n = l1.lower() if l1 else ''
    l2n = l2.lower() if l2 else ''
    if l2n:
        # Allow subcategory-only filters; include l1 only when provided
        if l1n:
            products = (
                products
                .annotate(l1_norm=Lower(Trim('sub_category')), l2_norm=Lower(Trim('sub_subcategory')))
                .filter(l1_norm=l1n, l2_norm=l2n)
            )
            # If taxonomy JSON and DB disagree on level-1, relax to l2-only
            if not products.exists():
                products = (
                    All_Products.objects
                    .annotate(l2_norm=Lower(Trim('sub_subcategory')))
                    .filter(l2_norm=l2n)
                )
        else:
            products = (
                products
                .annotate(l2_norm=Lower(Trim('sub_subcategory')))
                .filter(l2_norm=l2n)
            )
    elif l1n:
        products = (
            products
            .annotate(l1_norm=Lower(Trim('sub_category')))
            .filter(l1_norm=l1n)
        )

    # ---- 2) Apply text query (AND with any category filter) ----
    if query:
        q_ci = query.casefold()
        qn = query.strip().lower()
        l1_set = {n.casefold() for n in level1_names}
        l2_set = {n.casefold() for n in level2_names}

        if q_ci in l2_set:
            products = products.annotate(l2_norm=Lower(Trim('sub_subcategory'))).filter(l2_norm=qn)
        elif q_ci in l1_set:
            products = products.annotate(l1_norm=Lower(Trim('sub_category'))).filter(l1_norm=qn)
        else:
            # Fallback: if metadata is stale, try exact DB category match first
            db_l2 = products.annotate(l2_norm=Lower(Trim('sub_subcategory'))).filter(l2_norm=qn)
            if db_l2.exists():
                products = db_l2
            else:
                db_l1 = products.annotate(l1_norm=Lower(Trim('sub_category'))).filter(l1_norm=qn)
                if db_l1.exists():
                    products = db_l1
                else:
                    products = products.filter(
                        Q(name__icontains=query) |
                        Q(main_category__icontains=query) |
                        Q(sub_category__icontains=query) |
                        Q(sub_subcategory__icontains=query)
                    )

    # Hide items with display RSP over £50 (use rsp or price*1.3 fallback)
    display_expr = ExpressionWrapper(F('price') * Value(Decimal('1.30')), output_field=DecimalField(max_digits=10, decimal_places=2))
    products = (
        products
        .annotate(
            display_rsp=Case(
                When(rsp__gt=0, then=F('rsp')),
                default=display_expr,
                output_field=DecimalField(max_digits=10, decimal_places=2),
            )
        )
        .filter(display_rsp__lte=Decimal('50.00'))
    )

    # If a category is selected but this strict DB filter yields no results,
    # retry with a Python-side unit price calculation that divides by pack size
    # inferred from the variant text. This avoids hiding valid multipacks.
    if (l1n or l2n):
        try:
            has_results = products.exists()
        except Exception:
            # If products is a list already, treat as having results/non-empty
            has_results = bool(products)
        if not has_results:
            base_qs = _apply_category_filters(All_Products.objects.all(), l1, l2)
            recovered = []
            for p in base_qs:
                try:
                    if p.rsp is not None and Decimal(str(p.rsp)) > Decimal('0'):
                        display_val = Decimal(str(p.rsp))
                    else:
                        try:
                            pack = max(1, int(p.pack_amount()))
                        except Exception:
                            pack = 1
                        price_val = Decimal(str(getattr(p, 'price', '0') or '0'))
                        display_val = (price_val * Decimal('1.30')) / Decimal(pack)
                    if display_val <= Decimal('50.00'):
                        recovered.append(p)
                except Exception:
                    recovered.append(p)
            products = recovered

    # Final stable ordering
    if isinstance(products, list):
        products.sort(key=lambda x: (getattr(x, 'name', '').casefold(), getattr(x, 'id', 0)))
    else:
        products = products.order_by('name', 'id')

    # Pagination
    paginator = Paginator(products, 24)
    page_number = request.GET.get('page')
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    # Ensure each product has an RSP for display if DB did not provide one
    try:
        for p in page_obj:
            _ensure_rsp(p)
    except Exception:
        pass

    context = {
        'products': page_obj,
        'page_obj': page_obj,
        'query': query,
        'category_tree': category_tree,
        'level1_names': level1_names,
        'level2_names': level2_names,
        'level2_map': level2_map,
        'initial_level2_options': level2_map.get(l1, []) if l1 else [],
    }

    # recent_purchased_items block unchanged
    ...
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
                # Base unit is RSP when available; otherwise fallback to cost price
                base_unit = product.rsp if (product.rsp is not None and product.rsp > 0) else product.price
                price_dec = Decimal(str(base_unit))
                # For bulk items, charge for the whole pack (multiply by pack size)
                try:
                    pack = int(product.pack_amount()) if callable(product.pack_amount) else int(getattr(product, 'pack_amount', 1) or 1)
                except Exception:
                    pack = 1
                if pack > 1:
                    price_dec *= Decimal(pack)
                qty = int(quantity)
                item_total = price_dec * qty
                total_price += item_total
                cart_items.append({
                    'product': product,
                    'quantity': qty,
                    'unit_price': price_dec,
                    'item_total': item_total,
                })

    # Synchronize the pending order with the session cart.
    # Remove any existing order items...
    order.items.all().delete()
    # ...and recreate them from the current cart.
    for pid, quantity in cart.items():
        product = products_by_id.get(str(pid))
        if product:
            base_unit = product.rsp if (product.rsp is not None and product.rsp > 0) else product.price
            price_dec = Decimal(str(base_unit))
            try:
                pack = int(product.pack_amount()) if callable(product.pack_amount) else int(getattr(product, 'pack_amount', 1) or 1)
            except Exception:
                pack = 1
            if pack > 1:
                price_dec *= Decimal(pack)
            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=quantity,
                price=price_dec
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


@require_GET
def search_api(request):
    """
    JSON search endpoint with optional trigram ranking when Postgres is available.
    """
    query = (request.GET.get('q') or '').strip()
    l1 = (request.GET.get('l1') or '').strip()
    l2 = (request.GET.get('l2') or '').strip()
    page_number = request.GET.get('page') or 1
    try:
        page_size = int(request.GET.get('page_size', 12))
    except (TypeError, ValueError):
        page_size = 12
    page_size = max(1, min(page_size, 48))

    if request.user.is_superuser:
        products_qs = All_Products.objects.all()
    else:
        products_qs = All_Products.objects.filter(is_visible_to_customers=True)
    products_qs = _apply_category_filters(products_qs, l1, l2)

    use_trigram = bool(query) and TrigramSimilarity is not None and connection.vendor == 'postgresql'
    if use_trigram:
        try:
            products_qs = (
                products_qs
                .annotate(
                    similarity=Greatest(
                        TrigramSimilarity('name', query),
                        TrigramSimilarity('main_category', query),
                        TrigramSimilarity('sub_category', query),
                        TrigramSimilarity('sub_subcategory', query),
                    )
                )
                .filter(similarity__gte=0.1)
                .order_by('-similarity', 'name')
            )
        except DatabaseError:
            use_trigram = False

    if query and not use_trigram:
        products_qs = products_qs.filter(
            Q(name__icontains=query) |
            Q(main_category__icontains=query) |
            Q(sub_category__icontains=query) |
            Q(sub_subcategory__icontains=query)
        ).order_by('name')
    elif not query:
        products_qs = products_qs.order_by('name')

    paginator = Paginator(products_qs, page_size)
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    results = []
    for product in page_obj:
        results.append({
            'id': product.pk,
            'name': product.name,
            'unit_price': str(product.unit_price or ''),
            'l1': (product.sub_category or '').strip(),
            'l2': (product.sub_subcategory or '').strip(),
            'image_url': product.image_url,
            'detail_url': reverse('product_detail', args=[product.pk]),
            'add_to_cart_url': reverse('add_to_cart', args=[product.pk]),
        })

    return JsonResponse({
        'page': page_obj.number,
        'total_pages': paginator.num_pages,
        'total_results': paginator.count,
        'results': results,
    })


@require_GET
def search_suggest(request):
    """
    Lightweight autocomplete endpoint returning categories and product hits.
    """
    query = (request.GET.get('q') or '').strip()
    if len(query) < 2:
        return JsonResponse({'suggestions': []})

    l1 = (request.GET.get('l1') or '').strip()
    l2 = (request.GET.get('l2') or '').strip()
    limit_param = request.GET.get('limit')
    limit = None
    if limit_param:
        try:
            limit = max(1, int(limit_param))
        except (TypeError, ValueError):
            limit = None

    _, level1_names, _, level2_map = _category_metadata()
    suggestions = []
    query_cf = query.casefold()

    for level1 in level1_names:
        if query_cf in level1.casefold():
            suggestions.append({
                'type': 'category',
                'label': f"{level1}",
                'value': level1,
                'l1': level1,
            })
            if limit and len(suggestions) >= limit:
                break

        for level2 in level2_map.get(level1, []):
            label = f"{level1} \u203a {level2}"
            haystack = f"{level1} {level2}".casefold()
            if query_cf in level2.casefold() or query_cf in haystack:
                suggestions.append({
                    'type': 'subcategory',
                    'label': label,
                    'value': level2,
                    'l1': level1,
                    'l2': level2,
                })
                if limit and len(suggestions) >= limit:
                    break
        if limit and len(suggestions) >= limit:
            break

    return JsonResponse({'suggestions': suggestions})

def load_more_products(request):
    page_number = request.GET.get('page', 1)
    query = request.GET.get('q', '').strip()
    l1 = request.GET.get('l1', '').strip()
    l2 = request.GET.get('l2', '').strip()

    # Show all products to superusers; hide non-visible items from customers.
    # Placeholder images are handled in the template.
    if request.user.is_superuser:
        products_qs = All_Products.objects.all().order_by('id')
    else:
        products_qs = All_Products.objects.filter(is_visible_to_customers=True).order_by('id')

    # Rebuild the category name sets using helper metadata
    _, level1_name_list, level2_name_list, _ = _category_metadata()
    level1_names = {name.casefold() for name in level1_name_list}
    level2_names = {name.casefold() for name in level2_name_list}

    if l2:
        l2n = l2.strip().lower()
        annotations = {'l2_norm': Lower(Trim('sub_subcategory'))}
        filters = {'l2_norm': l2n}
        if l1:
            l1n = l1.strip().lower()
            annotations['l1_norm'] = Lower(Trim('sub_category'))
            filters['l1_norm'] = l1n
        products_qs = products_qs.annotate(**annotations).filter(**filters)
        if l1 and not products_qs.exists():
            # Relax to l2-only if the strict pair yields no results
            products_qs = (
                All_Products.objects
                .annotate(l2_norm=Lower(Trim('sub_subcategory')))
                .filter(l2_norm=l2n)
                .order_by('id')
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
        qn = query.strip().lower()
        if q_ci in level2_names:
            products_qs = (
                products_qs
                .annotate(l2_norm=Lower(Trim('sub_subcategory')))
                .filter(l2_norm=qn)
            )
        elif q_ci in level1_names:
            products_qs = (
                products_qs
                .annotate(l1_norm=Lower(Trim('sub_category')))
                .filter(l1_norm=qn)
            )
        else:
            db_l2 = (
                products_qs
                .annotate(l2_norm=Lower(Trim('sub_subcategory')))
                .filter(l2_norm=qn)
            )
            if db_l2.exists():
                products_qs = db_l2
            else:
                db_l1 = (
                    products_qs
                    .annotate(l1_norm=Lower(Trim('sub_category')))
                    .filter(l1_norm=qn)
                )
                if db_l1.exists():
                    products_qs = db_l1
                else:
                    products_qs = products_qs.filter(
                        Q(name__icontains=query) |
                        Q(main_category__icontains=query) |
                        Q(sub_category__icontains=query) |
                        Q(sub_subcategory__icontains=query)
                    )
    elif l2:
        products_qs = products_qs.filter(sub_subcategory__iexact=l2)
    elif l1:
        l1n = l1.strip().lower()
        products_qs = (
            products_qs
            .annotate(l1_norm=Lower(Trim('sub_category')))
            .filter(l1_norm=l1n)
        )
    
    # Hide items with display RSP over £50 (use rsp>0 else price*1.3)
    display_expr = ExpressionWrapper(F('price') * Value(Decimal('1.30')), output_field=DecimalField(max_digits=10, decimal_places=2))
    products_qs = products_qs.annotate(
        display_rsp=Case(
            When(rsp__gt=0, then=F('rsp')),
            default=display_expr,
            output_field=DecimalField(max_digits=10, decimal_places=2),
        )
    ).filter(display_rsp__lte=Decimal('50.00'))

    paginator = Paginator(products_qs, 8)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        '_catalog/partial_products.html',
        {'page_obj': page_obj, 'products': page_obj}
    )


@require_POST
@login_required
def product_admin_update(request, pk):
    """
    Inline admin endpoint for superusers to toggle customer visibility
    and update RSP from the product listing/cards.
    """
    if not request.user.is_superuser:
        return HttpResponseForbidden("Admins only")

    product = get_object_or_404(All_Products, pk=pk)
    action = (request.POST.get('action') or '').strip()
    return_to = request.POST.get('return_to') or request.META.get('HTTP_REFERER') or reverse('product_list')

    if not url_has_allowed_host_and_scheme(return_to, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return_to = reverse('product_list')

    if action == 'toggle_visibility':
        current = getattr(product, 'is_visible_to_customers', True)
        product.is_visible_to_customers = not current
        product.save(update_fields=['is_visible_to_customers'])
        if product.is_visible_to_customers:
            messages.success(request, "Product is now visible to customers.")
        else:
            messages.success(request, "Product is now invisible for customers.")
    elif action == 'change_rsp':
        rsp_raw = (request.POST.get('rsp') or '').strip()
        if rsp_raw == "":
            product.rsp = None
            product.save(update_fields=['rsp'])
            messages.success(request, "RSP cleared for this product.")
        else:
            try:
                rsp_val = Decimal(rsp_raw)
                if rsp_val < 0:
                    raise InvalidOperation
            except (InvalidOperation, ValueError):
                messages.error(request, "Invalid RSP value. Please enter a non-negative number.")
            else:
                product.rsp = rsp_val
                product.save(update_fields=['rsp'])
                messages.success(request, "RSP updated successfully.")
    else:
        messages.error(request, "Unknown admin action.")

    return redirect(return_to)


