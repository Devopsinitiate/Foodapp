"""
Forms for vendor application and management.
"""
from django import forms
from .models import VendorProfile
from restaurants.models import Restaurant, MenuItem, Category


class VendorApplicationForm(forms.ModelForm):
    """
    Form for vendor application.
    """
    terms_accepted = forms.BooleanField(
        required=True,
        label='I agree to the Terms of Service and Vendor Agreement'
    )
    
    class Meta:
        model = VendorProfile
        fields = [
            'business_name',
            'business_type',
            'business_registration_number',
            'bank_account_name',
            'bank_account_number',
            'bank_name',
            'years_of_experience',
            'description',
            'business_license',
            'health_certificate',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add CSS classes for styling
        for field_name, field in self.fields.items():
            if field_name != 'terms_accepted':
                field.widget.attrs['class'] = 'form-input w-full rounded-lg border-gray-300 dark:border-gray-600 bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-white focus:border-primary focus:ring-primary'


class RestaurantForm(forms.ModelForm):
    """
    Form for creating/editing restaurants.
    """
    class Meta:
        model = Restaurant
        fields = [
            'name',
            'description',
            'logo',
            'cover_image',
            'phone_number',
            'email',
            'street_address',
            'city',
            'state',
            'postal_code',
            'categories',
            'cuisine_type',
            'delivery_fee',
            'minimum_order',
            'estimated_delivery_time',
            'delivery_radius',
            'is_accepting_orders',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'categories': forms.CheckboxSelectMultiple(),
        }


class MenuItemForm(forms.ModelForm):
    """
    Form for creating/editing menu items.
    """
    class Meta:
        model = MenuItem
        fields = [
            'restaurant',
            'name',
            'description',
            'image',
            'category',
            'price',
            'discounted_price',
            'preparation_time',
            'calories',
            'is_vegetarian',
            'is_vegan',
            'is_gluten_free',
            'spice_level',
            'is_available',
            'is_featured',
            'stock_quantity',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }
