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
