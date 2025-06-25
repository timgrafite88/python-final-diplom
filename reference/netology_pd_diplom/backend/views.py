from distutils.util import strtobool
from rest_framework.request import Request
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import IntegrityError
from django.db.models import Q, Sum, F
from django.http import JsonResponse
from requests import get
from rest_framework.authtoken.models import Token
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from ujson import loads as load_json
from yaml import load as load_yaml, Loader
from django.core.files.storage import FileSystemStorage
import tempfile
import os

from .models import Shop, Category, Product, ProductInfo, Parameter, ProductParameter, Order, OrderItem, \
    Contact, ConfirmEmailToken, User
from .serializers import UserSerializer, CategorySerializer, ShopSerializer, ProductInfoSerializer, \
    OrderItemSerializer, OrderSerializer, ContactSerializer, UserRegisterSerializer, ConfirmEmailTokenSerializer
from .signals import new_user_registered, new_order
from .tasks import send_order_confirmation_email, process_import_task


class RegisterAccount(APIView):
    """
    Регистрация пользователей
    """

    def post(self, request, *args, **kwargs):
        required_fields = {'first_name', 'last_name', 'email', 'password', 'company', 'position'}
        if not required_fields.issubset(request.data):
            return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

        try:
            validate_password(request.data['password'])
        except Exception as password_error:
            return JsonResponse({
                'Status': False,
                'Errors': {'password': list(password_error)}
            })

        user_serializer = UserRegisterSerializer(data=request.data)
        if user_serializer.is_valid():
            user = user_serializer.save()
            user.set_password(request.data['password'])
            user.save()
            new_user_registered.send(sender=self.__class__, user_id=user.id)
            return JsonResponse({'Status': True})
        else:
            return JsonResponse({'Status': False, 'Errors': user_serializer.errors})


class ConfirmAccount(APIView):
    """
    Подтверждение почтового адреса
    """

    def post(self, request, *args, **kwargs):
        if {'email', 'token'}.issubset(request.data):
            token = ConfirmEmailToken.objects.filter(
                user__email=request.data['email'],
                key=request.data['token']
            ).first()

            if token:
                token.user.is_active = True
                token.user.save()
                token.delete()
                return JsonResponse({'Status': True})

        return JsonResponse({'Status': False, 'Errors': 'Неверный токен или email'})


class AccountDetails(APIView):
    """
    Управление данными пользователя
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        if 'password' in request.data:
            try:
                validate_password(request.data['password'])
            except Exception as password_error:
                return JsonResponse({
                    'Status': False,
                    'Errors': {'password': list(password_error)}
                })
            else:
                request.user.set_password(request.data['password'])

        user_serializer = UserSerializer(
            request.user,
            data=request.data,
            partial=True
        )

        if user_serializer.is_valid():
            user_serializer.save()
            return JsonResponse({'Status': True})
        else:
            return JsonResponse({'Status': False, 'Errors': user_serializer.errors})


class LoginAccount(APIView):
    """
    Авторизация пользователей
    """

    def post(self, request, *args, **kwargs):
        if {'email', 'password'}.issubset(request.data):
            user = authenticate(
                request,
                username=request.data['email'],
                password=request.data['password']
            )

            if user is not None:
                if user.is_active:
                    token, _ = Token.objects.get_or_create(user=user)
                    return JsonResponse({'Status': True, 'Token': token.key})

            return JsonResponse({'Status': False, 'Errors': 'Не удалось авторизовать'})

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})


class CategoryView(ListAPIView):
    """
    Просмотр категорий
    """
    queryset = Category.objects.all()
    serializer_class = CategorySerializer


class ShopView(ListAPIView):
    """
    Просмотр списка магазинов
    """
    queryset = Shop.objects.filter(state=True)
    serializer_class = ShopSerializer


class ProductInfoView(APIView):
    """
    Поиск товаров
    """

    def get(self, request, *args, **kwargs):
        query = Q(shop__state=True)

        shop_id = request.query_params.get('shop_id')
        if shop_id:
            query &= Q(shop_id=shop_id)

        category_id = request.query_params.get('category_id')
        if category_id:
            query &= Q(product__category_id=category_id)

        queryset = ProductInfo.objects.filter(query) \
            .select_related('shop', 'product__category') \
            .prefetch_related('product_parameters__parameter') \
            .distinct()

        serializer = ProductInfoSerializer(queryset, many=True)
        return Response(serializer.data)


class BasketView(APIView):
    """
    Управление корзиной пользователя
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        basket = Order.objects.filter(
            user_id=request.user.id,
            state='basket'
        ).prefetch_related(
            'ordered_items__product_info__product__category',
            'ordered_items__product_info__product_parameters__parameter'
        ).annotate(
            total_sum=Sum(F('ordered_items__quantity') * F('ordered_items__product_info__price'))
        ).distinct()

        serializer = OrderSerializer(basket, many=True)
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        items = request.data.get('items')
        if not items:
            return JsonResponse({'Status': False, 'Errors': 'Не указаны товары'})

        try:
            items_dict = load_json(items)
        except ValueError:
            return JsonResponse({'Status': False, 'Errors': 'Неверный формат запроса'})

        basket, _ = Order.objects.get_or_create(
            user_id=request.user.id,
            state='basket'
        )
        objects_created = 0

        for order_item in items_dict:
            order_item.update({'order': basket.id})
            serializer = OrderItemSerializer(data=order_item)

            if serializer.is_valid():
                try:
                    serializer.save()
                    objects_created += 1
                except IntegrityError as error:
                    return JsonResponse({'Status': False, 'Errors': str(error)})
            else:
                return JsonResponse({'Status': False, 'Errors': serializer.errors})

        return JsonResponse({'Status': True, 'Создано объектов': objects_created})

    def delete(self, request, *args, **kwargs):
        items = request.data.get('items')
        if not items:
            return JsonResponse({'Status': False, 'Errors': 'Не указаны товары'})

        items_list = items.split(',')
        basket, _ = Order.objects.get_or_create(
            user_id=request.user.id,
            state='basket'
        )
        query = Q()
        objects_deleted = False

        for order_item_id in items_list:
            if order_item_id.isdigit():
                query |= Q(order_id=basket.id, id=order_item_id)
                objects_deleted = True

        if objects_deleted:
            deleted_count = OrderItem.objects.filter(query).delete()[0]
            return JsonResponse({'Status': True, 'Удалено объектов': deleted_count})

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

    def put(self, request, *args, **kwargs):
        items = request.data.get('items')
        if not items:
            return JsonResponse({'Status': False, 'Errors': 'Не указаны товары'})

        try:
            items_dict = load_json(items)
        except ValueError:
            return JsonResponse({'Status': False, 'Errors': 'Неверный формат запроса'})

        basket, _ = Order.objects.get_or_create(
            user_id=request.user.id,
            state='basket'
        )
        objects_updated = 0

        for order_item in items_dict:
            if isinstance(order_item.get('id'), int) and isinstance(order_item.get('quantity'), int):
                objects_updated += OrderItem.objects.filter(
                    order_id=basket.id,
                    id=order_item['id']
                ).update(quantity=order_item['quantity'])

        return JsonResponse({'Status': True, 'Обновлено объектов': objects_updated})


class PartnerUpdate(APIView):
    """
    Обновление прайса от партнера
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        if request.user.type != 'shop':
            return JsonResponse({'Status': False, 'Error': 'Только для магазинов'}, status=403)

        url = request.data.get('url')
        if not url:
            return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

        validate_url = URLValidator()
        try:
            validate_url(url)
        except ValidationError as e:
            return JsonResponse({'Status': False, 'Error': str(e)})

        stream = get(url).content
        data = load_yaml(stream, Loader=Loader)

        shop, _ = Shop.objects.get_or_create(
            name=data['shop'],
            user_id=request.user.id
        )

        for category in data['categories']:
            category_object, _ = Category.objects.get_or_create(
                id=category['id'],
                name=category['name']
            )
            category_object.shops.add(shop.id)
            category_object.save()

        ProductInfo.objects.filter(shop_id=shop.id).delete()

        for item in data['goods']:
            product, _ = Product.objects.get_or_create(
                name=item['name'],
                category_id=item['category']
            )

            product_info = ProductInfo.objects.create(
                product_id=product.id,
                external_id=item['id'],
                model=item.get('model', ''),
                price=item['price'],
                price_rrc=item.get('price_rrc', item['price']),
                quantity=item['quantity'],
                shop_id=shop.id
            )

            for name, value in item.get('parameters', {}).items():
                parameter_object, _ = Parameter.objects.get_or_create(name=name)
                ProductParameter.objects.create(
                    product_info_id=product_info.id,
                    parameter_id=parameter_object.id,
                    value=value
                )

        return JsonResponse({'Status': True})


class PartnerState(APIView):
    """
    Управление статусом магазина
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        if request.user.type != 'shop':
            return JsonResponse({'Status': False, 'Error': 'Только для магазинов'}, status=403)

        shop = request.user.shop
        serializer = ShopSerializer(shop)
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        if request.user.type != 'shop':
            return JsonResponse({'Status': False, 'Error': 'Только для магазинов'}, status=403)

        state = request.data.get('state')
        if not state:
            return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

        try:
            Shop.objects.filter(user_id=request.user.id).update(
                state=strtobool(state)
            )
            return JsonResponse({'Status': True})
        except ValueError as error:
            return JsonResponse({'Status': False, 'Errors': str(error)})


class PartnerOrders(APIView):
    """
    Получение заказов поставщиками
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        if request.user.type != 'shop':
            return JsonResponse({'Status': False, 'Error': 'Только для магазинов'}, status=403)

        orders = Order.objects.filter(
            ordered_items__product_info__shop__user_id=request.user.id
        ).exclude(state='basket').prefetch_related(
            'ordered_items__product_info__product__category',
            'ordered_items__product_info__product_parameters__parameter'
        ).select_related('contact').annotate(
            total_sum=Sum(F('ordered_items__quantity') * F('ordered_items__product_info__price'))
        ).distinct()

        serializer = OrderSerializer(orders, many=True)
        return Response(serializer.data)


class ContactView(APIView):
    """
    Управление контактами пользователей
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        contacts = Contact.objects.filter(user_id=request.user.id)
        serializer = ContactSerializer(contacts, many=True)
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        if not {'city', 'street', 'phone'}.issubset(request.data):
            return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

        request.data._mutable = True
        request.data.update({'user': request.user.id})
        serializer = ContactSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save()
            return JsonResponse({'Status': True})
        else:
            return JsonResponse({'Status': False, 'Errors': serializer.errors})

    def delete(self, request, *args, **kwargs):
        items = request.data.get('items')
        if not items:
            return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

        items_list = items.split(',')
        query = Q()
        objects_deleted = False

        for contact_id in items_list:
            if contact_id.isdigit():
                query |= Q(user_id=request.user.id, id=contact_id)
                objects_deleted = True

        if objects_deleted:
            deleted_count = Contact.objects.filter(query).delete()[0]
            return JsonResponse({'Status': True, 'Удалено объектов': deleted_count})

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

    def put(self, request, *args, **kwargs):
        contact_id = request.data.get('id')
        if not contact_id or not contact_id.isdigit():
            return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

        contact = Contact.objects.filter(
            id=contact_id,
            user_id=request.user.id
        ).first()

        if not contact:
            return JsonResponse({'Status': False, 'Errors': 'Контакт не найден'})

        serializer = ContactSerializer(
            contact,
            data=request.data,
            partial=True
        )

        if serializer.is_valid():
            serializer.save()
            return JsonResponse({'Status': True})
        else:
            return JsonResponse({'Status': False, 'Errors': serializer.errors})


class OrderView(APIView):
    """
    Управление заказами пользователей
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        orders = Order.objects.filter(
            user_id=request.user.id
        ).exclude(state='basket').prefetch_related(
            'ordered_items__product_info__product__category',
            'ordered_items__product_info__product_parameters__parameter'
        ).select_related('contact').annotate(
            total_sum=Sum(F('ordered_items__quantity') * F('ordered_items__product_info__price'))
        ).distinct()

        serializer = OrderSerializer(orders, many=True)
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        if not {'id', 'contact'}.issubset(request.data):
            return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

        if not request.data['id'].isdigit():
            return JsonResponse({'Status': False, 'Errors': 'Неверный ID заказа'})

        try:
            order = Order.objects.get(
                id=request.data['id'],
                user_id=request.user.id
            )
        except Order.DoesNotExist:
            return JsonResponse({'Status': False, 'Errors': 'Заказ не найден'})

        try:
            is_updated = Order.objects.filter(
                id=order.id
            ).update(
                contact_id=request.data['contact'],
                state='new'
            )
        except IntegrityError:
            return JsonResponse({'Status': False, 'Errors': 'Неправильно указаны аргументы'})

        if is_updated:
            send_order_confirmation_email.delay(order.id)
            new_order.send(sender=self.__class__, user_id=request.user.id)
            return JsonResponse({'Status': True})

        return JsonResponse({'Status': False, 'Errors': 'Не удалось обновить заказ'})


class ShopViewSet(viewsets.ModelViewSet):
    """
    Управление магазинами (расширенное API)
    """
    queryset = Shop.objects.all()
    serializer_class = ShopSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def import_products(self, request, pk=None):
        shop = self.get_object()
        if request.user != shop.user and not request.user.is_superuser:
            return Response(
                {'status': False, 'error': 'Недостаточно прав'},
                status=status.HTTP_403_FORBIDDEN
            )

        if 'file' not in request.FILES:
            return Response(
                {'status': False, 'error': 'Файл не предоставлен'},
                status=status.HTTP_400_BAD_REQUEST
            )

        uploaded_file = request.FILES['file']
        fs = FileSystemStorage(location=tempfile.gettempdir())
        filename = fs.save(uploaded_file.name, uploaded_file)
        file_path = os.path.join(tempfile.gettempdir(), filename)

        try:
            task = process_import_task.delay(file_path, request.user.id)
            return Response({
                'status': True,
                'task_id': task.id
            })
        except Exception as e:
            return Response(
                {'status': False, 'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)