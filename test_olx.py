import sys
import json
import re
import os
import platform
from playwright.sync_api import sync_playwright
from scraper_utils import extract_mileage_range, parse_listing_price

def scrape_olx_standalone(merek_car, model_car, output_file="olx_temp.json"):
    # TRIK CLOUD: Jika berjalan di Linux (Streamlit Cloud), aktifkan Virtual Monitor (Xvfb)
    if platform.system() == "Linux":
        try:
            from pyvirtualdisplay import Display
            display = Display(visible=0, size=(1280, 850))
            display.start()
        except Exception as e:
            print(f"Xvfb Notice: {e}", file=sys.stderr)

    query = f"{merek_car} {model_car}".strip()
    search_url = f"https://www.olx.co.id/mobil-bekas_c198?q={query.replace(' ', '%20')}"
    
    olx_data = []
    merek_clean = merek_car.lower().strip()
    model_keywords = [w for w in model_car.lower().split() if len(w) >= 2]

    try:
        with sync_playwright() as p:
            # TETAP PAKAI headless=False AGAR 100% LOLOS AKAMAI OLX!
            browser = p.chromium.launch(
                headless=False,
                args=[
                    "--window-position=-2400,-2400",
                    "--window-size=1280,850",
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-http2"
                ],
                ignore_default_args=["--enable-automation"]
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 850},
                locale="id-ID"
            )
            page = context.new_page()
            page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            page.goto(search_url, wait_until="load", timeout=25000)
            page.evaluate("window.scrollTo(0, 800)")
            page.wait_for_timeout(3000)

            item_links = page.query_selector_all("a[href*='/item/']")
            seen_urls = set()

            for link in item_links:
                try:
                    href = link.get_attribute("href") or ""
                    if not href:
                        continue
                    full_url = f"https://www.olx.co.id{href}" if href.startswith("/") else href
                    if full_url in seen_urls:
                        continue
                    seen_urls.add(full_url)

                    card_text = link.inner_text().strip()
                    combined_text = (card_text + " " + href).lower()
                    
                    merek_match = merek_clean in combined_text
                    model_match = any(kw in combined_text for kw in model_keywords) if model_keywords else True
                    
                    if not (merek_match and model_match):
                        continue

                    price_val = parse_listing_price(card_text) or 0
                    if price_val:

                        if price_val > 30000000:
                            year_match = re.search(r'\b(20[0-2][0-9]|19[8-9][0-9])\b', card_text)
                            extracted_year = int(year_match.group(1)) if year_match else None
                            
                            slug_match = re.search(r'/item/(.+?)-iid-\d+', href)
                            if slug_match:
                                raw_slug = slug_match.group(1).replace('-', ' ')
                                title_text = raw_slug.title()
                            else:
                                lines = [line.strip() for line in card_text.split('\n') if line.strip()]
                                non_price_lines = [l for l in lines if not re.match(r'^Rp\s*[\d\.,]+$', l, re.I)]
                                title_text = non_price_lines[0] if non_price_lines else f"{merek_car} {model_car}"

                            mileage_min_km, mileage_max_km = extract_mileage_range(
                                card_text
                            )
                            location = None
                            for selector in (
                                '[itemprop="addressLocality"]',
                                '[data-testid="location-date"]',
                                '[data-testid*="location"]',
                                '[class*="location"]',
                            ):
                                location_element = link.query_selector(selector)
                                if not location_element:
                                    continue
                                location_text = location_element.inner_text().strip()
                                location_text = re.sub(
                                    r"(?i)\s*(?:,|[•|])?\s*\d+\s*"
                                    r"(?:menit|jam|hari|minggu|bulan|tahun)"
                                    r".*$",
                                    "",
                                    location_text,
                                ).strip(" ,|•-")
                                if location_text and not re.fullmatch(
                                    r"(?i)(lokasi|location|indonesia)",
                                    location_text,
                                ):
                                    location = location_text
                                    break

                            olx_data.append({
                                "source": "OLX",
                                "title": title_text,
                                "price": price_val,
                                "year": extracted_year,
                                "url": full_url,
                                "mileage_min_km": mileage_min_km,
                                "mileage_max_km": mileage_max_km,
                                "location": location,
                            })
                except Exception:
                    continue
            browser.close()
    except Exception as e:
        print(f"Error Scraper: {e}", file=sys.stderr)

    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(olx_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error Saving JSON: {e}", file=sys.stderr)

if __name__ == "__main__":
    merek_arg = sys.argv[1] if len(sys.argv) > 1 else "Toyota"
    model_arg = sys.argv[2] if len(sys.argv) > 2 else "Kijang Innova"
    file_arg = sys.argv[3] if len(sys.argv) > 3 else "olx_temp.json"
    
    scrape_olx_standalone(merek_arg, model_arg, file_arg)