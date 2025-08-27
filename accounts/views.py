from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import TemplateView, FormView, ListView
from django.contrib.auth.views import LoginView as DjangoLoginView, LogoutView as DjangoLogoutView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import login, authenticate
from django.urls import reverse_lazy
from django.http import JsonResponse
from django.utils import timezone
from .forms import CustomUserCreationForm, ProfileUpdateForm, MobileLoginForm, OTPVerificationForm, AddressForm
from .models import OTPVerification, User, UserProfile, Wishlist
from locations.models import Address
from catalog.models import StoreProduct
import random
import json

# Simulate OTP sending (in production, use actual SMS service)
def send_otp_sms(phone_number, otp_code):
    """
    In production, integrate with SMS service like:
    - Twilio
    - AWS SNS
    - MSG91
    - TextLocal
    
    For now, we'll just return True (for development)
    """
    # SMS integration would go here
    return True

class MobileLoginView(FormView):
    """Mobile number login - Step 1"""
    template_name = 'accounts/mobile_login.html'
    form_class = MobileLoginForm
    
    def form_valid(self, form):
        mobile_number = form.cleaned_data['mobile_number']
        
        # Check if user exists with this mobile number
        try:
            user = User.objects.get(phone_number=mobile_number)
        except User.DoesNotExist:
            # Create a new user account
            username = f"user_{mobile_number}"
            user = User.objects.create_user(
                username=username,
                phone_number=mobile_number
            )
        
        # Create OTP
        otp = OTPVerification.create_otp(mobile_number, user=user)
        
        # Send OTP via SMS (simulated)
        if send_otp_sms(mobile_number, otp.otp_code):
            # Store mobile number in session for OTP verification
            self.request.session['login_mobile_number'] = mobile_number
            self.request.session['otp_attempts'] = 0
            return redirect('accounts:verify_otp')
        else:
            return self.form_invalid(form)

class VerifyOTPView(FormView):
    """OTP Verification - Step 2"""
    template_name = 'accounts/verify_otp.html'
    form_class = OTPVerificationForm
    success_url = reverse_lazy('core:home')
    
    def dispatch(self, request, *args, **kwargs):
        # Check if mobile number is in session
        if not request.session.get('login_mobile_number'):
            return redirect('accounts:mobile_login')
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        mobile_number = self.request.session.get('login_mobile_number')
        context['mobile_number'] = mobile_number
        context['masked_mobile'] = f"****{mobile_number[-4:]}" if mobile_number else ""
        return context
    
    def form_valid(self, form):
        otp_code = form.cleaned_data['otp']
        mobile_number = self.request.session.get('login_mobile_number')
        
        # Check OTP attempts
        attempts = self.request.session.get('otp_attempts', 0)
        if attempts >= 3:
            return redirect('accounts:mobile_login')
        
        # Verify OTP
        try:
            otp = OTPVerification.objects.get(
                phone_number=mobile_number,
                otp_code=otp_code,
                is_verified=False
            )
            
            if otp.is_expired():
                return redirect('accounts:mobile_login')
            
            # Mark OTP as verified
            otp.is_verified = True
            otp.save()
            
            # Get or create user
            user = User.objects.get(phone_number=mobile_number)
            user.phone_verified = True
            user.save()
            
            # Log the user in
            login(self.request, user)
            
            # Clear session data
            del self.request.session['login_mobile_number']
            del self.request.session['otp_attempts']
            return super().form_valid(form)
            
        except OTPVerification.DoesNotExist:
            # Increment attempts
            self.request.session['otp_attempts'] = attempts + 1
            return self.form_invalid(form)

class ResendOTPView(TemplateView):
    """Resend OTP"""
    def post(self, request, *args, **kwargs):
        mobile_number = request.session.get('login_mobile_number')
        if not mobile_number:
            return JsonResponse({'success': False, 'message': 'Session expired'})
        
        try:
            user = User.objects.get(phone_number=mobile_number)
            otp = OTPVerification.create_otp(mobile_number, user=user)
            
            if send_otp_sms(mobile_number, otp.otp_code):
                request.session['otp_attempts'] = 0  # Reset attempts
                return JsonResponse({'success': True, 'message': 'OTP sent successfully'})
            else:
                return JsonResponse({'success': False, 'message': 'Failed to send OTP'})
        except User.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'User not found'})

class LoginView(DjangoLoginView):
    template_name = 'accounts/login.html'
    success_url = reverse_lazy('core:home')

class LogoutView(DjangoLogoutView):
    next_page = reverse_lazy('core:home')
    http_method_names = ['post']  # Only allow POST for logout
    
    def dispatch(self, request, *args, **kwargs):
        # If someone tries to access logout with GET, redirect to home
        if request.method == 'GET':
            return redirect('core:home')
        return super().dispatch(request, *args, **kwargs)

class RegisterView(FormView):
    template_name = 'accounts/register.html'
    form_class = CustomUserCreationForm
    success_url = reverse_lazy('accounts:mobile_login')
    
    def form_valid(self, form):
        user = form.save()
        return super().form_valid(form)

class ProfileView(LoginRequiredMixin, FormView):
    template_name = 'accounts/profile.html'
    form_class = ProfileUpdateForm
    success_url = reverse_lazy('accounts:profile')
    
    def get_object(self):
        return self.request.user
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['instance'] = self.get_object()
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user'] = self.request.user
        return context
    
    def form_valid(self, form):
        form.save()
        return super().form_valid(form)

class EditProfileView(LoginRequiredMixin, FormView):
    template_name = 'accounts/edit_profile.html'
    form_class = ProfileUpdateForm
    success_url = reverse_lazy('accounts:profile')
    
    def get_object(self):
        return self.request.user
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['instance'] = self.get_object()
        return kwargs
    
    def form_valid(self, form):
        form.save()
        return super().form_valid(form)

class AddressListView(LoginRequiredMixin, ListView):
    template_name = 'accounts/address_list.html'
    context_object_name = 'addresses'
    
    def dispatch(self, request, *args, **kwargs):
        # Only allow customers to access address management
        if not request.user.is_authenticated or request.user.user_type != 'customer':
            return redirect('accounts:profile')
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Check if coming from checkout
        context['from_checkout'] = self.request.GET.get('next') == 'checkout'
        return context

class AddAddressView(LoginRequiredMixin, FormView):
    template_name = 'accounts/add_address.html'
    form_class = AddressForm
    success_url = reverse_lazy('accounts:address_list')
    
    def dispatch(self, request, *args, **kwargs):
        # Only allow customers to access address management
        if not request.user.is_authenticated or request.user.user_type != 'customer':
            return redirect('accounts:profile')
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        try:
            # Create address with correct field mapping
            address = Address.objects.create(
                user=self.request.user,
                label=form.cleaned_data['label'],
                address_type=form.cleaned_data['address_type'],
                address_line_1=form.cleaned_data['address_line_1'],
                address_line_2=form.cleaned_data.get('address_line_2', ''),
                landmark=form.cleaned_data.get('landmark', ''),
                city=form.cleaned_data['city'],
                state=form.cleaned_data['state'],
                zip_code=form.cleaned_data['zip_code'],
                contact_person=form.cleaned_data.get('contact_person', ''),
                contact_phone=form.cleaned_data.get('contact_phone', ''),
                is_default=form.cleaned_data.get('is_default', False)
            )
            
            # Check if we came from checkout
            if self.request.GET.get('next') == 'checkout':
                return redirect('orders:checkout')
            else:
                return redirect('accounts:address_list')
        except Exception as e:
            return self.form_invalid(form)
    
    def form_invalid(self, form):
        return super().form_invalid(form)

class EditAddressView(LoginRequiredMixin, FormView):
    template_name = 'accounts/edit_address.html'
    form_class = AddressForm
    success_url = reverse_lazy('accounts:address_list')
    
    def dispatch(self, request, *args, **kwargs):
        # Only allow customers to access address management
        if not request.user.is_authenticated or request.user.user_type != 'customer':
            return redirect('accounts:profile')
        return super().dispatch(request, *args, **kwargs)
    
    def get_object(self):
        return get_object_or_404(Address, pk=self.kwargs['pk'], user=self.request.user)
    
    def get_initial(self):
        address = self.get_object()
        return {
            'label': address.label,
            'address_type': address.address_type,
            'address_line_1': address.address_line_1,
            'address_line_2': address.address_line_2,
            'landmark': address.landmark,
            'city': address.city,
            'state': address.state,
            'zip_code': address.zip_code,
            'contact_person': address.contact_person,
            'contact_phone': address.contact_phone,
            'is_default': address.is_default
        }
    
    def form_valid(self, form):
        address = self.get_object()
        address.label = form.cleaned_data['label']
        address.address_type = form.cleaned_data['address_type']
        address.address_line_1 = form.cleaned_data['address_line_1']
        address.address_line_2 = form.cleaned_data.get('address_line_2', '')
        address.landmark = form.cleaned_data.get('landmark', '')
        address.city = form.cleaned_data['city']
        address.state = form.cleaned_data['state']
        address.zip_code = form.cleaned_data['zip_code']
        address.contact_person = form.cleaned_data.get('contact_person', '')
        address.contact_phone = form.cleaned_data.get('contact_phone', '')
        address.is_default = form.cleaned_data['is_default']
        address.save()
        
        return super().form_valid(form)

class DeleteAddressView(LoginRequiredMixin, TemplateView):
    template_name = 'accounts/delete_address.html'
    
    def dispatch(self, request, *args, **kwargs):
        # Only allow customers to access address management
        if not request.user.is_authenticated or request.user.user_type != 'customer':
            return redirect('accounts:profile')
        return super().dispatch(request, *args, **kwargs)
    
    def get_object(self):
        return get_object_or_404(Address, pk=self.kwargs['pk'], user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['address'] = self.get_object()
        return context
    
    def post(self, request, *args, **kwargs):
        address = self.get_object()
        address.delete()
        return redirect('accounts:address_list')


# Wishlist Views
class WishlistView(LoginRequiredMixin, ListView):
    """Display user's wishlist - Authentication working properly"""
    model = Wishlist
    template_name = 'accounts/wishlist.html'
    context_object_name = 'wishlist_items'
    paginate_by = 20
    
    def get_queryset(self):        
        return Wishlist.objects.filter(
            user=self.request.user
        ).select_related(
            'store_product__product', 
            'store_product__store'
        ).prefetch_related(
            'store_product__product__images'
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['wishlist_count'] = self.get_queryset().count()
        return context


def toggle_wishlist_new(request):
    """AJAX view to add/remove items from wishlist - Fixed database locking and removed flash messages"""
    if not request.user.is_authenticated:
        return JsonResponse({
            'success': False, 
            'message': 'Please login first',
            'redirect': '/accounts/login/'
        })
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method'})
    
    try:
        # Parse request data
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.POST
        
        store_product_id = data.get('store_product_id')
        
        if not store_product_id:
            return JsonResponse({'success': False, 'message': 'Product ID is required'})
        
        # Validate store product exists
        try:
            store_product = StoreProduct.objects.select_related('product', 'store').get(
                id=store_product_id
            )
        except StoreProduct.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Product not found'})
        
        # Use database transaction with proper isolation to prevent locking
        from django.db import transaction
        import time
        
        max_retries = 5
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                with transaction.atomic():
                    # Use select_for_update to prevent race conditions
                    existing_item = Wishlist.objects.select_for_update().filter(
                        user=request.user,
                        store_product=store_product
                    ).first()
                    
                    if existing_item:
                        # Item exists, remove it
                        existing_item.delete()
                        added = False
                    else:
                        # Item doesn't exist, add it (but first check again to prevent race condition)
                        if not Wishlist.objects.filter(user=request.user, store_product=store_product).exists():
                            Wishlist.objects.create(
                                user=request.user,
                                store_product=store_product
                            )
                        added = True
                    
                    # Get updated counts for navbar
                    from core.cart_utils import update_navbar_counts
                    response_data = update_navbar_counts(request, {
                        'added': added,
                        'product_name': store_product.product.name
                    })
                    
                    return JsonResponse({
                        'success': True,
                        **response_data
                    })
                    
            except Exception as db_error:
                retry_count += 1
                if retry_count >= max_retries:
                    return JsonResponse({
                        'success': False, 
                        'message': 'Database busy. Please try again.'
                    })
                # Brief pause before retry
                time.sleep(0.05 * retry_count)  # Exponential backoff
    
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'Invalid JSON data'})
    except Exception as e:
        return JsonResponse({
            'success': False, 
            'message': 'An error occurred. Please try again.'
        })


def remove_from_wishlist(request, wishlist_id):
    """Remove specific item from wishlist - Removed flash messages"""
    if not request.user.is_authenticated:
        return redirect('accounts:login')
    
    try:
        wishlist_item = get_object_or_404(
            Wishlist, 
            id=wishlist_id, 
            user=request.user
        )
        wishlist_item.delete()
    except Exception as e:
        pass  # Silently handle errors
    
    return redirect('accounts:wishlist')


def clear_wishlist(request):
    """Clear entire wishlist - Updated for AJAX support"""
    if not request.user.is_authenticated:
        if request.headers.get('Content-Type') == 'application/json':
            return JsonResponse({'success': False, 'message': 'Authentication required'})
        return redirect('accounts:login')
    
    if request.method == 'POST':
        try:
            Wishlist.objects.filter(user=request.user).delete()
            
            # For AJAX requests, return JSON with updated counts
            if request.headers.get('Content-Type') == 'application/json':
                from core.cart_utils import update_navbar_counts
                response_data = update_navbar_counts(request, {
                    'message': 'All items cleared from wishlist'
                })
                
                return JsonResponse({
                    'success': True,
                    **response_data
                })
            
        except Exception as e:
            if request.headers.get('Content-Type') == 'application/json':
                return JsonResponse({'success': False, 'message': 'Error clearing wishlist'})
    
    return redirect('accounts:wishlist')


def toggle_wishlist(request):
    """Legacy wishlist toggle - redirects to new implementation"""
    return toggle_wishlist_new(request)
