from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate
from django.views import View
from django.contrib import messages
from django.contrib.auth.hashers import make_password
from django.db import transaction
from stores.models import StoreStaff
from accounts.models import User

class StaffLoginView(View):
    """Special login view for store staff using Staff ID + Email"""
    
    def get(self, request):
        if request.user.is_authenticated and request.user.user_type == 'store_staff':
            return redirect('stores:staff_dashboard')
        
        return render(request, 'accounts/staff_login.html')
    
    def post(self, request):
        staff_id = request.POST.get('staff_id', '').strip()
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '').strip()
        new_password = request.POST.get('new_password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()
        
        if not staff_id or not email:
            messages.error(request, 'Please enter both Staff ID and email.')
            return render(request, 'accounts/staff_login.html')
        
        try:
            # Find staff member
            staff = StoreStaff.objects.select_related('user', 'store').get(
                staff_id=staff_id,
                user__email=email,
                is_active=True
            )
            
            # Check if user has a password set
            if not staff.user.has_usable_password():
                # First time login - need to set password
                if not new_password or not confirm_password:
                    context = {
                        'first_login': True,
                        'staff_id': staff_id,
                        'email': email,
                        'staff_name': staff.user.get_full_name()
                    }
                    return render(request, 'accounts/staff_login.html', context)
                
                # Validate new password
                if new_password != confirm_password:
                    messages.error(request, 'Passwords do not match.')
                    context = {
                        'first_login': True,
                        'staff_id': staff_id,
                        'email': email,
                        'staff_name': staff.user.get_full_name()
                    }
                    return render(request, 'accounts/staff_login.html', context)
                
                if len(new_password) < 6:
                    messages.error(request, 'Password must be at least 6 characters long.')
                    context = {
                        'first_login': True,
                        'staff_id': staff_id,
                        'email': email,
                        'staff_name': staff.user.get_full_name()
                    }
                    return render(request, 'accounts/staff_login.html', context)
                
                # Set new password
                with transaction.atomic():
                    staff.user.set_password(new_password)
                    staff.user.save()
                    
                    # Login user
                    login(request, staff.user)
                    messages.success(request, f'Welcome {staff.user.get_full_name()}! Your password has been set successfully.')
                    return redirect('stores:staff_dashboard')
            
            else:
                # Normal login with existing password
                if not password:
                    messages.error(request, 'Please enter your password.')
                    return render(request, 'accounts/staff_login.html')
                
                user = authenticate(request, username=staff.user.username, password=password)
                if user and user == staff.user:
                    login(request, user)
                    return redirect('stores:staff_dashboard')
                else:
                    messages.error(request, 'Invalid password.')
                    return render(request, 'accounts/staff_login.html')
        
        except StoreStaff.DoesNotExist:
            messages.error(request, 'Invalid Staff ID or email. Please check your credentials.')
            return render(request, 'accounts/staff_login.html')
        
        except Exception as e:
            messages.error(request, f'Login error: {str(e)}')
            return render(request, 'accounts/staff_login.html')


class StaffPasswordChangeView(View):
    """Allow staff to change their password"""
    
    def get(self, request):
        if not request.user.is_authenticated or request.user.user_type != 'store_staff':
            return redirect('accounts:staff_login')
        
        return render(request, 'accounts/staff_password_change.html')
    
    def post(self, request):
        if not request.user.is_authenticated or request.user.user_type != 'store_staff':
            return redirect('accounts:staff_login')
        
        current_password = request.POST.get('current_password', '').strip()
        new_password = request.POST.get('new_password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()
        
        if not current_password or not new_password or not confirm_password:
            messages.error(request, 'All fields are required.')
            return render(request, 'accounts/staff_password_change.html')
        
        if not request.user.check_password(current_password):
            messages.error(request, 'Current password is incorrect.')
            return render(request, 'accounts/staff_password_change.html')
        
        if new_password != confirm_password:
            messages.error(request, 'New passwords do not match.')
            return render(request, 'accounts/staff_password_change.html')
        
        if len(new_password) < 6:
            messages.error(request, 'Password must be at least 6 characters long.')
            return render(request, 'accounts/staff_password_change.html')
        
        # Change password
        request.user.set_password(new_password)
        request.user.save()
        
        # Re-authenticate to maintain session
        user = authenticate(request, username=request.user.username, password=new_password)
        if user:
            login(request, user)
        
        messages.success(request, 'Your password has been changed successfully.')
        return redirect('stores:staff_dashboard')
