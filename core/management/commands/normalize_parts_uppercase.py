from django.core.management.base import BaseCommand

from django.db import transaction

from core.models import Part


class Command(BaseCommand):

    help = "Normalize Part fields to uppercase, including renaming lowercase primary keys safely."

    def add_arguments(self, parser):

        parser.add_argument(

            "--dry-run",

            action="store_true",

            help="Show what would change, but don't write to the database.",

        )

    @transaction.atomic

    def handle(self, *args, **options):

        dry_run = options["dry_run"]

        # Fields we want uppercase on existing rows

        normal_fields = ["description", "sta", "bl", "wl", "dwg", "sht", "rev"]

        # Collect parts up front

        parts = list(Part.objects.all())

        rename_count = 0

        update_count = 0

        skip_conflict = 0

        # We’ll process renames first (pk changes), then normal updates

        for part in parts:

            old_pk = part.part_number

            new_pk = (old_pk or "").strip().upper()

            if not old_pk:

                continue

            # If pk already uppercase (or no change), skip rename

            if old_pk == new_pk:

                continue

            # If uppercase version already exists, we have a conflict:

            # We can’t rename without deciding how to merge.

            if Part.objects.filter(part_number=new_pk).exists():

                skip_conflict += 1

                self.stdout.write(

                    self.style.WARNING(

                        f"SKIP (conflict): '{old_pk}' -> '{new_pk}' (target already exists)"

                    )

                )

                continue

            rename_count += 1

            self.stdout.write(f"RENAME: '{old_pk}' -> '{new_pk}'")

            if dry_run:

                continue

            # Create the new Part row with the uppercase PK and copy fields

            new_part = Part(

                part_number=new_pk,

                description=part.description,

                sta=part.sta,

                bl=part.bl,

                wl=part.wl,

                dwg=part.dwg,

                sht=part.sht,

                rev=part.rev,

                notes=part.notes,

            )

            new_part.save()

            # Update any ForeignKey relations pointing to Part

            # This is generic: it finds all models with FK to Part automatically

            for rel in Part._meta.related_objects:

                if not rel.many_to_one:

                    continue  # only handle FK relations

                accessor = rel.get_accessor_name()

                related_manager = getattr(part, accessor, None)

                if related_manager is None:

                    continue

                # Bulk update FK to point to new pk

                fk_field_name = rel.field.name  # e.g. "part"

                related_manager.all().update(**{fk_field_name: new_part})

            # Delete the old row

            part.delete()

        # Refresh list after renames

        parts = list(Part.objects.all())

        for part in parts:

            changed = False

            for field in normal_fields:

                val = getattr(part, field, None)

                if isinstance(val, str) and val:

                    new_val = val.strip().upper()

                    if new_val != val:

                        setattr(part, field, new_val)

                        changed = True

            # notes is intentionally NOT uppercased (human text).

            if changed:

                update_count += 1

                if dry_run:

                    self.stdout.write(f"UPDATE: {part.part_number}")

                else:

                    part.save()

        if dry_run:

            self.stdout.write(

                self.style.SUCCESS(

                    f"[DRY RUN] Would rename {rename_count} parts, update {update_count} parts, skip {skip_conflict} conflicts."

                )

            )

        else:

            self.stdout.write(

                self.style.SUCCESS(

                    f"Done. Renamed {rename_count} parts, updated {update_count} parts, skipped {skip_conflict} conflicts."

                )

            )
 