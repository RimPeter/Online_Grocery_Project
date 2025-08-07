# _catalog/signals.py
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import All_Products, Product_Labels_For_Searchbar
from django.core.cache import cache

@receiver(post_save, sender=All_Products)
def update_search_labels(sender, instance, **kwargs):
    # words from ga_product_id
    words = instance.ga_product_id.split()

    # words from all three category levels (skip blanks)
    for field in ("main_category", "sub_category", "sub_subcategory"):
        value = getattr(instance, field, "")
        if value:
            words.extend(value.split())

    labels_str = " ".join(sorted(set(words)))   # de-dupe + stable order

    Product_Labels_For_Searchbar.objects.update_or_create(
        product=instance,
        defaults={"labels": labels_str},
    )

@receiver([post_save, post_delete], sender=Product_Labels_For_Searchbar)
def clear_labels_cache(sender, **kwargs):
    cache.delete("all_labels")
