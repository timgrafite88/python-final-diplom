from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from baton.admin import InputFilter
from baton.autodiscover import admin

from backend.models import User, Shop, Category, Product, ProductInfo, Parameter, ProductParameter, Order, OrderItem, \
    Contact, ConfirmEmailToken


class EmailFilter(InputFilter):
    parameter_name = 'email'
    title = 'Email'

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(email__icontains=self.value())


class TypeFilter(admin.SimpleListFilter):
    title = 'User Type'
    parameter_name = 'type'

    def lookups(self, request, model_admin):
        return (
            ('shop', 'Shop'),
            ('buyer', 'Buyer'),
        )

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(type=self.value())


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """
    Панель управления пользователями с улучшенным интерфейсом
    """
    model = User
    list_display = ('email', 'first_name', 'last_name', 'type', 'is_active', 'is_staff')
    list_filter = (EmailFilter, TypeFilter, 'is_active', 'is_staff')
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('email',)
    filter_horizontal = ('groups', 'user_permissions',)

    fieldsets = (
        (None, {
            'fields': ('email', 'password', 'type'),
            'classes': ('baton-tabs-init', 'baton-tab-fs-personal', 'baton-tab-fs-permissions', 'baton-tab-fs-dates')
        }),
        ('Personal info', {
            'fields': ('first_name', 'last_name', 'company', 'position'),
            'classes': ('tab-fs-personal',)
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
            'classes': ('tab-fs-permissions',)
        }),
        ('Important dates', {
            'fields': ('last_login', 'date_joined'),
            'classes': ('tab-fs-dates',)
        }),
    )


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ('name', 'url', 'state')
    list_filter = ('state',)
    search_fields = ('name',)
    list_editable = ('state',)
    baton_form_includes = [
        ('admin/shop_description.html', 'bottom', 'description'),
    ]


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'get_shops')
    list_filter = ('category',)
    search_fields = ('name', 'category__name')
    filter_horizontal = ('shops',)
    baton_cl_list_display = ('name', 'category', 'get_shops_list')

    def get_shops(self, obj):
        return ", ".join([shop.name for shop in obj.shops.all()])
    get_shops.short_description = 'Shops'

    def get_shops_list(self, obj):
        return ", ".join([shop.name for shop in obj.shops.all()])
    get_shops_list.short_description = 'Shops'


@admin.register(ProductInfo)
class ProductInfoAdmin(admin.ModelAdmin):
    list_display = ('product', 'shop', 'quantity', 'price', 'price_rrc')
    list_filter = ('shop',)
    search_fields = ('product__name', 'shop__name')
    list_editable = ('quantity', 'price', 'price_rrc')
    baton_list_filter = (
        ('shop', admin.RelatedOnlyFieldListFilter),
    )


@admin.register(Parameter)
class ParameterAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


@admin.register(ProductParameter)
class ProductParameterAdmin(admin.ModelAdmin):
    list_display = ('product_info', 'parameter', 'value')
    list_filter = ('parameter',)
    search_fields = ('product_info__product__name', 'parameter__name')


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    baton_form_includes = [
        ('admin/order_item_help.html', 'top', 'items'),
    ]


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'state', 'created_at', 'total_sum')
    list_filter = ('state', 'created_at')
    search_fields = ('user__email', 'user__first_name', 'user__last_name')
    inlines = (OrderItemInline,)
    baton_list_display = ('id', 'user', 'state_badge', 'created_at', 'total_sum_formatted')
    baton_list_filter = (
        ('state', admin.ChoicesFieldListFilter),
        ('created_at', admin.DateFieldListFilter),
    )

    def total_sum(self, obj):
        return sum(item.quantity * item.product_info.price for item in obj.ordered_items.all())
    total_sum.short_description = 'Total Sum'

    def total_sum_formatted(self, obj):
        return f"{self.total_sum(obj):.2f} ₽"
    total_sum_formatted.short_description = 'Total Sum'

    def state_badge(self, obj):
        colors = {
            'basket': 'secondary',
            'new': 'info',
            'confirmed': 'primary',
            'assembled': 'warning',
            'sent': 'success',
            'delivered': 'success',
            'canceled': 'danger',
        }
        return f'<span class="badge badge-{colors.get(obj.state, "secondary")}">{obj.get_state_display()}</span>'
    state_badge.allow_tags = True
    state_badge.short_description = 'State'


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'product_info', 'quantity', 'total_price')
    list_filter = ('order__state',)
    search_fields = ('order__user__email', 'product_info__product__name')

    def total_price(self, obj):
        return obj.quantity * obj.product_info.price
    total_price.short_description = 'Total Price'


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ('user', 'city', 'street', 'house', 'phone')
    search_fields = ('user__email', 'city', 'street', 'phone')
    baton_list_display = ('user', 'full_address', 'phone')

    def full_address(self, obj):
        return f"{obj.city}, {obj.street}, {obj.house}"
    full_address.short_description = 'Address'


@admin.register(ConfirmEmailToken)
class ConfirmEmailTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'key', 'created_at')
    search_fields = ('user__email', 'key')
    readonly_fields = ('created_at',)
    baton_list_display = ('user_email', 'short_key', 'created_at')

    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User Email'

    def short_key(self, obj):
        return f"{obj.key[:10]}..." if obj.key else ""
    short_key.short_description = 'Key'