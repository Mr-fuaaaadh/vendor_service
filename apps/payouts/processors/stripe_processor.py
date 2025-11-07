import stripe
from django.conf import settings
from shared.exceptions import CustomException


class StripeProcessor:
    def __init__(self):
        stripe.api_key = settings.STRIPE_SECRET_KEY
    
    def verify_account(self, payout_account):
        try:
            if payout_account.account_type == 'bank_account':
                # Verify bank account
                token = stripe.Token.create(
                    bank_account={
                        'country': 'US',
                        'currency': 'usd',
                        'account_holder_name': payout_account.account_name,
                        'account_holder_type': 'individual',
                        'account_number': payout_account.account_number,
                        'routing_number': payout_account.routing_number,
                    },
                )
                
                # Create Stripe account
                account = stripe.Account.create(
                    type='custom',
                    country='US',
                    email=payout_account.vendor.contact_email,
                    business_type='individual',
                    individual={
                        'first_name': payout_account.vendor.business_name.split()[0],
                        'last_name': ' '.join(payout_account.vendor.business_name.split()[1:]),
                        'email': payout_account.vendor.contact_email,
                    },
                    external_account=token.id,
                    tos_acceptance={
                        'date': 1609798905,
                        'ip': '8.8.8.8',
                    },
                )
                
                payout_account.stripe_account_id = account.id
                payout_account.save()
                
                return {'success': True, 'account_id': account.id}
            
            else:
                return {'success': False, 'error': 'Unsupported account type for Stripe'}
                
        except stripe.error.StripeError as e:
            return {'success': False, 'error': str(e)}
    
    def process_payout(self, payout):
        try:
            if payout.payout_account.stripe_account_id:
                # Create transfer to connected account
                transfer = stripe.Transfer.create(
                    amount=int(payout.net_amount * 100),  # Convert to cents
                    currency=payout.currency.lower(),
                    destination=payout.payout_account.stripe_account_id,
                    description=f"Payout for {payout.vendor.business_name}"
                )
                
                return {
                    'success': True,
                    'reference': transfer.id,
                    'transfer': transfer
                }
            else:
                return {'success': False, 'error': 'Stripe account not configured'}
                
        except stripe.error.StripeError as e:
            return {'success': False, 'error': str(e)}