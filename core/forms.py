from django import forms
from .models import Part, InstallationRequirement, PlanningRequestItem, PlanningRequest
from django.forms import modelformset_factory, inlineformset_factory


class PartForm(forms.ModelForm):
    class Meta:
        model = Part
        fields = "__all__"
        widgets = {
            "part_number": forms.TextInput(attrs={"class": "form-control"}),
            # Set rows to 1
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 1}),
            "sta": forms.TextInput(attrs={"class": "form-control"}),
            "bl": forms.TextInput(attrs={"class": "form-control"}),
            "wl": forms.TextInput(attrs={"class": "form-control"}),
            "dwg": forms.TextInput(attrs={"class": "form-control"}),
            "sht": forms.TextInput(attrs={"class": "form-control"}),
            "rev": forms.TextInput(attrs={"class": "form-control"}),
            # Set rows to 3
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }


class InstallationRequirementForm(forms.ModelForm):
   class Meta:
       model = InstallationRequirement
       fields = ["requirement_type", "note"]
       widgets = {
           "requirement_type": forms.Select(attrs={"class": "form-select"}),
           "note": forms.Textarea(attrs={"class": "form-control", "rows": 2}),  # ← reduce rows here
       }


class InstallationRequirementCreateForm(forms.ModelForm):
    class Meta:
        model = InstallationRequirement
        fields = ["requirement_type", "note"]


# Create a formset for InstallationRequirement
InstallationRequirementFormSet = inlineformset_factory(
   Part,
   InstallationRequirement,
   form=InstallationRequirementForm,
   extra=1,
   can_delete=True
)


class PlanningRequestForm(forms.ModelForm):
    class Meta:
        model = PlanningRequest
        fields = ["job_number"]


class PlanningRequestItemForm(forms.ModelForm):
    class Meta:
        model = PlanningRequestItem
        fields = ["part", "operation"]


PlanningRequestItemFormSet = modelformset_factory(
    PlanningRequestItem,
    fields=("part", "operation"),
    extra=3,  # show 3 items by default; adjust as needed
)

class UnifiedRemovalForm(forms.Form):
    LOG_TYPE_CHOICES = [
        ('AP', 'Airplane'),
        ('BOOM', 'BOOM')
    ]
    widget=forms.HiddenInput()

    log_type = forms.ChoiceField(choices=LOG_TYPE_CHOICES)
    ncr_number = forms.CharField(max_length=50)
    job_number = forms.CharField(max_length=50)
    log_operation = forms.CharField(max_length=100)
    part_number = forms.ModelChoiceField(
        queryset=Part.objects.all(), label="Part Number", widget=forms.Select(attrs={
            'id': 'id_part_number',
            'class': 'form-select'
            }),
    )
    description = forms.CharField(widget=forms.TextInput(attrs={
        'id': 'id_description',
        'readonly': 'readonly',
        'class': 'form-control'
        }),
    )
    comments = forms.CharField(widget=forms.Textarea, required=False)
    is_closed = forms.BooleanField(required=False)


