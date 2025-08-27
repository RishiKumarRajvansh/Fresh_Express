from django.shortcuts import render, get_object_or_404
from django.views.generic import TemplateView, ListView, DetailView, FormView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.utils import timezone
from core.decorators import DeliveryAgentRequiredMixin

# Import models
from .models import DeliveryAgent, DeliveryAssignment
from orders.models import Order

class AgentDashboardView(DeliveryAgentRequiredMixin, TemplateView):
    template_name = 'delivery/agent_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        try:
            # Get the delivery agent profile
            agent = DeliveryAgent.objects.get(user=user)
            
            # Get dashboard statistics
            today_assignments = DeliveryAssignment.objects.filter(
                agent=agent,
                assigned_at__date__gte=timezone.now().date()
            )
            
            pending_assignments = DeliveryAssignment.objects.filter(
                agent=agent,
                status__in=['assigned', 'accepted', 'picked_up']
            )
            
            completed_assignments = DeliveryAssignment.objects.filter(
                agent=agent,
                status='delivered'
            )
            
            context.update({
                'agent': agent,
                'today_assignments': today_assignments.count(),
                'pending_assignments': pending_assignments,
                'completed_assignments': completed_assignments.count(),
                'agent_earnings': completed_assignments.count() * 50,  # Simple calculation
                'recent_assignments': pending_assignments[:5],
            })
            
        except DeliveryAgent.DoesNotExist:
            context.update({
                'agent': None,
                'today_assignments': 0,
                'pending_assignments': [],
                'completed_assignments': 0,
                'agent_earnings': 0,
                'recent_assignments': [],
            })
        
        return context

class AgentOrdersView(LoginRequiredMixin, ListView):
    template_name = 'delivery/agent_orders.html'
    context_object_name = 'orders'
    
    def get_queryset(self):
        return []

class AgentOrderDetailView(LoginRequiredMixin, DetailView):
    template_name = 'delivery/agent_order_detail.html'
    context_object_name = 'order'

class AgentProfileView(LoginRequiredMixin, TemplateView):
    template_name = 'delivery/agent_profile.html'

class AgentEarningsView(LoginRequiredMixin, TemplateView):
    template_name = 'delivery/agent_earnings.html'

class AcceptOrderView(LoginRequiredMixin, TemplateView):
    def post(self, request, *args, **kwargs):
        return JsonResponse({'success': True})

class PickupOrderView(LoginRequiredMixin, TemplateView):
    template_name = 'delivery/pickup_order.html'

class DeliverOrderView(LoginRequiredMixin, TemplateView):
    template_name = 'delivery/deliver_order.html'

class ProofOfDeliveryView(LoginRequiredMixin, FormView):
    template_name = 'delivery/proof_of_delivery.html'

class UpdateLocationView(LoginRequiredMixin, TemplateView):
    def post(self, request, *args, **kwargs):
        return JsonResponse({'success': True})

class ToggleAvailabilityView(LoginRequiredMixin, TemplateView):
    def post(self, request, *args, **kwargs):
        return JsonResponse({'success': True})

class TrackOrderView(TemplateView):
    """Track order for customers"""
    template_name = 'delivery/track_order.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order_number = kwargs.get('order_number')
        context['order_number'] = order_number
        context['title'] = f'Track Order #{order_number}'
        return context

class TrackingAPIView(TemplateView):
    def get(self, request, *args, **kwargs):
        return JsonResponse({'location': {'lat': 0, 'lng': 0}})

class AgentLocationAPIView(TemplateView):
    def get(self, request, *args, **kwargs):
        return JsonResponse({'location': {'lat': 0, 'lng': 0}})

class DeliveryZonesAPIView(TemplateView):
    def get(self, request, *args, **kwargs):
        return JsonResponse({'zones': []})

class OptimizeRouteAPIView(TemplateView):
    def post(self, request, *args, **kwargs):
        return JsonResponse({'route': []})
