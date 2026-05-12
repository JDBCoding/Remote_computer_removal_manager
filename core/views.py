import logging

logger = logging.getLogger(__name__)
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.db.models import Case, When, Value, IntegerField
from .models import Part, InstallationRequirement, PlanningRequest, PlanningRequestItem
from .forms import (
    PartForm,
    InstallationRequirementForm,
    PlanningRequestForm,
    PlanningRequestItemFormSet,
    InstallationRequirementCreateForm,
)

logger = logging.getLogger(__name__)

from django.forms.models import inlineformset_factory

# from django.forms import modelformset_factory
from .forms import UnifiedRemovalForm
from django.http import HttpResponseBadRequest, HttpResponse


InstallationRequirementFormSet = inlineformset_factory(
    Part,
    InstallationRequirement,
    form=InstallationRequirementForm,
    extra=1,
    can_delete=True,
)


def home(request):
    total_parts = Part.objects.count()
    parts = Part.objects.sorted_for_planning()
    selected_part = None
    requirements = []
    part_number = request.GET.get("part_number")
    if part_number:
        selected_part = get_object_or_404(Part, part_number=part_number)
        requirements = selected_part.requirements.all()
    return render(
        request,
        "core/home.html",
        {
            "parts": parts,
            "selected_part": selected_part,
            "requirements": requirements,
            "total_parts": total_parts,
        },
    )


def how_to_use(request):
    return render(request, "core/how_to_use.html")


def add_part(request):
    if request.method == "POST":
        part_form = PartForm(request.POST)
        if part_form.is_valid():
            part = part_form.save(commit=False)  # don't save yet
            formset = InstallationRequirementFormSet(request.POST, instance=part)
            if formset.is_valid():
                part.save()  # now we can save the part
                formset.save()
                return redirect("home")
            else:
                logger.warning("Formset Errors: %s", formset.errors)
                logger.warning("Formset Non-Form Errors: %s", formset.non_form_errors())
        else:
            formset = InstallationRequirementFormSet(
                request.POST
            )  # fallback for rendering
            logger.warning("Part Form Errors: %s", part_form.errors)
            logger.warning(
                "Part Form Non-Field Errors: %s", part_form.non_field_errors()
            )
    else:
        part_form = PartForm()
        formset = InstallationRequirementFormSet()
    return render(
        request,
        "core/part_form.html",
        {"part_form": part_form, "formset": formset, "action": "Create"},
    )


def edit_part(request, pk):
    part = get_object_or_404(Part, pk=pk)
    if request.method == "POST":
        part_form = PartForm(request.POST, instance=part)
        formset = InstallationRequirementFormSet(
            request.POST, instance=part, prefix="form"
        )
        if part_form.is_valid() and formset.is_valid():
            part = part_form.save()
            formset.save()
            return redirect(f"/?part_number={part.part_number}")
        else:
            logger.warning("Part Form Errors: %s", part_form.errors)
            logger.warning("Formset Errors: %s", formset.errors)
    else:
        part_form = PartForm(instance=part)
        formset = InstallationRequirementFormSet(instance=part, prefix="form")
    return render(
        request,
        "core/part_form.html",
        {"part_form": part_form, "formset": formset, "action": "Save", "part": part},
    )


def delete_part(request, pk):
    part = get_object_or_404(Part, pk=pk)
    if request.method == "POST":
        part.delete()
        return redirect("home")
    return render(request, "core/part_delete.html", {"part": part})


def add_requirement(request, pk):
    part = get_object_or_404(Part, pk=pk)

    if request.method == "POST":
        formset = InstallationRequirementFormSet(
            request.POST, queryset=InstallationRequirement.objects.filter(part=part)
        )
        if formset.is_valid():
            requirements = formset.save(commit=False)
            for requirement in requirements:
                requirement.part = part  # Associate the requirement with the part
                requirement.save()
            return redirect("home")  # Redirect to home or another appropriate page
    else:
        formset = InstallationRequirementFormSet(
            queryset=InstallationRequirement.objects.filter(part=part)
        )

    return render(
        request,
        "core/requirement_form.html",
        {
            "formset": formset,
            "part": part,
        },
    )


def edit_requirements(request, part_number):
    part = get_object_or_404(Part, pk=part_number)
    delete_param = request.GET.get("delete")
    logger.info("🧪 Raw delete param:", delete_param)
    if delete_param:
        req_id = int(delete_param)
        logger.info(
            f"🔥 DELETE TRIGGERED: req_id=%s, part=%s", req_id, part.part_number
        )
        match = InstallationRequirement.objects.filter(id=req_id, part=part)
        logger.info(f"🔍 Matching objects: %s", match.count())
        for obj in match:
            logger.info(
                "Found requirement: %s | notes=%s", obj.requirement_type, obj.note
            )
        deleted, _ = match.delete()
        logger.info("Deleted count: %s", deleted)
        return redirect("edit_requirements", part_number=part.part_number)
    if request.method == "POST":
        form = InstallationRequirementCreateForm(request.POST)
        if form.is_valid():
            req = form.save(commit=False)
            req.part = part
            req.save()
            return redirect("edit_requirements", part_number=part.part_number)
    else:
        form = InstallationRequirementCreateForm()
    requirements = InstallationRequirement.objects.filter(part=part)
    return render(
        request,
        "core/edit_requirements.html",
        {"part": part, "requirements": requirements, "form": form},
    )


def requirement_edit(request, pk):
    req = get_object_or_404(InstallationRequirement, pk=pk)
    part = req.part
    if request.method == "POST":
        form = InstallationRequirementCreateForm(request.POST, instance=req)
        if form.is_valid():
            form.save()
            return redirect("edit_requirements", part_number=part.part_number)
    else:
        form = InstallationRequirementCreateForm(instance=req)
    return render(
        request,
        "core/requirement_edit.html",
        {
            "form": form,
            "requirement": req,  # ← THIS LINE
        },
    )


def planning_request_create(request):
    parts = Part.objects.sorted_for_planning()
    if request.method == "POST":
        job_number = (request.POST.get("job_number") or "").strip()
        notes = (request.POST.get("notes") or "").strip()
        selected_part_ids = request.POST.getlist("parts")
        selected_parts = Part.objects.filter(id__in=selected_part_ids)
        # Preserve the checkbox order as the user selected them
        # (Django won't guarantee IN() ordering)
        selected_parts_by_id = {str(p.id): p for p in selected_parts}
        ordered_selected_parts = [
            selected_parts_by_id[pid]
            for pid in selected_part_ids
            if pid in selected_parts_by_id
        ]
        planning_message_lines = []
        planning_message_lines.append(f"Job Number: {job_number}")
        if notes:
            planning_message_lines.append(f"Notes: {notes}")
        planning_message_lines.append("")
        for part in ordered_selected_parts:
            op = (request.POST.get(f"op_{part.id}") or "").strip()
            planning_message_lines.append(f"OP: {op}")
            planning_message_lines.append(f"Part: {part.part_number}")
            planning_message_lines.append(
                f"DWG: {part.dwg} | SHT: {part.sht} | REV: {part.rev}"
            )
            planning_message_lines.append(
                "Planning please add the following data collect/s:"
            )
            requirements = part.requirements.all()
            if requirements.exists():
                for req in requirements:
                    line = f"- {req.requirement_type}"
                    if req.note:
                        line += f" - {req.note}"
                    planning_message_lines.append(line)
            else:
                planning_message_lines.append("- (No requirements listed)")
            planning_message_lines.append("")  # blank line between parts
        planning_message = "\n".join(planning_message_lines).strip()
        # Used for the mailto subject
        email_subject = f"Planning Request - Job {job_number}".strip()

        return render(
            request,
            "core/planning_message_result.html",
            {
                "planning_message": planning_message,
                "email_subject": email_subject,
            },
        )

    # GET
    return render(request, "core/planning_request_form.html", {"parts": parts})


def planning_request_detail(request, pk):
    # Get the planning request by primary key (pk)
    request_obj = get_object_or_404(PlanningRequest, pk=pk)

    # Get all parts associated with this planning request
    parts = request_obj.parts.all()

    return render(
        request,
        "core/planning_request_detail.html",
        {
            "request_obj": request_obj,
            "parts": parts,
        },
    )


def create_planning_request(request):
    if request.method == "POST":
        request_form = PlanningRequestForm(request.POST)
        formset = PlanningRequestItemFormSet(request.POST)
        if request_form.is_valid() and formset.is_valid():
            planning_request = request_form.save()
            items = formset.save(commit=False)
            for item in items:
                item.planning_request = planning_request
                item.save()
            return redirect("planning_request_success")  # redirect to confirmation page
    else:
        request_form = PlanningRequestForm()
        formset = PlanningRequestItemFormSet(
            queryset=PlanningRequestItem.objects.none()
        )
        parts = Part.objects.all().order_by("-part_number")

    return render(
        request,
        "create_planning_request.html",
        {
            "request_form": request_form,
            "formset": formset,
            "parts": parts,
        },
    )


def generate_planning_message(request):
    if request.method == "POST":
        job_number = request.POST.get("job_number")
        notes = request.POST.get("notes")
        op_fields = {
            key: value for key, value in request.POST.items() if key.startswith("op_")
        }
        part_numbers = [key.replace("op_", "") for key in op_fields]
        parts = Part.objects.filter(part_number__in=part_numbers)
        lines = []
        lines.append(f"Job Number: {job_number}")
        lines.append(f"Notes: {notes}")
        lines.append("")
        for part in parts:
            op = op_fields.get(f"op_{part.part_number}", "")
            lines.append(f"OP: {op}")
            lines.append(f"Part: {part.part_number}")
            lines.append(f"  DWG: {part.dwg} | SHT: {part.sht} | REV: {part.rev}")
            lines.append("  Planning please add the following data collect/s:")
            reqs = part.requirements.all()
            if reqs:
                for req in reqs:
                    line = f"    - {req.requirement_type}"
                    if req.note:
                        line += f" — {req.note}"
                    lines.append(line)
            else:
                lines.append("    - None")
            lines.append("")  # blank line between parts
        message = "\n".join(lines)
        return render(
            request, "core/planning_message_result.html", {"message": message}
        )
