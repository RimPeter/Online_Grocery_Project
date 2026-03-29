from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from _analytics.models import GoogleAdsLandingArrival, Visit
from .models import All_Products, HomeCategoryTileFavorite, ProductFavorite
from .templatetags.price_tags import display_bulk_total, display_rsp


class HomeCategoryFavoritesTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username='testuser', password='testpass')

        All_Products.objects.create(
            ga_product_id='12345',
            name='Test item',
            price='1.00',
            main_category='Groceries',
            sub_category='Produce',
            sub_subcategory='Fruit',
            variant='1',
            list_position=1,
            url='http://example.com/test',
            image_url='http://example.com/image.png',
            sku='SKU123',
            is_visible_to_customers=True,
        )

    def test_homecategorytilefavorite_creation_and_deletion(self):
        fav = HomeCategoryTileFavorite.objects.create(user=self.user, l1='Produce', l2='Fruit')
        self.assertTrue(HomeCategoryTileFavorite.objects.filter(user=self.user, l1__iexact='produce', l2__iexact='fruit').exists())
        fav.delete()
        self.assertFalse(HomeCategoryTileFavorite.objects.filter(user=self.user).exists())

    def test_toggle_home_tile_favorite_view_auth_and_csrf(self):
        self.client.login(username='testuser', password='testpass')
        url = reverse('home_tile_favorite_toggle')

        resp = self.client.post(url, {'l1': 'Produce', 'l2': 'Fruit'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['success'], True)
        self.assertEqual(resp.json()['is_favourite'], True)

        self.assertTrue(HomeCategoryTileFavorite.objects.filter(user=self.user, l1__iexact='produce', l2__iexact='fruit').exists())

        resp2 = self.client.post(url, {'l1': 'produce', 'l2': 'fruit'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp2.json()['success'], True)
        self.assertEqual(resp2.json()['is_favourite'], False)
        self.assertFalse(HomeCategoryTileFavorite.objects.filter(user=self.user).exists())

        self.client.logout()
        resp3 = self.client.post(url, {'l1': 'Produce', 'l2': 'Fruit'})
        self.assertEqual(resp3.status_code, 302)

    def test_home_context_includes_is_favourite(self):
        HomeCategoryTileFavorite.objects.create(user=self.user, l1='Produce', l2='Fruit')
        self.client.login(username='testuser', password='testpass')

        resp = self.client.get(reverse('home'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('subcats', resp.context)
        self.assertIn('favorite_tiles', resp.context)

        fav = resp.context['favorite_tiles']
        self.assertTrue(any(item.get('l1').lower() == 'produce' and item.get('l2').lower() == 'fruit' and item.get('is_favourite') for item in fav))

    def test_home_google_uses_clone_template_and_tracks_landing_path(self):
        response = self.client.get(
            reverse('home_google'),
            {
                'utm_source': 'google',
                'utm_medium': 'cpc',
                'utm_campaign': 'spring-shop',
            },
            HTTP_REFERER='https://www.google.com/',
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, '_catalog/home-google.html')
        self.assertTrue(
            Visit.objects.filter(
                landing_path=reverse('home_google'),
                utm_source='google',
                utm_medium='cpc',
                utm_campaign='spring-shop',
            ).exists()
        )
        self.assertTrue(
            GoogleAdsLandingArrival.objects.filter(
                path=reverse('home_google'),
                utm_source='google',
                utm_medium='cpc',
                utm_campaign='spring-shop',
            ).exists()
        )

    def test_home_google_excludes_superuser_arrivals(self):
        user_model = get_user_model()
        admin_user = user_model.objects.create_superuser(
            username='adminuser',
            email='admin@example.com',
            password='adminpass123',
        )
        self.client.force_login(admin_user)

        response = self.client.get(
            reverse('home_google'),
            {
                'utm_source': 'google',
                'utm_medium': 'cpc',
                'utm_campaign': 'admin-campaign',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            GoogleAdsLandingArrival.objects.filter(
                path=reverse('home_google'),
                utm_campaign='admin-campaign',
            ).exists()
        )

    def test_productfavorite_creation_and_toggle_endpoint(self):
        self.client.login(username='testuser', password='testpass')
        product = All_Products.objects.first()

        # initially not favorited
        self.assertFalse(ProductFavorite.objects.filter(user=self.user, product=product).exists())

        url_toggle = reverse('product_favorite_toggle')
        resp = self.client.post(url_toggle, {'product_id': product.id}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json().get('success'))
        self.assertTrue(resp.json().get('is_favourite'))
        self.assertTrue(ProductFavorite.objects.filter(user=self.user, product=product).exists())

        # toggle off, case-insensitive behavior irrelevant for numeric ID
        resp2 = self.client.post(url_toggle, {'product_id': product.id}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resp2.status_code, 200)
        self.assertTrue(resp2.json().get('success'))
        self.assertFalse(resp2.json().get('is_favourite'))
        self.assertFalse(ProductFavorite.objects.filter(user=self.user, product=product).exists())

        # Protected endpoint for unauthenticated
        self.client.logout()
        response = self.client.post(url_toggle, {'product_id': product.id})
        self.assertEqual(response.status_code, 302)

    def test_product_list_marks_favorites_and_favorites_page(self):
        product = All_Products.objects.first()
        ProductFavorite.objects.create(user=self.user, product=product)

        self.client.login(username='testuser', password='testpass')
        resp = self.client.get(reverse('product_list') + '?l1=Produce&l2=Fruit')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('products', resp.context)
        products = list(resp.context['products'])
        self.assertTrue(any(getattr(p, 'is_favourite', False) for p in products))

        fav_resp = self.client.get(reverse('favorite_products'))
        self.assertEqual(fav_resp.status_code, 200)
        self.assertIn('products', fav_resp.context)
        fav_products = list(fav_resp.context['products'])
        self.assertEqual(len(fav_products), 1)
        self.assertEqual(fav_products[0].id, product.id)

        # Add-all button behavior
        add_all_resp = self.client.post(reverse('favorite_add_all_to_cart'))
        self.assertEqual(add_all_resp.status_code, 302)
        cart = self.client.session.get('cart', {})
        self.assertEqual(cart.get(str(product.id)), 1)

        # Remove individual favorite from favorites page
        remove_resp = self.client.post(reverse('favorite_remove', args=[product.id]))
        self.assertEqual(remove_resp.status_code, 302)
        self.assertFalse(ProductFavorite.objects.filter(user=self.user, product=product).exists())

        # Re-add, then remove all
        ProductFavorite.objects.create(user=self.user, product=product)
        remove_all_resp = self.client.post(reverse('favorite_remove_all'))
        self.assertEqual(remove_all_resp.status_code, 302)
        self.assertFalse(ProductFavorite.objects.filter(user=self.user).exists())

    def test_cart_context_marks_favorite_products(self):
        product = All_Products.objects.first()
        ProductFavorite.objects.create(user=self.user, product=product)

        self.client.login(username='testuser', password='testpass')
        session = self.client.session
        session['cart'] = {str(product.id): 1}
        session.save()

        resp = self.client.get(reverse('cart_view'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('cart_items', resp.context)
        self.assertTrue(resp.context['cart_items'][0]['product'].is_favourite)

    def test_bulk_items_use_rsp_without_pack_multiplier(self):
        bulk_product = All_Products.objects.create(
            ga_product_id='bulk-test-1',
            name='Bulk Test Item',
            price='2.00',
            main_category='Groceries',
            sub_category='Produce',
            sub_subcategory='Fruit',
            variant='1L x 6 x 1',
            list_position=2,
            url='http://example.com/bulk-test',
            image_url='http://example.com/bulk-image.png',
            sku='BULK123',
            is_visible_to_customers=True,
        )

        self.client.login(username='testuser', password='testpass')
        session = self.client.session
        session['cart'] = {str(bulk_product.id): 2}
        session.save()

        resp = self.client.get(reverse('cart_view'))
        self.assertEqual(resp.status_code, 200)

        expected_unit_price = display_rsp(bulk_product)
        self.assertEqual(display_bulk_total(bulk_product), expected_unit_price)
        self.assertEqual(resp.context['cart_items'][0]['unit_price'], expected_unit_price)
        self.assertEqual(resp.context['total_price'], expected_unit_price * 2)

