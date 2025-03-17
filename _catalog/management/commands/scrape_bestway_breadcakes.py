# python manage.py scrape_bestway_breadcakes


import requests
from bs4 import BeautifulSoup
import json
import os

from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = "Scrapes product data from multiple Bestway Wholesale pages and saves it to JSON."

    def handle(self, *args, **options):
        # The three URLs you want to scrape
        urls = [
            "https://www.bestwaywholesale.co.uk/bread-cakes/401",
            "https://www.bestwaywholesale.co.uk/bread-cakes/381",
            "https://www.bestwaywholesale.co.uk/chilled-fresh/501",
            "https://www.bestwaywholesale.co.uk/chilled-fresh/481",
            "https://www.bestwaywholesale.co.uk/chilled-fresh/531",
            "https://www.bestwaywholesale.co.uk/chilled-fresh/511",
            "https://www.bestwaywholesale.co.uk/chilled-fresh/411",
            "https://www.bestwaywholesale.co.uk/chilled-fresh/581",
            "https://www.bestwaywholesale.co.uk/chilled-fresh/541",
            "https://www.bestwaywholesale.co.uk/chilled-fresh/491",
            "https://www.bestwaywholesale.co.uk/frozen/651",
            "https://www.bestwaywholesale.co.uk/frozen/711",
            "https://www.bestwaywholesale.co.uk/frozen/631",
            "https://www.bestwaywholesale.co.uk/frozen/721",
            "https://www.bestwaywholesale.co.uk/frozen/731",
            "https://www.bestwaywholesale.co.uk/frozen/671",
            "https://www.bestwaywholesale.co.uk/frozen/701",
            "https://www.bestwaywholesale.co.uk/frozen/681",
            "https://www.bestwaywholesale.co.uk/frozen/741",
            "https://www.bestwaywholesale.co.uk/frozen/641",
            "https://www.bestwaywholesale.co.uk/frozen/691",
            "https://www.bestwaywholesale.co.uk/frozen/661",
            "https://www.bestwaywholesale.co.uk/grocery/241",
            "https://www.bestwaywholesale.co.uk/grocery/11",
            "https://www.bestwaywholesale.co.uk/grocery/31",
            "https://www.bestwaywholesale.co.uk/grocery/141",
            "https://www.bestwaywholesale.co.uk/grocery/41",
            "https://www.bestwaywholesale.co.uk/grocery/71",
            "https://www.bestwaywholesale.co.uk/grocery/21",
            "https://www.bestwaywholesale.co.uk/grocery/89",
            "https://www.bestwaywholesale.co.uk/grocery/85",
            "https://www.bestwaywholesale.co.uk/grocery/161",
            "https://www.bestwaywholesale.co.uk/grocery/151",
            "https://www.bestwaywholesale.co.uk/grocery/83",
            "https://www.bestwaywholesale.co.uk/grocery/81",
            "https://www.bestwaywholesale.co.uk/grocery/88",
            "https://www.bestwaywholesale.co.uk/grocery/111",
            "https://www.bestwaywholesale.co.uk/grocery/1",
            "https://www.bestwaywholesale.co.uk/grocery/191",
            "https://www.bestwaywholesale.co.uk/grocery/231",
            "https://www.bestwaywholesale.co.uk/grocery/87",
            "https://www.bestwaywholesale.co.uk/grocery/211",
            "https://www.bestwaywholesale.co.uk/grocery/91",
            "https://www.bestwaywholesale.co.uk/grocery/101",
            "https://www.bestwaywholesale.co.uk/grocery/51",
            "https://www.bestwaywholesale.co.uk/grocery/181",
            "https://www.bestwaywholesale.co.uk/grocery/171",
            "https://www.bestwaywholesale.co.uk/grocery/61",
            "https://www.bestwaywholesale.co.uk/grocery/121",
            "https://www.bestwaywholesale.co.uk/grocery/221",
            "https://www.bestwaywholesale.co.uk/grocery/251",
            "https://www.bestwaywholesale.co.uk/confectionery/311",
            "https://www.bestwaywholesale.co.uk/cadbury",
            "https://www.bestwaywholesale.co.uk/confectionery/341",
            "https://www.bestwaywholesale.co.uk/confectionery/361",
            "https://www.bestwaywholesale.co.uk/confectionery/301",
            "https://www.bestwaywholesale.co.uk/confectionery/321",
            "https://www.bestwaywholesale.co.uk/confectionery/281",
            "https://www.bestwaywholesale.co.uk/confectionery/331",
            "https://www.bestwaywholesale.co.uk/confectionery/291",
            "https://www.bestwaywholesale.co.uk/confectionery/351",
            "https://www.bestwaywholesale.co.uk/soft-drinks/501831",
            "https://www.bestwaywholesale.co.uk/soft-drinks/501821",
            "https://www.bestwaywholesale.co.uk/soft-drinks/501865",
            "https://www.bestwaywholesale.co.uk/soft-drinks/501931",
            "https://www.bestwaywholesale.co.uk/soft-drinks/501911",
            "https://www.bestwaywholesale.co.uk/soft-drinks/501971",
            "https://www.bestwaywholesale.co.uk/soft-drinks/501895",
            "https://www.bestwaywholesale.co.uk/soft-drinks/501941",
            "https://www.bestwaywholesale.co.uk/soft-drinks/501901",
            "https://www.bestwaywholesale.co.uk/soft-drinks/501801",
            "https://www.bestwaywholesale.co.uk/soft-drinks/501965",
            "https://www.bestwaywholesale.co.uk/soft-drinks/501861",
            "https://www.bestwaywholesale.co.uk/soft-drinks/501811",
            "https://www.bestwaywholesale.co.uk/soft-drinks/501741",
            "https://www.bestwaywholesale.co.uk/soft-drinks/501951",
            "https://www.bestwaywholesale.co.uk/soft-drinks/501891",
            "https://www.bestwaywholesale.co.uk/soft-drinks/501871",
            "https://www.bestwaywholesale.co.uk/soft-drinks/501881",
            "https://www.bestwaywholesale.co.uk/soft-drinks/502001",
            "https://www.bestwaywholesale.co.uk/soft-drinks/501921",
            "https://www.bestwaywholesale.co.uk/beers-wines-spirits/791",
            "https://www.bestwaywholesale.co.uk/beers-wines-spirits/825",
            "https://www.bestwaywholesale.co.uk/beers-wines-spirits/801",
            "https://www.bestwaywholesale.co.uk/beers-wines-spirits/781",
            "https://www.bestwaywholesale.co.uk/beers-wines-spirits/821",
            "https://www.bestwaywholesale.co.uk/beers-wines-spirits/751",
            "https://www.bestwaywholesale.co.uk/beers-wines-spirits/755",
            "https://www.bestwaywholesale.co.uk/beers-wines-spirits/811",
            "https://www.bestwaywholesale.co.uk/beers-wines-spirits/741",
            "https://www.bestwaywholesale.co.uk/beers-wines-spirits/761",
            "https://www.bestwaywholesale.co.uk/cigarettes-tobacco/cigarettes",
            "https://www.bestwaywholesale.co.uk/cigarettes-tobacco/cigars",
            "https://www.bestwaywholesale.co.uk/cigarettes-tobacco/heat-not-burn",
            "https://www.bestwaywholesale.co.uk/cigarettes-tobacco/others",
            "https://www.bestwaywholesale.co.uk/cigarettes-tobacco/roll-your-own",
            "https://www.bestwaywholesale.co.uk/cigarettes-tobacco/smoker-accessories",
            "https://www.bestwaywholesale.co.uk/cigarettes-tobacco/vaping-e-cigarettes",
            "https://www.bestwaywholesale.co.uk/non-food/971",
            "https://www.bestwaywholesale.co.uk/non-food/951",
            "https://www.bestwaywholesale.co.uk/non-food/961",
        ]

        all_products = []
        list_position = 0

        for url in urls:
            # Make a request to the page
            response = requests.get(url)
            response.raise_for_status()  # Raise an exception on 4xx/5xx errors

            soup = BeautifulSoup(response.text, "html.parser")

            # Each product is in <li data-ga-product-id="...">
            product_list_items = soup.select('li[data-ga-product-id]')

            for li in product_list_items:
                list_position += 1

                ga_product_id = li.get("data-ga-product-id", "").strip()
                ga_product_name = li.get("data-ga-product-name", "").strip()
                ga_product_price = li.get("data-ga-product-price", "0").strip()
                ga_product_category = li.get("data-ga-product-category", "").strip()
                ga_product_variant = li.get("data-ga-product-variant", "").strip()
                ga_product_url = li.get("data-ga-product-url", "").strip()

                # Extract image URL
                img_tag = li.select_one(".prodimageinner img")
                image_url = img_tag["src"].strip() if img_tag and img_tag.has_attr("src") else None

                # Extract SKU
                sku_tag = li.select_one(".prodsku")
                sku_text = sku_tag.get_text(strip=True) if sku_tag else ""
                # Example format is "SKU: 807771"
                sku = sku_text.replace("SKU:", "").strip() if "SKU:" in sku_text else ""

                # Extract RSP (like "RSP: £1.99")
                rsp_tag = li.select_one(".prodrsp")
                rsp_text = rsp_tag.get_text(strip=True) if rsp_tag else ""
                # Remove "RSP:" / "£" from the string to get just the numeric part
                rsp_numeric_str = rsp_text.replace("RSP:", "").replace("£", "").strip()
                try:
                    rsp_value = float(rsp_numeric_str)
                except ValueError:
                    rsp_value = 0.0

                product_data = {
                    "ga_product_id": ga_product_id,
                    "name": ga_product_name,
                    "price": float(ga_product_price) if ga_product_price else 0.0,
                    "category": ga_product_category,
                    "variant": ga_product_variant,
                    "list_position": list_position,
                    "url": f"https://www.bestwaywholesale.co.uk{ga_product_url}",
                    "image_url": image_url,
                    "sku": sku,
                    "rsp": rsp_value,  # numeric value
                    "promotion_end_date": None,  # Not scraped
                    "multi_buy": False,          # Not scraped
                    "retail_EAN": "",            # Not scraped
                    "vat_rate": "standard",      # Default assumption
                }

                all_products.append(product_data)

        # Remove duplicates by ga_product_id if it appears in multiple URLs
        # (We keep the first occurrence; or you can override with the last if you prefer.)
        unique_products = {}
        for p in all_products:
            unique_products[p["ga_product_id"]] = p
        # Overwriting the same ID effectively ensures only one final record per ID
        final_list = list(unique_products.values())

        # Write JSON to data_job/products6.json
        output_directory = os.path.join("data_job")
        os.makedirs(output_directory, exist_ok=True)
        output_file = os.path.join(output_directory, "products6.json")

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(final_list, f, indent=2, ensure_ascii=False)

        self.stdout.write(self.style.SUCCESS(f"Scraped {len(all_products)} raw products."))
        self.stdout.write(self.style.SUCCESS(f"Reduced to {len(final_list)} unique products."))
        self.stdout.write(self.style.SUCCESS(f"Data saved to {output_file}"))
