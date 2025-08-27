from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth import get_user_model
from .models import UserProfile, OTPVerification, Wishlist

User = get_user_model()

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'phone_number', 'user_type', 'is_active', 'is_staff', 'date_joined')
    list_filter = ('user_type', 'is_active', 'is_staff', 'date_joined')
    search_fields = ('username', 'email', 'phone_number', 'first_name', 'last_name')
    ordering = ('-date_joined',)
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Additional Info', {
            'fields': ('phone_number', 'user_type', 'phone_verified')
        }),
    )
    
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Additional Info', {
            'fields': ('phone_number', 'user_type')
        }),
    )

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'loyalty_points', 'created_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(OTPVerification)
class OTPVerificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'otp_type', 'is_verified', 'created_at', 'expires_at')
    list_filter = ('is_verified', 'otp_type', 'created_at')
    search_fields = ('user__username', 'user__phone_number')
    readonly_fields = ('created_at',)

@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ('user', 'store_product', 'added_at')
    list_filter = ('added_at', 'store_product__store')
    search_fields = ('user__username', 'store_product__product__name', 'store_product__store__name')
    readonly_fields = ('added_at',)
    raw_id_fields = ('user', 'store_product')
    
    def get_queryset(self, request):
        """Allow superusers to see all wishlists"""
        return super().get_queryset(request).select_related('user', 'store_product__product', 'store_product__store')
