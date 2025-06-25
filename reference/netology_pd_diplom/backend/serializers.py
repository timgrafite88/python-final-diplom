from rest_framework import serializers
from .models import (
    User, Shop, Category, Product, ProductInfo,
    Parameter, ProductParameter, Order, OrderItem, Contact,
    ConfirmEmailToken
)

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'email', 'username', 'first_name', 'last_name',
                 'company', 'position', 'type', 'is_active')
        read_only_fields = ('id', 'is_active')

class UserRegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('email', 'password', 'first_name', 'last_name',
                 'company', 'position', 'type')
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user

class ShopSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shop
        fields = ('id', 'name', 'url', 'state', 'created_at', 'updated_at')
        read_only_fields = ('id', 'created_at', 'updated_at')

class CategorySerializer(serializers.ModelSerializer):
    shops = serializers.StringRelatedField(many=True)

    class Meta:
        model = Category
        fields = ('id', 'name', 'shops', 'created_at', 'updated_at')
        read_only_fields = ('id', 'created_at', 'updated_at')

class ProductSerializer(serializers.ModelSerializer):
    category = serializers.StringRelatedField()

    class Meta:
        model = Product
        fields = ('id', 'name', 'category', 'created_at', 'updated_at')
        read_only_fields = ('id', 'created_at', 'updated_at')

class ParameterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Parameter
        fields = ('id', 'name', 'created_at', 'updated_at')
        read_only_fields = ('id', 'created_at', 'updated_at')

class ProductParameterSerializer(serializers.ModelSerializer):
    parameter = serializers.StringRelatedField()

    class Meta:
        model = ProductParameter
        fields = ('parameter', 'value', 'created_at', 'updated_at')
        read_only_fields = ('created_at', 'updated_at')

class ProductInfoSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    shop = ShopSerializer(read_only=True)
    product_parameters = ProductParameterSerializer(read_only=True, many=True)

    class Meta:
        model = ProductInfo
        fields = ('id', 'model', 'external_id', 'product', 'shop',
                 'quantity', 'price', 'price_rrc', 'discount',
                 'product_parameters', 'created_at', 'updated_at')
        read_only_fields = ('id', 'created_at', 'updated_at')

class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = ('id', 'city', 'street', 'house', 'structure',
                 'building', 'apartment', 'phone', 'created_at', 'updated_at')
        read_only_fields = ('id', 'created_at', 'updated_at')

class OrderItemSerializer(serializers.ModelSerializer):
    product_info = ProductInfoSerializer(read_only=True)

    class Meta:
        model = OrderItem
        fields = ('id', 'product_info', 'quantity', 'created_at', 'updated_at')
        read_only_fields = ('id', 'created_at', 'updated_at')

class OrderItemCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ('id', 'product_info', 'quantity')
        read_only_fields = ('id',)

class OrderSerializer(serializers.ModelSerializer):
    ordered_items = OrderItemSerializer(read_only=True, many=True)
    total_sum = serializers.SerializerMethodField()
    contact = ContactSerializer(read_only=True)
    status_display = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = ('id', 'user', 'dt', 'state', 'status_display', 'contact',
                 'comment', 'ordered_items', 'total_sum', 'created_at', 'updated_at')
        read_only_fields = ('id', 'dt', 'total_sum', 'created_at', 'updated_at')

    def get_total_sum(self, obj):
        return obj.total_sum()

    def get_status_display(self, obj):
        return obj.get_status_display()

class ConfirmEmailTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConfirmEmailToken
        fields = ('key',)