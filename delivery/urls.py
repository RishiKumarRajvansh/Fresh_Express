from django.urls import path
from . import views
from .production_views import *
from .workflow_views import *
from django.shortcuts import render
from django.contrib.auth.decorators import login_required

# Placeholder views for missing functions
@login_required
def ratings_feedback(request):
    return render(request, 'delivery/ratings_feedback.html', {
        'title': 'Ratings & Feedback',
        'agent': request.user.deliveryagent if hasattr(request.user, 'deliveryagent') else None
    })

@login_required 
def vehicle_info(request):
    return render(request, 'delivery/vehicle_info.html', {
        'title': 'Vehicle Information',
        'user': request.user
    })

@login_required
def delivery_history(request):
    return render(request, 'delivery/delivery_history.html', {
        'title': 'Delivery History'
    })

@login_required 
def toggle_availability(request):
    from django.http import JsonResponse
    return JsonResponse({'success': True, 'available': True})

@login_required
def update_location(request):
    from django.http import JsonResponse
    return JsonResponse({'success': True})

app_name = 'delivery'

urlpatterns = [
    # Agent Dashboard
    path('dashboard/', AgentDashboardView.as_view(), name='agent_dashboard'),
    
    # Order Management
    path('orders/', AgentOrdersView.as_view(), name='agent_orders'),
    path('orders/<int:assignment_id>/', AgentOrderDetailView.as_view(), name='assignment_detail'),
    path('accept-order/<int:assignment_id>/', accept_order, name='accept_order'),
    path('pickup-order/<int:assignment_id>/', pickup_order, name='pickup_order'),
    path('deliver-order/<int:assignment_id>/', deliver_order, name='deliver_order'),
    
    # Agent Features
    path('earnings/', AgentEarningsView.as_view(), name='earnings'),
    path('history/', delivery_history, name='delivery_history'),
    path('ratings/', ratings_feedback, name='ratings_feedback'),
    path('vehicle-info/', vehicle_info, name='vehicle_info'),
    
    # AJAX APIs
    path('api/toggle-availability/', toggle_availability, name='toggle_availability'),
    path('api/update-location/', update_location, name='update_location'),
    
    # Enhanced Workflow APIs
    path('scan-handover/', scan_handover_code, name='scan_handover_code'),
    path('confirm-delivery/', confirm_delivery, name='confirm_delivery'),
    path('store/confirm-handover/', store_confirm_handover, name='store_confirm_handover'),
    path('workflow-status/<str:order_number>/', order_workflow_status, name='workflow_status'),
    
    # Order Tracking (for customers)
    path('track/<str:order_number>/', views.TrackOrderView.as_view(), name='track_order'),
    
    # Legacy URLs (for backward compatibility)
    path('agent/orders/<str:order_number>/', views.AgentOrderDetailView.as_view(), name='agent_order_detail_legacy'),
    path('agent/profile/', views.AgentProfileView.as_view(), name='agent_profile'),
]
