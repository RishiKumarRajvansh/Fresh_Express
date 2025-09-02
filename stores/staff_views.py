from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, TemplateView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.db import transaction
from django.contrib.auth.hashers import make_password
from django.http import JsonResponse, Http404
from django.views import View
from django.utils import timezone
from django.db.models import Count, Q
import random
import string

from core.decorators import StoreRequiredMixin
from .models import Store, StoreStaff, StaffOrderAssignment
from .forms import StoreStaffCreateForm
from orders.models import Order
from delivery.models import DeliveryAgent, DeliveryAssignment

User = get_user_model()

class StaffManagementView(StoreRequiredMixin, ListView):
    """Store owner can view and manage all staff members"""
    template_name = 'stores/staff/staff_list.html'
    context_object_name = 'staff_members'
    
    def get_queryset(self):
        """Get staff for the current store owner's store"""
        return StoreStaff.objects.filter(
            store__owner=self.request.user,
            is_active=True
        ).select_related('user', 'store')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['store'] = Store.objects.filter(owner=self.request.user).first()
        return context

class StaffCreateView(StoreRequiredMixin, CreateView):
    """Create new staff member for the store"""
    template_name = 'stores/staff/staff_create.html'
    form_class = StoreStaffCreateForm
    success_url = reverse_lazy('stores:staff_list')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['store'] = Store.objects.filter(owner=self.request.user).first()
        return kwargs
    
    def form_valid(self, form):
        try:
            with transaction.atomic():
                # Get store
                store = Store.objects.filter(owner=self.request.user).first()
                if not store:
                    messages.error(self.request, 'Store not found.')
                    return self.form_invalid(form)
                
                # Create user account without password
                username = f"staff_{store.id}_{form.cleaned_data['staff_id']}"
                email = form.cleaned_data['email']
                
                # Check if user already exists
                if User.objects.filter(email=email).exists():
                    messages.error(self.request, 'A user with this email already exists.')
                    return self.form_invalid(form)
                
                if User.objects.filter(username=username).exists():
                    messages.error(self.request, 'A staff member with this ID already exists.')
                    return self.form_invalid(form)
                
                # Create user without setting password (unusable password)
                user = User.objects.create(
                    username=username,
                    email=email,
                    first_name=form.cleaned_data['first_name'],
                    last_name=form.cleaned_data['last_name'],
                    user_type='store_staff',
                    phone_number=form.cleaned_data.get('phone_number'),
                    is_active=True
                )
                # Set unusable password - staff will set it on first login
                user.set_unusable_password()
                user.save()
                
                # Create staff profile
                staff = StoreStaff.objects.create(
                    store=store,
                    user=user,
                    staff_id=form.cleaned_data['staff_id'],
                    role=form.cleaned_data['role']
                )
                
                messages.success(
                    self.request, 
                    f'Staff member {user.get_full_name()} created successfully!\\n'
                    f'Staff ID: {staff.staff_id}\\n'
                    f'Email: {user.email}\\n\\n'
                    f'Instructions for {user.get_full_name()}:\\n'
                    f'1. Go to Staff Login page\\n'
                    f'2. Enter Staff ID: {staff.staff_id}\\n'
                    f'3. Enter Email: {user.email}\\n'
                    f'4. Leave password blank on first login\\n'
                    f'5. Set up a new password when prompted'
                )
                
                return redirect(self.success_url)
                
        except Exception as e:
            messages.error(self.request, f'Error creating staff member: {str(e)}')
            return self.form_invalid(form)

class StaffDetailView(StoreRequiredMixin, UpdateView):
    """View and edit staff member details"""
    model = StoreStaff
    template_name = 'stores/staff/staff_detail.html'
    fields = ['role', 'is_active']
    success_url = reverse_lazy('stores:staff_list')
    
    def get_queryset(self):
        """Only allow editing staff from the owner's store"""
        return StoreStaff.objects.filter(store__owner=self.request.user)
    
    def form_valid(self, form):
        messages.success(self.request, 'Staff member updated successfully!')
        return super().form_valid(form)

class StaffDeleteView(StoreRequiredMixin, DeleteView):
    """Deactivate staff member (soft delete)"""
    model = StoreStaff
    template_name = 'stores/staff/staff_confirm_delete.html'
    success_url = reverse_lazy('stores:staff_list')
    
    def get_queryset(self):
        """Only allow deleting staff from the owner's store"""
        return StoreStaff.objects.filter(store__owner=self.request.user)
    
    def delete(self, request, *args, **kwargs):
        """Soft delete - deactivate instead of deleting"""
        self.object = self.get_object()
        
        # Deactivate staff and user
        self.object.is_active = False
        self.object.save()
        
        self.object.user.is_active = False
        self.object.user.save()
        
        messages.success(request, f'Staff member {self.object.user.get_full_name()} has been deactivated.')
        return redirect(self.success_url)

# =================
# STAFF DASHBOARD VIEWS
# =================

class StoreStaffRequiredMixin(LoginRequiredMixin):
    """Mixin to ensure only store staff can access views"""
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        
        if request.user.user_type not in ['store_owner', 'store_staff']:
            messages.error(request, 'You do not have permission to access this page.')
            return redirect('accounts:login')
        
        return super().dispatch(request, *args, **kwargs)

class StaffDashboardView(StoreStaffRequiredMixin, TemplateView):
    """Dashboard for store staff members"""
    template_name = 'stores/staff/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get staff profile and store
        staff_profile = None
        store = None
        
        if self.request.user.user_type == 'store_staff':
            try:
                staff_profile = StoreStaff.objects.get(user=self.request.user, is_active=True)
                store = staff_profile.store
            except StoreStaff.DoesNotExist:
                messages.error(self.request, 'Staff profile not found. Please contact your store manager.')
                return redirect('accounts:login')
        elif self.request.user.user_type == 'store_owner':
            store = Store.objects.filter(owner=self.request.user).first()
        
        if not store:
            messages.error(self.request, 'Store not found.')
            return redirect('accounts:login')
        
        # Get staff assignments if staff member
        assigned_orders = []
        if staff_profile:
            assigned_orders = StaffOrderAssignment.objects.filter(
                staff=staff_profile,
                status__in=['assigned', 'accepted', 'in_progress']
            ).select_related('order').order_by('-assigned_at')[:10]
        
        # Get store order statistics
        today = timezone.now().date()
        store_orders = Order.objects.filter(store=store)
        
        context.update({
            'staff_profile': staff_profile,
            'store': store,
            'assigned_orders': assigned_orders,
            'total_orders_today': store_orders.filter(created_at__date=today).count(),
            'pending_orders': store_orders.filter(status='pending').count(),
            'processing_orders': store_orders.filter(status='confirmed').count(),
            'ready_orders': store_orders.filter(status='ready').count(),
        })
        
        return context

class StaffOrdersView(StoreStaffRequiredMixin, ListView):
    """View for staff to see their assigned orders"""
    template_name = 'stores/staff/orders.html'
    context_object_name = 'assignments'
    paginate_by = 20
    
    def get_queryset(self):
        if self.request.user.user_type == 'store_staff':
            try:
                staff_profile = StoreStaff.objects.get(user=self.request.user, is_active=True)
                return StaffOrderAssignment.objects.filter(
                    staff=staff_profile
                ).select_related('order', 'order__user').order_by('-assigned_at')
            except StoreStaff.DoesNotExist:
                return StaffOrderAssignment.objects.none()
        elif self.request.user.user_type == 'store_owner':
            store = Store.objects.filter(owner=self.request.user).first()
            if store:
                return StaffOrderAssignment.objects.filter(
                    staff__store=store
                ).select_related('order', 'staff__user').order_by('-assigned_at')
        return StaffOrderAssignment.objects.none()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get staff profile
        staff_profile = None
        if self.request.user.user_type == 'store_staff':
            try:
                staff_profile = StoreStaff.objects.get(user=self.request.user, is_active=True)
            except StoreStaff.DoesNotExist:
                pass
        
        context['staff_profile'] = staff_profile
        return context

class StaffOrderDetailView(StoreStaffRequiredMixin, DetailView):
    """Detailed view of an order for staff - Only assigned orders"""
    template_name = 'stores/staff/order_detail.html'
    context_object_name = 'order'
    
    def get_object(self):
        order_number = self.kwargs['order_number']
        order = get_object_or_404(Order, order_number=order_number)
        
        # Check if staff has access to this order
        if self.request.user.user_type == 'store_staff':
            # Staff can only see orders assigned to them
            try:
                staff_profile = StoreStaff.objects.get(user=self.request.user, is_active=True)
                staff_assignment = StaffOrderAssignment.objects.get(order=order, staff=staff_profile)
            except (StoreStaff.DoesNotExist, StaffOrderAssignment.DoesNotExist):
                messages.error(self.request, 'You can only view orders that are assigned to you.')
                raise Http404("Order not found or not assigned to you.")
        elif self.request.user.user_type == 'store_owner':
            # Store owners can see any order from their store
            try:
                store = Store.objects.get(owner=self.request.user)
                if order.store != store:
                    raise Http404("Order not found in your store.")
            except Store.DoesNotExist:
                raise Http404("Store not found.")
        
        return order
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        order = self.get_object()
        
        # Get staff assignment if exists
        try:
            staff_assignment = StaffOrderAssignment.objects.get(order=order)
            context['staff_assignment'] = staff_assignment
        except StaffOrderAssignment.DoesNotExist:
            context['staff_assignment'] = None
        
        # Get available delivery agents
        delivery_agents = DeliveryAgent.objects.filter(
            status='active', 
            is_available=True
        ).select_related('user')
        context['delivery_agents'] = delivery_agents
        
        # Get current delivery assignment if exists
        try:
            delivery_assignment = DeliveryAssignment.objects.get(order=order)
            context['delivery_assignment'] = delivery_assignment
        except DeliveryAssignment.DoesNotExist:
            context['delivery_assignment'] = None
        
        return context

class StaffUpdateOrderStatusView(StoreStaffRequiredMixin, View):
    """API endpoint for staff to update order status"""
    
    def post(self, request):
        try:
            order_id = request.POST.get('order_id')
            new_status = request.POST.get('status')
            notes = request.POST.get('notes', '')
            
            order = get_object_or_404(Order, id=order_id)
            
            # Update order status
            order.status = new_status
            order.save()
            
            # Update staff assignment status if exists
            try:
                staff_assignment = StaffOrderAssignment.objects.get(order=order)
                
                # Map order status to assignment status
                status_mapping = {
                    'confirmed': 'accepted',
                    'processing': 'in_progress',
                    'ready': 'packed',
                    'out_for_delivery': 'ready_for_delivery'
                }
                
                if new_status in status_mapping:
                    staff_assignment.status = status_mapping[new_status]
                    if notes:
                        staff_assignment.notes = notes
                    staff_assignment.save()
                
            except StaffOrderAssignment.DoesNotExist:
                pass
            
            return JsonResponse({
                'success': True,
                'message': f'Order status updated to {new_status}',
                'order_status': order.status
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })

class StaffAssignDeliveryAgentView(StoreStaffRequiredMixin, View):
    """API endpoint for staff to assign delivery agents to orders"""
    
    def post(self, request):
        try:
            order_id = request.POST.get('order_id')
            agent_id = request.POST.get('agent_id')
            
            order = get_object_or_404(Order, id=order_id)
            agent = get_object_or_404(DeliveryAgent, id=agent_id)
            
            # Verify staff has access to this order
            if request.user.user_type == 'store_staff':
                staff_assignment = get_object_or_404(
                    StaffOrderAssignment, 
                    order=order, 
                    staff__user=request.user
                )
            
            # Create or update delivery assignment
            assignment, created = DeliveryAssignment.objects.get_or_create(
                order=order,
                defaults={
                    'agent': agent,
                    'assigned_by': request.user,
                    'status': 'assigned',
                    'pickup_address': order.store.address
                }
            )
            
            if not created:
                assignment.agent = agent
                assignment.assigned_by = request.user
                assignment.status = 'assigned'
                assignment.save()
            
            # Update order status to out_for_delivery
            if order.status == 'ready':
                order.status = 'out_for_delivery'
                order.save()
                
                # Update staff assignment status
                if request.user.user_type == 'store_staff':
                    staff_assignment = StaffOrderAssignment.objects.filter(order=order).first()
                    if staff_assignment:
                        staff_assignment.status = 'ready_for_delivery'
                        staff_assignment.save()
            
            return JsonResponse({
                'success': True,
                'message': f'Delivery agent {agent.user.get_full_name()} assigned to order',
                'agent_name': agent.user.get_full_name(),
                'order_status': order.status
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })

class AssignOrderToStaffView(StoreRequiredMixin, View):
    """API endpoint for store managers to assign orders to staff"""
    
    def dispatch(self, request, *args, **kwargs):
        # Only allow store owners
        if request.user.user_type != 'store_owner':
            return JsonResponse({
                'success': False,
                'error': 'Only store managers can assign orders to staff'
            })
        return super().dispatch(request, *args, **kwargs)
    
    def post(self, request):
        try:
            order_id = request.POST.get('order_id')
            staff_id = request.POST.get('staff_id')
            
            order = get_object_or_404(Order, id=order_id)
            staff = get_object_or_404(StoreStaff, id=staff_id)
            
            # Verify order belongs to the manager's store
            store = Store.objects.get(owner=request.user)
            if order.store != store:
                return JsonResponse({
                    'success': False,
                    'error': 'Order does not belong to your store'
                })
            
            # Create or update staff assignment
            assignment, created = StaffOrderAssignment.objects.get_or_create(
                order=order,
                defaults={
                    'staff': staff,
                    'assigned_by': request.user,
                    'status': 'assigned'
                }
            )
            
            if not created:
                assignment.staff = staff
                assignment.assigned_by = request.user
                assignment.status = 'assigned'
                assignment.assigned_at = timezone.now()
                assignment.save()
            
            # Update order status to confirmed if it was pending
            if order.status == 'pending':
                order.status = 'confirmed'
                order.save()
            
            return JsonResponse({
                'success': True,
                'message': f'Order assigned to {staff.user.get_full_name()}',
                'staff_name': staff.user.get_full_name(),
                'order_status': order.status
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
        self.object.user.is_active = False
        self.object.user.save()
        
        messages.success(request, f'Staff member {self.object.user.get_full_name()} has been deactivated.')
        return redirect(self.success_url)
