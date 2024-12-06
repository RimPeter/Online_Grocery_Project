from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import All_Products, Product_Labels_For_Searchbar
from django.core.cache import cache

@receiver(post_save, sender=All_Products)
def update_search_labels(sender, instance, **kwargs):
    ga_id_words = instance.ga_product_id.split()
    category_words = instance.category.split() if instance.category else []
    all_words = set(ga_id_words + category_words)  # Use a set to remove duplicates
    
    labels_str = " ".join(all_words)

    # Create or update the related Product_Labels_For_Searchbar object
    Product_Labels_For_Searchbar.objects.update_or_create(
        product=instance,
        defaults={'labels': labels_str}
    )


@receiver([post_save, post_delete], sender=Product_Labels_For_Searchbar)
def clear_labels_cache(sender, **kwargs):
    cache.delete('all_labels')
    
    