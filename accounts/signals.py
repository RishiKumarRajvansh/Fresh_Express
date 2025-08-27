"""
Signals for automatic loyalty points processing
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from orders.models import Order
from .models_loyalty import UserLoyaltyAccount, LoyaltyProgram, ReferralProgram

User = get_user_model()

@receiver(post_save, sender=Order)
def award_loyalty_points(sender, instance, created, **kwargs):
    """Award loyalty points when order is delivered"""
    if instance.status == 'delivered' and not hasattr(instance, '_loyalty_points_awarded'):
        # Get active loyalty program
        loyalty_program = LoyaltyProgram.objects.filter(is_active=True).first()
        if not loyalty_program:
            return
        
        # Get or create user loyalty account
        loyalty_account, created = UserLoyaltyAccount.objects.get_or_create(
            user=instance.user,
            defaults={'loyalty_program': loyalty_program}
        )
        
        # Calculate points (points_per_rupee * order total)
        points_to_award = int(float(instance.total_amount) * float(loyalty_program.points_per_rupee))
        
        # Award points
        loyalty_account.add_points(
            points_to_award,
            f"Order #{instance.order_number} - ₹{instance.total_amount}"
        )
        
        # Mark as processed to avoid duplicate awards
        instance._loyalty_points_awarded = True

@receiver(post_save, sender=Order)
def process_referral_bonus(sender, instance, created, **kwargs):
    """Process referral bonus when referred user makes their first order"""
    if instance.status == 'delivered':
        # Check if this is user's first delivered order
        user_delivered_orders = Order.objects.filter(
            user=instance.user,
            status='delivered'
        ).count()
        
        if user_delivered_orders == 1:  # This is the first delivered order
            # Check if user was referred
            try:
                referral = ReferralProgram.objects.get(referred=instance.user)
                if not referral.referred_first_order:
                    referral.referred_first_order = instance
                    referral.save()
                    referral.process_referral_bonus()
            except ReferralProgram.DoesNotExist:
                pass  # User wasn't referred

@receiver(post_save, sender=User)
def create_loyalty_account(sender, instance, created, **kwargs):
    """Create loyalty account for new users"""
    if created:
        loyalty_program = LoyaltyProgram.objects.filter(is_active=True).first()
        if loyalty_program:
            UserLoyaltyAccount.objects.get_or_create(
                user=instance,
                defaults={'loyalty_program': loyalty_program}
            )
