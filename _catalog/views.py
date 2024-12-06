from django.shortcuts import render, get_object_or_404
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
    query = request.GET.get('q', '').strip().lower()  # Normalize query to lowercase
    print(f"Search query: {query}")
    words = query.split() if query else []

    # Cache keys
    ga_ids_to_labels_key = 'ga_ids_to_labels'
    labels_to_ga_ids_key = 'labels_to_ga_ids'

    # Load mappings from cache or files
    ga_ids_to_labels = cache.get(ga_ids_to_labels_key)
    labels_to_ga_ids = cache.get(labels_to_ga_ids_key)

    if not ga_ids_to_labels or not labels_to_ga_ids:
        print("Loading label mappings from files...")
        label_mappings_dir = os.path.join(settings.BASE_DIR, 'label_mappings')
        ga_ids_to_labels_path = os.path.join(label_mappings_dir, 'ga_ids_to_labels.json')
        labels_to_ga_ids_path = os.path.join(label_mappings_dir, 'labels_to_ga_ids.json')

        try:
            with open(ga_ids_to_labels_path, 'r', encoding='utf-8') as f:
                ga_ids_to_labels = json.load(f)
            # Normalize keys in ga_ids_to_labels to lowercase
            ga_ids_to_labels = {k.lower(): v for k, v in ga_ids_to_labels.items()}
            cache.set(ga_ids_to_labels_key, ga_ids_to_labels, 3600)
        except FileNotFoundError:
            ga_ids_to_labels = {}
            print(f"File not found: {ga_ids_to_labels_path}")

        try:
            with open(labels_to_ga_ids_path, 'r', encoding='utf-8') as f:
                labels_to_ga_ids = json.load(f)
            # Normalize keys in labels_to_ga_ids to lowercase
            labels_to_ga_ids = {k.lower(): v for k, v in labels_to_ga_ids.items()}
            cache.set(labels_to_ga_ids_key, labels_to_ga_ids, 3600)
        except FileNotFoundError:
            labels_to_ga_ids = {}
            print(f"File not found: {labels_to_ga_ids_path}")

    # Ensure defaults
    if ga_ids_to_labels is None:
        ga_ids_to_labels = {}
    if labels_to_ga_ids is None:
        labels_to_ga_ids = {}

    # Process search query
    matching_ga_ids = set()
    if words:
        product_id_sets = []
        for word in words:
            ga_ids = set(labels_to_ga_ids.get(word, []))  # Case-insensitive match
            product_id_sets.append(ga_ids)
            print(f"GA IDs for word '{word}': {ga_ids}")

        if product_id_sets:
            matching_ga_ids = set.intersection(*product_id_sets)
            print(f"Matching GA IDs: {matching_ga_ids}")
            products = All_Products.objects.filter(ga_product_id__in=matching_ga_ids).order_by('id')
        else:
            print("No matching labels.")
            products = All_Products.objects.none()
    else:
        print("No query provided. Returning all products.")
        products = All_Products.objects.all().order_by('id')

    # Reduce labels based on products in search results
    listed_ga_ids = products.values_list('ga_product_id', flat=True)
    reduced_labels = set()
    for ga_id in listed_ga_ids:
        related_labels = ga_ids_to_labels.get(str(ga_id).lower(), [])  # Case-insensitive access
        reduced_labels.update(related_labels)
    reduced_labels = sorted(reduced_labels)

    # Updated context with reduced labels
    context = {
        'products': products,
        'all_labels': reduced_labels,  # Dynamically reduced labels
        'query': query,  # Include query for debugging purposes
    }
    return render(request, '_catalog/product.html', context)

