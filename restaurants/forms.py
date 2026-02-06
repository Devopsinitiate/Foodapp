from django import forms
from .models import Review


class ReviewForm(forms.ModelForm):
    """Form for submitting restaurant reviews."""
    
    rating = forms.TypedChoiceField(
        choices=[(i, f'{i} Star{"s" if i > 1 else ""}') for i in range(1, 6)],
        coerce=int,
        widget=forms.RadioSelect(attrs={'class': 'star-rating-input'}),
        label='Your Rating'
    )
    
    class Meta:
        model = Review
        fields = ['rating', 'comment']
        widgets = {
            'comment': forms.Textarea(
                attrs={
                    'rows': 5,
                    'class': 'w-full px-4 py-3 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-primary/50 focus:border-primary',
                    'placeholder': 'Share your experience with this restaurant...'
                }
            ),
        }
        labels = {
            'rating': 'Your Rating',
            'comment': 'Your Review',
        }
    
    def clean_rating(self):
        rating = self.cleaned_data.get('rating')
        if rating < 1 or rating > 5:
            raise forms.ValidationError('Rating must be between 1 and 5 stars.')
        return rating
    
    def clean_comment(self):
        comment = self.cleaned_data.get('comment')
        if len(comment) < 10:
            raise forms.ValidationError('Review must be at least 10 characters long.')
        return comment


class VendorResponseForm(forms.ModelForm):
    """Form for vendors to respond to reviews."""
    
    class Meta:
        model = Review
        fields = ['vendor_response']
        widgets = {
            'vendor_response': forms.Textarea(
                attrs={
                    'rows': 3,
                    'class': 'w-full px-4 py-3 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-primary/50',
                    'placeholder': 'Thank your customer or address their feedback...'
                }
            ),
        }
        labels = {
            'vendor_response': 'Your Response',
        }


class VendorCouponForm(forms.ModelForm):
    """Form for vendors to create restaurant-specific coupons."""
    
    class Meta:
        from orders.models import Coupon
        model = Coupon
        fields = [
            'code', 'description',
            'discount_type', 'discount_value',
            'max_discount_amount',
            'min_order_amount',
            'max_total_uses', 'max_uses_per_user',
            'first_order_only',
            'valid_from', 'valid_until'
        ]
        widgets = {
            'code': forms.TextInput(attrs={
                'class': 'form-input w-full px-4 py-3 rounded-lg border',
                'placeholder': 'e.g., SAVE20',
                'style': 'text-transform: uppercase;'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-input w-full px-4 py-3 rounded-lg border',
                'rows': 3
            }),
            'discount_type': forms.Select(attrs={'class': 'form-select w-full px-4 py-3 rounded-lg border'}),
            'discount_value': forms.NumberInput(attrs={'class': 'form-input w-full', 'step': '0.01', 'min': '0'}),
            'max_discount_amount': forms.NumberInput(attrs={'class': 'form-input w-full', 'step': '0.01'}),
            'min_order_amount': forms.NumberInput(attrs={'class': 'form-input w-full', 'step': '0.01', 'value': '0'}),
            'max_total_uses': forms.NumberInput(attrs={'class': 'form-input w-full', 'min': '1'}),
            'max_uses_per_user': forms.NumberInput(attrs={'class': 'form-input w-full', 'min': '1', 'value': '1'}),
            'first_order_only': forms.CheckboxInput(attrs={'class': 'form-checkbox h-5 w-5'}),
            'valid_from': forms.DateTimeInput(attrs={'class': 'form-input w-full', 'type': 'datetime-local'}),
            'valid_until': forms.DateTimeInput(attrs={'class': 'form-input w-full', 'type': 'datetime-local'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.restaurant = kwargs.pop('restaurant', None)
        super().__init__(*args, **kwargs)
    
    def clean_code(self):
        from orders.models import Coupon
        code = self.cleaned_data.get('code', '').upper().strip()
        
        if self.instance.pk:
            if Coupon.objects.filter(code=code).exclude(pk=self.instance.pk).exists():
                raise forms.ValidationError('This coupon code already exists.')
        else:
            if Coupon.objects.filter(code=code).exists():
                raise forms.ValidationError('This coupon code already exists.')
        
        return code
    
    def clean_discount_value(self):
        discount_type = self.cleaned_data.get('discount_type')
        discount_value = self.cleaned_data.get('discount_value')
        
        if discount_type == 'percentage' and discount_value > 100:
            raise forms.ValidationError('Percentage cannot exceed 100%.')
        if discount_value <= 0:
            raise forms.ValidationError('Value must be greater than 0.')
        
        return discount_value
    
    def clean(self):
        cleaned_data = super().clean()
        valid_from = cleaned_data.get('valid_from')
        valid_until = cleaned_data.get('valid_until')
        
        if valid_from and valid_until and valid_from >= valid_until:
            raise forms.ValidationError('Valid Until must be after Valid From.')
        
        return cleaned_data
