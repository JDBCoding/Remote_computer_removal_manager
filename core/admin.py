from django.contrib import admin, messages
from django import forms
from django.urls import path
from django.shortcuts import redirect
from django.template.response import TemplateResponse

import pandas as pd

from .models import Part, InstallationRequirement
from .import_utils import INSTALLATION_MAP, extract_dwg_and_sheets, norm_title
from .oracle_client import fetch_oracle_rows


class PartImportForm(forms.Form):
    file = forms.FileField(label="Excel file")


class OracleImportForm(forms.Form):
    work_orders = forms.CharField(
        label="Work Orders (Job Numbers)",
        required=True,
        widget=forms.Textarea(attrs={"rows": 6, "cols": 40, "placeholder": "One work order per line (max 10)"}),
        help_text="Paste up to 10 work orders (job numbers), one per line.",
    )


@admin.register(Part)
class PartAdmin(admin.ModelAdmin):
    list_display = ("part_number", "description")
    search_fields = ("part_number", "description")
    
    change_list_template = "admin/core/part/change_list.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "import-oracle/",
                self.admin_site.admin_view(self.import_oracle_view),
                name="core_part_import_oracle",
            ),
        ]
        return custom_urls + urls

    def import_oracle_view(self, request):
        if request.method == "POST":
            form = OracleImportForm(request.POST)
            if form.is_valid():
                raw = (form.cleaned_data.get("work_orders") or "").strip()
                work_orders = [w.strip() for w in raw.replace("\r", "\n").split("\n") if w.strip()]
                work_orders = work_orders[:10]

                try:
                    rows = fetch_oracle_rows(work_orders)
                except Exception as e:
                    messages.error(request, f"Oracle pull failed: {e}")
                    return redirect("..")

                if not rows:
                    messages.warning(request, "No rows returned from Oracle for the provided work orders.")
                    return redirect("..")

                df = pd.DataFrame(rows)
                if "OPERATION_NUMBER" not in df.columns or "DCB_TITLE" not in df.columns or "DCB_VALUE" not in df.columns:
                    messages.error(request, "Oracle results missing required columns: OPERATION_NUMBER, DCB_TITLE, DCB_VALUE")
                    return redirect("..")

                imported = 0
                skipped = 0
                warnings = 0

                grouped = df.groupby("OPERATION_NUMBER")

                for op_number, group in grouped:
                    part_number_rows = group[group["DCB_TITLE"].apply(norm_title) == norm_title("part number")]
                    if part_number_rows.empty:
                        warnings += 1
                        continue

                    part_number = str(part_number_rows.iloc[0]["DCB_VALUE"]).strip().rstrip(":").upper()
                    if not part_number:
                        warnings += 1
                        continue
                    # Use case-insensitive check so we don't create duplicates like "abc" vs "ABC"
                    if Part.objects.filter(part_number__iexact=part_number).exists():
                        skipped += 1
                        continue
                    part = Part(part_number=part_number)

                    parsed_sheet = ""
                    explicit_sheet = ""

                    for _, row in group.iterrows():
                        title = norm_title(row.get("DCB_TITLE", ""))
                        value = str(row["DCB_VALUE"]).strip().upper() if pd.notnull(row.get("DCB_VALUE")) else ""

                        if title == norm_title("drawing rev"):
                            part.rev = value
                        elif title == norm_title("sta"):
                            part.sta = value
                        elif title == norm_title("b l"):
                            part.bl = value
                        elif title == norm_title("wl"):
                            part.wl = value
                        elif title in (norm_title("part number description"), norm_title("description")):
                            part.description = value
                        elif title in (
                            norm_title("drawing authority"),
                            norm_title("drawing (authority)"),
                            norm_title("drawing number"),
                        ):
                            dwg, sheets = extract_dwg_and_sheets(value)
                            if dwg:
                                part.dwg = dwg
                            if sheets:
                                parsed_sheet = sheets
                        elif title == norm_title("drawing sheet"):
                            if value:
                                explicit_sheet = value.strip()

                    if explicit_sheet:
                        part.sht = explicit_sheet
                    elif parsed_sheet:
                        part.sht = parsed_sheet

                    part.save()

                    added_types = set()
                    for _, row in group.iterrows():
                        title = norm_title(row.get("DCB_TITLE", ""))
                        value = str(row["DCB_VALUE"]).strip() if pd.notnull(row.get("DCB_VALUE")) else ""

                        if title == norm_title("dcma required? yes/no") and value.lower() != "yes":
                            continue
                        if title == norm_title("torque value 2") and not value:
                            continue

                        if title in INSTALLATION_MAP:
                            req_type = INSTALLATION_MAP[title].strip().upper()
                            if req_type not in added_types:
                                InstallationRequirement.objects.create(part=part, requirement_type=req_type)
                                added_types.add(req_type)

                    imported += 1

                messages.success(
                    request,
                    f"Oracle import complete. Imported: {imported}, Skipped existing: {skipped}, Warnings: {warnings}",
                )
                return redirect("..")

        else:
            form = OracleImportForm()

        context = dict(
            self.admin_site.each_context(request),
            title="Import Parts from Oracle",
            form=form,
        )
        return TemplateResponse(request, "admin/core/part/import_oracle.html", context)
