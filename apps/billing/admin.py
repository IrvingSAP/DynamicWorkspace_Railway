from django.contrib import admin

from apps.billing.models import Payment, Plan, Subscription, SubscriptionContact

admin.site.register(Plan)
admin.site.register(Subscription)
admin.site.register(SubscriptionContact)
admin.site.register(Payment)
