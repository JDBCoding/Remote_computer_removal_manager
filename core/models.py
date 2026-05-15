import uuid
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db.models import Case, When, IntegerField, Value, F, CharField


INSTALLATION_REQUIREMENTS = [
    ("TORQUE", "TORQUE"),
    ("SEAL", "SEAL"),
    ("BOND", "BOND"),
    ("HIRF", "HIRF"),
    ("FINISH", "FINISH"),
    ("RETEST", "RETEST"),
    ("DCMA", "DCMA"),
    ("OTHER", "OTHER")
    
]


class PartQuerySet(models.QuerySet):
   def sorted_for_planning(self):
       return (
           self.annotate(
               starts_with_number=Case(
                   When(part_number__regex=r'^[0-9]', then=Value(0)),  # numbers first
                   default=Value(1),  # letters second
                   output_field=IntegerField(),
               )
           )
           .annotate(
               number_sort=Case(
                   When(part_number__regex=r'^[0-9]', then=F("part_number")),
                   default=Value(""),
                   output_field=CharField(),
               )
           )
           .annotate(
               letter_sort=Case(
                   When(part_number__regex=r'^[A-Za-z]', then=F("part_number")),
                   default=Value(""),
                   output_field=CharField(),
               )
           )
           .order_by(
               "starts_with_number",   # numbers first
               "-number_sort",         # numbers HIGH -> LOW
               "letter_sort",          # letters A -> Z
           )
       )


class Part(models.Model):
    objects = PartQuerySet.as_manager()
    id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    part_number = models.CharField(max_length=15, primary_key=True)
    description = models.TextField(max_length=60, blank=False)
    sta = models.CharField(max_length=4, blank=False)
    bl = models.CharField(max_length=4, blank=False)
    wl = models.CharField(max_length=5, blank=False)
    dwg = models.CharField(max_length=20, blank=False)
    sht = models.CharField(max_length=4, blank=False)
    rev = models.CharField(max_length=3, blank=False)
    notes = models.TextField(blank=True)

    def __str__(self):
        return self.part_number

    def save(self, *args, **kwargs):
        # Normalize key fields to uppercase on every save
        uppercase_fields = [
            "part_number",
            "description",
            "sta",
            "bl",
            "wl",
            "dwg",
            "sht",
            "rev",
        ]
        for field in uppercase_fields:
            value = getattr(self, field, None)
            if isinstance(value, str) and value:
                setattr(self, field, value.strip().upper())
        super().save(*args, **kwargs)

    def save(self, *args, **kwargs):
       # Normalize key fields to uppercase on every save
       uppercase_fields = [
           "part_number",
           "description",
           "sta",
           "bl",
           "wl",
           "dwg",
           "sht",
           "rev",
       ]
       for field in uppercase_fields:
           value = getattr(self, field, None)
           if isinstance(value, str) and value:
               setattr(self, field, value.strip().upper())
       super().save(*args, **kwargs)
       self.ensure_default_installation()
       
    def ensure_default_installation(self):
       installation, created = PartInstallation.objects.get_or_create(
           part=self,
           name="DEFAULT",
           defaults={
               "sta": self.sta or "",
               "bl": self.bl or "",
               "wl": self.wl or "",
           }
       )
       if self.dwg:
           DrawingReference.objects.get_or_create(
               installation=installation,
               dwg=self.dwg,
               sht=self.sht or "",
               rev=self.rev or "",
           )
       return installation

class PartInstallation(models.Model):
   part = models.ForeignKey(
       Part,
       on_delete=models.CASCADE,
       related_name='installations'
   )
   name = models.CharField(
       max_length=100,
       blank=True,
       default='DEFAULT'
   )
   sta = models.CharField(max_length=20, blank=True)
   bl = models.CharField(max_length=20, blank=True)
   wl = models.CharField(max_length=20, blank=True)
   notes = models.TextField(blank=True)
   created_at = models.DateTimeField(auto_now_add=True)
   def __str__(self):
       return f"{self.part.part_number} - {self.name}"

   
class DrawingReference(models.Model):
   installation = models.ForeignKey(
       PartInstallation,
       on_delete=models.CASCADE,
       related_name='drawing_refs'
   )
   dwg = models.CharField(max_length=50)
   sht = models.CharField(max_length=20, blank=True)
   rev = models.CharField(max_length=20, blank=True)
   note = models.CharField(max_length=255, blank=True)
   def __str__(self):
       return f"{self.dwg} | SHT {self.sht} | REV {self.rev}"

class InstallationRequirement(models.Model):
    part = models.ForeignKey(
        Part, on_delete=models.CASCADE, related_name="requirements"
    )
    requirement_type = models.CharField(
        max_length=10, choices=INSTALLATION_REQUIREMENTS
    )
    note = models.TextField(blank=True)  # <-- Add this

    def __str__(self):
        return f"{self.part.part_number} - {self.requirement_type}"


class PlanningRequest(models.Model):
    job_number = models.CharField(
        max_length=10,
        blank=True,
        help_text="User-entered job number to help planning identify the job.",
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    parts = models.ManyToManyField(Part)


class PlanningRequestItem(models.Model):
    planning_request = models.ForeignKey(
        PlanningRequest, on_delete=models.CASCADE, related_name="items"
    )
    part = models.ForeignKey(Part, on_delete=models.CASCADE)
    operation = models.CharField(max_length=10)  # User provided

    def __str__(self):
        return f"WO {self.planning_request.job_number} - Op {self.operation} - Part {self.part.part_number}"
