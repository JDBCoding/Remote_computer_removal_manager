import logging

logger = logging.getLogger(__name__)
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.db.models import Case, When, Value, IntegerField
from .models import (
    Part,
    PartInstallation,
    DrawingReference,
    InstallationRequirement,
    PlanningRequest,
    PlanningRequestItem,
)
from .forms import (
    PartForm,
    PartInstallationFormSet,
    PartInstallationCreateFormSet,
    DrawingReferenceFormSet,
    InstallationRequirementForm,
    PlanningRequestForm,
    PlanningRequestItemFormSet,
    InstallationRequirementCreateForm,
    PrimaryDrawingReferenceForm,
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
    installations = []
    part_number = request.GET.get("part_number")
    if part_number:
        selected_part = get_object_or_404(Part, part_number=part_number)
        requirements = selected_part.requirements.all()
        installations = selected_part.installations.prefetch_related(
            "drawing_refs"
        ).order_by("id")
    return render(
        request,
        "core/home.html",
        {
            "parts": parts,
            "selected_part": selected_part,
            "requirements": requirements,
            "installations": installations,
            "total_parts": total_parts,
        },
    )


def how_to_use(request):
    return render(request, "core/how_to_use.html")


def add_part(request):
    if request.method == "POST":
        submitted_part_number = request.POST.get("part_number", "").strip().upper()
        existing_part = None
        if submitted_part_number:
            existing_part = Part.objects.filter(
                part_number=submitted_part_number
            ).first()
        if existing_part:
            return render(
                request,
                "core/part_exists.html",
                {
                    "part": existing_part,
                },
            )
        part_form = PartForm(request.POST)
        formsset = InstallationRequirementFormSet(request.POST, prefix="form")
        if part_form.is_valid() and formsset.is_valid():
            part = part_form.save()
            location_count = int(request.POST.get("location_count", "1") or "1")
            default_installation = part.ensure_default_installation()
            for location_index in range(location_count):
                location_name = request.POST.get(
                    f"location_{location_index}_name", ""
                ).strip()
                sta = request.POST.get(f"location_{location_index}_sta", "").strip()
                bl = request.POST.get(f"location_{location_index}_bl", "").strip()
                wl = request.POST.get(f"location_{location_index}_wl", "").strip()
                notes = request.POST.get(f"location_{location_index}_notes", "").strip()
                if location_index == 0:
                    installation = default_installation
                    installation.name = location_name or "DEFAULT"
                    installation.sta = sta
                    installation.bl = bl
                    installation.wl = wl
                    installation.notes = notes
                    installation.save()
                else:
                    installation = PartInstallation.objects.create(
                        part=part,
                        name=location_name or f"LOCATION {location_index + 1}",
                        sta=sta,
                        bl=bl,
                        wl=wl,
                        notes=notes,
                    )
                dwg_count = int(
                    request.POST.get(f"location_{location_index}_dwg_count", "1") or "1"
                )
                for dwg_index in range(dwg_count):
                    dwg = request.POST.get(
                        f"location_{location_index}_dwg_{dwg_index}", ""
                    ).strip()
                    sht = request.POST.get(
                        f"location_{location_index}_sht_{dwg_index}", ""
                    ).strip()
                    rev = request.POST.get(
                        f"location_{location_index}_rev_{dwg_index}", ""
                    ).strip()
                    note = request.POST.get(
                        f"location_{location_index}_dwg_note_{dwg_index}", ""
                    ).strip()
                    if dwg:
                        DrawingReference.objects.create(
                            installation=installation,
                            dwg=dwg,
                            sht=sht,
                            rev=rev,
                            note=note,
                        )
            formsset.instance = part
            formsset.save()
            return redirect(f"/?part_number={part.part_number}")
        else:
            logger.warning("Part Form Errors: %s", part_form.errors)
            logger.warning("Requirement Formset Errors: %s", formsset.errors)
    else:
        part_form = PartForm()
        formsset = InstallationRequirementFormSet(prefix="form")
    return render(
        request,
        "core/part_form.html",
        {
            "part_form": part_form,
            "formset": formsset,
            "installation_formset": None,
            "drawing_formsets": [],
            "primary_drawing_form": None,
            "action": "Create",
            "show_location_name": False,
        },
    )


def edit_part(request, pk):
    part = get_object_or_404(Part, pk=pk)
    if request.method == "POST":
        part_form = PartForm(request.POST, instance=part)
        formsset = InstallationRequirementFormSet(
            request.POST, instance=part, prefix="form"
        )
        installation_formset = PartInstallationFormSet(
            request.POST, instance=part, prefix="install"
        )
        installations_valid = installation_formset.is_valid()
        drawing_formsets = []
        if installations_valid:
            for install_form in installation_formset.forms:
                installation_instance = install_form.instance
                drawing_formset = DrawingReferenceFormSet(
                    request.POST,
                    instance=installation_instance,
                    prefix=f"dwg-{install_form.prefix}",
                )
                drawing_formsets.append(drawing_formset)
        drawing_valid = all(fs.is_valid() for fs in drawing_formsets)
        if (
            part_form.is_valid()
            and formsset.is_valid()
            and installations_valid
            and drawing_valid
        ):
            part = part_form.save()
            formsset.save()
            installation_formset.save()
            for drawing_formset in drawing_formsets:
                drawing_formset.save()
            return redirect(f"/?part_number={part.part_number}")
        else:
            logger.warning("Part Form Errors: %s", part_form.errors)
            logger.warning("Requirement Formset Errors: %s", formsset.errors)
            logger.warning(
                "Installation Formset Errors: %s", installation_formset.errors
            )
            for drawing_formset in drawing_formsets:
                logger.warning("Drawing Formset Errors: %s", drawing_formset.errors)
    else:
        part_form = PartForm(instance=part)
        formsset = InstallationRequirementFormSet(instance=part, prefix="form")
        installation_formset = PartInstallationFormSet(instance=part, prefix="install")
        drawing_formsets = []
        for install_form in installation_formset.forms:
            drawing_formsets.append(
                (
                    install_form.instance.pk,
                    DrawingReferenceFormSet(
                        instance=install_form.instance,
                        prefix=f"dwg-{install_form.prefix}",
                    ),
                )
            )
    return render(
        request,
        "core/part_form.html",
        {
            "part_form": part_form,
            "formset": formsset,
            "installation_formset": installation_formset,
            "drawing_formsets": drawing_formsets,
            "action": "Save",
            "part": part,
            "show_location_name": part.installations.count() > 1,
        },
    )


def add_install_location(request, pk):
    part = get_object_or_404(Part, pk=pk)
    location_count = part.installations.count() + 1
    PartInstallation.objects.create(
        part=part, name=f"LOCATION {location_count}", sta="", bl="", wl="", notes=""
    )
    return redirect("edit_part", pk=part.pk)


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

    parts = Part.objects.sorted_for_planning().prefetch_related(
        "installations",
        "installations__drawing_refs",
        "requirements",
    )

    if request.method == "POST":

        job_number = (request.POST.get("job_number") or "").strip()

        notes = (request.POST.get("notes") or "").strip()

        selected_installation_ids = request.POST.getlist("installations")

        installations = (
            PartInstallation.objects.filter(id__in=selected_installation_ids)
            .select_related("part")
            .prefetch_related(
                "drawing_refs",
                "part__requirements",
            )
        )

        installations_by_id = {
            str(installation.id): installation for installation in installations
        }

        ordered_installations = [
            installations_by_id[installation_id]
            for installation_id in selected_installation_ids
            if installation_id in installations_by_id
        ]

        planning_message_lines = []

        if job_number:

            planning_message_lines.append(f"Job Number: {job_number}")

        if notes:

            planning_message_lines.append(f"Notes: {notes}")

        if job_number or notes:

            planning_message_lines.append("")

        for installation in ordered_installations:

            part = installation.part

            op = (request.POST.get(f"op_{installation.id}") or "").strip()

            planning_message_lines.append(f"OP: {op}")

            planning_message_lines.append(f"Part: {part.part_number}")

            if installation.name and installation.name != "DEFAULT":

                planning_message_lines.append(f"Location: {installation.name}")

            planning_message_lines.append(
                f"STA: {installation.sta} | BL: {installation.bl} | WL: {installation.wl}"
            )

            drawing_refs = installation.drawing_refs.all()

            if drawing_refs:

                planning_message_lines.append("Reference DWGs:")

                for ref in drawing_refs:

                    planning_message_lines.append(
                        f"- DWG: {ref.dwg} | SHT: {ref.sht} | REV: {ref.rev}"
                    )

            else:

                planning_message_lines.append("Reference DWGs: None listed")

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

            planning_message_lines.append("")

        planning_message = "\n".join(planning_message_lines).strip()

        email_subject = f"Planning Request - Job {job_number}".strip()

        return render(
            request,
            "core/planning_message_result.html",
            {
                "planning_message": planning_message,
                "email_subject": email_subject,
            },
        )

    return render(
        request,
        "core/planning_request_form.html",
        {
            "parts": parts,
        },
    )


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
