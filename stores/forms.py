from django import forms
from django.contrib.auth import get_user_model
from locations.models import ZipArea
from stores.models import StoreZipCoverage, StoreStaff
from delivery.models import DeliveryAgentZipCoverage

User = get_user_model()

class StoreStaffCreateForm(forms.Form):
    """Form for creating new store staff members"""
    
    staff_id = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., ST001'
        }),
        help_text='Unique staff ID for this store'
    )
    
    first_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'First Name'
        })
    )
    
    last_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Last Name'
        })
    )
    
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'email@example.com'
        })
    )
    
    phone_number = forms.CharField(
        max_length=15,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+1234567890'
        })
    )
    
    role = forms.ChoiceField(
        choices=StoreStaff.STAFF_ROLES,
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    
    def __init__(self, *args, **kwargs):
        self.store = kwargs.pop('store', None)
        # Remove instance parameter if passed (CreateView passes this but we don't need it)
        kwargs.pop('instance', None)
        super().__init__(*args, **kwargs)
    
    def clean_staff_id(self):
        staff_id = self.cleaned_data['staff_id']
        
        if self.store:
            # Check if staff ID already exists in this store
            if StoreStaff.objects.filter(store=self.store, staff_id=staff_id).exists():
                raise forms.ValidationError('A staff member with this ID already exists in your store.')
        
        return staff_id
    
    def clean_email(self):
        email = self.cleaned_data['email']
        
        # Check if email is already used
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('A user with this email already exists.')
        
        return email

class StaffLoginForm(forms.Form):
    """Custom login form for store staff"""
    
    store_id = forms.CharField(
        max_length=10,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Store ID (e.g., 001)'
        })
    )
    
    staff_id = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Staff ID (e.g., ST001001)'
        })
    )
    
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Password'
        })
    )


class StoreZipCoverageForm(forms.Form):
    """Form for store managers to select ZIP areas they want to serve"""
    zip_areas = forms.ModelMultipleChoiceField(
        queryset=ZipArea.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        help_text="Select all ZIP areas where you want to deliver products"
    )
    
    def __init__(self, *args, **kwargs):
        self.store = kwargs.pop('store', None)
        super().__init__(*args, **kwargs)
        
        if self.store:
            # Pre-select currently covered ZIP areas
            current_zip_areas = ZipArea.objects.filter(
                store_coverages__store=self.store,
                store_coverages__is_active=True
            )
            self.fields['zip_areas'].initial = current_zip_areas
    
    def save(self):
        if not self.store:
            return
        
        selected_zip_areas = self.cleaned_data['zip_areas']
        
        # Deactivate all current coverages
        StoreZipCoverage.objects.filter(store=self.store).update(is_active=False)
        
        # Create/activate coverage for selected areas
        for zip_area in selected_zip_areas:
            coverage, created = StoreZipCoverage.objects.get_or_create(
                store=self.store,
                zip_area=zip_area,
                defaults={'is_active': True}
            )
            if not created:
                coverage.is_active = True
                coverage.save()


class DeliveryAgentZipCoverageForm(forms.Form):
    """Form for delivery agents to select ZIP areas they can serve"""
    zip_areas = forms.ModelMultipleChoiceField(
        queryset=ZipArea.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        help_text="Select all ZIP areas where you can deliver orders"
    )
    
    def __init__(self, *args, **kwargs):
        self.agent = kwargs.pop('agent', None)
        super().__init__(*args, **kwargs)
        
        if self.agent:
            # Pre-select currently covered ZIP areas
            current_zip_areas = ZipArea.objects.filter(
                delivery_agent_coverages__agent=self.agent,
                delivery_agent_coverages__is_active=True
            )
            self.fields['zip_areas'].initial = current_zip_areas
    
    def save(self):
        if not self.agent:
            return
        
        selected_zip_areas = self.cleaned_data['zip_areas']
        
        # Deactivate all current coverages
        DeliveryAgentZipCoverage.objects.filter(agent=self.agent).update(is_active=False)
        
        # Create/activate coverage for selected areas
        for zip_area in selected_zip_areas:
            coverage, created = DeliveryAgentZipCoverage.objects.get_or_create(
                agent=self.agent,
                zip_area=zip_area,
                defaults={'is_active': True}
            )
            if not created:
                coverage.is_active = True
                coverage.save()
