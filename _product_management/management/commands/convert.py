#   python data_job/convert.py


import json
import re
from bs4 import BeautifulSoup

# Read the file
with open("data_job\data6.txt", "r", encoding="utf-8") as file:
    content = file.read()

# Parse the content with BeautifulSoup
soup = BeautifulSoup(content, "html.parser")

# Extract data from each list item
products = []
for item in soup.find_all("li"):
    product = {
        "ga_product_id": item.get("data-ga-product-id", "").strip(),
        "name": item.get("data-ga-product-name", "").strip(),
        "price": float(item.get("data-ga-product-price", "0").strip()),
        "category": item.get("data-ga-product-category", "").strip(),
        "variant": item.get("data-ga-product-variant", "").strip(),
        "list_position": int(item.get("data-ga-product-position", "0").strip()),
        "url": item.get("data-ga-product-url", "").strip(),
        "image_url": item.find("img")["src"] if item.find("img") else None,
        "sku": re.search(r"SKU:\s*(\d+)", item.text).group(1) if "SKU:" in item.text else None,
        "rsp": float(re.search(r"RSP:\s*£([\d\.]+)", item.text).group(1)) if "RSP:" in item.text else None,
        "promotion_end_date": re.search(r"Promotion ends\s*(\d+\w+\s+\w+)", item.text).group(1) if "Promotion ends" in item.text else None,
        "multi_buy": "Multibuy" in item.text
    }
    products.append(product)

# Write the data to a JSON file
with open("data_job/products6.json", "w", encoding="utf-8") as json_file:
    json.dump(products, json_file, indent=4, ensure_ascii=False)

print("Data successfully written to products.json")
