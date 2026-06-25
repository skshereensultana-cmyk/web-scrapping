import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

DEFAULT_TARGET_PRICE = 50.0
DEFAULT_URLS = ["sample_product_page.html"]
OUTPUT_FOLDER = Path(__file__).resolve().parent / "downloaded_images"
OUTPUT_FOLDER.mkdir(exist_ok=True)


def load_page(source):
    """Load HTML from a website URL or a local file."""
    if source.startswith(("http://", "https://")):
        response = requests.get(source, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        response.raise_for_status()
        return response.text, source

    if source.startswith("file://"):
        path = Path(urlparse(source).path)
        return path.read_text(encoding="utf-8"), str(path.resolve())

    path = Path(source)
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()

    if not path.exists():
        raise FileNotFoundError(f"The file was not found: {source}")

    return path.read_text(encoding="utf-8"), str(path.resolve())


def resolve_url(link, source_url):
    """Convert a relative image path to a full URL or file path."""
    if not link:
        return None

    if link.startswith(("http://", "https://", "file://")):
        return link

    if source_url.startswith(("http://", "https://")):
        return urljoin(source_url, link)

    source_path = Path(source_url).resolve()
    if source_path.exists() and source_path.is_file():
        return str((source_path.parent / link).resolve())

    return link


def extract_product_details(html, source_url):
    """Extract the product title, price, and image URL from page HTML."""
    soup = BeautifulSoup(html, "html.parser")

    title = None
    title_tag = soup.find("h1")
    if title_tag:
        title = title_tag.get_text(" ", strip=True)

    if not title:
        meta_title = soup.find("meta", attrs={"property": "og:title"})
        if meta_title and meta_title.get("content"):
            title = meta_title["content"].strip()

    if not title and soup.title:
        title = soup.title.get_text(strip=True)

    price = None
    for element in soup.find_all(string=True):
        text = " ".join(str(element).split())
        if not text:
            continue

        match = re.search(r"(?:[$€£])?\s*(\d+(?:[.,]\d{1,2})?)", text)
        if match and ("price" in text.lower() or "$" in text or "€" in text or "£" in text):
            price = float(match.group(1).replace(",", "."))
            break

    image_url = None
    meta_image = soup.find("meta", attrs={"property": "og:image"})
    if meta_image and meta_image.get("content"):
        image_url = meta_image["content"].strip()

    if not image_url:
        img_tag = soup.select_one("img")
        if img_tag and img_tag.get("src"):
            image_url = img_tag.get("src")

    resolved_image_url = resolve_url(image_url, source_url) if image_url else None

    return {
        "title": title or "Unknown title",
        "price": price,
        "image_url": resolved_image_url,
    }


def download_image(image_url, save_folder, file_name):
    """Save the product image to the local downloads folder."""
    if not image_url:
        return None

    if image_url.startswith(("http://", "https://")):
        response = requests.get(image_url, timeout=10)
        response.raise_for_status()
        content = response.content
    else:
        path = Path(image_url)
        if image_url.startswith("file://"):
            path = Path(urlparse(image_url).path)
        elif not path.is_absolute():
            path = (Path.cwd() / path).resolve()

        if not path.exists():
            raise FileNotFoundError(f"Image file was not found: {image_url}")

        content = path.read_bytes()

    extension = Path(urlparse(image_url).path).suffix or ".jpg"
    save_path = save_folder / f"{file_name}{extension}"
    save_path.write_bytes(content)
    return str(save_path)


def compare_price(price, target_price):
    """Compare the product price with the target price."""
    if price is None:
        return "No price found"

    if price < target_price:
        return f"The product is cheaper than the target price by {target_price - price:.2f}."
    if price > target_price:
        return f"The product is more expensive than the target price by {price - target_price:.2f}."
    return "The product price matches the target price."


def parse_arguments(arguments):
    """Support simple command-line input for URLs and target price."""
    urls = []
    target_price = DEFAULT_TARGET_PRICE

    for argument in arguments:
        if argument.startswith("--target="):
            target_price = float(argument.split("=", 1)[1])
        else:
            urls.append(argument)

    return urls or DEFAULT_URLS, target_price


def main():
    urls, target_price = parse_arguments(sys.argv[1:])

    print("Starting product scraping...")
    print(f"Target price: {target_price}")

    for index, url in enumerate(urls, start=1):
        print(f"\nProduct {index}: {url}")
        html, source_url = load_page(url)
        details = extract_product_details(html, source_url)

        print("Product title:", details["title"])
        print("Price:", details["price"] if details["price"] is not None else "Not found")
        print("Image URL:", details["image_url"] or "Not found")

        if details["image_url"]:
            image_path = download_image(details["image_url"], OUTPUT_FOLDER, f"product_{index}")
            print("Image saved to:", image_path)

        print("Price comparison:", compare_price(details["price"], target_price))

    print("\nScraping completed.")


if __name__ == "__main__":
    main()
