from django.shortcuts import render, get_object_or_404
from .models import Product

def product_list(request):
    products = Product.objects.all()
    context = {
        'products': products
    }
    return render(request, '_catalog/product.html', context)

def home(request):
    return render(request, '_catalog/home.html')

def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    context = {'product': product}
    return render(request, '_catalog/product_detail.html', context)
