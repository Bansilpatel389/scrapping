# """
# Pipeline:
# 1) Accept a list of URLs directly via command line arguments.
# 2) For each URL, fetch HTML using Playwright wrapped in Stealth (v2.x).
# 3) Bypass Google Cookie Consent (if present) and scroll to load images.
# 4) Parse ALL products on the page into a list of dictionaries.
# 5) Write the consolidated data to a CSV.
# """

# import argparse
# import csv
# import os
# import sys
# import math
# import random
# import time
# import requests
# from bs4 import BeautifulSoup
# from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
# from playwright_stealth import Stealth # <-- Updated import for v2.0+
# from solve_captch import solve_audio_captcha

# OUT_FIELDS = [
#     "url",
#     "name",
#     "image_url",
#     "price",
#     "seller",
#     "pid",
#     "cid",
#     "gid"
# ]

# def show_mouse_cursor(page):
#     page.evaluate("""
#     () => {
#         if (document.getElementById('playwright-cursor')) return;

#         const cursor = document.createElement('div');
#         cursor.id = 'playwright-cursor';

#         Object.assign(cursor.style, {
#             position: 'fixed',
#             width: '14px',
#             height: '14px',
#             background: 'red',
#             border: '2px solid white',
#             borderRadius: '50%',
#             zIndex: '2147483647',
#             pointerEvents: 'none',
#             transform: 'translate(-50%, -50%)',
#             left: '0px',
#             top: '0px'
#         });

#         document.body.appendChild(cursor);

#         document.addEventListener('mousemove', e => {
#             cursor.style.left = e.clientX + 'px';
#             cursor.style.top = e.clientY + 'px';
#         });
#     }
#     """)
    
# def human_mouse_move(page, min_seconds=2, max_seconds=5):
#     show_mouse_cursor(page)
#     duration = random.uniform(min_seconds, max_seconds)

#     viewport = page.viewport_size

#     if not viewport:
#         viewport = page.evaluate("""
#             () => ({
#                 width: window.innerWidth,
#                 height: window.innerHeight
#             })
#         """)

#     width = viewport["width"]
#     height = viewport["height"]

#     current_x = random.randint(100, max(101, width - 100))
#     current_y = random.randint(100, max(101, height - 100))

#     page.mouse.move(current_x, current_y)

#     start_time = time.time()

#     while time.time() - start_time < duration:
#         distance_x = random.randint(-300, 300)
#         distance_y = random.randint(-200, 200)

#         target_x = max(30, min(width - 30, current_x + distance_x))
#         target_y = max(30, min(height - 30, current_y + distance_y))

#         control_x = (current_x + target_x) / 2 + random.randint(-80, 80)
#         control_y = (current_y + target_y) / 2 + random.randint(-80, 80)

#         steps = random.randint(60, 120)

#         for i in range(1, steps + 1):
#             if time.time() - start_time >= duration:
#                 return

#             t = i / steps
#             eased_t = (1 - math.cos(math.pi * t)) / 2

#             x = (
#                 (1 - eased_t) ** 2 * current_x
#                 + 2 * (1 - eased_t) * eased_t * control_x
#                 + eased_t ** 2 * target_x
#             )

#             y = (
#                 (1 - eased_t) ** 2 * current_y
#                 + 2 * (1 - eased_t) * eased_t * control_y
#                 + eased_t ** 2 * target_y
#             )

#             x += random.uniform(-0.5, 0.5)
#             y += random.uniform(-0.5, 0.5)

#             x = max(2, min(width - 2, x))
#             y = max(2, min(height - 2, y))

#             page.mouse.move(x, y)
#             time.sleep(random.uniform(0.012, 0.025))

#         current_x = target_x
#         current_y = target_y

#         if random.random() < 0.60:
#             time.sleep(random.uniform(0.10, 0.40))       

# def find_recaptcha_frame(page, match):
#     iframes = page.locator("iframe")
#     for i in range(iframes.count()):
#         iframe = iframes.nth(i)
#         title = iframe.get_attribute("title") or ""
#         if match in title:
#             return iframe.content_frame
#     return None

# def detect_recaptcha(page):
#     frame = find_recaptcha_frame(page,"reCAPTCHA")

#     if not frame:
#         print("No reCAPTCHA iframe found")
#         return False

#     try:
#         checkbox = frame.locator("div.recaptcha-checkbox-border")

#         if checkbox.count() > 0:
#             human_mouse_move(page,2,3)
#             checkbox.first.click()
#             print("reCAPTCHA detected")
#             human_mouse_move(page,2,5)
            
#             new_frame = find_recaptcha_frame(page,"recaptcha challenge")
#             if not new_frame:
#                 print("No challenge iframe found")
#                 return False
#             audio_button = new_frame.locator("button.rc-button-audio")
#             if audio_button.count() > 0:
#                 audio_button.first.click()
#                 print("Audio button clicked")
#                 human_mouse_move(page,2,5)
                
#                 new_frame_2 = find_recaptcha_frame(page,"recaptcha challenge")
#                 if not new_frame_2:
#                     print("No challenge 2 iframe found")
#                     return False
#                 # if new_frame_2.locator("div.rc-doscaptcha-body-text") : 
#                     # print("Automation detected")
#                     return False
#                 a_tag = new_frame_2.locator("a.rc-audiochallenge-tdownload-link")
#                 if a_tag.count() > 0:
#                     url = a_tag.get_attribute("href")
#                     if not url:
#                         print("No href found")
#                         return False
#                     print("Download URL:", url)
#                     response = requests.get(url, stream=True, timeout=60)
#                     response.raise_for_status()

#                     with open("captcha_audio.mp4", "wb") as f:
#                         for chunk in response.iter_content(chunk_size=8192):
#                             if chunk:
#                                 f.write(chunk)

#                     print(f"Saved to: captcha_audio.mp4")
#                     for i in range(3): 
#                         detected_text = solve_audio_captcha("captcha_audio.mp4") 
#                         print(f"Solved: {detected_text}")
#                         # input("continue : ")  # Uncomment to debug step-by-step
#                         input_box = new_frame.locator("input#audio-response")
#                         input_box.wait_for(state="visible", timeout=10000)
#                         input_box.fill(detected_text)
#                         input("continue : ")  # Uncomment to debug step-by-step
#                         page.wait_for_timeout(1000)
#                         page.keyboard.press("Enter")
#                         page.wait_for_timeout(5000)
                        
#                         break
#                     return True
#                 else : 
#                     print("Automation Detected")
#                     return False
#     except PlaywrightTimeoutError:
#         pass

#     return False


# def extract_all_products(html_content):
#     soup = BeautifulSoup(html_content, 'html.parser')
#     products = []
    
#     containers = soup.find_all('div', attrs={'data-gid': True, 'data-pid': True, 'data-cid': True})
    
#     for container in containers:
#         data_gid = container.get('data-gid')
#         data_pid = container.get('data-pid')
#         data_cid = container.get('data-cid')
        
#         name_element = container.find('div', class_=lambda c: c and 'gkQHve' in c)
#         name = name_element.get_text(strip=True) if name_element else None
        
#         price_element = container.find('span', class_='lmQWe')
#         price = price_element.get_text(strip=True) if price_element else None
        
#         seller_element = container.find('span', class_=lambda c: c and 'WJMUdc' in c)
#         seller_name = seller_element.get_text(strip=True) if seller_element else None
        
#         first_image_url = None
#         for img in container.find_all('img'):
#             src = img.get('src', '')
#             if src.startswith('https://'):
#                 first_image_url = src
#                 break

#         products.append({
#             'name': name,
#             'image_url': first_image_url,
#             'price': price,
#             'seller': seller_name,
#             'pid': data_pid,
#             'cid': data_cid,
#             'gid': data_gid
#         })
        
#     return products


# def main() -> int:
#     ap = argparse.ArgumentParser()
#     ap.add_argument("--urls", nargs="+", required=True, help="One or more URLs to process")
#     ap.add_argument("--out", default=os.path.join(os.getcwd(), "scraped_products.csv"))
#     ap.add_argument("--flush-every", type=int, default=25, help="Flush progress every N written rows")
#     args = ap.parse_args()

#     os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)

#     wrote = 0
#     processed = 0

#     # Wraps sync_playwright() inside Stealth().use_sync() for playwright-stealth >= 2.0.x
#     with Stealth().use_sync(sync_playwright()) as p:
#         # Launch Chromium visibly to allow debugging and seeing CAPTCHAs
#         browser = p.chromium.launch(headless=False)
        
#         context = browser.new_context(
#             viewport={"width": 1920, "height": 1080}
#         )
#         page = context.new_page()
        
#         with open(args.out, "w", newline="", encoding="utf-8") as out_f:
#             w = csv.DictWriter(out_f, fieldnames=OUT_FIELDS)
#             w.writeheader()
#             out_f.flush()

#             for url in args.urls:
#                 url = url.strip()
#                 if not url:
#                     continue

#                 processed += 1
#                 html = None
#                 try:
#                     for i in range(3) : 
#                         page.goto(url, wait_until="domcontentloaded", timeout=30000)
#                         page.wait_for_timeout(3000)
                        
#                         print("Checking for Captcha...")
#                         success = detect_recaptcha(page)
#                         if "sorry" in page.url : 
#                             print("Retrying..")
#                             continue
#                         if not success : continue
                    
#                         # 1. Handle Google's EU Cookie Consent popup (ID: L2AGLb usually maps to "Accept All")
#                         try:
#                             consent_button = page.locator("button#L2AGLb")
#                             if consent_button.is_visible(timeout=3000):
#                                 consent_button.click()
#                                 page.wait_for_load_state("domcontentloaded")
#                         except Exception:
#                             pass # No consent popup appeared, proceed normally
                        
#                         # 2. Scroll to the bottom to trigger lazy-loaded images
#                         page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
#                         page.wait_for_timeout(1500) 
                        
#                         html = page.content()
#                         break
#                 except PlaywrightTimeoutError:
#                     print(f"[warn] timeout fetching: {url}", file=sys.stderr)
#                     continue
#                 except Exception as e:
#                     print(f"[warn] fetch failed: {url} ({e})", file=sys.stderr)
#                     continue
#                 if not html : 
#                     print(f"Skipping url {url}")
#                     continue
#                 parsed_products = extract_all_products(html)
                
#                 if not parsed_products:
#                     print(f"[warn] No products found for {url}. Page might be blocked or structure changed.", file=sys.stderr)
#                     continue

#                 for prod in parsed_products:
#                     out_row = {
#                         "url": url,
#                         **prod
#                     }
#                     w.writerow(out_row)
#                     wrote += 1
                
#                 if wrote % max(1, args.flush_every) == 0:
#                     out_f.flush()
#                     print(f"[progress] wrote {wrote} rows (processed {processed} urls)")

#         browser.close()

#     print(f"Saved {wrote} rows to: {args.out}")
#     return 0

# if __name__ == "__main__":
#     sys.exit(main())
"""
Pipeline:
1) Accept a list of URLs directly via command line arguments.
2) For each URL, fetch HTML using Playwright wrapped in Stealth (v2.x).
3) Bypass Google Cookie Consent (if present) and scroll to load images.
4) Parse ALL products on the page into a list of dictionaries.
5) Write the consolidated data to a CSV.
"""

import argparse
import csv
import os
import sys
import math
import random
import time
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from playwright_stealth import Stealth # <-- Updated import for v2.0+
from solve_captch import solve_audio_captcha

OUT_FIELDS = [
    "url",
    "name",
    "image_url",
    "price",
    "seller",
    "pid",
    "cid",
    "gid"
]

def show_mouse_cursor(page):
    page.evaluate("""
    () => {
        if (document.getElementById('playwright-cursor')) return;

        const cursor = document.createElement('div');
        cursor.id = 'playwright-cursor';

        Object.assign(cursor.style, {
            position: 'fixed',
            width: '14px',
            height: '14px',
            background: 'red',
            border: '2px solid white',
            borderRadius: '50%',
            zIndex: '2147483647',
            pointerEvents: 'none',
            transform: 'translate(-50%, -50%)',
            left: '0px',
            top: '0px'
        });

        document.body.appendChild(cursor);

        document.addEventListener('mousemove', e => {
            cursor.style.left = e.clientX + 'px';
            cursor.style.top = e.clientY + 'px';
        });
    }
    """)
    
def human_mouse_move(page, min_seconds=2, max_seconds=5):
    show_mouse_cursor(page)
    duration = random.uniform(min_seconds, max_seconds)

    viewport = page.viewport_size

    if not viewport:
        viewport = page.evaluate("""
            () => ({
                width: window.innerWidth,
                height: window.innerHeight
            })
        """)

    width = viewport["width"]
    height = viewport["height"]

    current_x = random.randint(100, max(101, width - 100))
    current_y = random.randint(100, max(101, height - 100))

    page.mouse.move(current_x, current_y)

    start_time = time.time()

    while time.time() - start_time < duration:
        distance_x = random.randint(-300, 300)
        distance_y = random.randint(-200, 200)

        target_x = max(30, min(width - 30, current_x + distance_x))
        target_y = max(30, min(height - 30, current_y + distance_y))

        control_x = (current_x + target_x) / 2 + random.randint(-80, 80)
        control_y = (current_y + target_y) / 2 + random.randint(-80, 80)

        steps = random.randint(60, 120)

        for i in range(1, steps + 1):
            if time.time() - start_time >= duration:
                return

            t = i / steps
            eased_t = (1 - math.cos(math.pi * t)) / 2

            x = (
                (1 - eased_t) ** 2 * current_x
                + 2 * (1 - eased_t) * eased_t * control_x
                + eased_t ** 2 * target_x
            )

            y = (
                (1 - eased_t) ** 2 * current_y
                + 2 * (1 - eased_t) * eased_t * control_y
                + eased_t ** 2 * target_y
            )

            x += random.uniform(-0.5, 0.5)
            y += random.uniform(-0.5, 0.5)

            x = max(2, min(width - 2, x))
            y = max(2, min(height - 2, y))

            page.mouse.move(x, y)
            time.sleep(random.uniform(0.012, 0.025))

        current_x = target_x
        current_y = target_y

        if random.random() < 0.60:
            time.sleep(random.uniform(0.10, 0.40))       

def find_recaptcha_frame(page, match):
    iframes = page.locator("iframe")
    for i in range(iframes.count()):
        iframe = iframes.nth(i)
        title = iframe.get_attribute("title") or ""
        if match in title:
            return iframe.content_frame
    return None

def detect_recaptcha(page):
    frame = find_recaptcha_frame(page,"reCAPTCHA")

    if not frame:
        print("No reCAPTCHA iframe found")
        return False

    try:
        checkbox = frame.locator("div.recaptcha-checkbox-border")

        if checkbox.count() > 0:
            human_mouse_move(page,2,3)
            checkbox.first.click()
            print("reCAPTCHA detected")
            human_mouse_move(page,2,5)
            
            new_frame = find_recaptcha_frame(page,"recaptcha challenge")
            if not new_frame:
                print("No challenge iframe found")
                return False
            audio_button = new_frame.locator("button.rc-button-audio")
            if audio_button.count() > 0:
                audio_button.first.click()
                print("Audio button clicked")
                human_mouse_move(page,2,5)
                
                new_frame_2 = find_recaptcha_frame(page,"recaptcha challenge")
                if not new_frame_2:
                    print("No challenge 2 iframe found")
                    return False
                locator = new_frame_2.locator("div.rc-doscaptcha-body-text")
                locator.wait_for(state="visible", timeout=10000)

                captcha_text = locator.inner_text()
                print(captcha_text)
                a_tag = new_frame_2.locator("a.rc-audiochallenge-tdownload-link")
                if a_tag.count() > 0:
                    url = a_tag.get_attribute("href")
                    if not url:
                        print("No href found")
                        return False
                    print("Download URL:", url)
                    response = requests.get(url, stream=True, timeout=60)
                    response.raise_for_status()

                    with open("captcha_audio.mp4", "wb") as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)

                    print(f"Saved to: captcha_audio.mp4")
                    for i in range(3): 
                        detected_text = solve_audio_captcha("captcha_audio.mp4") 
                        print(f"Solved: {detected_text}")
                        # input("continue : ")  # Uncomment to debug step-by-step
                        input_box = new_frame.locator("input#audio-response")
                        input_box.wait_for(state="visible", timeout=10000)
                        input_box.fill(detected_text)
                        page.wait_for_timeout(1000)
                        page.keyboard.press("Enter")
                        page.wait_for_timeout(5000)
                        
                        break
                    return True
                else : 
                    print("Automation Detected")
                    return False
    except PlaywrightTimeoutError:
        pass

    return False


def extract_all_products(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    products = []
    
    containers = soup.find_all('div', attrs={'data-gid': True, 'data-pid': True, 'data-cid': True})
    
    for container in containers:
        data_gid = container.get('data-gid')
        data_pid = container.get('data-pid')
        data_cid = container.get('data-cid')
        
        name_element = container.find('div', class_=lambda c: c and 'gkQHve' in c)
        name = name_element.get_text(strip=True) if name_element else None
        
        price_element = container.find('span', class_='lmQWe')
        price = price_element.get_text(strip=True) if price_element else None
        
        seller_element = container.find('span', class_=lambda c: c and 'WJMUdc' in c)
        seller_name = seller_element.get_text(strip=True) if seller_element else None
        
        first_image_url = None
        for img in container.find_all('img'):
            src = img.get('src', '')
            if src.startswith('https://'):
                first_image_url = src
                break

        products.append({
            'name': name,
            'image_url': first_image_url,
            'price': price,
            'seller': seller_name,
            'pid': data_pid,
            'cid': data_cid,
            'gid': data_gid
        })
        
    return products



def load_urls(url_args):
    """
    Load URLs from command-line arguments.

    Supports:
      --urls https://example.com https://example2.com

    Or a CSV chunk:
      --urls chunks/urls_0.csv

    CSV URL columns supported:
      product_url
      url
    """
    urls = []

    for value in url_args:
        value = value.strip()

        if not value:
            continue

        if os.path.isfile(value):
            print(f"Loading URLs from CSV: {value}")

            with open(value, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)

                if not reader.fieldnames:
                    print(f"[warn] CSV has no header: {value}", file=sys.stderr)
                    continue

                print(f"CSV columns: {reader.fieldnames}")

                for row in reader:
                    url = row.get("product_url") or row.get("url")

                    if not url:
                        continue

                    url = url.strip()

                    if url.startswith(("http://", "https://")):
                        urls.append(url)
                    else:
                        print(f"[warn] Invalid URL in CSV: {url}", file=sys.stderr)

            continue

        if value.startswith(("http://", "https://")):
            urls.append(value)
        else:
            print(f"[warn] Invalid URL or file: {value}", file=sys.stderr)

    return urls

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--urls", nargs="+", required=True, help="One or more URLs to process")
    ap.add_argument("--out", default=os.path.join(os.getcwd(), "scraped_products.csv"))
    ap.add_argument("--flush-every", type=int, default=25, help="Flush progress every N written rows")
    args = ap.parse_args()

    urls = load_urls(args.urls)
    print(f"Loaded {len(urls)} URLs")

    if not urls:
        print("No valid URLs found.", file=sys.stderr)
        return 1

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)

    wrote = 0
    processed = 0

    # Wraps sync_playwright() inside Stealth().use_sync() for playwright-stealth >= 2.0.x
    with Stealth().use_sync(sync_playwright()) as p:
        # Launch Chromium visibly to allow debugging and seeing CAPTCHAs
        browser = p.chromium.launch(headless=False)
        
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080}
        )
        page = context.new_page()
        
        with open(args.out, "w", newline="", encoding="utf-8") as out_f:
            w = csv.DictWriter(out_f, fieldnames=OUT_FIELDS)
            w.writeheader()
            out_f.flush()

            for url in urls:
                url = url.strip()
                if not url:
                    continue

                processed += 1
                html = None
                try:
                    for i in range(3) : 
                        page.goto(url, wait_until="domcontentloaded", timeout=30000)
                        page.wait_for_timeout(3000)
                        
                        print("Checking for Captcha...")

                        recaptcha_frame = find_recaptcha_frame(page, "reCAPTCHA")

                        if recaptcha_frame:
                            print("reCAPTCHA challenge detected.")
                            # Existing handler may attempt the challenge. If it cannot
                            # complete it, skip this attempt rather than scraping a
                            # challenge page as product content.
                            success = detect_recaptcha(page)

                            if not success:
                                print("reCAPTCHA was not completed. Retrying...")
                                continue

                            page.wait_for_timeout(2000)

                            if find_recaptcha_frame(page, "reCAPTCHA") or "sorry" in page.url:
                                print("reCAPTCHA/block page still present. Retrying...")
                                continue
                        else:
                            print("No reCAPTCHA detected. Continuing normally.")
                            
                        if "sorry" in page.url:
                            print("Google block page detected. Retrying...")
                            continue
                        # 1. Handle Google's EU Cookie Consent popup (ID: L2AGLb usually maps to "Accept All")
                        try:
                            consent_button = page.locator("button#L2AGLb")
                            if consent_button.is_visible(timeout=3000):
                                consent_button.click()
                                page.wait_for_load_state("domcontentloaded")
                        except Exception:
                            pass # No consent popup appeared, proceed normally
                        
                        # 2. Scroll to the bottom to trigger lazy-loaded images
                        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        page.wait_for_timeout(1500) 
                        
                        html = page.content()
                        break
                except PlaywrightTimeoutError:
                    print(f"[warn] timeout fetching: {url}", file=sys.stderr)
                    continue
                except Exception as e:
                    print(f"[warn] fetch failed: {url} ({e})", file=sys.stderr)
                    continue
                if not html : 
                    print(f"Skipping url {url}")
                    continue
                parsed_products = extract_all_products(html)
                
                if not parsed_products:
                    print(f"[warn] No products found for {url}. Page might be blocked or structure changed.", file=sys.stderr)
                    continue

                for prod in parsed_products:
                    out_row = {
                        "url": url,
                        **prod
                    }
                    w.writerow(out_row)
                    wrote += 1
                
                if wrote % max(1, args.flush_every) == 0:
                    out_f.flush()
                    print(f"[progress] wrote {wrote} rows (processed {processed} urls)")

        browser.close()

    print(f"Saved {wrote} rows to: {args.out}")
    return 0

if __name__ == "__main__":
    sys.exit(main())