from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from .models import (
    Shop, Category, Product, ProductInfo,
    Order, OrderItem, Contact, ConfirmEmailToken
)

User = get_user_model()


class UserTests(TestCase):
    """
    Тесты для функционала пользователей (регистрация, подтверждение, вход, выход).
    """

    def setUp(self):
        self.client = APIClient()
        self.user_data = {
            'email': 'test@example.com',
            'password': 'testpass123',
            'first_name': 'Test',
            'last_name': 'User',
            'type': 'buyer'
        }
        self.user = User.objects.create_user(**self.user_data, is_active=True)

    def test_user_registration(self):
        """
        Тест регистрации нового пользователя.
        """
        data = {
            'email': 'new@example.com',
            'password': 'newpass123',
            'first_name': 'New',
            'last_name': 'User',
            'type': 'buyer'
        }
        response = self.client.post('/api/register/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(email='new@example.com').exists())

    def test_user_login(self):
        """
        Тест входа пользователя в систему.
        """
        response = self.client.post(
            '/api/login/',
            {'email': 'test@example.com', 'password': 'testpass123'}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_user_logout(self):
        """
        Тест выхода пользователя из системы.
        """
        self.client.force_authenticate(user=self.user)
        response = self.client.post('/api/logout/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class ShopTests(TestCase):
    """
    Тесты для функционала магазинов.
    """

    def setUp(self):
        self.client = APIClient()
        self.shop = Shop.objects.create(name='Test Shop', url='http://example.com', state=True)

    def test_get_active_shops(self):
        """
        Тест получения списка активных магазинов.
        """
        response = self.client.get('/api/shops/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'Test Shop')


class ProductTests(TestCase):
    """
    Тесты для функционала товаров.
    """

    def setUp(self):
        self.client = APIClient()
        self.shop = Shop.objects.create(name='Test Shop')
        self.category = Category.objects.create(name='Test Category')
        self.product = Product.objects.create(
            name='Test Product',
            category=self.category
        )
        self.product_info = ProductInfo.objects.create(
            product=self.product,
            shop=self.shop,
            quantity=10,
            price=100,
            price_rrc=120,
            external_id=1
        )

    def test_get_products(self):
        """
        Тест получения списка товаров.
        """
        response = self.client.get('/api/products/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'Test Product')

    def test_filter_products_by_category(self):
        """
        Тест фильтрации товаров по категории.
        """
        response = self.client.get('/api/products/?category_id=1')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_filter_products_by_shop(self):
        """
        Тест фильтрации товаров по магазину.
        """
        response = self.client.get('/api/products/?shop_id=1')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)


class BasketTests(TestCase):
    """
    Тесты для функционала корзины.
    """

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            is_active=True
        )
        self.shop = Shop.objects.create(name='Test Shop')
        self.category = Category.objects.create(name='Test Category')
        self.product = Product.objects.create(
            name='Test Product',
            category=self.category
        )
        self.product_info = ProductInfo.objects.create(
            product=self.product,
            shop=self.shop,
            quantity=10,
            price=100,
            price_rrc=120,
            external_id=1
        )
        self.client.force_authenticate(user=self.user)

    def test_add_to_basket(self):
        """
        Тест добавления товара в корзину.
        """
        data = {
            'product_info': self.product_info.id,
            'quantity': 2
        }
        response = self.client.post('/api/basket/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(OrderItem.objects.count(), 1)

    def test_remove_from_basket(self):
        """
        Тест удаления товара из корзины.
        """
        order = Order.objects.create(user=self.user, state='basket')
        order_item = OrderItem.objects.create(
            order=order,
            product_info=self.product_info,
            quantity=2
        )
        response = self.client.delete(f'/api/basket/{order_item.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(OrderItem.objects.count(), 0)


class OrderTests(TestCase):
    """
    Тесты для функционала заказов.
    """

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            is_active=True
        )
        self.shop = Shop.objects.create(name='Test Shop')
        self.category = Category.objects.create(name='Test Category')
        self.product = Product.objects.create(
            name='Test Product',
            category=self.category
        )
        self.product_info = ProductInfo.objects.create(
            product=self.product,
            shop=self.shop,
            quantity=10,
            price=100,
            price_rrc=120,
            external_id=1
        )
        self.contact = Contact.objects.create(
            user=self.user,
            city='Test City',
            street='Test Street',
            house='1',
            phone='+79999999999'
        )
        self.client.force_authenticate(user=self.user)

    def test_confirm_order(self):
        """
        Тест подтверждения заказа.
        """
        order = Order.objects.create(user=self.user, state='basket')
        OrderItem.objects.create(
            order=order,
            product_info=self.product_info,
            quantity=2
        )
        response = self.client.post(f'/api/orders/{order.id}/confirm/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        order.refresh_from_db()
        self.assertEqual(order.state, 'new')

    def test_get_orders(self):
        """
        Тест получения списка заказов.
        """
        order = Order.objects.create(user=self.user, state='new')
        response = self.client.get('/api/orders/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)


class ContactTests(TestCase):
    """
    Тесты для функционала контактов.
    """

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            is_active=True
        )
        self.client.force_authenticate(user=self.user)

    def test_create_contact(self):
        """
        Тест создания контакта.
        """
        data = {
            'city': 'Test City',
            'street': 'Test Street',
            'house': '1',
            'phone': '+79999999999'
        }
        response = self.client.post('/api/contacts/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Contact.objects.count(), 1)

    def test_delete_contact(self):
        """
        Тест удаления контакта.
        """
        contact = Contact.objects.create(
            user=self.user,
            city='Test City',
            street='Test Street',
            house='1',
            phone='+79999999999'
        )
        response = self.client.delete(f'/api/contacts/{contact.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Contact.objects.count(), 0)