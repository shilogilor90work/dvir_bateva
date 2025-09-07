from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import OrderCSVUploadView, CustomerListView, CustomerUpdateView, CustomerCSVUploadView, CustomerViewSet, ItemViewSet, WeekOrderViewSet, OrderViewSet, OrderItemViewSet

router = DefaultRouter()
router.register(r'customers', CustomerViewSet)
router.register(r'items', ItemViewSet)
router.register(r'weekorders', WeekOrderViewSet)
router.register(r'orders', OrderViewSet)
router.register(r'orderitems', OrderItemViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('upload-customers/', CustomerCSVUploadView.as_view(), name='upload_customers'),
    path('customers_list/', CustomerListView.as_view(), name='customer_list'),
    path('customers/<int:customer_id>/update/', CustomerUpdateView.as_view(), name='customer_update'),
    path('upload-orders/', OrderCSVUploadView.as_view(), name='upload_orders'),
]