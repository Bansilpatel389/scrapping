# """
# Pipeline:
# 1) Accept a list of URLs directly via command line arguments or CSV chunks.
# 2) For each URL, fetch HTML using Selenium + Chrome.
# 3) Handle Google Cookie Consent (if present) and scroll to load images.
# 4) Parse ALL products on the page into a list of dictionaries.
# 5) Write consolidated data to CSV.
# 6) Save URLs that return no product data to --pending-out.

# Note:
# - reCAPTCHA/block pages are detected and treated as pending when unsolved.
# - This script attempts audio CAPTCHA solving when a challenge appears;
#   success is not guaranteed and unsolved URLs go to pending.
# """

# from __future__ import annotations

# import argparse
# import atexit
# import csv
# import logging
# import os
# import random
# import re
# import sys
# import tempfile
# import time
# from typing import Any

# import requests
# import undetected_chromedriver as uc
# from bs4 import BeautifulSoup
# from selenium.common.exceptions import (
#     NoSuchElementException,
#     StaleElementReferenceException,
#     TimeoutException,
#     WebDriverException,
# )
# from selenium.webdriver.common.action_chains import ActionChains
# from selenium.webdriver.common.by import By
# from selenium.webdriver.common.keys import Keys
# from selenium.webdriver.support import expected_conditions as EC
# from selenium.webdriver.support.ui import WebDriverWait

# from solve_captch import solve_audio_captcha

# # ---------------------------------------------------------------------------
# # Logging
# # ---------------------------------------------------------------------------

# logging.basicConfig(
#     level=logging.INFO,
#     format="%(asctime)s [%(levelname)s] %(message)s",
#     datefmt="%Y-%m-%d %H:%M:%S",
#     stream=sys.stdout,
# )
# log = logging.getLogger("collect_set")

# OUT_FIELDS = [
#     "url",
#     "name",
#     "image_url",
#     "price",
#     "seller",
#     "pid",
#     "cid",
#     "gid",
# ]

# # Temporary files created during CAPTCHA solving; cleaned on exit.
# _TEMP_FILES: list[str] = []


# def _cleanup_temp_files() -> None:
#     for path in _TEMP_FILES:
#         try:
#             if os.path.isfile(path):
#                 os.remove(path)
#         except OSError:
#             pass


# atexit.register(_cleanup_temp_files)


# # ---------------------------------------------------------------------------
# # Consent / session helpers
# # ---------------------------------------------------------------------------

# def accept_google_consent_if_present(driver) -> bool:
#     consent_selectors = [
#         (By.XPATH, "//button[.//div[normalize-space()='Accept all'] or normalize-space()='Accept all']"),
#         (By.XPATH, "//button[.//div[normalize-space()='I agree'] or normalize-space()='I agree']"),
#         (By.XPATH, "//div[@role='button'][normalize-space()='Accept all' or normalize-space()='I agree']"),
#         (By.ID, "L2AGLb"),
#     ]
#     for by, selector in consent_selectors:
#         try:
#             button = WebDriverWait(driver, 4).until(
#                 EC.element_to_be_clickable((by, selector))
#             )
#             driver.execute_script("arguments[0].click();", button)
#             time.sleep(random.uniform(1.0, 2.0))
#             return True
#         except Exception:
#             continue
#     return False


# def warm_google_session(driver) -> None:
#     try:
#         driver.get("https://www.google.com/ncr")
#         time.sleep(random.uniform(2.0, 3.5))
#         accept_google_consent_if_present(driver)

#         try:
#             search_box = WebDriverWait(driver, 5).until(
#                 EC.presence_of_element_located((By.NAME, "q"))
#             )
#             search_box.click()
#             time.sleep(random.uniform(0.4, 0.9))
#             search_box.send_keys("furniture")
#             time.sleep(random.uniform(0.3, 0.7))
#             search_box.send_keys(Keys.ENTER)
#             time.sleep(random.uniform(2.0, 3.5))
#         except Exception:
#             pass

#         try:
#             driver.execute_script(
#                 "window.scrollBy(0, Math.max(300, window.innerHeight * 0.35));"
#             )
#             time.sleep(random.uniform(0.8, 1.4))
#         except Exception:
#             pass
#     except Exception as exc:
#         log.warning("Session warm-up skipped: %s", exc)


# # ---------------------------------------------------------------------------
# # Fingerprint normalisation
# # ---------------------------------------------------------------------------

# def parse_platform_from_user_agent(user_agent: str) -> tuple[str, str]:
#     ua = (user_agent or "").lower()
#     if "windows" in ua:
#         return "Windows", "Win32"
#     if "mac os x" in ua or "macintosh" in ua:
#         return "macOS", "MacIntel"
#     return "Linux", "Linux x86_64"


# def build_user_agent_metadata(user_agent: str, platform_name: str) -> dict | None:
#     match = re.search(r"Chrome/(\d+)\.(\d+)\.(\d+)\.(\d+)", user_agent or "")
#     if not match:
#         return None

#     major = match.group(1)
#     full_version = ".".join(match.groups())
#     return {
#         "brands": [
#             {"brand": "Not/A)Brand", "version": "8"},
#             {"brand": "Chromium", "version": major},
#             {"brand": "Google Chrome", "version": major},
#         ],
#         "fullVersionList": [
#             {"brand": "Not/A)Brand", "version": "8.0.0.0"},
#             {"brand": "Chromium", "version": full_version},
#             {"brand": "Google Chrome", "version": full_version},
#         ],
#         "fullVersion": full_version,
#         "platform": platform_name,
#         "platformVersion": "10.0.0" if platform_name == "Windows" else "0.0.0",
#         "architecture": "x86",
#         "model": "",
#         "mobile": False,
#         "bitness": "64",
#         "wow64": False,
#     }


# def normalize_driver_fingerprint(driver) -> None:
#     accept_language = os.environ.get("BROWSER_ACCEPT_LANGUAGE", "en-US,en;q=0.9")
#     timezone_id = os.environ.get("BROWSER_TIMEZONE", "America/New_York")
#     locale = accept_language.split(",")[0].strip() or "en-US"

#     try:
#         browser_version = driver.execute_cdp_cmd("Browser.getVersion", {})
#     except Exception as exc:
#         log.warning("Fingerprint normalization skipped: %s", exc)
#         return

#     raw_user_agent = browser_version.get("userAgent", "") or ""
#     user_agent = raw_user_agent.replace("HeadlessChrome/", "Chrome/")
#     platform_name, navigator_platform = parse_platform_from_user_agent(user_agent)
#     metadata = build_user_agent_metadata(user_agent, platform_name)

#     try:
#         driver.execute_cdp_cmd("Network.enable", {})
#     except Exception:
#         pass

#     ua_override: dict[str, Any] = {
#         "userAgent": user_agent,
#         "acceptLanguage": accept_language,
#         "platform": navigator_platform,
#     }
#     if metadata:
#         ua_override["userAgentMetadata"] = metadata

#     try:
#         driver.execute_cdp_cmd("Network.setUserAgentOverride", ua_override)
#     except Exception as exc:
#         log.warning("User agent override skipped: %s", exc)

#     try:
#         driver.execute_cdp_cmd("Emulation.setLocaleOverride", {"locale": locale})
#     except Exception as exc:
#         log.warning("Locale override skipped: %s", exc)

#     try:
#         driver.execute_cdp_cmd("Emulation.setTimezoneOverride", {"timezoneId": timezone_id})
#     except Exception as exc:
#         log.warning("Timezone override skipped: %s", exc)

#     script = f"""
# Object.defineProperty(navigator, 'webdriver', {{
#   get: () => undefined,
# }});
# Object.defineProperty(navigator, 'languages', {{
#   get: () => ['en-US', 'en'],
# }});
# Object.defineProperty(navigator, 'platform', {{
#   get: () => '{navigator_platform}',
# }});
# Object.defineProperty(navigator, 'hardwareConcurrency', {{
#   get: () => 8,
# }});
# Object.defineProperty(navigator, 'deviceMemory', {{
#   get: () => 8,
# }});
# Object.defineProperty(navigator, 'plugins', {{
#   get: () => [1, 2, 3, 4, 5],
# }});
# window.chrome = window.chrome || {{
#   runtime: {{}},
#   app: {{}},
# }};
# """
#     try:
#         driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": script})
#     except Exception as exc:
#         log.warning("Preload fingerprint script skipped: %s", exc)


# # ---------------------------------------------------------------------------
# # Driver lifecycle
# # ---------------------------------------------------------------------------

# def _detect_chrome_major() -> int | None:
#     """Best-effort detection of installed Chrome major version."""
#     chrome_bin = os.environ.get("CHROME_BIN") or os.environ.get("CHROME_PATH") or "google-chrome"
#     try:
#         import subprocess

#         out = subprocess.check_output(
#             [chrome_bin, "--version"],
#             stderr=subprocess.STDOUT,
#             text=True,
#             timeout=10,
#         )
#         m = re.search(r"(\d+)\.\d+\.\d+\.\d+", out)
#         if m:
#             return int(m.group(1))
#     except Exception as exc:
#         log.debug("Could not detect Chrome version via CLI: %s", exc)
#     return None


# def setup_driver(max_attempts: int = 3, base_delay: float = 4.0):
#     last_err: Exception | None = None
#     version_main = _detect_chrome_major()

#     for attempt in range(1, max_attempts + 1):
#         driver = None
#         try:
#             time.sleep(1.5)
#             options = uc.ChromeOptions()
#             chrome_bin = os.environ.get("CHROME_BIN") or os.environ.get("CHROME_PATH")
#             if chrome_bin:
#                 options.binary_location = chrome_bin

#             # Prefer headless in CI; allow override via env for local debug.
#             # if os.environ.get("HEADLESS", "1").lower() in ("1", "true", "yes"):
#                 # options.add_argument("--headless=new")

#             options.add_argument("--no-sandbox")
#             options.add_argument("--disable-dev-shm-usage")
#             options.add_argument("--disable-logging")
#             options.add_argument("--log-level=3")
#             options.add_argument("--window-size=1366,768")
#             options.add_argument("--lang=en-US")
#             options.add_argument("--disable-notifications")
#             options.add_argument("--disable-blink-features=AutomationControlled")

#             kwargs: dict[str, Any] = {"options": options, "use_subprocess": True}
#             if version_main:
#                 kwargs["version_main"] = version_main
#                 log.info("Starting Chrome with version_main=%s", version_main)
#             else:
#                 log.info("Starting Chrome with auto version detection")

#             driver = uc.Chrome(**kwargs)
#             normalize_driver_fingerprint(driver)
#             warm_google_session(driver)
#             return driver
#         except Exception as e:
#             last_err = e
#             log.warning(
#                 "Driver start failed (attempt %s/%s): %s",
#                 attempt,
#                 max_attempts,
#                 e,
#             )
#             try:
#                 if driver is not None:
#                     driver.quit()
#             except Exception:
#                 pass
#             if attempt < max_attempts:
#                 time.sleep(base_delay * attempt + random.uniform(0, 2))

#     if last_err:
#         raise last_err
#     raise RuntimeError("Driver start failed with unknown error")


# def is_driver_alive(driver) -> bool:
#     if driver is None:
#         return False
#     try:
#         _ = driver.current_url
#         driver.execute_script("return 1")
#         return True
#     except Exception as exc:
#         log.warning("[BROWSER] Driver is not alive: %s", exc)
#         return False


# def ensure_driver_alive(driver):
#     if is_driver_alive(driver):
#         return driver

#     log.warning("[BROWSER] Restarting dead driver...")
#     try:
#         if driver is not None:
#             driver.quit()
#     except Exception:
#         pass

#     driver = setup_driver()
#     log.info("[BROWSER] Driver restarted successfully.")
#     return driver


# # ---------------------------------------------------------------------------
# # Human-like interaction (debug / parity only)
# # ---------------------------------------------------------------------------

# def human_mouse_move(driver, min_seconds: float = 2, max_seconds: float = 5) -> None:
#     duration = random.uniform(min_seconds, max_seconds)
#     start_time = time.time()

#     try:
#         width = driver.execute_script(
#             "return Math.max(document.documentElement.clientWidth || 0, window.innerWidth || 0);"
#         )
#         height = driver.execute_script(
#             "return Math.max(document.documentElement.clientHeight || 0, window.innerHeight || 0);"
#         )
#     except Exception:
#         width, height = 1920, 1080

#     width = max(int(width or 1920), 200)
#     height = max(int(height or 1080), 200)

#     try:
#         body = driver.find_element(By.TAG_NAME, "body")
#         ActionChains(driver).move_to_element_with_offset(
#             body,
#             random.randint(20, min(300, width - 20)),
#             random.randint(20, min(300, height - 20)),
#         ).perform()
#     except Exception:
#         return

#     while time.time() - start_time < duration:
#         dx = random.randint(-100, 100)
#         dy = random.randint(-80, 80)
#         try:
#             ActionChains(driver).move_by_offset(dx, dy).perform()
#         except Exception:
#             try:
#                 body = driver.find_element(By.TAG_NAME, "body")
#                 ActionChains(driver).move_to_element_with_offset(
#                     body,
#                     random.randint(10, min(250, width - 10)),
#                     random.randint(10, min(250, height - 10)),
#                 ).perform()
#             except Exception:
#                 break
#         time.sleep(random.uniform(0.05, 0.15))


# # ---------------------------------------------------------------------------
# # reCAPTCHA detection / attempt (UNCHANGED per request)
# # ---------------------------------------------------------------------------

# def find_recaptcha_frame(driver, match):
#     """
#     Find an iframe whose title contains `match` and switch to it.
#     Returns True if switched successfully, False otherwise.
#     Always switches back to default content first.
#     """
#     driver.switch_to.default_content()
#     iframes = driver.find_elements(By.TAG_NAME, "iframe")
#     for iframe in iframes:
#         title = iframe.get_attribute("title") or ""
#         if match in title:
#             driver.switch_to.frame(iframe)
#             return True
#     return False


# def detect_recaptcha(driver):
#     # 1. Find and switch to the main reCAPTCHA iframe
#     if not find_recaptcha_frame(driver, "reCAPTCHA"):
#         print("No reCAPTCHA iframe found")
#         return False

#     try:
#         # 2. Click the checkbox
#         checkboxes = driver.find_elements(By.CSS_SELECTOR, "div.recaptcha-checkbox-border")
#         if not checkboxes:
#             print("Checkbox not found")
#             driver.switch_to.default_content()
#             return False

#         # Optional: human-like mouse movement (keep your existing helper)
#         # human_mouse_move(driver, 2, 3)

#         checkboxes[0].click()
#         print("reCAPTCHA detected")
#         # human_mouse_move(driver, 2, 5)

#         # 3. Switch to the challenge iframe
#         if not find_recaptcha_frame(driver, "recaptcha challenge"):
#             print("No challenge iframe found")
#             return False

#         # 4. Click the audio button
#         audio_buttons = driver.find_elements(By.CSS_SELECTOR, "button.rc-button-audio")
#         if not audio_buttons:
#             print("Audio button not found")
#             driver.switch_to.default_content()
#             return False

#         audio_buttons[0].click()
#         print("Audio button clicked")
#         # human_mouse_move(driver, 2, 5)

#         # 5. Stay in / re-find the challenge iframe (sometimes it refreshes)
#         if not find_recaptcha_frame(driver, "recaptcha challenge"):
#             print("No challenge 2 iframe found")
#             return False

#         # Optional: read the doscaptcha text
#         try:
#             locator = WebDriverWait(driver, 10).until(
#                 EC.visibility_of_element_located((By.CSS_SELECTOR, "div.rc-doscaptcha-body-text"))
#             )
#             captcha_text = locator.text
#             print(captcha_text)
#         except TimeoutException:
#             pass

#         # 6. Get the audio download link
#         a_tags = driver.find_elements(By.CSS_SELECTOR, "a.rc-audiochallenge-tdownload-link")
#         if not a_tags:
#             print("Automation Detected")
#             driver.switch_to.default_content()
#             return False

#         url = a_tags[0].get_attribute("href")
#         if not url:
#             print("No href found")
#             driver.switch_to.default_content()
#             return False

#         print("Download URL:", url)

#         # Download the audio
#         response = requests.get(url, stream=True, timeout=60)
#         response.raise_for_status()
#         with open("captcha_audio.mp4", "wb") as f:
#             for chunk in response.iter_content(chunk_size=8192):
#                 if chunk:
#                     f.write(chunk)
#         print("Saved to: captcha_audio.mp4")

#         # 7. Solve and submit (up to 3 attempts)
#         for i in range(3):
#             detected_text = solve_audio_captcha("captcha_audio.mp4")
#             print(f"Solved: {detected_text}")

#             # Make sure we are still in the challenge frame
#             if not find_recaptcha_frame(driver, "recaptcha challenge"):
#                 print("Lost challenge frame")
#                 return False

#             input_box = WebDriverWait(driver, 10).until(
#                 EC.visibility_of_element_located((By.CSS_SELECTOR, "input#audio-response"))
#             )
#             input_box.clear()
#             input_box.send_keys(detected_text)

#             time.sleep(1)
#             input_box.send_keys(Keys.ENTER)   # or driver.find_element(...).click() on the verify button
#             time.sleep(5)

#             break   # keep the same early-break logic you had

#         driver.switch_to.default_content()
#         return True

#     except (TimeoutException, NoSuchElementException) as e:
#         print(f"Exception: {e}")
#         driver.switch_to.default_content()
#         return False


# # ---------------------------------------------------------------------------
# # Parsing
# # ---------------------------------------------------------------------------

# def extract_all_products(html_content: str) -> list[dict]:
#     soup = BeautifulSoup(html_content, "html.parser")
#     products: list[dict] = []

#     containers = soup.find_all(
#         "div",
#         attrs={"data-gid": True, "data-pid": True, "data-cid": True},
#     )

#     for container in containers:
#         data_gid = container.get("data-gid")
#         data_pid = container.get("data-pid")
#         data_cid = container.get("data-cid")

#         name_element = container.find(
#             "div",
#             class_=lambda c: c and "gkQHve" in c,
#         )
#         name = name_element.get_text(strip=True) if name_element else None

#         price_element = container.find("span", class_="lmQWe")
#         price = price_element.get_text(strip=True) if price_element else None

#         seller_element = container.find(
#             "span",
#             class_=lambda c: c and "WJMUdc" in c,
#         )
#         seller_name = (
#             seller_element.get_text(strip=True) if seller_element else None
#         )

#         first_image_url = None
#         for img in container.find_all("img"):
#             src = img.get("src", "")
#             if src.startswith("https://"):
#                 first_image_url = src
#                 break

#         products.append(
#             {
#                 "name": name,
#                 "image_url": first_image_url,
#                 "price": price,
#                 "seller": seller_name,
#                 "pid": data_pid,
#                 "cid": data_cid,
#                 "gid": data_gid,
#             }
#         )

#     log.info("Found %s products", len(products))
#     return products


# # ---------------------------------------------------------------------------
# # URL loading
# # ---------------------------------------------------------------------------

# def load_urls(url_args: list[str]) -> list[str]:
#     """
#     Load URLs from command-line arguments.

#     Supports:
#       --urls https://example.com https://example2.com
#     Or a CSV chunk:
#       --urls chunks/urls_0.csv

#     CSV URL columns supported: product_url, url
#     """
#     urls: list[str] = []

#     for value in url_args:
#         value = value.strip()
#         if not value:
#             continue

#         if os.path.isfile(value):
#             log.info("Loading URLs from CSV: %s", value)
#             with open(value, "r", encoding="utf-8-sig") as f:
#                 reader = csv.DictReader(f)
#                 if not reader.fieldnames:
#                     log.warning("CSV has no header: %s", value)
#                     continue
#                 log.info("CSV columns: %s", reader.fieldnames)
#                 for row in reader:
#                     url = (row.get("product_url") or row.get("url") or "").strip()
#                     if not url:
#                         continue
#                     if url.startswith(("http://", "https://")):
#                         urls.append(url)
#                     else:
#                         log.warning("Invalid URL in CSV: %s", url)
#             continue

#         if value.startswith(("http://", "https://")):
#             urls.append(value)
#         else:
#             log.warning("Invalid URL or file: %s", value)

#     # Preserve order, drop exact duplicates
#     seen: set[str] = set()
#     deduped: list[str] = []
#     for u in urls:
#         if u not in seen:
#             seen.add(u)
#             deduped.append(u)
#     return deduped


# def print_public_ip() -> str | None:
#     try:
#         response = requests.get("https://api.ipify.org?format=json", timeout=10)
#         response.raise_for_status()
#         ip = response.json().get("ip")
#         log.info("[NETWORK] Public IP: %s", ip)
#         return ip
#     except Exception as e:
#         log.warning("[NETWORK] Could not get public IP: %s", e)
#         return None


# # ---------------------------------------------------------------------------
# # Page fetch with retries
# # ---------------------------------------------------------------------------

# def fetch_page_html(driver, url: str, max_attempts: int = 3) -> str | None:
#     """
#     Navigate to url, handle consent / CAPTCHA, scroll, and return page source.
#     Returns None when the page could not be loaded or yielded no usable content.
#     """
#     for attempt in range(1, max_attempts + 1):
#         driver = ensure_driver_alive(driver)
#         log.info("Fetching URL attempt %s/%s: %s", attempt, max_attempts, url)

#         try:
#             driver.get(url)
#         except TimeoutException:
#             log.warning("Page load timeout: %s", url)
#             try:
#                 driver.execute_script("window.stop();")
#             except Exception:
#                 pass
#         except WebDriverException as e:
#             log.warning("WebDriver get failed: %s (%s)", url, e)
#             continue

#         time.sleep(3)

#         # CAPTCHA / block page
#         if detect_recaptcha(driver):
#             log.warning("reCAPTCHA/block page present. Retrying...")
#             continue

#         # Cookie consent (covers both warm-up residual and EU banner)
#         accept_google_consent_if_present(driver)
#         try:
#             WebDriverWait(driver, 5).until(
#                 lambda d: d.execute_script("return document.readyState")
#                 in ("interactive", "complete")
#             )
#         except Exception:
#             pass

#         # Scroll to trigger lazy-loaded images / product cards
#         try:
#             driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
#             time.sleep(0.8)
#             driver.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.5);")
#             time.sleep(0.5)
#             driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
#         except Exception:
#             pass

#         time.sleep(1.5)

#         # Wait for at least one product container (reduces false "no products")
#         try:
#             WebDriverWait(driver, 10).until(
#                 EC.presence_of_element_located(
#                     (By.CSS_SELECTOR, "div[data-gid][data-pid][data-cid]")
#                 )
#             )
#         except TimeoutException:
#             log.warning("No product containers appeared within timeout for %s", url)

#         # Second CAPTCHA check after scroll/consent
#         if detect_recaptcha(driver):
#             log.warning("Challenge appeared after navigation. Retrying...")
#             continue

#         html = driver.page_source
#         if html and len(html) > 500:
#             log.info("Page loaded successfully (%s chars).", len(html))
#             return html

#         log.warning("Empty or tiny page source on attempt %s", attempt)

#     return None


# # ---------------------------------------------------------------------------
# # Main
# # ---------------------------------------------------------------------------

# def main() -> int:
#     ap = argparse.ArgumentParser(
#         description="Scrape Google Shopping product sets from a list of URLs."
#     )
#     ap.add_argument(
#         "--urls",
#         nargs="+",
#         required=True,
#         help="One or more URLs, or path(s) to CSV chunk files",
#     )
#     ap.add_argument(
#         "--out",
#         default=os.path.join(os.getcwd(), "scraped_products.csv"),
#         help="Output CSV path for successful product rows",
#     )
#     ap.add_argument(
#         "--pending-out",
#         default=None,
#         help="CSV file for URLs that returned no product data",
#     )
#     ap.add_argument(
#         "--flush-every",
#         type=int,
#         default=25,
#         help="Flush progress every N written rows",
#     )
#     args = ap.parse_args()

#     print_public_ip()

#     urls = load_urls(args.urls)
#     log.info("Loaded %s URLs", len(urls))

#     if not urls:
#         log.error("No valid URLs found.")
#         return 1

#     out_dir = os.path.dirname(args.out) or "."
#     os.makedirs(out_dir, exist_ok=True)

#     wrote = 0
#     processed = 0
#     pending_urls: list[str] = []
#     driver = None

#     try:
#         driver = setup_driver()

#         with open(args.out, "w", newline="", encoding="utf-8") as out_f:
#             writer = csv.DictWriter(out_f, fieldnames=OUT_FIELDS)
#             writer.writeheader()
#             out_f.flush()

#             for url in urls:
#                 url = url.strip()
#                 if not url:
#                     continue

#                 processed += 1
#                 html = None

#                 try:
#                     html = fetch_page_html(driver, url, max_attempts=3)
#                 except TimeoutException:
#                     log.warning("Timeout fetching: %s", url)
#                 except WebDriverException as e:
#                     log.warning("WebDriver failed: %s (%s)", url, e)
#                 except Exception as e:
#                     log.warning("Fetch failed: %s (%s)", url, e)

#                 if not html:
#                     log.warning("Skipping url (no HTML): %s", url)
#                     pending_urls.append(url)
#                     continue

#                 parsed_products = extract_all_products(html)

#                 if not parsed_products:
#                     log.warning(
#                         "No products found for %s. Page might be blocked or structure changed.",
#                         url,
#                     )
#                     pending_urls.append(url)
#                     continue

#                 for prod in parsed_products:
#                     writer.writerow({"url": url, **prod})
#                     wrote += 1

#                 if wrote % max(1, args.flush_every) == 0:
#                     out_f.flush()
#                     log.info(
#                         "[progress] wrote %s rows (processed %s urls)",
#                         wrote,
#                         processed,
#                     )

#             out_f.flush()

#     finally:
#         if driver is not None:
#             try:
#                 driver.quit()
#             except Exception:
#                 pass

#     # Write pending URLs (deduplicated, order preserved)
#     if args.pending_out:
#         pending_dir = os.path.dirname(args.pending_out) or "."
#         os.makedirs(pending_dir, exist_ok=True)

#         pending_urls = list(dict.fromkeys(pending_urls))

#         with open(args.pending_out, "w", newline="", encoding="utf-8") as pending_f:
#             pending_writer = csv.writer(pending_f)
#             pending_writer.writerow(["product_url"])
#             for pending_url in pending_urls:
#                 pending_writer.writerow([pending_url])

#         log.info(
#             "Saved %s pending URLs to: %s",
#             len(pending_urls),
#             args.pending_out,
#         )

#     log.info("Saved %s rows to: %s", wrote, args.out)

#     # Non-zero exit when a large fraction failed — surfaces problems in CI
#     if processed > 0 and len(pending_urls) / processed > 0.85 and wrote == 0:
#         log.error(
#             "High failure rate: %s/%s URLs pending and 0 rows written.",
#             len(pending_urls),
#             processed,
#         )
#         return 2

#     return 0


# if __name__ == "__main__":
#     sys.exit(main())

"""
Pipeline:
1) Accept a list of URLs directly via command line arguments or CSV chunks.
2) For each URL, fetch HTML using Selenium + Chrome.
3) Handle Google Cookie Consent (if present) and scroll to load images.
4) Parse ALL products on the page into a list of dictionaries.
5) Write consolidated data to CSV.
6) Save URLs that return no product data to --pending-out.

Note:
- reCAPTCHA/block pages are detected and treated as pending when unsolved.
- This script attempts audio CAPTCHA solving when a challenge appears;
  success is not guaranteed and unsolved URLs go to pending.
"""

from __future__ import annotations

import argparse
import atexit
import csv
import logging
import os
import random
import re
import sys
import tempfile
import time
import uuid
from typing import Any

import requests
import undetected_chromedriver as uc
from bs4 import BeautifulSoup
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from solve_captch import solve_audio_captcha

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
log = logging.getLogger("collect_set")

OUT_FIELDS = [
    "url",
    "name",
    "image_url",
    "price",
    "seller",
    "pid",
    "cid",
    "gid",
]

# Temporary files created during CAPTCHA solving; cleaned on exit.
_TEMP_FILES: list[str] = []


def _cleanup_temp_files() -> None:
    for path in _TEMP_FILES:
        try:
            if os.path.isfile(path):
                os.remove(path)
        except OSError:
            pass


atexit.register(_cleanup_temp_files)


def _unique_captcha_audio_path() -> str:
    """Per-process unique audio path to avoid collisions across parallel jobs."""
    path = os.path.join(
        tempfile.gettempdir(),
        f"captcha_audio_{os.getpid()}_{uuid.uuid4().hex[:8]}.mp4",
    )
    _TEMP_FILES.append(path)
    return path


# ---------------------------------------------------------------------------
# Consent / session helpers
# ---------------------------------------------------------------------------

def accept_google_consent_if_present(driver) -> bool:
    consent_selectors = [
        (By.XPATH, "//button[.//div[normalize-space()='Accept all'] or normalize-space()='Accept all']"),
        (By.XPATH, "//button[.//div[normalize-space()='I agree'] or normalize-space()='I agree']"),
        (By.XPATH, "//div[@role='button'][normalize-space()='Accept all' or normalize-space()='I agree']"),
        (By.ID, "L2AGLb"),
    ]
    for by, selector in consent_selectors:
        try:
            button = WebDriverWait(driver, 4).until(
                EC.element_to_be_clickable((by, selector))
            )
            driver.execute_script("arguments[0].click();", button)
            time.sleep(random.uniform(1.0, 2.0))
            return True
        except Exception:
            continue
    return False


def warm_google_session(driver) -> None:
    try:
        driver.get("https://www.google.com/ncr")
        time.sleep(random.uniform(2.0, 3.5))
        accept_google_consent_if_present(driver)

        try:
            search_box = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.NAME, "q"))
            )
            search_box.click()
            time.sleep(random.uniform(0.4, 0.9))
            search_box.send_keys("furniture")
            time.sleep(random.uniform(0.3, 0.7))
            search_box.send_keys(Keys.ENTER)
            time.sleep(random.uniform(2.0, 3.5))
        except Exception:
            pass

        try:
            driver.execute_script(
                "window.scrollBy(0, Math.max(300, window.innerHeight * 0.35));"
            )
            time.sleep(random.uniform(0.8, 1.4))
        except Exception:
            pass
    except Exception as exc:
        log.warning("Session warm-up skipped: %s", exc)


# ---------------------------------------------------------------------------
# Fingerprint normalisation
# ---------------------------------------------------------------------------

def parse_platform_from_user_agent(user_agent: str) -> tuple[str, str]:
    ua = (user_agent or "").lower()
    if "windows" in ua:
        return "Windows", "Win32"
    if "mac os x" in ua or "macintosh" in ua:
        return "macOS", "MacIntel"
    return "Linux", "Linux x86_64"


def build_user_agent_metadata(user_agent: str, platform_name: str) -> dict | None:
    match = re.search(r"Chrome/(\d+)\.(\d+)\.(\d+)\.(\d+)", user_agent or "")
    if not match:
        return None

    major = match.group(1)
    full_version = ".".join(match.groups())
    return {
        "brands": [
            {"brand": "Not/A)Brand", "version": "8"},
            {"brand": "Chromium", "version": major},
            {"brand": "Google Chrome", "version": major},
        ],
        "fullVersionList": [
            {"brand": "Not/A)Brand", "version": "8.0.0.0"},
            {"brand": "Chromium", "version": full_version},
            {"brand": "Google Chrome", "version": full_version},
        ],
        "fullVersion": full_version,
        "platform": platform_name,
        "platformVersion": "10.0.0" if platform_name == "Windows" else "0.0.0",
        "architecture": "x86",
        "model": "",
        "mobile": False,
        "bitness": "64",
        "wow64": False,
    }


def normalize_driver_fingerprint(driver) -> None:
    accept_language = os.environ.get("BROWSER_ACCEPT_LANGUAGE", "en-US,en;q=0.9")
    timezone_id = os.environ.get("BROWSER_TIMEZONE", "America/New_York")
    locale = accept_language.split(",")[0].strip() or "en-US"

    try:
        browser_version = driver.execute_cdp_cmd("Browser.getVersion", {})
    except Exception as exc:
        log.warning("Fingerprint normalization skipped: %s", exc)
        return

    raw_user_agent = browser_version.get("userAgent", "") or ""
    user_agent = raw_user_agent.replace("HeadlessChrome/", "Chrome/")
    platform_name, navigator_platform = parse_platform_from_user_agent(user_agent)
    metadata = build_user_agent_metadata(user_agent, platform_name)

    try:
        driver.execute_cdp_cmd("Network.enable", {})
    except Exception:
        pass

    ua_override: dict[str, Any] = {
        "userAgent": user_agent,
        "acceptLanguage": accept_language,
        "platform": navigator_platform,
    }
    if metadata:
        ua_override["userAgentMetadata"] = metadata

    try:
        driver.execute_cdp_cmd("Network.setUserAgentOverride", ua_override)
    except Exception as exc:
        log.warning("User agent override skipped: %s", exc)

    try:
        driver.execute_cdp_cmd("Emulation.setLocaleOverride", {"locale": locale})
    except Exception as exc:
        log.warning("Locale override skipped: %s", exc)

    try:
        driver.execute_cdp_cmd("Emulation.setTimezoneOverride", {"timezoneId": timezone_id})
    except Exception as exc:
        log.warning("Timezone override skipped: %s", exc)

    script = f"""
Object.defineProperty(navigator, 'webdriver', {{
  get: () => undefined,
}});
Object.defineProperty(navigator, 'languages', {{
  get: () => ['en-US', 'en'],
}});
Object.defineProperty(navigator, 'platform', {{
  get: () => '{navigator_platform}',
}});
Object.defineProperty(navigator, 'hardwareConcurrency', {{
  get: () => 8,
}});
Object.defineProperty(navigator, 'deviceMemory', {{
  get: () => 8,
}});
Object.defineProperty(navigator, 'plugins', {{
  get: () => [1, 2, 3, 4, 5],
}});
window.chrome = window.chrome || {{
  runtime: {{}},
  app: {{}},
}};
"""
    try:
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": script})
    except Exception as exc:
        log.warning("Preload fingerprint script skipped: %s", exc)


# ---------------------------------------------------------------------------
# Driver lifecycle
# ---------------------------------------------------------------------------

def _detect_chrome_major() -> int | None:
    """Best-effort detection of installed Chrome major version."""
    chrome_bin = os.environ.get("CHROME_BIN") or os.environ.get("CHROME_PATH") or "google-chrome"
    try:
        import subprocess

        out = subprocess.check_output(
            [chrome_bin, "--version"],
            stderr=subprocess.STDOUT,
            text=True,
            timeout=10,
        )
        m = re.search(r"(\d+)\.\d+\.\d+\.\d+", out)
        if m:
            return int(m.group(1))
    except Exception as exc:
        log.debug("Could not detect Chrome version via CLI: %s", exc)
    return None


def setup_driver(max_attempts: int = 3, base_delay: float = 4.0):
    last_err: Exception | None = None
    version_main = _detect_chrome_major()

    for attempt in range(1, max_attempts + 1):
        driver = None
        try:
            time.sleep(1.5)
            options = uc.ChromeOptions()
            chrome_bin = os.environ.get("CHROME_BIN") or os.environ.get("CHROME_PATH")
            if chrome_bin:
                options.binary_location = chrome_bin

            # Prefer headless in CI; allow override via env for local debug.
            # if os.environ.get("HEADLESS", "1").lower() in ("1", "true", "yes"):
            #     options.add_argument("--headless=new")

            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-logging")
            options.add_argument("--log-level=3")
            options.add_argument("--window-size=1366,768")
            options.add_argument("--lang=en-US")
            options.add_argument("--disable-notifications")
            options.add_argument("--disable-blink-features=AutomationControlled")

            kwargs: dict[str, Any] = {"options": options, "use_subprocess": True}
            if version_main:
                kwargs["version_main"] = version_main
                log.info("Starting Chrome with version_main=%s", version_main)
            else:
                log.info("Starting Chrome with auto version detection")

            driver = uc.Chrome(**kwargs)
            normalize_driver_fingerprint(driver)
            warm_google_session(driver)
            return driver
        except Exception as e:
            last_err = e
            log.warning(
                "Driver start failed (attempt %s/%s): %s",
                attempt,
                max_attempts,
                e,
            )
            try:
                if driver is not None:
                    driver.quit()
            except Exception:
                pass
            if attempt < max_attempts:
                time.sleep(base_delay * attempt + random.uniform(0, 2))

    if last_err:
        raise last_err
    raise RuntimeError("Driver start failed with unknown error")


def is_driver_alive(driver) -> bool:
    if driver is None:
        return False
    try:
        _ = driver.current_url
        driver.execute_script("return 1")
        return True
    except Exception as exc:
        log.warning("[BROWSER] Driver is not alive: %s", exc)
        return False


def ensure_driver_alive(driver):
    if is_driver_alive(driver):
        return driver

    log.warning("[BROWSER] Restarting dead driver...")
    try:
        if driver is not None:
            driver.quit()
    except Exception:
        pass

    driver = setup_driver()
    log.info("[BROWSER] Driver restarted successfully.")
    return driver


# ---------------------------------------------------------------------------
# Human-like interaction (debug / parity only)
# ---------------------------------------------------------------------------

def human_mouse_move(driver, min_seconds: float = 2, max_seconds: float = 5) -> None:
    duration = random.uniform(min_seconds, max_seconds)
    start_time = time.time()

    try:
        width = driver.execute_script(
            "return Math.max(document.documentElement.clientWidth || 0, window.innerWidth || 0);"
        )
        height = driver.execute_script(
            "return Math.max(document.documentElement.clientHeight || 0, window.innerHeight || 0);"
        )
    except Exception:
        width, height = 1920, 1080

    width = max(int(width or 1920), 200)
    height = max(int(height or 1080), 200)

    try:
        body = driver.find_element(By.TAG_NAME, "body")
        ActionChains(driver).move_to_element_with_offset(
            body,
            random.randint(20, min(300, width - 20)),
            random.randint(20, min(300, height - 20)),
        ).perform()
    except Exception:
        return

    while time.time() - start_time < duration:
        dx = random.randint(-100, 100)
        dy = random.randint(-80, 80)
        try:
            ActionChains(driver).move_by_offset(dx, dy).perform()
        except Exception:
            try:
                body = driver.find_element(By.TAG_NAME, "body")
                ActionChains(driver).move_to_element_with_offset(
                    body,
                    random.randint(10, min(250, width - 10)),
                    random.randint(10, min(250, height - 10)),
                ).perform()
            except Exception:
                break
        time.sleep(random.uniform(0.05, 0.15))


# ---------------------------------------------------------------------------
# reCAPTCHA helpers
# ---------------------------------------------------------------------------

def _safe_default_content(driver) -> None:
    """Always return to top-level document; never raise."""
    try:
        driver.switch_to.default_content()
    except Exception:
        pass


def find_recaptcha_frame(driver, match: str) -> bool:
    """
    Find an iframe whose title contains `match` (case-insensitive) and switch to it.
    Returns True if switched successfully, False otherwise.
    Always switches back to default content first.
    """
    _safe_default_content(driver)
    try:
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
    except Exception:
        return False

    match_lower = match.lower()
    for iframe in iframes:
        try:
            title = (iframe.get_attribute("title") or "").lower()
        except StaleElementReferenceException:
            continue
        if match_lower in title:
            try:
                driver.switch_to.frame(iframe)
                return True
            except Exception:
                _safe_default_content(driver)
                return False
    return False


def _wait_for_recaptcha_frame(driver, match: str, timeout: float = 8.0) -> bool:
    """Poll until an iframe whose title contains `match` appears, then switch into it."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if find_recaptcha_frame(driver, match):
            return True
        time.sleep(0.4)
    _safe_default_content(driver)
    return False


def is_recaptcha_present(driver) -> bool:
    """
    Read-only check: is a reCAPTCHA / challenge iframe or block page visible?
    Does not click or interact. Always returns to default content.
    """
    _safe_default_content(driver)

    try:
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
    except Exception:
        iframes = []

    for iframe in iframes:
        try:
            title = (iframe.get_attribute("title") or "").lower()
            src = (iframe.get_attribute("src") or "").lower()
        except StaleElementReferenceException:
            continue
        if "recaptcha" in title or "recaptcha" in src:
            return True

    try:
        page = (driver.page_source or "").lower()
        current = (driver.current_url or "").lower()
        if "unusual traffic" in page or "/sorry/" in current:
            return True
    except Exception:
        pass

    return False


def detect_recaptcha(driver) -> bool:
    """
    Attempt to detect and solve a reCAPTCHA audio challenge.

    Guarantees:
    - Always restores default content before returning (no frame leaks).
    - Waits for challenge UI after checkbox / audio clicks.
    - Catches click-intercepted and other WebDriver errors.
    - Uses a unique temp path for the audio file (safe under parallel jobs).

    Early-break after the first solve attempt is intentional and preserved.
    Returns True only if the full solve path completed; False on any failure.
    Caller must re-check is_recaptcha_present() to know if the page is clear.
    """
    _safe_default_content(driver)
    audio_path = _unique_captcha_audio_path()

    # 1. Find and switch to the main reCAPTCHA iframe
    if not find_recaptcha_frame(driver, "reCAPTCHA"):
        print("No reCAPTCHA iframe found")
        _safe_default_content(driver)
        return False

    try:
        # 2. Wait for checkbox, then click
        try:
            checkbox = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "div.recaptcha-checkbox-border")
                )
            )
        except TimeoutException:
            print("Checkbox not found")
            return False

        try:
            checkbox.click()
        except WebDriverException:
            try:
                driver.execute_script("arguments[0].click();", checkbox)
            except WebDriverException as e:
                print(f"Checkbox click failed: {e}")
                return False

        print("reCAPTCHA detected")

        # Wait for challenge iframe to mount after checkbox click
        time.sleep(1.5)

        # 3. Switch to the challenge iframe (with wait)
        if not _wait_for_recaptcha_frame(driver, "recaptcha challenge", timeout=10):
            print("No challenge iframe found")
            return False

        # 4. Wait for audio button, then click
        try:
            audio_button = WebDriverWait(driver, 6).until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "button.rc-button-audio")
                )
            )
        except TimeoutException:
            print("Audio button not found")
            return False

        try:
            audio_button.click()
        except WebDriverException:
            try:
                driver.execute_script("arguments[0].click();", audio_button)
            except WebDriverException as e:
                print(f"Audio button click failed: {e}")
                return False

        print("Audio button clicked")

        # Challenge iframe often refreshes after switching to audio mode
        time.sleep(1.5)

        # 5. Re-find the challenge iframe
        if not _wait_for_recaptcha_frame(driver, "recaptcha challenge", timeout=8):
            print("No challenge 2 iframe found")
            return False

        # Optional: read the doscaptcha text
        try:
            locator = WebDriverWait(driver, 5).until(
                EC.visibility_of_element_located(
                    (By.CSS_SELECTOR, "div.rc-doscaptcha-body-text")
                )
            )
            captcha_text = locator.text
            print(captcha_text)
        except TimeoutException:
            pass

        # 6. Wait for audio download link
        try:
            a_tag = WebDriverWait(driver, 8).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "a.rc-audiochallenge-tdownload-link")
                )
            )
        except TimeoutException:
            print("Automation Detected")
            return False

        url = a_tag.get_attribute("href")
        if not url:
            print("No href found")
            return False

        print("Download URL:", url)

        # Download the audio to a unique temp path
        response = requests.get(url, stream=True, timeout=60)
        response.raise_for_status()
        with open(audio_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        print(f"Saved to: {audio_path}")

        # 7. Solve and submit (up to 3 attempts — early break preserved)
        for i in range(3):
            detected_text = solve_audio_captcha(audio_path)
            print(f"Solved: {detected_text}")

            if not detected_text or not str(detected_text).strip():
                print("Empty solve result")
                return False

            # Make sure we are still in the challenge frame
            if not _wait_for_recaptcha_frame(driver, "recaptcha challenge", timeout=5):
                print("Lost challenge frame")
                return False

            input_box = WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located(
                    (By.CSS_SELECTOR, "input#audio-response")
                )
            )
            input_box.clear()
            time.sleep(0.3)
            input_box.send_keys(str(detected_text).strip())

            time.sleep(1)
            input_box.send_keys(Keys.ENTER)
            time.sleep(5)

            break   # keep the same early-break logic

        return True

    except (TimeoutException, NoSuchElementException, WebDriverException) as e:
        print(f"Exception: {e}")
        return False
    finally:
        # Frame-leak fix: every exit path restores top-level context
        _safe_default_content(driver)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def extract_all_products(html_content: str) -> list[dict]:
    soup = BeautifulSoup(html_content, "html.parser")
    products: list[dict] = []

    containers = soup.find_all(
        "div",
        attrs={"data-gid": True, "data-pid": True, "data-cid": True},
    )

    for container in containers:
        data_gid = container.get("data-gid")
        data_pid = container.get("data-pid")
        data_cid = container.get("data-cid")

        name_element = container.find(
            "div",
            class_=lambda c: c and "gkQHve" in c,
        )
        name = name_element.get_text(strip=True) if name_element else None

        price_element = container.find("span", class_="lmQWe")
        price = price_element.get_text(strip=True) if price_element else None

        seller_element = container.find(
            "span",
            class_=lambda c: c and "WJMUdc" in c,
        )
        seller_name = (
            seller_element.get_text(strip=True) if seller_element else None
        )

        first_image_url = None
        for img in container.find_all("img"):
            src = img.get("src", "")
            if src.startswith("https://"):
                first_image_url = src
                break

        products.append(
            {
                "name": name,
                "image_url": first_image_url,
                "price": price,
                "seller": seller_name,
                "pid": data_pid,
                "cid": data_cid,
                "gid": data_gid,
            }
        )

    log.info("Found %s products", len(products))
    return products


# ---------------------------------------------------------------------------
# URL loading
# ---------------------------------------------------------------------------

def load_urls(url_args: list[str]) -> list[str]:
    """
    Load URLs from command-line arguments.

    Supports:
      --urls https://example.com https://example2.com
    Or a CSV chunk:
      --urls chunks/urls_0.csv

    CSV URL columns supported: product_url, url
    """
    urls: list[str] = []

    for value in url_args:
        value = value.strip()
        if not value:
            continue

        if os.path.isfile(value):
            log.info("Loading URLs from CSV: %s", value)
            with open(value, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                if not reader.fieldnames:
                    log.warning("CSV has no header: %s", value)
                    continue
                log.info("CSV columns: %s", reader.fieldnames)
                for row in reader:
                    url = (row.get("product_url") or row.get("url") or "").strip()
                    if not url:
                        continue
                    if url.startswith(("http://", "https://")):
                        urls.append(url)
                    else:
                        log.warning("Invalid URL in CSV: %s", url)
            continue

        if value.startswith(("http://", "https://")):
            urls.append(value)
        else:
            log.warning("Invalid URL or file: %s", value)

    # Preserve order, drop exact duplicates
    seen: set[str] = set()
    deduped: list[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            deduped.append(u)
    return deduped


def print_public_ip() -> str | None:
    try:
        response = requests.get("https://api.ipify.org?format=json", timeout=10)
        response.raise_for_status()
        ip = response.json().get("ip")
        log.info("[NETWORK] Public IP: %s", ip)
        return ip
    except Exception as e:
        log.warning("[NETWORK] Could not get public IP: %s", e)
        return None


# ---------------------------------------------------------------------------
# Page fetch with retries
# ---------------------------------------------------------------------------

def fetch_page_html(driver, url: str, max_attempts: int = 3) -> str | None:
    """
    Navigate to url, handle consent / CAPTCHA, scroll, and return page source.
    Returns None when the page could not be loaded or yielded no usable content.

    CAPTCHA policy:
    - If a reCAPTCHA widget is present, attempt solve via detect_recaptcha().
    - Whether solve succeeds or fails, if the widget is STILL present afterward,
      treat the page as blocked and retry (or eventually mark pending).
    """
    for attempt in range(1, max_attempts + 1):
        driver = ensure_driver_alive(driver)
        log.info("Fetching URL attempt %s/%s: %s", attempt, max_attempts, url)

        try:
            driver.get(url)
        except TimeoutException:
            log.warning("Page load timeout: %s", url)
            try:
                driver.execute_script("window.stop();")
            except Exception:
                pass
        except WebDriverException as e:
            log.warning("WebDriver get failed: %s (%s)", url, e)
            continue

        time.sleep(3)

        # --- CAPTCHA gate -------------------------------------------------
        captcha_seen = is_recaptcha_present(driver)

        if captcha_seen:
            log.warning("reCAPTCHA present on attempt %s — attempting solve", attempt)
            try:
                detect_recaptcha(driver)
            except WebDriverException as e:
                log.warning("CAPTCHA interaction failed: %s", e)
            _safe_default_content(driver)
            time.sleep(2)

            if is_recaptcha_present(driver):
                log.warning(
                    "reCAPTCHA still present after solve attempt. Retrying..."
                )
                time.sleep(random.uniform(2.0, 4.0))
                continue
            log.info("reCAPTCHA cleared on attempt %s", attempt)

        # Cookie consent
        accept_google_consent_if_present(driver)
        try:
            WebDriverWait(driver, 5).until(
                lambda d: d.execute_script("return document.readyState")
                in ("interactive", "complete")
            )
        except Exception:
            pass

        # Scroll to trigger lazy-loaded images / product cards
        try:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(0.8)
            driver.execute_script(
                "window.scrollTo(0, document.body.scrollHeight * 0.5);"
            )
            time.sleep(0.5)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        except Exception:
            pass

        time.sleep(1.5)

        # CAPTCHA may appear only after scroll / interaction
        if is_recaptcha_present(driver):
            log.warning("Challenge appeared after navigation/scroll. Retrying...")
            time.sleep(random.uniform(2.0, 4.0))
            continue

        # Wait for at least one product container
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "div[data-gid][data-pid][data-cid]")
                )
            )
        except TimeoutException:
            log.warning(
                "No product containers appeared within timeout for %s", url
            )
            if is_recaptcha_present(driver):
                log.warning("Page still blocked by reCAPTCHA after timeout.")
                time.sleep(random.uniform(2.0, 4.0))
                continue

        try:
            html = driver.page_source
        except WebDriverException as e:
            log.warning("Could not read page_source: %s", e)
            continue

        if html and len(html) > 500 and not is_recaptcha_present(driver):
            log.info("Page loaded successfully (%s chars).", len(html))
            return html

        log.warning("Empty, blocked, or tiny page source on attempt %s", attempt)
        time.sleep(random.uniform(1.5, 3.0))

    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(
        description="Scrape Google Shopping product sets from a list of URLs."
    )
    ap.add_argument(
        "--urls",
        nargs="+",
        required=True,
        help="One or more URLs, or path(s) to CSV chunk files",
    )
    ap.add_argument(
        "--out",
        default=os.path.join(os.getcwd(), "scraped_products.csv"),
        help="Output CSV path for successful product rows",
    )
    ap.add_argument(
        "--pending-out",
        default=None,
        help="CSV file for URLs that returned no product data",
    )
    ap.add_argument(
        "--flush-every",
        type=int,
        default=25,
        help="Flush progress every N written rows",
    )
    args = ap.parse_args()

    print_public_ip()

    urls = load_urls(args.urls)
    log.info("Loaded %s URLs", len(urls))

    if not urls:
        log.error("No valid URLs found.")
        return 1

    out_dir = os.path.dirname(args.out) or "."
    os.makedirs(out_dir, exist_ok=True)

    wrote = 0
    processed = 0
    pending_urls: list[str] = []
    driver = None

    try:
        driver = setup_driver()

        with open(args.out, "w", newline="", encoding="utf-8") as out_f:
            writer = csv.DictWriter(out_f, fieldnames=OUT_FIELDS)
            writer.writeheader()
            out_f.flush()

            for url in urls:
                url = url.strip()
                if not url:
                    continue

                processed += 1
                html = None

                try:
                    html = fetch_page_html(driver, url, max_attempts=3)
                except TimeoutException:
                    log.warning("Timeout fetching: %s", url)
                except WebDriverException as e:
                    log.warning("WebDriver failed: %s (%s)", url, e)
                except Exception as e:
                    log.warning("Fetch failed: %s (%s)", url, e)

                if not html:
                    log.warning("Skipping url (no HTML): %s", url)
                    pending_urls.append(url)
                    continue

                parsed_products = extract_all_products(html)

                if not parsed_products:
                    log.warning(
                        "No products found for %s. Page might be blocked or structure changed.",
                        url,
                    )
                    pending_urls.append(url)
                    continue

                for prod in parsed_products:
                    writer.writerow({"url": url, **prod})
                    wrote += 1

                if wrote % max(1, args.flush_every) == 0:
                    out_f.flush()
                    log.info(
                        "[progress] wrote %s rows (processed %s urls)",
                        wrote,
                        processed,
                    )

            out_f.flush()

    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass

    # Write pending URLs (deduplicated, order preserved)
    if args.pending_out:
        pending_dir = os.path.dirname(args.pending_out) or "."
        os.makedirs(pending_dir, exist_ok=True)

        pending_urls = list(dict.fromkeys(pending_urls))

        with open(args.pending_out, "w", newline="", encoding="utf-8") as pending_f:
            pending_writer = csv.writer(pending_f)
            pending_writer.writerow(["product_url"])
            for pending_url in pending_urls:
                pending_writer.writerow([pending_url])

        log.info(
            "Saved %s pending URLs to: %s",
            len(pending_urls),
            args.pending_out,
        )

    log.info("Saved %s rows to: %s", wrote, args.out)

    # Non-zero exit when a large fraction failed — surfaces problems in CI
    if processed > 0 and len(pending_urls) / processed > 0.85 and wrote == 0:
        log.error(
            "High failure rate: %s/%s URLs pending and 0 rows written.",
            len(pending_urls),
            processed,
        )
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())