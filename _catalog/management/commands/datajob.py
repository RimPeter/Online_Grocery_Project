from django.core.management.base import BaseCommand
from django.core.management import call_command
from time import perf_counter


def data_job(
    *,
    run_scrape: bool = False,
    run_variants: bool = False,
    variants_limit: int = 0,
    variants_dry_run: bool = False,
    run_vat: bool = False,
    run_home_subcats: bool = False,
    home_active: bool = True,
    verbosity: int = 1,
    stdout=None,
    stderr=None,
) -> None:
    """Orchestrate data jobs for the catalog app.

    Steps: scrape_bestway, backfill_variants, update_vat_rates, populate_home_subcategories.
    Each step is optional and errors are reported but do not stop subsequent steps.
    """

    def _run(step_name: str, fn, *args, **kwargs):
        started = perf_counter()
        if stdout:
            stdout.write(f"Starting {step_name}...")
        try:
            fn(*args, **kwargs)
            took = perf_counter() - started
            if stdout:
                stdout.write(f"Finished {step_name} in {took:.2f}s")
        except Exception as exc:
            took = perf_counter() - started
            if stderr:
                stderr.write(f"{step_name} failed after {took:.2f}s: {exc}")

    if run_scrape:
        _run(
            'scrape_bestway',
            call_command,
            'scrape_bestway',
            verbosity=verbosity,
            stdout=stdout,
            stderr=stderr,
        )

    if run_variants:
        call_kwargs = dict(verbosity=verbosity, stdout=stdout, stderr=stderr)
        if variants_limit:
            call_kwargs['limit'] = variants_limit
        if variants_dry_run:
            call_kwargs['dry_run'] = True
        _run('backfill_variants', call_command, 'backfill_variants', **call_kwargs)

    if run_vat:
        _run('update_vat_rates', call_command, 'update_vat_rates', verbosity=verbosity, stdout=stdout, stderr=stderr)

    if run_home_subcats:
        _run(
            'populate_home_subcategories',
            call_command,
            'populate_home_subcategories',
            verbosity=verbosity,
            stdout=stdout,
            stderr=stderr,
            active=home_active,
        )


class Command(BaseCommand):
    help = 'Run catalog data jobs (wrapper around existing commands)'

    def add_arguments(self, parser):
        # Master selector
        parser.add_argument('--all', action='store_true', help='Run all steps')

        # Individual steps
        parser.add_argument('--scrape', action='store_true', help='Run scrape_bestway')
        parser.add_argument('--no-scrape', action='store_true', help='Skip scrape even when using --all')

        parser.add_argument('--variants', action='store_true', help='Run backfill_variants')
        parser.add_argument('--variants-limit', type=int, default=0, help='Limit number of variant updates')
        parser.add_argument('--variants-dry-run', action='store_true', help='Backfill variants without saving')

        parser.add_argument('--vat', action='store_true', help='Run update_vat_rates')

        parser.add_argument('--home-subcats', action='store_true', help='Run populate_home_subcategories')
        parser.add_argument('--home-inactive', action='store_true', help='Create home subcategories as inactive')

    def handle(self, *args, **options):
        verbosity = int(options.get('verbosity', 1) or 1)

        run_all = bool(options.get('all'))
        want_scrape = bool(options.get('scrape')) or run_all
        if options.get('no_scrape'):
            want_scrape = False

        want_variants = bool(options.get('variants')) or run_all
        want_vat = bool(options.get('vat')) or run_all
        want_home = bool(options.get('home_subcats')) or run_all

        data_job(
            run_scrape=want_scrape,
            run_variants=want_variants,
            variants_limit=int(options.get('variants_limit') or 0),
            variants_dry_run=bool(options.get('variants_dry_run')),
            run_vat=want_vat,
            run_home_subcats=want_home,
            home_active=not bool(options.get('home_inactive')),
            verbosity=verbosity,
            stdout=self.stdout,
            stderr=self.stderr,
        )

