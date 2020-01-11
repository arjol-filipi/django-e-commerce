from django.contrib import admin

from .models import Item,OrderItem,Order,Address,Payment,Coupon,Refound,UserProfile

def make_refund_accepted(modeladmin,request,queryset):
    queryset.update(refund_requested = False, refund_granted = True)
make_refund_accepted.short_description = "Grant refound"
class OrderAdmin(admin.ModelAdmin):
    list_display = ['user','ordered','being_delivered','received','refund_requested','refund_granted','billing_address','payment','coupon','user']
    list_display_links = ['billing_address','payment','coupon','user']
    list_filter = ['user','ordered','being_delivered','received','refund_requested','refund_granted']
    search_fields = [
        'user_username','ref_code'
    ]
    actions = [make_refund_accepted]

class AddressAdmin(admin.ModelAdmin):
    list_display = ['user','street_address','apartment_address','country','zip','address_type','default']
    list_filter = ['user','country','address_type','default']
    search_fields = ['user','country','zip']
admin.site.register(Item)
admin.site.register(OrderItem)
admin.site.register(Order,OrderAdmin)
admin.site.register(Address,AddressAdmin)
admin.site.register(Payment)
admin.site.register(Coupon)
admin.site.register(Refound)
admin.site.register(UserProfile)