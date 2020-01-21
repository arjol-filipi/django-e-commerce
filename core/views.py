from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import render, get_object_or_404
from django.views.generic import ListView,DetailView,View
from django.shortcuts import redirect
from django.utils import timezone
from .models import Coupon,Item, Order, OrderItem,Address,Payment,Refound,UserProfile,CATEGORY_CHOICES
from .forms import CheckoutForm,CouponForm,RefundForm,PaymentForm

from django.db.models import Q

import stripe
import random
import string

stripe.api_key = settings.STRIPE_SECRET_KEY

# `source` is obtained with Stripe.js; see https://stripe.com/docs/payments/accept-a-payment-charges#web-create-token

def create_ref_code():
    return ''.join(random.choices(string.ascii_lowercase+string.digits,k= 20))

def item_list(request):
    context ={
        'items':Item.objects.all()
    }
    return render(request,"home-page.html",context)


def products(request):
    context = {'items': Item.objects.all()}
    return render(request, "product.html", context)

def is_valid_form(values):
    valid = True
    for field in values:
        if field == '':
            valid = False
    return valid


class CheckoutView(View):
    def get(self,*args,**kwargs):
        form = CheckoutForm()
        try:
            order = Order.objects.get(user= self.request.user,ordered= False)
            context = {
                        'form':form,
                        'couponform':CouponForm(),
                        'order':order,
                        'DISPLAY_COUPON_FORM':True
                    }
            shipping_address_qs = Address.objects.filter(
                user= self.request.user,
                address_type='S',
                default= True
            )
            if shipping_address_qs.exists():
                context.update({
                    'default_shipping_address':shipping_address_qs[0]
                })
            billing_address_qs = Address.objects.filter(
                user= self.request.user,
                address_type='B',
                default= True
            )
            if billing_address_qs.exists():
                context.update({
                    'default_billing_address':billing_address_qs[0]
                })
            return render(self.request, "checkout.html",context)

        except ObjectDoesNotExist:
            return redirect("order-summary")
        
    def post(self,*args,**kwargs):
        form = CheckoutForm(self.request.POST or None)
        try:
            order = Order.objects.get(user= self.request.user,ordered = False)
            if form.is_valid():

                use_default_shipping =form.cleaned_data.get(
                    'use_default_shipping')
                if use_default_shipping:
                    
                    address_qs = Address.objects.filter(
                        user= self.request.user,
                        address_type='S',
                        default=True
                    )
                    if address_qs.exists():
                        shipping_address = address_qs[0]
                        order.shipping_address = shipping_address
                        order.save()
                    else:
                        messages.info(
                            self.request,"no default shipping address")
                        return redirect('core:checkout')
                else:
                    shipping_address1   =form.cleaned_data.get(
                        'shipping_address')
                    shipping_address2  =form.cleaned_data.get(
                        'shipping_address2')
                    shipping_country   =form.cleaned_data.get(
                        'shipping_country')
                    shipping_zip       =form.cleaned_data.get('shipping_zip')
                    if is_valid_form([shipping_address1,shipping_address2,shipping_country,shipping_zip]):
                        shipping_address = Address(
                            user=self.request.user,
                            street_address=shipping_address1,
                            apartment_address=shipping_address2,
                            country=shipping_country,
                            zip=shipping_zip,
                            address_type='S'
                        )
                        shipping_address.save()
                        
                        order.shipping_address = shipping_address
                        order.save()

                        set_default_shipping = form.cleaned_data.get('set_default_shipping')
                        if set_default_shipping:
                            shipping_addresses = Address.objects.filter(
                        user= self.request.user,
                        address_type='S',
                        default=True
                    )
                            shipping_addresses.update(default=False)
                            shipping_address.default= True
                            shipping_address.save()
                    else:
                        messages.info(self.request,"Plesae fill shipping address")
                
                use_default_billing =form.cleaned_data.get('use_default_billing')
                same_billing_address =form.cleaned_data.get('same_billing_address')
                
                if same_billing_address:
                    billing_address = shipping_address
                    billing_address.address_type = 'B'
                    billing_address.pk = None
                    billing_address.save()
                    order.billing_address = billing_address
                    order.save()
                elif use_default_billing:
                    address_qs = Address.objects.filter(user= self.request.user,address_type= 'B',default= True)
                    if address_qs.exists():
                        billing_address = address_qs[0]
                        order.billing_address = billing_address
                        order.save()
                    else:
                        messages.info(self.request,"No default billing address")
                        return redirect('core:checkout')
                else:

                    billing_address1    =form.cleaned_data.get('billing_address')
                    billing_address2   =form.cleaned_data.get('billing_address2')
                    billing_country    =form.cleaned_data.get('billing_country')
                    billing_zip=form.cleaned_data.get('billing_zip')
                    if is_valid_form([billing_address1, billing_country, billing_zip]):
                        billing_address = Address(
                            user=self.request.user,
                            street_address=billing_address1,
                            apartment_address=billing_address2,
                            country=billing_country,
                            zip=billing_zip,
                            address_type='B'
                        )
                        billing_address.save()
                        order.billing_address = billing_address
                        order.save()
                        
                        set_default_billing =form.cleaned_data.get('set_default_billing')
                        if set_default_billing:
                            all_billing_a = Address.objects.filter(user= self.request.user,address_type= 'B',default= True)
                            all_billing_a.update(default= False)
                            billing_address.default = True
                            billing_address.save()
                    else:
                        messages.info( self.request,"Fill billing address")
                
                payment_option =form.cleaned_data.get('payment_option')
                if payment_option == 'S':
                    return redirect('core:payment',payment_option='stripe')
                elif payment_option == 'P':
                    return redirect('core:payment',payment_option='paypal')
                else:
                    messages.warning(self.request,"Invalid payment option")
                    return redirect('core:checkout')
        except ObjectDoesNotExist:
            messages.warning(self.request,"You do not have an acrive order")
            return redirect('core:order-summary')
            


class PaymentView (View):
    def get(self, *args,**kwargs):
        order = Order.objects.get(user= self.request.user,ordered= False)
        if order.billing_address:
            context = {
                'order':order,
                'DISPLAY_COUPON_FORM':False
            }
            userprofile = self.request.user.userprofile
            if userprofile.one_click_purchasing:
                # fetch the users card list
                cards = stripe.Customer.list_sources(
                    userprofile.stripe_customer_id,
                    limit=3,
                    object='card'
                )
                card_list = cards['data']
                if len(card_list) > 0:
                    # update the context with the default card
                    context.update({
                        'card': card_list[0]
                    })
            return render(self.request,"payment.html",context) 
        else:
            messages.warning(self.request,"You need to provide a billing address")
            return redirect('core:checkout')
            
    
    def post(self,*args,**kwargs):
        order = Order.objects.get(user= self.request.user,ordered= False)
        form = PaymentForm(self.request.POST)
        userprofile = UserProfile.objects.get(user = self.request.user)

        if form.is_valid():
            token = form.cleaned_data.get('stripeToken')
            save = form.cleaned_data.get('save')
            use_default = form.cleaned_data.get('use_default')

            if save:
                if userprofile.stripe_customer_id != '' and userprofile.stripe_customer_id is not None:
                    customer = stripe.Customer.retrieve(userprofile.stripe_customer_id)
                    customer.sources.create(source= token)
                else:
                    customer = stripe.Customer.create(email= self.request.user.email)
                    customer.sources.create(source= token)
                    userprofile.stripe_customer_id = customer['id']
                    userprofile.one_click_purchasing = True
                    userprofile.save()
            amount= int( order.get_total() * 100)
        
            try:
                # Use Stripe's library to make requests...
                if use_default or save:
                    charge = stripe.Charge.create(
                        amount=amount,  # cents
                        currency="usd",
                        customer=userprofile.stripe_customer_id
                    )
                else:
                    # charge once off on the token
                    charge = stripe.Charge.create(
                        amount=amount,  # cents
                        currency="usd",
                        source=token
                    )
                    
                payment = Payment()
                payment.stripe_charge_id = charge['id']
                payment.user = self.request.user
                payment.amount = order.get_total()
                payment.save()

                order_items = order.items.all()
                order_items.update(ordered =True)
                for item in order_items:
                    item.save()

                order.ordered = True
                order.payment = payment
                #ref code
                order.ref_code = create_ref_code()
                order.save()

                messages.success(self.request,"Your order was successfull")
                return redirect("/")

            except stripe.error.CardError as e:
                # Since it's a decline, stripe.error.CardError will be caught
                messages.warning(self.request,f"{e.error.message}")
                return redirect("/")
                
            except stripe.error.RateLimitError as e:
                # Too many requests made to the API too quickly
                messages.warning(self.request,f"{e.error.message}")
                return redirect("/")
                
            except stripe.error.InvalidRequestError as e:
                # Invalid parameters were supplied to Stripe's API
                messages.warning(self.request,f"{e.error.message}")
                return redirect("/")
                
            except stripe.error.AuthenticationError as e:
                # Authentication with Stripe's API failed
                # (maybe you changed API keys recently)
                messages.warning(self.request,f"{e.error.message}")
                return redirect("/")
                
            except stripe.error.APIConnectionError as e:
                # Network communication with Stripe failed
                messages.warning(self.request,f"{e.error.message}")
                return redirect("/")
                
            except stripe.error.StripeError as e:
                # Display a very generic error to the user, and maybe send
                # yourself an email
                messages.error(self.request,f"{e.error.message}")
                return redirect("/")
            
            except Exception as e:
                # Something else happened, completely unrelated to Stripe
                messages.warning(self.request,"There is an error im our system, please be pacient")
                return redirect("/")
                        
        
class Search(ListView):
    model = Item
    paginate_by = 10
    template_name = "search.html"
    print("000")
    def get_context_data(self,**kwargs):
        context = super(Search,self).get_context_data(**kwargs)
        query = self.request.GET.get('q')
        context['sq'] = query
        sc = self.request.GET.get('category')
        context['sc'] = sc
        context['category'] = CATEGORY_CHOICES
        
        return context

    def get_queryset(self):
        query = self.request.GET.get('q')
        category = self.request.GET.get('category')
        print("cat",category)
        if category !="All" and query =='':
            object_list = Item.objects.filter(
                category__in=category
            )
        if category !="All" :
            object_list = Item.objects.filter(
                Q(title__icontains=query)|Q(description__icontains=query)
            )
            object_list = object_list.filter(
                category__in=category
            )
        else:
            object_list = Item.objects.filter(
                Q(title__icontains=query)|Q(description__icontains=query)
            )
        
            #object_list = object_list.filter(category=category)
        if not object_list:
            messages.warning(self.request,"No items match")
            
        return object_list


class HomeView (ListView):
    model = Item
    paginate_by = 10
    template_name ="home.html"
    def get_context_data(self,**kwargs):
        context = super(HomeView,self).get_context_data(**kwargs)
        context['category'] = CATEGORY_CHOICES
        
        return context

class OrderSummary(LoginRequiredMixin ,View):
    def get(self, *args , **kwargs):
        try:
            order = Order.objects.get(user= self.request.user, ordered = False)
            context = {
                'object': order
            }
        except ObjectDoesNotExist:
            messages.error(self.request,"You don't have any items in your cart")
            return redirect('/')
        return render(self.request,'order_summary.html',context)

class ItemDetailView (DetailView):
    model = Item
    template_name = "product.html"

@login_required
def add_to_cart(request,slug):
    item = get_object_or_404(Item,slug= slug)
    order_item, created = OrderItem.objects.get_or_create(
        item=item,
        user = request.user,
        ordered = False
        )
    order_qs = Order.objects.filter(user = request.user, ordered = False)
    if order_qs.exists():
        order = order_qs[0]
        # check if item is in the order
        if order.items.filter(item__slug = item.slug).exists():
            order_item.quantity +=1
            order_item.save()
            messages.info(request,"This item was updated")
            return redirect("core:order-summary")        
        else:
            messages.info(request,"This item was added to your cart")
            order.items.add(order_item)
    else:
        ordered_date = timezone.now()
        order = Order.objects.create(user = request.user,ordered_date=ordered_date)
        order.items.add(order_item)
        messages.info(request,"This item was added to your cart")
    return redirect("core:product",slug=slug)

@login_required
def remove_from_cart(request,slug):
    item = get_object_or_404(Item,slug= slug)
    order_qs = Order.objects.filter(user = request.user, ordered = False)
    if order_qs.exists():
        order = order_qs[0]
        # check if item is in the order
        if order.items.filter(item__slug = item.slug).exists():
            order_item = OrderItem.objects.filter(
                item=item,
                user = request.user,
                ordered = False
            )[0]
            order.items.remove(order_item)
            messages.info(request,"This item was removed from your cart")
            return redirect("core:product",slug=slug)        
        else:
            #add message no item in order
            messages.info(request,"This item was not in your cart")
            return redirect("core:product",slug = slug)
    else:
        #add message no  order
        messages.info(request,"You have not placed an order")
        return redirect("core:product",slug = slug)
    
@login_required
def remove_single_item_from_cart(request,slug):
    item = get_object_or_404(Item,slug= slug)
    order_qs = Order.objects.filter(user = request.user, ordered = False)
    if order_qs.exists():
        order = order_qs[0]
        # check if item is in the order
        if order.items.filter(item__slug = item.slug).exists():
            order_item = OrderItem.objects.filter(
                item=item,
                user = request.user,
                ordered = False
            )[0]
            if order_item.quantity >1:

                order_item.quantity -=1
                order_item.save()
            else:
                order.items.remove(order_item)
            
            messages.info(request,"This items quantity was reduced your cart")
            return redirect("core:order-summary")        
        else:
            #add message no item in order
            messages.info(request,"This item was not in your cart")
            return redirect("core:order-summary")
    else:
        #add message no  order
        messages.info(request,"You have not placed an order")
        return redirect("core:order-summary")

def get_coupon(request,code):
    try:
        coupon = Coupon.objects.get(code=code)
        return coupon
    except ObjectDoesNotExist:
        messages.info(request,"Coupon does not exist")
        return redirect("core:checkout")
    

class AddCouponView(View):
    def post(self, *args, **kwargs):
        form = CouponForm(self.request.POST or None)
        if form.is_valid():
            try:
                code = form.cleaned_data.get('code')
                order = Order.objects.get(user = self.request.user, ordered = False)
                coupon = get_coupon(self.request,code)
                order.coupon = coupon
                order.save()
                messages.success(self.request,"Coupon aplied")
                return redirect("core:checkout")
            
            except ObjectDoesNotExist:
                messages.info(self.request,"You have not placed an order")
                return redirect("core:order-summary")


class RequestRefundView (View):
    def get(self, *args, **kwargs):
        form = RefundForm()
        context = {
            'form':form
        }
        return render(self.request,"request-refund.html",context)
    def post(self, *args, **kwargs):
        form = RefundForm(self.request.POST or None)
        if form.is_valid():
            ref_code = form.cleaned_data.get('ref_code')
            message = form.cleaned_data.get('message')
            email = form.cleaned_data.get('email')
            try:
                order = Order.objects.get(ref_code = ref_code)
                order.refund_requested = True
                order.save()

                refund = Refund()
                refund.order= order
                refund.reason = message
                refund.email = email
                refund.save()

                messages.info(self.request,"Request received. Please wait for our e-mail")
                return redirect("/")
            except ObjectDoesNotExist:
                messages.info(self.request,"This order does not exist")
                return redirect("core:request-refund")
            