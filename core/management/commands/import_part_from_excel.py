import pandas as pd
from django.core.management.base import BaseCommand

from core.import_utils import INSTALLATION_MAP, extract_dwg_and_sheets, norm_title
from core.models import InstallationRequirement, Part


class Command(BaseCommand):
    help = "Import parts and installation requirements from Excel"

    def add_arguments(self, parser):
        parser.add_argument("filepath", type=str, help="Path to the Excel file")

    def handle(self, *args, **options):
        filepath = options["filepath"]
        df = pd.read_excel(filepath, sheet_name=0)

        # Defensive: ensure expected columns exist
        required_cols = {"OPERATION_NUMBER", "DCB_TITLE", "DCB_VALUE"}
        missing = required_cols - set(df.columns)
        if missing:
            self.stdout.write(self.style.ERROR(f"Missing required columns: {sorted(missing)}"))
            return

        grouped = df.groupby("OPERATION_NUMBER")

        for op_number, group in grouped:
            # Find part number
            part_number_rows = group[group["DCB_TITLE"].apply(norm_title) == norm_title("part number")]
            if part_number_rows.empty:
                self.stdout.write(self.style.WARNING(f"Skipping OP {op_number}: No part number found."))
                continue

            part_number = str(part_number_rows.iloc[0]["DCB_VALUE"]).strip().rstrip(":")
            if not part_number:
                self.stdout.write(self.style.WARNING(f"Skipping OP {op_number}: Blank part number."))
                continue

            # Skip if part already exists
            if Part.objects.filter(part_number=part_number).exists():
                self.stdout.write(f"Skipping existing part: {part_number}")
                continue

            part = Part(part_number=part_number)

            # Option #1 precedence variables for sheet assembly
            parsed_sheet = ""  # parsed from drawing authority/number value
            explicit_sheet = ""  # explicit "drawing sheet" row wins

            # Fill in fields
            for _, row in group.iterrows():
                title = norm_title(row.get("DCB_TITLE", ""))
                value = str(row["DCB_VALUE"]).strip() if pd.notnull(row.get("DCB_VALUE")) else ""

                if title == norm_title("drawing rev"):
                    part.rev = value

                elif title == norm_title("sta"):
                    part.sta = value

                elif title == norm_title("b l"):
                    # Note: norm_title("b/l") becomes "b l"
                    part.bl = value

                elif title == norm_title("wl"):
                    part.wl = value

                elif title in (norm_title("part number description"), norm_title("description")):
                    part.description = value

                # Drawing authority variants and drawing number variants
                elif title in (norm_title("drawing authority"), norm_title("drawing number")):
                    dwg, sheets = extract_dwg_and_sheets(value)
                    if dwg:
                        part.dwg = dwg
                    if sheets:
                        parsed_sheet = sheets

                # Explicit drawing sheet row should override parsed sheet
                elif title == norm_title("drawing sheet"):
                    if value:
                        explicit_sheet = value.strip()

            # Apply sheet precedence AFTER loop (Option #1)
            if explicit_sheet:
                part.sht = explicit_sheet
            elif parsed_sheet:
                part.sht = parsed_sheet

            part.save()

            # Add installation requirements
            added_types = set()

            for _, row in group.iterrows():
                title = norm_title(row.get("DCB_TITLE", ""))
                value = str(row["DCB_VALUE"]).strip() if pd.notnull(row.get("DCB_VALUE")) else ""

                # Conditional rules
                if title == norm_title("dcma required? yes/no") and value.lower() != "yes":
                    continue
                if title == norm_title("torque value 2") and not value:
                    continue

                if title in INSTALLATION_MAP:
                    req_type = INSTALLATION_MAP[title].strip().upper()
                    if req_type not in added_types:
                        InstallationRequirement.objects.create(part=part, requirement_type=req_type)
                        added_types.add(req_type)

            self.stdout.write(self.style.SUCCESS(f"Imported part: {part.part_number}"))
