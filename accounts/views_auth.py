from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.views import PasswordResetView, PasswordResetConfirmView
from django.views import View
from django.http import JsonResponse
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.urls import reverse_lazy
from django.template.loader import render_to_string
import random
import string
from .models import User, OTPVerification
from .forms import (
    PhoneLoginForm, PhoneRegistrationForm, StoreRegistrationForm, 
    DeliveryAgentRegistrationForm
)
from core.otp_service import OTPService

class PhoneLoginView(View):
    """Phone-based OTP login for customers"""
    
    def get(self, request):
        if request.user.is_authenticated and request.user.user_type == 'customer':
            return redirect('core:home')
        return render(request, 'accounts/phone_login.html')
    
    def post(self, request):
        phone_number = request.POST.get('phone_number', '').strip()
        otp_code = request.POST.get('otp_code', '').strip()
        step = request.POST.get('step', 'phone')
        
        if step == 'phone':
            # Step 1: Send OTP
            if not phone_number:
                return render(request, 'accounts/phone_login.html')
            
            # Validate phone number format (basic validation)
            if not phone_number.isdigit() or len(phone_number) != 10:
                return render(request, 'accounts/phone_login.html')
            
            # Check if user exists with this phone number
            user = User.objects.filter(phone_number=phone_number, user_type='customer').first()
            if not user:
                # User doesn't exist - redirect to registration with message
                return redirect(f'/accounts/phone-register/?error=no_account&phone={phone_number}')
            
            # Generate and send OTP using Twilio
            otp_service = OTPService()
            success, message = otp_service.send_otp_to_phone(phone_number)
            
            if success:
                return render(request, 'accounts/phone_login.html', {
                    'step': 'otp',
                    'phone_number': phone_number
                })
            else:
                return render(request, 'accounts/phone_login.html')
        
        elif step == 'otp':
            # Step 2: Verify OTP
            if not otp_code:
                return render(request, 'accounts/phone_login.html', {
                    'step': 'otp',
                    'phone_number': phone_number
                })
            
            # Verify OTP using Twilio service
            otp_service = OTPService()
            success, message = otp_service.verify_otp(phone_number, otp_code)
            
            if success:
                # Find user and login
                user = User.objects.filter(phone_number=phone_number, user_type='customer').first()
                if user:
                    user.phone_verified = True
                    user.save()
                    
                    login(request, user)
                    return redirect('core:home')
                else:
                    return render(request, 'accounts/phone_login.html', {
                        'step': 'otp', 
                        'phone_number': phone_number
                    })
            else:
                return render(request, 'accounts/phone_login.html', {
                    'step': 'otp',
                    'phone_number': phone_number
                })
        
        return render(request, 'accounts/phone_login.html')

class PhoneRegistrationView(View):
    """Phone-based OTP registration for customers"""
    
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('core:home')
        
        context = {}
        
        # Check if user was redirected from login due to no account
        error = request.GET.get('error')
        phone = request.GET.get('phone')
        
        if error == 'no_account':
            context['error_message'] = "No Account Exists - Please Register Your Account"
            context['suggested_phone'] = phone
        
        return render(request, 'accounts/phone_register.html', context)
    
    def post(self, request):
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        otp_code = request.POST.get('otp_code', '').strip()
        step = request.POST.get('step', 'details')
        
        if step == 'details':
            # Step 1: Collect user details and send OTP
            if not all([name, email, phone_number]):
                return render(request, 'accounts/phone_register.html')
            
            # Validate phone number
            if not phone_number.isdigit() or len(phone_number) != 10:
                return render(request, 'accounts/phone_register.html')
            
            # Check if phone number already exists
            if User.objects.filter(phone_number=phone_number).exists():
                return render(request, 'accounts/phone_register.html')
            
            # Check if email already exists
            if User.objects.filter(email=email).exists():
                return render(request, 'accounts/phone_register.html')
            
            # Generate and send OTP using Twilio
            otp_service = OTPService()
            success, message = otp_service.send_otp_to_phone(phone_number)
            
            if success:
                # Store registration data in session
                request.session['registration_data'] = {
                    'name': name,
                    'email': email,
                    'phone_number': phone_number
                }
                return render(request, 'accounts/phone_register.html', {
                    'step': 'otp',
                    'phone_number': phone_number
                })
            else:
                return render(request, 'accounts/phone_register.html')
        
        elif step == 'otp':
            # Step 2: Verify OTP and create account
            if not otp_code:
                return render(request, 'accounts/phone_register.html', {
                    'step': 'otp',
                    'phone_number': phone_number
                })
            
            registration_data = request.session.get('registration_data')
            if not registration_data:
                return redirect('accounts:phone_register')
            
            # Verify OTP using Twilio service
            otp_service = OTPService()
            success, message = otp_service.verify_otp(registration_data['phone_number'], otp_code)
            
            if success:
                # Create user account
                username = f"user_{registration_data['phone_number']}"
                user = User.objects.create_user(
                    username=username,
                    email=registration_data['email'],
                    first_name=registration_data['name'].split(' ')[0],
                    last_name=' '.join(registration_data['name'].split(' ')[1:]) if ' ' in registration_data['name'] else '',
                    phone_number=registration_data['phone_number'],
                    user_type='customer',
                    phone_verified=True,
                    email_verified=False
                )
                
                # Clear session data
                del request.session['registration_data']
                
                # Login user
                login(request, user)
                return redirect('core:home')
            else:
                return render(request, 'accounts/phone_register.html', {
                    'step': 'otp',
                    'phone_number': registration_data['phone_number']
                })
        
        return render(request, 'accounts/phone_register.html')

class EmailLoginView(View):
    """Email-based login for Store Admin and Delivery agents (NOT for main Admin)"""
    
    def get(self, request):
        user_type = request.GET.get('type', 'store')
        # Redirect admin users to proper admin login
        if user_type == 'admin':
            return redirect('/admin/login/')
            
        if request.user.is_authenticated and request.user.user_type != 'customer':
            if user_type == 'store' and request.user.user_type in ['store_owner', 'store_staff']:
                return redirect('stores:dashboard')
            elif user_type == 'delivery' and request.user.user_type == 'delivery_agent':
                return redirect('delivery:dashboard')
        
        return render(request, 'accounts/email_login.html', {'user_type': user_type})
    
    def post(self, request):
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()
        user_type = request.POST.get('user_type', 'store')
        
        # Redirect admin login attempts
        if user_type == 'admin':
            return redirect('/admin/login/')
        
        if not email or not password:
            return render(request, 'accounts/email_login.html', {'user_type': user_type})
        
        # Authenticate user
        user = authenticate(request, username=email, password=password)
        if not user:
            # Try with email field
            try:
                user_obj = User.objects.get(email=email)
                user = authenticate(request, username=user_obj.username, password=password)
            except User.DoesNotExist:
                pass
        
        if not user:
            # Check if user exists but password is wrong vs user doesn't exist
            user_exists = User.objects.filter(email=email).exists()
            
            if not user_exists:
                # User doesn't exist - redirect to registration
                if user_type == 'store':
                    return redirect(f'/accounts/store-register/?error=no_account&email={email}')
                elif user_type == 'delivery':
                    return redirect(f'/accounts/delivery-register/?error=no_account&email={email}')
            
            return render(request, 'accounts/email_login.html', {'user_type': user_type})
        
        # Check user type (no admin allowed here)
        allowed_types = {
            'store': ['store_owner', 'store_staff'],
            'delivery': ['delivery_agent']
        }
        
        if user.user_type not in allowed_types.get(user_type, []):
            if user.user_type == 'admin':
                return redirect('/admin/login/')
            else:
                return render(request, 'accounts/email_login.html', {'user_type': user_type})
        
        login(request, user)
        
        # Redirect based on user type
        if user_type == 'store':
            return redirect('stores:dashboard')
        elif user_type == 'delivery':
            return redirect('delivery:agent_dashboard')
        
        return redirect('core:home')

class CustomPasswordResetView(PasswordResetView):
    """Custom password reset for non-customer users"""
    template_name = 'accounts/password_reset.html'
    email_template_name = 'accounts/password_reset_email.html'
    success_url = reverse_lazy('accounts:password_reset_done')
    
    def form_valid(self, form):
        email = form.cleaned_data['email']
        # Only allow password reset for non-customer users
        user = User.objects.filter(email=email).exclude(user_type='customer').first()
        if not user:
            return self.form_invalid(form)
        return super().form_valid(form)

class ResendOTPView(View):
    """Resend OTP for phone authentication"""
    
    def post(self, request):
        phone_number = request.POST.get('phone_number', '').strip()
        
        if not phone_number:
            return JsonResponse({'success': False, 'message': 'Phone number is required.'})
        
        # Delete old OTPs for this phone number
        OTPVerification.objects.filter(phone_number=phone_number, is_verified=False).delete()
        
        # Generate new OTP
        otp = OTPVerification.objects.create(
            phone_number=phone_number,
            otp_type='phone'
        )
        
        # In production, integrate with SMS service
        return JsonResponse({
            'success': True, 
            'message': f'New OTP sent to your phone: {otp.otp_code} (Testing mode)'
        })

class StoreRegistrationView(View):
    """Store registration for new store owners"""
    
    def get(self, request):
        context = {}
        
        # Check if user was redirected from login due to no account
        error = request.GET.get('error')
        email = request.GET.get('email')
        
        if error == 'no_account':
            context['error_message'] = "No Account Exists - Please Register Your Store Account"
            context['suggested_email'] = email
        
        return render(request, 'accounts/store_register.html', context)
    
    def post(self, request):
        # Get form data
        store_name = request.POST.get('store_name', '').strip()
        owner_name = request.POST.get('owner_name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        address = request.POST.get('address', '').strip()
        city = request.POST.get('city', '').strip()
        zip_code = request.POST.get('zip_code', '').strip()
        store_type = request.POST.get('store_type', '').strip()
        gst_number = request.POST.get('gst_number', '').strip()
        description = request.POST.get('description', '').strip()
        password = request.POST.get('password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()
        
        # Validate required fields
        required_fields = [store_name, owner_name, email, phone, address, city, zip_code, store_type, password]
        if not all(required_fields):
            return render(request, 'accounts/store_register.html')
        
        # Check password confirmation
        if password != confirm_password:
            return render(request, 'accounts/store_register.html')
        
        # Check password strength
        if len(password) < 8:
            return render(request, 'accounts/store_register.html')
        
        # Check if email already exists
        if User.objects.filter(email=email).exists():
            return render(request, 'accounts/store_register.html')
        
        # Store registration data in session for admin review
        registration_data = {
            'store_name': store_name,
            'owner_name': owner_name,
            'email': email,
            'phone': phone,
            'address': address,
            'city': city,
            'zip_code': zip_code,
            'store_type': store_type,
            'gst_number': gst_number,
            'description': description,
            'status': 'pending_review',
            'submitted_at': timezone.now().isoformat()
        }
        
        # In a real application, you would:
        # 1. Save to a StoreRegistration model
        # 2. Send email notification to admin
        # 3. Create pending approval workflow
        
        # For now, let's create the store owner account directly (you can modify this)
        try:
            # Create user account
            username = f"store_{email.split('@')[0]}"
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,  # Now setting the password
                first_name=owner_name.split(' ')[0],
                last_name=' '.join(owner_name.split(' ')[1:]) if ' ' in owner_name else '',
                phone_number=phone,
                user_type='store_owner',
                is_active=True  # Make account active so they can log in
            )
            
            # Create Store record
            from stores.models import Store
            store_code = f"ST{user.id:04d}"
            store = Store.objects.create(
                owner=user,
                store_code=store_code,
                name=store_name,
                description=description,
                phone_number=phone,
                email=email,
                address_line_1=address,
                city=city,
                state='Delhi',  # Default state - can be made configurable
                zip_code=zip_code,
                status='open',  # Store is immediately operational
                is_active=True
            )
            return redirect('accounts:email_login')
            
        except Exception as e:
            return render(request, 'accounts/store_register.html')

class DeliveryAgentRegistrationView(View):
    """Delivery agent registration for new delivery agents"""
    
    def get(self, request):
        context = {}
        
        # Check if user was redirected from login due to no account
        error = request.GET.get('error')
        email = request.GET.get('email')
        
        if error == 'no_account':
            context['error_message'] = "No Account Exists - Please Register Your Delivery Agent Account"
            context['suggested_email'] = email
        
        return render(request, 'accounts/delivery_register.html', context)
    
    def post(self, request):
        # Get form data
        full_name = request.POST.get('full_name', '').strip()
        email = request.POST.get('email', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        emergency_contact = request.POST.get('emergency_contact', '').strip()
        address = request.POST.get('address', '').strip()
        city = request.POST.get('city', '').strip()
        zip_code = request.POST.get('zip_code', '').strip()
        vehicle_type = request.POST.get('vehicle_type', '').strip()
        vehicle_number = request.POST.get('vehicle_number', '').strip()
        license_number = request.POST.get('license_number', '').strip()
        experience_years = request.POST.get('experience_years', '0')
        password = request.POST.get('password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()
        
        # Validate required fields
        required_fields = [full_name, email, phone_number, address, city, zip_code, 
                          vehicle_type, vehicle_number, license_number, password]
        if not all(required_fields):
            return render(request, 'accounts/delivery_register.html')
        
        # Check password confirmation
        if password != confirm_password:
            return render(request, 'accounts/delivery_register.html')
        
        # Check password strength
        if len(password) < 8:
            return render(request, 'accounts/delivery_register.html')
        
        # Check if email already exists
        if User.objects.filter(email=email).exists():
            return render(request, 'accounts/delivery_register.html')
        
        # Store registration data in session for admin review
        registration_data = {
            'full_name': full_name,
            'email': email,
            'phone_number': phone_number,
            'emergency_contact': emergency_contact,
            'address': address,
            'city': city,
            'zip_code': zip_code,
            'vehicle_type': vehicle_type,
            'vehicle_number': vehicle_number,
            'license_number': license_number,
            'experience_years': experience_years,
            'status': 'pending_review',
            'submitted_at': timezone.now().isoformat()
        }
        
        # In a real application, you would:
        # 1. Save to a DeliveryAgentApplication model
        # 2. Send email notification to admin
        # 3. Create pending approval workflow
        
        # For now, let's create the delivery agent account directly (you can modify this)
        try:
            # Create user account
            username = f"agent_{email.split('@')[0]}"
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,  # Now setting the password
                first_name=full_name.split(' ')[0],
                last_name=' '.join(full_name.split(' ')[1:]) if ' ' in full_name else '',
                phone_number=phone_number,
                user_type='delivery_agent',
                is_active=True  # Make account active so they can log in
            )
            
            # Create DeliveryAgent record
            from delivery.models import DeliveryAgent
            # For now, assign to first available store (in production, this would be admin-managed)
            from stores.models import Store
            default_store = Store.objects.filter(is_active=True).first()
            
            if default_store:
                agent_id = f"AGT{user.id:04d}"
                delivery_agent = DeliveryAgent.objects.create(
                    user=user,
                    store=default_store,
                    agent_id=agent_id,
                    phone_number=phone_number,
                    emergency_contact=emergency_contact,
                    vehicle_type=vehicle_type,
                    vehicle_number=vehicle_number,
                    license_number=license_number,
                    status='inactive',  # Agent starts as inactive until they go online
                    is_available=False
                )
            return redirect('accounts:email_login')
            
        except Exception as e:
            return render(request, 'accounts/delivery_register.html')

class BusinessRegistrationView(View):
    """Business registration landing page for choosing store owner or delivery agent"""
    
    def get(self, request):
        return render(request, 'accounts/business_register.html')

class LogoutView(View):
    """Custom logout view - handles both GET and POST"""
    
    def dispatch(self, request, *args, **kwargs):
        return self.perform_logout(request)
    
    def perform_logout(self, request):
        user_type = getattr(request.user, 'user_type', 'customer') if request.user.is_authenticated else 'customer'
        logout(request)
        
        # Redirect based on user type
        if user_type in ['admin']:
            return redirect('/admin/login/')
        elif user_type in ['store_owner', 'store_staff']:
            return redirect('accounts:email_login') 
        elif user_type == 'delivery_agent':
            return redirect('accounts:email_login')
        else:  # customer
            return redirect('core:home')
    
    def get(self, request):
        return self.perform_logout(request)
    
    def post(self, request):
        return self.perform_logout(request)
