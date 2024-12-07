# Description: A Django management command to update VAT rates for all products by scraping the product pages.
# catalog/management/commands/update_vat_rates.py
#    python manage.py update_vat_rates
#    python manage.py update_vat_rates --verbosity 2

import requests
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand
from _catalog.models import All_Products
import time
from tqdm import tqdm  # Import tqdm for progress bar

class Command(BaseCommand):
    help = 'Update VAT rates for all products by scraping the product pages.'

    def handle(self, *args, **options):
        products = All_Products.objects.all()
        total = products.count()
        updated = 0

        self.stdout.write(f"Starting VAT rate update for {total} products.\n")

        # Initialize tqdm progress bar
        with tqdm(total=total, desc="Updating VAT Rates", unit="product") as pbar:
            for product in products.iterator():
                try:
                    # Construct the product URL
                    product_url = f"https://www.bestwaywholesale.co.uk/product/{product.ga_product_id}"
                    
                    # Fetch the product page
                    response = requests.get(product_url, timeout=10)
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
                    time.sleep(0.4)

                except requests.RequestException as e:
                    self.stderr.write(f"Request error for {product_url}: {e}")
                except Exception as e:
                    self.stderr.write(f"Error processing {product_url}: {e}")

                # Update the progress bar
                pbar.update(1)

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
