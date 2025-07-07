from django.urls import include, path
from django_rest_passwordreset.views import reset_password_request_token, reset_password_confirm
from .views import (PartnerUpdate, RegisterAccount, LoginAccount,
                    CategoryView, ShopView, ProductInfoView, BasketView,
                    AccountDetails, ContactView, OrderView, PartnerState,
                    PartnerOrders, ConfirmAccount, ShopViewSet)

from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

schema_view = get_schema_view(
    openapi.Info(
        title="Order Service API",
        default_version='v1',
        description="API для сервиса заказа товаров",
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [

    path('admin/', include('baton.urls')),
    path('partner/update', PartnerUpdate.as_view(), name='partner-update'),
    path('partner/state', PartnerState.as_view(), name='partner-state'),
    path('partner/orders', PartnerOrders.as_view(), name='partner-orders'),
    path('user/register', RegisterAccount.as_view(), name='user-register'),
    path('user/register/confirm', ConfirmAccount.as_view(), name='user-register-confirm'),
    path('user/details', AccountDetails.as_view(), name='user-details'),
    path('user/contact', ContactView.as_view(), name='user-contact'),
    path('user/login', LoginAccount.as_view(), name='user-login'),
    path('user/password_reset', reset_password_request_token, name='password-reset'),
    path('user/password_reset/confirm', reset_password_confirm, name='password-reset-confirm'),
    path('categories', CategoryView.as_view(), name='categories'),
    path('shops', ShopView.as_view(), name='shops'),
    path('products', ProductInfoView.as_view(), name='products'),
    path('basket', BasketView.as_view(), name='basket'),
    path('order', OrderView.as_view(), name='order'),

    # Документация
    path('swagger<format>/', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),

    # ViewSet для магазинов
    path('shops/', ShopViewSet.as_view({'get': 'list', 'post': 'create'}), name='shop-list'),
    path('shops/<int:pk>/', ShopViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}),
         name='shop-detail'),
    path('shops/<int:pk>/import_products/', ShopViewSet.as_view({'post': 'import_products'}),
         name='shop-import-products'),

    # social autorization
    path('social-auth/', include('social_django.urls', namespace='social')),
]