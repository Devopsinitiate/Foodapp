"""
Driver registration forms for onboarding new drivers.
"""
from django import forms
from django.contrib.auth.forms import UserCreationForm
from users.models import User


class DriverRegistrationForm(UserCreationForm):
    """Form for driver registration with vehicle and license information."""
    
    # Personal Information
    first_name = forms.CharField(max_length=150, required=True)
    last_name = forms.CharField(max_length=150, required=True)
    email = forms.EmailField(required=True)
    phone_number = forms.CharField(max_length=17, required=True)
    
    # Address
    street_address = forms.CharField(max_length=255, required=True)
    city = forms.CharField(max_length=100, required=True)
    state = forms.CharField(max_length=100, required=True)
    postal_code = forms.CharField(max_length=20, required=True)
    
    # Driver License
    driver_license_number = forms.CharField(max_length=50, required=True)
    driver_license_expiry = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        required=True
    )
    
    # Vehicle Information
    vehicle_type = forms.ChoiceField(
        choices=[
            ('bike', 'Motorcycle'),
            ('bicycle', 'Bicycle'),
            ('car', 'Car'),
            ('scooter', 'Scooter'),
        ],
        required=True
    )
    vehicle_plate = forms.CharField(max_length=20, required=True)
    vehicle_insurance_expiry = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        required=True
    )
    
    # Agreement
    agree_to_terms = forms.BooleanField(
        required=True,
        label='I agree to the driver terms and conditions'
    )
    
    class Meta:
        model = User
        fields = [
            'username', 'email', 'password1', 'password2',
            'first_name', 'last_name', 'phone_number',
            'street_address', 'city', 'state', 'postal_code',
            'driver_license_number', 'driver_license_expiry',
            'vehicle_type', 'vehicle_plate', 'vehicle_insurance_expiry'
        ]
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.user_type = 'driver'
        user.driver_documents_uploaded = False  # Will be updated after document upload
        user.is_verified_driver = False  # Requires admin approval
        
        if commit:
            user.save()
        return user


class DriverDocumentUploadForm(forms.Form):
    """Form for uploading driver verification documents."""
    
    driver_license_photo = forms.ImageField(
        required=True,
        label='Driver License Photo',
        help_text='Clear photo of your driver license'
    )
    vehicle_registration = forms.ImageField(
        required=True,
        label='Vehicle Registration',
        help_text='Vehicle registration document'
    )
    insurance_certificate = forms.ImageField(
        required=True,
        label='Insurance Certificate',
        help_text='Valid insurance certificate'
    )
    profile_photo = forms.ImageField(
        required=False,
        label='Profile Photo',
        help_text='Your profile photo (optional)'
    )
