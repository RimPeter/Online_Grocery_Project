"""
Run the full Bestway subcategory scraping pipeline in one go.

This command runs, in order:
    python manage.py scrape_subcategories
    python manage.py scrape_sub_subcategories
    python manage.py scraper_for_sub_subcategory
    python manage.py load_sub_subcategory_products

Usage:
    python manage.py run_subcategory_pipeline
    python manage.py run_subcategory_pipeline --from-step scraper_for_sub_subcategory
    python manage.py run_subcategory_pipeline --to-step scrape_sub_subcategories
    python manage.py run_subcategory_pipeline --continue-on-error
"""

import time

from django.core.management import BaseCommand, call_command
from django.utils import timezone

from _product_management.models import SubcategoryPipelineRun


class Command(BaseCommand):
    help = (
        "Run the full Bestway subcategory scraping pipeline and load "
        "results into All_Products."
    )

    # Ordered list of pipeline steps (name, human-readable description)
    STEPS = [
        ("scrape_subcategories", "Scrape subcategory navigation pages"),
        ("scrape_sub_subcategories", "Discover sub-subcategory listing URLs"),
        ("scraper_for_sub_subcategory", "Scrape sub-subcategory product listings to JSON"),
        ("load_sub_subcategory_products", "Load scraped JSON into All_Products"),
    ]

    def add_arguments(self, parser):
        step_names = [name for name, _ in self.STEPS]
        parser.add_argument(
            "--from-step",
            choices=step_names,
            help="Optional name of the first step to run (defaults to the first pipeline step).",
        )
        parser.add_argument(
            "--to-step",
            choices=step_names,
            help="Optional name of the last step to run (defaults to the final pipeline step).",
        )
        parser.add_argument(
            "--continue-on-error",
            action="store_true",
            help="Continue executing later steps even if an earlier step fails.",
        )

    def handle(self, *args, **options):
        """
        Execute the underlying management commands in sequence with
        basic error handling and optional partial runs.
        """
        verbosity = options.get("verbosity", 1)
        from_step = options.get("from_step")
        to_step = options.get("to_step")
        continue_on_error = bool(options.get("continue_on_error"))

        all_step_names = [name for name, _ in self.STEPS]

        # Resolve start/end indices for slicing the pipeline.
        start_idx = all_step_names.index(from_step) if from_step else 0
        end_idx = all_step_names.index(to_step) if to_step else len(all_step_names) - 1
        if start_idx > end_idx:
            raise SystemExit(
                f"--from-step {from_step!r} comes after --to-step {to_step!r}."
            )

        selected_steps = all_step_names[start_idx : end_idx + 1]
        total = len(selected_steps)

        self.stdout.write(
            self.style.NOTICE(
                f"Running subcategory pipeline steps: {', '.join(selected_steps)}"
            )
        )

        # Create a DB record for this run so the UI can show the most
        # recent pipeline errors.
        run = SubcategoryPipelineRun.objects.create(
            started_at=timezone.now(),
            from_step=from_step or "",
            to_step=to_step or "",
            steps=",".join(selected_steps),
            succeeded=False,
        )

        successes = []
        failures = []
        error_lines = []

        for idx, name in enumerate(selected_steps, start=1):
            label = dict(self.STEPS).get(name, name)
            self.stdout.write(
                self.style.NOTICE(f"[{idx}/{total}] Running {name} ({label})...")
            )
            started = time.monotonic()
            try:
                call_command(name, verbosity=verbosity)
            except Exception as exc:
                duration = time.monotonic() - started
                failures.append(name)
                msg = f"Step {name} failed after {duration:.1f}s: {exc}"
                error_lines.append(msg)
                self.stderr.write(
                    self.style.ERROR(msg)
                )
                if not continue_on_error:
                    self.stderr.write(
                        self.style.ERROR(
                            "Stopping pipeline due to error. "
                            "Re-run with --continue-on-error to ignore failures."
                        )
                    )
                    break
            else:
                duration = time.monotonic() - started
                successes.append(name)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Finished {name} in {duration:.1f}s"
                    )
                )

        # Persist final status and any collected error messages.
        run.finished_at = timezone.now()
        run.succeeded = not failures
        run.errors = "\n".join(error_lines)
        run.save(update_fields=["finished_at", "succeeded", "errors"])

        if failures:
            summary = (
                f"Pipeline completed with errors. "
                f"Successful steps: {', '.join(successes) or 'none'}. "
                f"Failed steps: {', '.join(failures)}."
            )
            self.stderr.write(self.style.ERROR(summary))
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Subcategory scraping pipeline completed successfully "
                    f"({len(successes)} step(s))."
                )
            )
