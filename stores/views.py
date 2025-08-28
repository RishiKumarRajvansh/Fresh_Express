from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import TemplateView, ListView, DetailView, FormView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.contrib import messages
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
            # Determine available delivery agents for this store: either assigned to the store
            # or those who serve any of the store's active ZIP areas.
            served_zip_areas = store.zip_coverages.filter(is_active=True).values_list('zip_area', flat=True)
            agents_qs = DeliveryAgent.objects.filter(
                Q(store=store) | Q(zip_coverages__zip_area__in=served_zip_areas, zip_coverages__is_active=True),
                is_available=True
            ).distinct()

            # If the store is closed, we shouldn't show pending orders or available agents
            if store.status != 'open':
                pending_orders = []
                pending_orders_count = 0
                available_agents_count = 0
            else:
                pending_orders = context.get('pending_orders', [])
                pending_orders_count = context.get('pending_orders_count', 0)
                available_agents_count = agents_qs.count()

            context['stats'] = {
                'pending_orders': pending_orders_count,
                'low_stock_count': StoreProduct.objects.filter(
                    store=store, 
                    stock_quantity__lt=10
                ).count(),
                'available_agents': available_agents_count,
            }
            
            # Store status
            context['store_status'] = store.status
            context['is_store_open'] = store.is_open
            # Provide agents queryset and a simple list for templates
            context['available_agents_qs'] = agents_qs if store.status == 'open' else DeliveryAgent.objects.none()
            context['available_agents'] = list(agents_qs) if store.status == 'open' else []
            
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
            # If the store is closed, return no agents
            if store.status != 'open':
                return DeliveryAgent.objects.none()

            # Return delivery agents assigned to the store or who serve the store's active ZIP areas
            served_zip_areas = store.zip_coverages.filter(is_active=True).values_list('zip_area', flat=True)
            agents_qs = DeliveryAgent.objects.filter(
                Q(store=store) | Q(zip_coverages__zip_area__in=served_zip_areas, zip_coverages__is_active=True),
                is_active=True
            ).distinct().order_by('-is_available', 'user__last_name')

            return agents_qs
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
            from catalog.models import Product, Category, ProductImage
            
            # Get or create the base product
            product_name = request.POST.get('product_name')
            description = request.POST.get('description', '')
            category_id = request.POST.get('category')
            
            # Get the category object
            try:
                category = Category.objects.get(id=category_id, is_active=True)
            except Category.DoesNotExist:
                messages.error(request, 'Please select a valid category.')
                return redirect('stores:inventory_management')
            
            # Handle images
            images = request.FILES.getlist('images')
            if not images:
                messages.error(request, 'Please upload at least one product image.')
                return redirect('stores:inventory_management')
            
            if len(images) > 5:
                messages.error(request, 'You can upload maximum 5 images.')
                return redirect('stores:inventory_management')
            
            # Create the product with the first image as main image
            product, created = Product.objects.get_or_create(
                name=product_name,
                category=category,
                defaults={
                    'description': description,
                    'brand': store.name,
                    'slug': product_name.lower().replace(' ', '-').replace('/', '-'),
                    'weight_per_unit': float(request.POST.get('weight_per_unit', 1000)),
                    'unit_type': request.POST.get('unit_type', 'grams'),
                    'nutritional_info': {},
                    'image': images[0],  # First image as main image
                }
            )
            
            # If product already exists, update the main image
            if not created:
                product.image = images[0]
                product.description = description
                product.save()
            
            # Add additional images (if any)
            if len(images) > 1:
                # Clear existing additional images for this product
                ProductImage.objects.filter(product=product).delete()
                
                for i, image in enumerate(images[1:], 1):  # Skip first image
                    ProductImage.objects.create(
                        product=product,
                        image=image,
                        sort_order=i,
                        is_active=True
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
            
            messages.success(request, f'Product "{product_name}" added successfully!')
            return redirect('stores:inventory_management')
            
        except Exception as e:
            print(f"Product addition error: {e}")  # For debugging
            import traceback
            traceback.print_exc()
            messages.error(request, 'Failed to add product. Please try again.')
            return redirect('stores:inventory_management')
    
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
def edit_store_product(request, product_id):
    """Edit a store product"""
    try:
        if request.user.user_type == 'store_owner':
            store = Store.objects.get(owner=request.user)
        else:
            store = Store.objects.get(staff=request.user)
    except Store.DoesNotExist:
        return redirect('core:home')
    
    # Get the store product
    store_product = get_object_or_404(StoreProduct, id=product_id, store=store)
    
    if request.method == 'POST':
        try:
            # Update store product details
            store_product.price = float(request.POST.get('price', store_product.price))
            store_product.stock_quantity = int(request.POST.get('stock_quantity', store_product.stock_quantity))
            store_product.is_available = request.POST.get('is_available') == 'on'
            store_product.is_featured = request.POST.get('is_featured') == 'on'
            store_product.discount_percentage = int(request.POST.get('discount_percentage', 0)) if request.POST.get('discount_percentage') else None
            
            # Update base product details if provided
            if request.POST.get('description'):
                store_product.product.description = request.POST.get('description')
                store_product.product.save()
            
            store_product.save()
            messages.success(request, f'Product "{store_product.product.name}" updated successfully!')
            
        except Exception as e:
            messages.error(request, f'Error updating product: {str(e)}')
            
        return redirect('stores:inventory_management')
    
    from catalog.models import Category
    categories = Category.objects.filter(is_active=True).order_by('sort_order', 'name')
    
    context = {
        'store': store,
        'store_product': store_product,
        'categories': categories,
    }
    return render(request, 'stores/edit_product.html', context)


@store_required
def delete_store_product(request, product_id):
    """Delete a store product"""
    try:
        if request.user.user_type == 'store_owner':
            store = Store.objects.get(owner=request.user)
        else:
            store = Store.objects.get(staff=request.user)
    except Store.DoesNotExist:
        return redirect('core:home')
    
    # Get the store product
    store_product = get_object_or_404(StoreProduct, id=product_id, store=store)
    
    if request.method == 'POST':
        product_name = store_product.product.name
        store_product.delete()
        messages.success(request, f'Product "{product_name}" removed from your inventory!')
        return redirect('stores:inventory_management')
    
    context = {
        'store': store,
        'store_product': store_product,
    }
    return render(request, 'stores/delete_product.html', context)


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
    
    # Get delivery agents in the store's coverage area
    from locations.models import ZipArea
    from stores.models import StoreZipCoverage
    
    # Get ZIP areas served by this store
    served_zip_areas = ZipArea.objects.filter(
        store_coverages__store=store,
        store_coverages__is_active=True,
        is_active=True
    ).distinct()
    
    # Get delivery agents that serve any of the ZIP areas this store serves
    from delivery.models import DeliveryAgent, DeliveryAgentZipCoverage
    
    # Combine both conditions into a single QuerySet using Q to avoid union issues
    from django.db.models import Q

    agents = DeliveryAgent.objects.filter(
        Q(zip_coverages__zip_area__in=served_zip_areas, zip_coverages__is_active=True) | Q(store=store)
    ).select_related('user').distinct().order_by('-is_available', 'user__first_name')
    
    # Separate available and unavailable agents
    available_agents = agents.filter(is_available=True)
    unavailable_agents = agents.filter(is_available=False)
    
    context = {
        'store': store,
        'agents': agents,
        'available_agents': available_agents,
        'unavailable_agents': unavailable_agents,
        'served_zip_areas': served_zip_areas,
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
            # Lightweight debug trace to confirm request arrives in server logs
            try:
                print('UPDATE_ORDER_STATUS_HIT', 'user=', getattr(request.user, 'username', None), 'COOKIES=', list(getattr(request, 'COOKIES', {}).keys()), 'POST_keys=', list(request.POST.keys()))
            except Exception:
                pass
            if request.user.user_type == 'store_owner':
                store = Store.objects.get(owner=request.user)
            else:
                store = Store.objects.get(staff=request.user)
            
            order_id = request.POST.get('order_id')
            status = request.POST.get('status')

            # Echo posted values for diagnostics
            if not order_id:
                return JsonResponse({'success': False, 'message': 'order_id not provided', 'posted_status': status})

            order = get_object_or_404(Order, id=order_id, store=store)

            # Validate status choice
            valid_statuses = [c[0] for c in Order._meta.get_field('status').choices]
            if status not in valid_statuses:
                return JsonResponse({'success': False, 'message': 'invalid status', 'posted_status': status, 'valid_statuses': valid_statuses})

            old_status = order.status
            order.status = status
            order.save()

            # Success trace
            try:
                print('UPDATE_ORDER_STATUS_SUCCESS', f'order={order.id}', f'from={old_status}', f'to={order.status}', 'by=', getattr(request.user, 'username', None))
            except Exception:
                pass

            return JsonResponse({
                'success': True,
                'message': f'Order status updated to {status}',
                'order_id': order.id,
                'old_status': old_status,
                'new_status': order.status,
            })
            
        except Store.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Store not found', 'posted_order_id': request.POST.get('order_id'), 'posted_status': request.POST.get('status')})
        except Exception as e:
            # Include posted values for easier debugging
            return JsonResponse({'success': False, 'message': str(e), 'posted_order_id': request.POST.get('order_id'), 'posted_status': request.POST.get('status')})
    
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


@store_required
def manage_zip_coverage(request):
    """View for store managers to select ZIP areas they serve"""
    try:
        if request.user.user_type == 'store_owner':
            store = Store.objects.get(owner=request.user)
        else:
            store = Store.objects.get(staff=request.user)
    except Store.DoesNotExist:
        return redirect('core:home')
    
    from .forms import StoreZipCoverageForm
    
    if request.method == 'POST':
        form = StoreZipCoverageForm(request.POST, store=store)
        if form.is_valid():
            form.save()
            messages.success(request, 'ZIP coverage areas updated successfully!')
            return redirect('stores:manage_zip_coverage')
    else:
        form = StoreZipCoverageForm(store=store)
    
    context = {
        'store': store,
        'form': form,
        'current_coverage': store.zip_coverages.filter(is_active=True).select_related('zip_area'),
    }
    
    return render(request, 'stores/manage_zip_coverage.html', context)


@login_required
def agent_zip_coverage(request):
    """View for delivery agents to select ZIP areas they can serve - MOVED TO DELIVERY APP"""
    # This function has been moved to delivery/views.py
    return redirect('delivery:agent_zip_coverage')
