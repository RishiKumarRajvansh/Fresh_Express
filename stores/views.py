from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import TemplateView, ListView, DetailView, FormView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.urls import reverse_lazy
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Q, Count
from .models import Store, StoreClosureRequest
from catalog.models import StoreProduct
from orders.models import Order
from delivery.models import DeliveryAgent
from core.decorators import StoreRequiredMixin, store_required
import json

# Note: We don't show store lists to users anymore (Blinkit-style automatic selection)
# These views are mainly for store owners to manage their stores

class StoreDashboardView(StoreRequiredMixin, TemplateView):
    """Store owner dashboard - Only accessible by store owners and staff"""
    template_name = 'stores/dashboard_enhanced.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get stores owned by current user
        user_stores = Store.objects.filter(owner=self.request.user)
        
        if user_stores.exists():
            # For now, get the first store (can be enhanced for multi-store owners)
            store = user_stores.first()
            context['store'] = store
            
            # Get basic stats
            context['total_products'] = StoreProduct.objects.filter(store=store).count()
            context['active_products'] = StoreProduct.objects.filter(
                store=store, 
                is_available=True
            ).count()
            
            # Get pending orders for dashboard
            try:
                from orders.models import Order
                pending_orders = Order.objects.filter(
                    delivery_agent__isnull=True,
                    status='pending'
                ).select_related('user')[:5]
                context['pending_orders'] = pending_orders
                context['pending_orders_count'] = Order.objects.filter(status='pending').count()
            except:
                context['pending_orders'] = []
                context['pending_orders_count'] = 0
            
            # Stats for the enhanced dashboard
            context['stats'] = {
                'pending_orders': context['pending_orders_count'],
                'low_stock_count': StoreProduct.objects.filter(
                    store=store, 
                    stock_quantity__lt=10
                ).count(),
                'available_agents': DeliveryAgent.objects.filter(is_available=True).count(),
            }
            
            # Store status
            context['store_status'] = store.status
            context['is_store_open'] = store.is_open
            
        return context

class StoreProfileView(LoginRequiredMixin, TemplateView):
    """Store profile management"""
    template_name = 'stores/profile.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_stores = Store.objects.filter(owner=self.request.user)
        if user_stores.exists():
            context['store'] = user_stores.first()
        return context

class StoreProductsView(LoginRequiredMixin, ListView):
    """Manage store products"""
    template_name = 'stores/products.html'
    context_object_name = 'products'
    paginate_by = 20
    
    def get_queryset(self):
        user_stores = Store.objects.filter(owner=self.request.user)
        if user_stores.exists():
            store = user_stores.first()
            return StoreProduct.objects.filter(store=store).select_related('product')
        return StoreProduct.objects.none()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_stores = Store.objects.filter(owner=self.request.user)
        if user_stores.exists():
            context['store'] = user_stores.first()
        return context

class StoreOrdersView(LoginRequiredMixin, ListView):
    """View and manage store orders"""
    template_name = 'stores/orders.html'
    context_object_name = 'orders'
    paginate_by = 20
    
    def get_queryset(self):
        user_stores = Store.objects.filter(owner=self.request.user)
        if user_stores.exists():
            store = user_stores.first()
            # Return orders for this store (will be implemented with Order model)
            return []
        return []
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_stores = Store.objects.filter(owner=self.request.user)
        if user_stores.exists():
            context['store'] = user_stores.first()
        return context

class DeliveryAgentsView(LoginRequiredMixin, ListView):
    """Manage delivery agents"""
    template_name = 'stores/delivery_agents.html'
    context_object_name = 'agents'
    
    def get_queryset(self):
        user_stores = Store.objects.filter(owner=self.request.user)
        if user_stores.exists():
            store = user_stores.first()
            # Return delivery agents for this store (will be implemented)
            return []
        return []

class ClosureRequestView(LoginRequiredMixin, FormView):
    """Request store closure"""
    template_name = 'stores/closure_request.html'
    success_url = reverse_lazy('stores:dashboard')
    
    def form_valid(self, form):
        user_stores = Store.objects.filter(owner=self.request.user)
        if user_stores.exists():
            store = user_stores.first()
            
            # Create closure request (simplified)
            StoreClosureRequest.objects.create(
                store=store,
                requested_by=self.request.user,
                reason=form.cleaned_data.get('reason', 'Emergency closure'),
                requested_until=form.cleaned_data.get('requested_until')
            )
        
        return super().form_valid(form)

# API Views for store management
class StoreStatusAPIView(LoginRequiredMixin, TemplateView):
    """API to check store status"""
    
    def get(self, request, *args, **kwargs):
        user_stores = Store.objects.filter(owner=request.user)
        
        if not user_stores.exists():
            return JsonResponse({'error': 'No store found'})
        
        store = user_stores.first()
        
        return JsonResponse({
            'store_id': store.id,
            'store_name': store.name,
            'status': store.status,
            'is_open': store.is_open,
            'total_products': StoreProduct.objects.filter(store=store).count(),
        })

class ToggleProductAPIView(LoginRequiredMixin, TemplateView):
    """API to toggle product availability"""
    
    def post(self, request, *args, **kwargs):
        product_id = request.POST.get('product_id')
        
        user_stores = Store.objects.filter(owner=request.user)
        if not user_stores.exists():
            return JsonResponse({'error': 'No store found'})
        
        store = user_stores.first()
        
        try:
            store_product = StoreProduct.objects.get(id=product_id, store=store)
            store_product.is_available = not store_product.is_available
            store_product.save()
            
            return JsonResponse({
                'success': True,
                'is_available': store_product.is_available,
                'message': f'Product {"enabled" if store_product.is_available else "disabled"}'
            })
        except StoreProduct.DoesNotExist:
            return JsonResponse({'error': 'Product not found'})

class StoreAnalyticsView(LoginRequiredMixin, TemplateView):
    template_name = 'stores/analytics.html'

class AddProductView(LoginRequiredMixin, FormView):
    template_name = 'stores/add_product.html'
    success_url = reverse_lazy('stores:products')

class EditProductView(LoginRequiredMixin, FormView):
    template_name = 'stores/edit_product.html'
    success_url = reverse_lazy('stores:products')

class BulkUploadView(LoginRequiredMixin, FormView):
    template_name = 'stores/bulk_upload.html'
    success_url = reverse_lazy('stores:products')

class OrderDetailView(LoginRequiredMixin, TemplateView):
    template_name = 'stores/order_detail.html'

class UpdateOrderStatusView(LoginRequiredMixin, TemplateView):
    template_name = 'stores/update_order_status.html'

class CheckAvailabilityView(TemplateView):
    def post(self, request, *args, **kwargs):
        return JsonResponse({'available': True})

class UpdateInventoryView(TemplateView):
    def post(self, request, *args, **kwargs):
        return JsonResponse({'success': True})


# ================ NEW STORE DASHBOARD VIEWS ================

@store_required
def store_orders(request):
    """View for managing store orders - Only accessible by store owners and staff"""
    # Get the store owned by current user
    try:
        if request.user.user_type == 'store_owner':
            store = Store.objects.get(owner=request.user)
        elif request.user.user_type == 'store_staff':
            # Store staff should have access to their assigned store
            store = Store.objects.get(staff=request.user)
        else:
            raise Store.DoesNotExist
    except Store.DoesNotExist:
        return redirect('core:home')
    
    # Get orders for this store
    status_filter = request.GET.get('status', '')
    orders = Order.objects.filter(store=store)
    
    if status_filter:
        orders = orders.filter(status=status_filter)
    
    orders = orders.order_by('-created_at')
    
    context = {
        'store': store,
        'orders': orders,
        'status_filter': status_filter,
        'order_statuses': Order._meta.get_field('status').choices,
    }
    
    return render(request, 'stores/orders_management.html', context)


@store_required
def order_detail(request, order_id):
    """View order details - Only accessible by store owners and staff"""
    try:
        if request.user.user_type == 'store_owner':
            store = Store.objects.get(owner=request.user)
        else:
            store = Store.objects.get(staff=request.user)
        order = get_object_or_404(Order, id=order_id, store=store)
    except Store.DoesNotExist:
        return redirect('core:home')
    
    context = {
        'store': store,
        'order': order,
    }
    
    return render(request, 'stores/order_detail.html', context)


@store_required
def store_inventory(request):
    """View and manage store inventory - Only accessible by store owners and staff"""
    try:
        if request.user.user_type == 'store_owner':
            store = Store.objects.get(owner=request.user)
        else:
            store = Store.objects.get(staff=request.user)
    except Store.DoesNotExist:
        return redirect('core:home')
    
    # Handle POST request for adding new products
    if request.method == 'POST':
        try:
            from catalog.models import Product, Category
            
            # Get or create the base product
            product_name = request.POST.get('product_name')
            description = request.POST.get('description', '')
            category_id = request.POST.get('category')
            
            # Get the category object
            try:
                category = Category.objects.get(id=category_id, is_active=True)
            except Category.DoesNotExist:
                return redirect('stores:inventory_management')
            
            product, created = Product.objects.get_or_create(
                name=product_name,
                defaults={
                    'description': description,
                    'category': category,
                    'brand': store.name,
                    'slug': product_name.lower().replace(' ', '-'),
                    'weight_per_unit': float(request.POST.get('weight_per_unit', 1000)),
                    'unit_type': request.POST.get('unit_type', 'grams'),
                    'nutritional_info': request.POST.get('nutritional_info', '{}'),
                }
            )
            
            # Create or update store product
            store_product, created = StoreProduct.objects.get_or_create(
                store=store,
                product=product,
                defaults={
                    'price': float(request.POST.get('price', 0)),
                    'stock_quantity': int(request.POST.get('stock_quantity', 0)),
                    'is_available': request.POST.get('is_available') == 'on',
                }
            )
            
            if not created:
                # Update existing product
                store_product.price = float(request.POST.get('price', 0))
                store_product.stock_quantity = int(request.POST.get('stock_quantity', 0))
                store_product.is_available = request.POST.get('is_available') == 'on'
                store_product.save()
            return redirect('stores:inventory_management')
            
        except Exception as e:
            pass  # Handle errors silently
    
    # Get products for this store
    products = StoreProduct.objects.filter(store=store).select_related('product')
    
    # Filter by stock level
    stock_filter = request.GET.get('stock', '')
    if stock_filter == 'low':
        products = products.filter(stock_quantity__lt=10)
    elif stock_filter == 'out':
        products = products.filter(stock_quantity=0)
    
    # Get categories for the form
    from catalog.models import Category
    categories = Category.objects.filter(is_active=True).order_by('sort_order', 'name')
    
    context = {
        'store': store,
        'products': products,
        'stock_filter': stock_filter,
        'categories': categories,
    }
    
    return render(request, 'stores/inventory_management.html', context)


@store_required
def delivery_agents(request):
    """View delivery agents - Only accessible by store owners and staff"""
    try:
        if request.user.user_type == 'store_owner':
            store = Store.objects.get(owner=request.user)
        else:
            store = Store.objects.get(staff=request.user)
    except Store.DoesNotExist:
        return redirect('core:home')
    
    # Get available delivery agents in the area
    agents = DeliveryAgent.objects.filter(
        is_available=True
    ).select_related('user')
    
    context = {
        'store': store,
        'agents': agents,
    }
    
    return render(request, 'stores/delivery_agents.html', context)


@store_required
def new_orders_count(request):
    """AJAX endpoint to get new orders count - Only accessible by store owners and staff"""
    try:
        if request.user.user_type == 'store_owner':
            store = Store.objects.get(owner=request.user)
        else:
            store = Store.objects.get(staff=request.user)
        
        pending_orders = Order.objects.filter(
            store=store,
            status='pending'
        ).count()
        
        new_orders = Order.objects.filter(
            store=store,
            status='pending',
            created_at__gte=timezone.now() - timezone.timedelta(minutes=5)
        ).count()
        
        return JsonResponse({
            'success': True,
            'pending_orders': pending_orders,
            'new_orders': new_orders,
        })
        
    except Store.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Store not found'
        })


@store_required
def update_order_status(request):
    """AJAX endpoint to update order status - Only accessible by store owners and staff"""
    if request.method == 'POST':
        try:
            if request.user.user_type == 'store_owner':
                store = Store.objects.get(owner=request.user)
            else:
                store = Store.objects.get(staff=request.user)
            
            order_id = request.POST.get('order_id')
            status = request.POST.get('status')
            
            order = get_object_or_404(Order, id=order_id, store=store)
            order.status = status
            order.save()
            
            return JsonResponse({
                'success': True,
                'message': f'Order status updated to {status}'
            })
            
        except Store.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Store not found'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            })
    
    return JsonResponse({
        'success': False,
        'message': 'Invalid request method'
    })


@store_required
def toggle_store_status(request):
    """AJAX endpoint to toggle store open/closed status"""
    if request.method == 'POST':
        try:
            if request.user.user_type == 'store_owner':
                store = Store.objects.get(owner=request.user)
            else:
                store = Store.objects.get(staff=request.user)
            
            # Toggle store status
            if store.status == 'open':
                store.status = 'closed'
            else:
                store.status = 'open'
            
            store.save()
            
            return JsonResponse({
                'success': True,
                'status': store.status,
                'message': f'Store is now {store.status}'
            })
            
        except Store.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Store not found'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            })
    
    return JsonResponse({
        'success': False,
        'message': 'Invalid request method'
    })


class UpdateInventoryView(TemplateView):
    def post(self, request, *args, **kwargs):
        return JsonResponse({'success': True})
