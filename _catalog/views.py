from django.shortcuts import render, get_object_or_404
from .models import All_Products

def product_list(request):
    products = All_Products.objects.all()
    return render(request, '_catalog/product.html', {'products': products})


def home(request):
    return render(request, '_catalog/home.html')

def product_detail(request, pk):
    product = get_object_or_404(All_Products, pk=pk)
    return render(request, '_catalog/product_detail.html', {'product': product})

def product_list(request):
    query = request.GET.get('q', '')
    if query:
        # Filter products by name or category fields
        products = All_Products.objects.filter(name__icontains=query) | All_Products.objects.filter(category__icontains=query)
    else:
        products = All_Products.objects.all()

    context = {
        'products': products,
    }
    return render(request, '_catalog/product.html', context)
