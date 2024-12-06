from django.shortcuts import render, get_object_or_404
from collections import defaultdict
from .models import All_Products, Product_Labels_For_Searchbar
from django.core.cache import cache
from django.conf import settings
import json
import os
from django.core.paginator import Paginator

def product_list(request):
    products = All_Products.objects.all()
    return render(request, '_catalog/product.html', {'products': products})


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

    # Rest of your product filtering logic...
    query = request.GET.get('q', '').strip()
    products = All_Products.objects.all()
    if query:
        products = products.filter(category__icontains=query)

    context = {
        'products': products,
        'level1_to_level2': dict(level1_to_level2),  # Pass Level 1 to Level 2 mapping
    }
    return render(request, '_catalog/product.html', context)