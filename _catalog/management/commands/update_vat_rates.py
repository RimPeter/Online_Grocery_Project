# Description: A Django management command to update VAT rates for all products by scraping the product pages.
# catalog/management/commands/update_vat_rates.py
#    python manage.py update_vat_rates
#    python manage.py update_vat_rates --verbosity 2

import os
import json
from datetime import datetime
from pathlib import Path
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand
from _catalog.models import All_Products
import time
from tqdm import tqdm  # Import tqdm for progress bar
from django.db import close_old_connections

class Command(BaseCommand):
    help = 'Update VAT rates for all products by scraping the product pages.'

    def add_arguments(self, parser):
        parser.add_argument('--start-from-pk', type=int, default=0, help='Start processing from product PK > value')
        parser.add_argument('--start-from-gaid', type=str, default='', help='Start processing from given ga_product_id (exclusive)')
        parser.add_argument('--resume', action='store_true', help='Resume from checkpoint file')
        parser.add_argument('--checkpoint', type=str, default='.vat_checkpoint.json', help='Checkpoint file path')
        parser.add_argument('--save-every', type=int, default=200, help='Write checkpoint every N products')

    def _read_checkpoint(self, path: Path):
        try:
            if path.exists():
                with path.open('r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _write_checkpoint(self, path: Path, data: dict):
        try:
            tmp = Path(str(path) + '.tmp')
            with tmp.open('w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
        except Exception:
            # Non-fatal
            pass

    def handle(self, *args, **options):
        # Resolve start point
        cp_path = Path(options.get('checkpoint') or '.vat_checkpoint.json')
        start_pk = int(options.get('start_from_pk') or 0)
        start_gaid = (options.get('start_from_gaid') or '').strip()
        if options.get('resume'):
            cp = self._read_checkpoint(cp_path)
            if cp:
                start_pk = int(cp.get('last_pk') or start_pk or 0)
                start_gaid = (cp.get('last_gaid') or start_gaid or '').strip()
                self.stdout.write(self.style.WARNING(f"Resuming from checkpoint: pk>{start_pk}, gaid={start_gaid or '-'}"))
            else:
                self.stdout.write(self.style.WARNING("--resume specified but no checkpoint found; starting fresh."))

        if start_gaid and not start_pk:
            try:
                start_pk = All_Products.objects.only('id').get(ga_product_id=start_gaid).pk
                self.stdout.write(f"Resolved start-from-gaid '{start_gaid}' to pk {start_pk}")
            except All_Products.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"start-from-gaid '{start_gaid}' not found; ignoring."))
                start_gaid = ''

        # Build ordered queryset and apply start filters
        base_qs = All_Products.objects.order_by('id')
        total_all = base_qs.count()
        if start_pk:
            products = base_qs.filter(id__gt=start_pk)
        else:
            products = base_qs
        total = products.count()
        updated = 0

        self.stdout.write(f"Starting VAT rate update for {total} products.\n")

        # Prepare a resilient HTTP session with retries/backoff
        session = requests.Session()
        retries = Retry(
            total=5,
            backoff_factor=0.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET",),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retries, pool_connections=16, pool_maxsize=16)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        # Initialize tqdm progress bar
        with tqdm(total=total, desc="Updating VAT Rates", unit="product") as pbar:
            last_pk = start_pk
            last_gaid = start_gaid
            started_at = datetime.utcnow().isoformat() + 'Z'
            save_every = max(1, int(options.get('save_every') or 200))
            for idx, product in enumerate(products.iterator(chunk_size=200), start=1):
                try:
                    # Construct the product URL
                    product_url = f"https://www.bestwaywholesale.co.uk/product/{product.ga_product_id}"
                    
                    # Fetch the product page
                    response = session.get(product_url, timeout=15)
                    response.raise_for_status()  # Raise an error for bad status codes

                    # Parse the HTML content
                    soup = BeautifulSoup(response.text, 'html.parser')

                    # Find the VAT Rate in the table
                    vat_rate = self.extract_vat_rate(soup)

                    if vat_rate:
                        # Map the scraped VAT rate to model choices
                        vat_rate_mapped = self.map_vat_rate(vat_rate)

                        if vat_rate_mapped and vat_rate_mapped != product.vat_rate:
                            product.vat_rate = vat_rate_mapped
                            product.save()
                            updated += 1
                            self.stdout.write(self.style.SUCCESS(f"Updated VAT rate to '{vat_rate_mapped}' for '{product.name}'"))
                        else:
                            self.stdout.write(f"No update needed for VAT rate: '{vat_rate}' for '{product.name}'")
                    else:
                        self.stdout.write(self.style.WARNING(f"VAT rate not found for '{product.name}'."))

                    # Be polite and avoid overwhelming the server
                    time.sleep(0.3)

                except requests.RequestException as e:
                    self.stderr.write(f"Request error for {product_url}: {e}")
                except Exception as e:
                    self.stderr.write(f"Error processing {product_url}: {e}")

                # Periodically refresh DB connections to avoid timeouts
                if idx % 200 == 0:
                    try:
                        close_old_connections()
                    except Exception:
                        # Non-fatal: continue processing
                        pass

                # Update the progress bar
                pbar.update(1)

                # Update checkpoint
                last_pk = product.pk
                last_gaid = product.ga_product_id
                if idx % save_every == 0:
                    self._write_checkpoint(cp_path, {
                        'last_pk': last_pk,
                        'last_gaid': last_gaid,
                        'updated_count': updated,
                        'remaining': max(0, total - idx),
                        'total_all': total_all,
                        'started_at': started_at,
                        'saved_at': datetime.utcnow().isoformat() + 'Z',
                    })

        # Final checkpoint write (completed)
        self._write_checkpoint(cp_path, {
            'last_pk': last_pk,
            'last_gaid': last_gaid,
            'updated_count': updated,
            'remaining': 0,
            'total_all': total_all,
            'completed_at': datetime.utcnow().isoformat() + 'Z',
            'completed': True,
        })

        self.stdout.write(self.style.SUCCESS(f"\nVAT rate update completed. {updated} products updated out of {total}."))

    def extract_vat_rate(self, soup):
        """
        Extracts the VAT Rate from the product page HTML.
        """
        table = soup.find('table', class_='prodtable')
        if not table:
            return None

        for row in table.find_all('tr'):
            header = row.find('th')
            if header and 'Vat Rate' in header.text:
                vat_rate_td = row.find('td')
                if vat_rate_td:
                    return vat_rate_td.text.strip().lower()  # Normalize to lowercase
        return None

    def map_vat_rate(self, vat_rate_str):
        """
        Maps the scraped VAT rate string to the model's VAT_RATE_CHOICES.
        """
        mapping = {
            'standard': 'standard',
            'reduced': 'reduced',
            'zero': 'zero',
            'exempt': 'exempt',
            'exempted': 'exempt',  # Handle possible variations
            'zero-rated': 'zero',
            '5%': '5%',  # Handle specific percentages
        }

        # Normalize the VAT rate string
        vat_rate_normalized = vat_rate_str.replace('%', '').replace('rate', '').strip().lower()

        # Direct mapping if exists
        if vat_rate_normalized in mapping:
            return mapping[vat_rate_normalized]

        # Handle specific cases from the scraped data
        if 'exempt' in vat_rate_normalized:
            return 'exempt'
        elif 'zero' in vat_rate_normalized:
            return 'zero'
        elif 'reduced' in vat_rate_normalized:
            return 'reduced'
        elif 'standard' in vat_rate_normalized:
            return 'standard'

        # If no mapping found, log a warning
        self.stderr.write(f"Unrecognized VAT rate: '{vat_rate_str}'")
        return None
