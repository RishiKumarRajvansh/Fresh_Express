from django.urls import path
from django.shortcuts import redirect
from . import views
from . import views_bulk_import
from . import views_additional

app_name = 'stores'

urlpatterns = [
    # Redirect store listing to home (Blinkit-style - no store selection for users)
    path('', lambda request: redirect('core:home'), name='store_list'),
    
    # Store management for store owners - Updated URL names to match dashboard templates
    path('dashboard/', views.StoreDashboardView.as_view(), name='dashboard'),
    path('orders/', views.store_orders, name='orders_management'),
    path('orders/<int:order_id>/', views.order_detail, name='order_detail'),
    path('inventory/', views.store_inventory, name='inventory_management'),
    path('agents/', views.delivery_agents, name='delivery_agents'),
    
    # Additional store management URLs
    path('profile/', views_additional.store_profile, name='store_profile'),
    path('business-hours/', views_additional.business_hours, name='business_hours'),
    path('analytics/', views_additional.store_analytics, name='analytics'),
    path('create/', views_additional.create_store, name='create_store'),
    
    # Bulk Import System
    path('bulk-import/', views_bulk_import.bulk_import_products, name='bulk_import'),
    path('bulk-import/validate/', views_bulk_import.validate_csv_data, name='validate_csv'),
    path('bulk-import/history/', views_bulk_import.import_history, name='import_history'),
    path('bulk-import/sample-csv/', views_bulk_import.download_sample_csv, name='sample_csv'),
    
    # API endpoints for AJAX
    path('api/check-availability/', views.CheckAvailabilityView.as_view(), name='check_availability'),
    path('api/update-inventory/', views.UpdateInventoryView.as_view(), name='update_inventory'),
    path('api/new-orders-count/', views.new_orders_count, name='new_orders_count'),
    path('api/update-order-status/', views.update_order_status, name='update_order_status'),
    path('api/toggle-store-status/', views.toggle_store_status, name='toggle_store_status'),
]
