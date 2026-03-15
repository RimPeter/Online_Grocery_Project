from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from .models import All_Products, HomeCategoryTileFavorite


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

