from django.shortcuts import render, get_object_or_404
from collections import defaultdict
from .models import All_Products
from django.conf import settings
import json
import os
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger


def home(request):
    return render(request, '_catalog/home.html')

def product_detail(request, pk):
    product = get_object_or_404(All_Products, pk=pk)
    return render(request, '_catalog/product_detail.html', {'product': product})

# _catalog/views.py



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
    if query:
        products = products.filter(category__icontains=query)

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
