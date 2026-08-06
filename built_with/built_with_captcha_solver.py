# #!/usr/bin/env python3
# """
# BuiltWith scraper with automatic CAPTCHA solving.
# - Reads domains from input.csv
# - Solves the human-test CAPTCHA when it appears
# - Extracts Meta + Technology data
# - Saves everything to CSV (no database)
# """

# import sys
# import time
# import random
# import io
# import re
# import json
# import csv
# from datetime import datetime
# from pathlib import Path

# from playwright.sync_api import sync_playwright
# from bs4 import BeautifulSoup
# from PIL import Image
# import torch
# from transformers import CLIPProcessor, CLIPModel


# # ============================================================
# # CLIP model (loaded once)
# # ============================================================
# print("Loading CLIP model...")
# device = "cuda" if torch.cuda.is_available() else "cpu"
# clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").to(device)
# clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
# print(f"CLIP ready on {device}\n")


# def human_delay(a=0.3, b=0.7):
#     time.sleep(random.uniform(a, b))


# def is_match(pil_image: Image.Image, target: str) -> float:
#     texts = [
#         f"a photo of a {target}",
#         f"a close-up of a {target}",
#         "a random object or animal",
#     ]
#     inputs = clip_processor(text=texts, images=pil_image, return_tensors="pt", padding=True).to(device)
#     with torch.no_grad():
#         outputs = clip_model(**inputs)
#         probs = outputs.logits_per_image.softmax(dim=1)[0]
#     return (probs[0] + probs[1]).item() / 2


# def get_cell_boxes(img_w: int, img_h: int):
#     cols, rows = 4, 3
#     gap, pad = 8, 6
#     cell_w = (img_w - 2 * pad - (cols - 1) * gap) // cols
#     cell_h = (img_h - 2 * pad - (rows - 1) * gap) // rows
#     boxes = []
#     for r in range(rows):
#         for c in range(cols):
#             x1 = pad + c * (cell_w + gap)
#             y1 = pad + r * (cell_h + gap)
#             boxes.append((x1, y1, x1 + cell_w, y1 + cell_h))
#     return boxes


# def is_captcha_present(page) -> bool:
#     try:
#         if page.locator("#human-test-img").count() and page.locator("#human-test-img").is_visible():
#             return True
#         if page.locator("#target-display").count() and page.locator("#target-display").is_visible():
#             return True
#         return False
#     except Exception:
#         return False


# def solve_captcha_once(page) -> bool:
#     page.wait_for_selector("#human-test-img", timeout=15000)
#     page.wait_for_timeout(1200)

#     img_el = page.locator("#human-test-img")
#     size = page.evaluate("""() => {
#         const img = document.getElementById("human-test-img");
#         return {w: img.naturalWidth, h: img.naturalHeight};
#     }""")
#     img_w, img_h = size["w"], size["h"]

#     raw = page.locator("#target-display").inner_text().strip()
#     target = " ".join(raw.split()[1:]) if raw and not raw[0].isalpha() else raw
#     target = target.lower().strip()
#     print(f"  Target: '{target}'")

#     img_bytes = img_el.screenshot()
#     full_img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
#     boxes = get_cell_boxes(img_w, img_h)

#     scores = []
#     for i, (x1, y1, x2, y2) in enumerate(boxes):
#         cell = full_img.crop((x1, y1, x2, y2))
#         score = is_match(cell, target)
#         scores.append((i, score, x1, y1, x2, y2))

#     scores.sort(key=lambda x: x[1], reverse=True)
#     top2 = scores[:2]
#     print(f"  Top cells: {[t[0] for t in top2]} scores={[round(t[1],3) for t in top2]}")

#     for rank, (i, score, x1, y1, x2, y2) in enumerate(top2, 1):
#         cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
#         box = img_el.bounding_box()
#         scale_x = box["width"] / img_w
#         scale_y = box["height"] / img_h
#         page.mouse.click(box["x"] + cx * scale_x, box["y"] + cy * scale_y)
#         human_delay(0.9, 1.5)
#         if rank == 1:
#             page.wait_for_timeout(1400)

#     page.wait_for_timeout(3500)
#     return not is_captcha_present(page)


# def solve_captcha(page, max_retries=3) -> bool:
#     for attempt in range(1, max_retries + 1):
#         if not is_captcha_present(page):
#             return True
#         print(f"  CAPTCHA attempt {attempt}/{max_retries}")
#         try:
#             if solve_captcha_once(page):
#                 print("  ✅ CAPTCHA solved")
#                 return True
#         except Exception as e:
#             print(f"  Error: {e}")
#         if attempt < max_retries:
#             page.reload(wait_until="domcontentloaded")
#             page.wait_for_timeout(2500)
#     print("  ❌ CAPTCHA failed after retries")
#     return False


# # ============================================================
# # Parsing helpers (adapted from your original script)
# # ============================================================
# def filter_dl(dts, dds):
#     data = {}
#     for dt, dd in zip(dts, dds):
#         key = dt.get_text(strip=True)
#         value = dd.get_text(strip=True)
#         if value == "-":
#             if any(w in key.lower() for w in ["count", "url", "ip", "subnet", "follower", "employee",
#                                                "dimensions", "metrics", "goals", "tags", "code", "rank",
#                                                "majestic", "builtwith"]):
#                 value = 0
#             else:
#                 value = None
#         else:
#             value_clean = value.replace(",", "").replace("+", "")
#             try:
#                 value = int(value_clean)
#             except ValueError:
#                 value = value_clean
#         data[key] = value
#     return data


# # def parse_value(value):
# #     value = str(value).strip()
# #     match = re.search(r"\$([\d,.]+)([KkMm]?)", value)
# #     if match:
# #         number = match.group(1).replace(",", "")
# #         suffix = match.group(2).lower()
# #         try:
# #             num = float(number)
# #             if suffix == "k":
# #                 num *= 1_000
# #             elif suffix == "m":
# #                 num *= 1_000_000
# #             return int(num)
# #         except ValueError:
# #             return 0
# #     match = re.search(r"\d+", value)
# #     return int(match.group(0)) if match else 0


# # def get_technology_profile(soup: BeautifulSoup):
# #     data = []
# #     try:
# #         form = soup.find("form", method="post")
# #         if not form:
# #             return []
# #         containers = form.find_all("div", class_="container")
# #         if len(containers) < 2:
# #             return []
# #         second = containers[1]
# #         div = second.select_one("div.row > div")
# #         if not div:
# #             return []
# #         cards = div.find_all("div", class_="card")
# #         for card in cards:
# #             title_el = card.select_one("div.card-body div.mb-2 div h6.card-title")
# #             if not title_el:
# #                 continue
# #             title = title_el.text.strip()
# #             row_data = []
# #             for row in card.select("div.card-body div.mt-1"):
# #                 a = row.select_one("div.col-12 h2 a")
# #                 if a:
# #                     row_data.append(a.text.strip())
# #             data.append({title: row_data})
# #     except Exception:
# #         pass
# #     return data


# # def get_meta(soup: BeautifulSoup):
# #     company_image = None
# #     emails = []
# #     company_name = None
# #     linkedIn = None
# #     location = None
# #     vertical = None
# #     telephone = []
# #     listed_contacts = []
# #     financial_information = None
# #     company_data = None
# #     google_data = None
# #     technology_spend = 0
# #     social_links = []
# #     ranking = None
# #     updated_at = datetime.now().isoformat()

# #     try:
# #         form = soup.find("form", method="post")
# #         if not form:
# #             return {}
# #         containers = form.find_all("div", class_="container")
# #         if len(containers) < 2:
# #             return {}
# #         second = containers[1]

# #         # Left column (col-md-8)
# #         try:
# #             div = second.select_one("div.row > div.col-md-8")
# #             if div:
# #                 for card in div.find_all("div", class_="card"):
# #                     try:
# #                         title = card.select_one("div.card-body h6")
# #                         if not title:
# #                             continue
# #                         title = title.text.strip()

# #                         if "Contact Information" in title:
# #                             dl = card.select("dl.row")
# #                             if len(dl) > 1:
# #                                 try:
# #                                     company_name = dl[0].find("dd").text.replace("Find People on LinkedIn", "").strip()
# #                                     if company_name in ("-", ""):
# #                                         company_name = None
# #                                 except Exception:
# #                                     company_name = None
# #                                 try:
# #                                     linkedIn = dl[0].select_one("dd a")["href"]
# #                                 except Exception:
# #                                     linkedIn = None
# #                                 try:
# #                                     if "Location" in dl[1].find("dt").text:
# #                                         location = ", ".join(dl[1].find("address").stripped_strings)
# #                                 except Exception:
# #                                     location = None
# #                                 try:
# #                                     dts = dl[1].find_all("dt")
# #                                     dds = dl[1].find_all("dd")
# #                                     for dt, dd in zip(dts, dds):
# #                                         if "Telephone" in dt.text:
# #                                             numbers = re.findall(r"\+\d{1,3}(?:-\d+)+", dd.text.strip())
# #                                             if numbers:
# #                                                 telephone = numbers
# #                                 except Exception:
# #                                     pass

# #                             try:
# #                                 if "Publicly Listed Contacts" in card.select_one("div.card-body h6.mb-3").text:
# #                                     table = card.select_one("div.card-body div table")
# #                                     for row in table.select("tbody tr"):
# #                                         tds = row.find_all("td")
# #                                         name = tds[0].text.strip()
# #                                         level = tds[2].text.strip()
# #                                         google_link = None
# #                                         linkedIn_link = None
# #                                         try:
# #                                             google_link = tds[3].find("a", attrs={"target": "_researchGOOG"})["href"]
# #                                         except Exception:
# #                                             pass
# #                                         try:
# #                                             linkedIn_link = tds[3].find("a", attrs={"target": "_researchLI"})["href"]
# #                                         except Exception:
# #                                             pass
# #                                         listed_contacts.append({
# #                                             "name": name, "level": level,
# #                                             "google": google_link, "linkedIn": linkedIn_link
# #                                         })
# #                             except Exception:
# #                                 pass

# #                         if "Financial Information" in title:
# #                             dts = card.select("div.card-body dl dt")
# #                             dds = card.select("div.card-body dl dd")
# #                             financial_information = filter_dl(dts, dds)

# #                         if "Website Information" in title:
# #                             dl = card.select("div.card-body dl")
# #                             if dl and "Vertical" in dl[0].find("dt").text:
# #                                 vertical = dl[0].find("dd").text.strip()
# #                                 if vertical == "-":
# #                                     vertical = None
# #                             if len(dl) > 1:
# #                                 company_data = filter_dl(dl[1].find_all("dt"), dl[1].find_all("dd"))
# #                             if len(dl) > 2:
# #                                 google_data = filter_dl(dl[2].find_all("dt"), dl[2].find_all("dd"))
# #                     except Exception:
# #                         continue
# #         except Exception:
# #             pass

# #         # Right column (col-md-4)
# #         try:
# #             div = second.select_one("div.row > div.col-md-4")
# #             if div:
# #                 for card in div.find_all("div", class_="card"):
# #                     body = card.select_one("div.card-body")
# #                     if not body:
# #                         continue
# #                     try:
# #                         title = body.find("h6").text.strip()
# #                     except Exception:
# #                         continue
# #                     if "Technology Spend" in title:
# #                         technology_spend = parse_value(body.find("div").text.strip())
# #                     if "Social Links" in title:
# #                         social_links = [a["href"] for a in body.select("ul.list-unstyled a[href]")]
# #                     if "Ranking" in title:
# #                         ranking = filter_dl(body.find_all("dt"), body.find_all("dd"))
# #         except Exception:
# #             pass

# #     except Exception:
# #         pass

# #     return {
# #         "company_name": company_name,
# #         "linkedin_site": linkedIn,
# #         "company_image": company_image,
# #         "location": location,
# #         "telephone": json.dumps(telephone),
# #         "listed_contacts": json.dumps(listed_contacts),
# #         "vertical": vertical,
# #         "company_data": json.dumps(company_data),
# #         "google_data": json.dumps(google_data),
# #         "performance_data": json.dumps(financial_information),
# #         "social_links": json.dumps(social_links),
# #         "emails": json.dumps(emails),
# #         "traffic_rankings": json.dumps(ranking),
# #         "technology_spend": technology_spend,
# #         "updated_at": updated_at,
# #     }

# def parse_value(value):
#     """Extract numeric value from strings like '$5,000+', '₹282,530+ / month', '1,500+'"""
#     value = str(value).strip()
#     # Remove currency symbols
#     cleaned = value.replace("₹", "").replace("$", "").replace("€", "").replace(",", "")
#     match = re.search(r"([\d.]+)\s*([KkMm]?)", cleaned)
#     if match:
#         try:
#             num = float(match.group(1))
#             suffix = match.group(2).lower()
#             if suffix == "k":
#                 num *= 1_000
#             elif suffix == "m":
#                 num *= 1_000_000
#             return int(num)
#         except ValueError:
#             pass
#     match = re.search(r"\d+", cleaned)
#     return int(match.group(0)) if match else 0


# # def get_meta(soup: BeautifulSoup) -> dict:
# #     """
# #     Parse BuiltWith Meta Data Profile page.
# #     Works with the current card-based layout.
# #     """
# #     result = {
# #         "company_name": None,
# #         "linkedin_site": None,
# #         "company_image": None,
# #         "location": None,
# #         "telephone": [],
# #         "listed_contacts": [],
# #         "vertical": None,
# #         "company_data": {},
# #         "google_data": {},
# #         "performance_data": {},
# #         "social_links": [],
# #         "emails": [],
# #         "traffic_rankings": {},
# #         "technology_spend": 0,
# #         "updated_at": datetime.now().isoformat(),
# #     }

# #     for card in soup.select("div.card"):
# #         header = card.select_one(".card-header")
# #         if not header:
# #             continue

# #         title = header.get_text(strip=True)
# #         body = card.select_one(".card-body")
# #         if not body:
# #             continue

# #         # ---------- Company Name ----------
# #         if title == "Company Name":
# #             name = body.get_text(strip=True)
# #             result["company_name"] = None if name in ("-", "") else name

# #         # ---------- Location ----------
# #         elif title == "Location":
# #             loc = " ".join(body.stripped_strings)
# #             result["location"] = None if loc in ("-", "") else loc

# #         # ---------- Telephones ----------
# #         elif title == "Telephones":
# #             text = body.get_text(" ", strip=True)
# #             numbers = re.findall(r"\+\d[\d\- ]+\d", text)
# #             result["telephone"] = [n.strip() for n in numbers]

# #         # ---------- Publicly Listed Contacts ----------
# #         elif title == "Publicly Listed Contacts":
# #             table = body.select_one("table")
# #             if table:
# #                 for row in table.select("tbody tr"):
# #                     tds = row.find_all("td")
# #                     if len(tds) >= 2:
# #                         contact = {
# #                             "name": tds[0].get_text(strip=True),
# #                             "level": tds[2].get_text(strip=True) if len(tds) > 2 else None,
# #                         }
# #                         for a in row.select("a[href]"):
# #                             href = a.get("href", "")
# #                             if "linkedin" in href.lower():
# #                                 contact["linkedin"] = href
# #                             elif "google" in href.lower():
# #                                 contact["google"] = href
# #                         result["listed_contacts"].append(contact)

# #         # ---------- Website Information ----------
# #         elif title == "Website Information":
# #             labels = body.select(".info-label")
# #             if labels:
# #                 for lab in labels:
# #                     key = lab.get_text(strip=True)
# #                     val_el = lab.find_next_sibling()
# #                     val = val_el.get_text(strip=True) if val_el else None
# #                     if not val:
# #                         parent_text = lab.parent.get_text(strip=True)
# #                         val = parent_text.replace(key, "", 1).strip() or None

# #                     if val in ("-", ""):
# #                         val = None

# #                     if "vertical" in key.lower():
# #                         result["vertical"] = val
# #                     else:
# #                         result["company_data"][key] = val
# #             else:
# #                 # fallback dt/dd
# #                 for dt in body.select("dt"):
# #                     dd = dt.find_next_sibling("dd")
# #                     if dd:
# #                         key = dt.get_text(strip=True)
# #                         val = dd.get_text(strip=True)
# #                         if val == "-":
# #                             val = None
# #                         if "vertical" in key.lower():
# #                             result["vertical"] = val
# #                         else:
# #                             result["company_data"][key] = val

# #         # ---------- Technology Spend ----------
# #         elif title == "Technology Spend":
# #             text = body.get_text(strip=True)
# #             result["technology_spend"] = parse_value(text)

# #         # ---------- Social Links ----------
# #         elif title == "Social Links":
# #             links = []
# #             for a in body.select("a[href]"):
# #                 href = a["href"].strip()
# #                 if href.startswith("//"):
# #                     href = "https:" + href
# #                 if href and not href.startswith("#") and href not in links:
# #                     links.append(href)

# #             # also catch plain text domains if no <a> tags
# #             if not links:
# #                 text = body.get_text(" ", strip=True)
# #                 for part in re.findall(r"(?:https?:)?//?[^\s]+|[\w\-]+\.(?:com|de|net|org|io|co)[^\s]*", text):
# #                     if part.startswith("//"):
# #                         part = "https:" + part
# #                     if part not in links:
# #                         links.append(part)

# #             result["social_links"] = links

# #         # ---------- Website Ranking ----------
# #         elif title == "Website Ranking":
# #             for dt in body.select("dt"):
# #                 dd = dt.find_next_sibling("dd")
# #                 if dd:
# #                     key = dt.get_text(strip=True)
# #                     val = dd.get_text(strip=True)
# #                     result["traffic_rankings"][key] = None if val == "-" else val

# #     # Convert complex fields to JSON strings for CSV
# #     for key in ["telephone", "listed_contacts", "company_data", "google_data",
# #                 "performance_data", "social_links", "emails", "traffic_rankings"]:
# #         result[key] = json.dumps(result[key], ensure_ascii=False)

# #     return result

# def get_meta(soup: BeautifulSoup) -> dict:
#     """
#     Parse BuiltWith Meta Data Profile page.
#     Works with the current card-based layout.
#     """
#     result = {
#         "company_name": None,
#         "linkedin_site": None,
#         "company_image": None,
#         "location": None,
#         "telephone": [],
#         "listed_contacts": [],
#         "vertical": None,
#         "company_data": {},
#         "google_data": {},
#         "performance_data": {},
#         "social_links": [],
#         "emails": [],
#         "traffic_rankings": {},
#         "technology_spend": 0,
#         "updated_at": datetime.now().isoformat(),
#     }

#     for card in soup.select("div.card"):
#         header = card.select_one(".card-header")
#         if not header:
#             continue

#         title = header.get_text(strip=True)
#         body = card.select_one(".card-body")
#         if not body:
#             continue

#         # ---------- Company Name ----------
#         if title == "Company Name":
#             name = body.get_text(strip=True)
#             # Clean common suffix
#             name = name.replace("Find People on LinkedIn", "").strip()
#             result["company_name"] = None if name in ("-", "") else name

#         # ---------- Location ----------
#         elif title == "Location":
#             loc = " ".join(body.stripped_strings)
#             result["location"] = None if loc in ("-", "") else loc

#         # ---------- Telephones ----------
#         elif title == "Telephones":
#             text = body.get_text(" ", strip=True)
#             numbers = re.findall(r"\+\d[\d\- ]+\d", text)
#             result["telephone"] = [n.strip() for n in numbers]

#         # ---------- Publicly Listed Contacts ----------
#         elif title == "Publicly Listed Contacts":
#             table = body.select_one("table")
#             if table:
#                 for row in table.select("tbody tr"):
#                     tds = row.find_all("td")
#                     if len(tds) >= 2:
#                         contact = {
#                             "name": tds[0].get_text(strip=True),
#                             "level": tds[2].get_text(strip=True) if len(tds) > 2 else None,
#                         }
#                         for a in row.select("a[href]"):
#                             href = a.get("href", "")
#                             if "linkedin" in href.lower():
#                                 contact["linkedin"] = href
#                             elif "google" in href.lower():
#                                 contact["google"] = href
#                         result["listed_contacts"].append(contact)

#         # ---------- Website Information ----------
#         elif title == "Website Information":
#             labels = body.select(".info-label")
#             if labels:
#                 for lab in labels:
#                     key = lab.get_text(strip=True)
#                     val_el = lab.find_next_sibling()
#                     val = val_el.get_text(strip=True) if val_el else None
#                     if not val:
#                         parent_text = lab.parent.get_text(strip=True)
#                         val = parent_text.replace(key, "", 1).strip() or None

#                     if val in ("-", ""):
#                         val = None

#                     if "vertical" in key.lower():
#                         result["vertical"] = val
#                     else:
#                         result["company_data"][key] = val
#             else:
#                 for dt in body.select("dt"):
#                     dd = dt.find_next_sibling("dd")
#                     if dd:
#                         key = dt.get_text(strip=True)
#                         val = dd.get_text(strip=True)
#                         if val == "-":
#                             val = None
#                         if "vertical" in key.lower():
#                             result["vertical"] = val
#                         else:
#                             result["company_data"][key] = val

#         # ---------- Technology Spend ----------
#         elif title == "Technology Spend":
#             text = body.get_text(strip=True)
#             result["technology_spend"] = parse_value(text)

#         # ---------- Social Links ----------
#         elif title == "Social Links":
#             links = []
#             for a in body.select("a[href]"):
#                 href = a["href"].strip()
#                 if href.startswith("//"):
#                     href = "https:" + href
#                 if href and not href.startswith("#") and href not in links:
#                     links.append(href)

#             if not links:
#                 text = body.get_text(" ", strip=True)
#                 for part in re.findall(r"(?:https?:)?//?[^\s]+|[\w\-]+\.(?:com|de|net|org|io|co)[^\s]*", text):
#                     if part.startswith("//"):
#                         part = "https:" + part
#                     if part not in links:
#                         links.append(part)

#             result["social_links"] = links

#         # ---------- Website Ranking ----------
#         elif title == "Website Ranking":
#             for dt in body.select("dt"):
#                 dd = dt.find_next_sibling("dd")
#                 if dd:
#                     key = dt.get_text(strip=True)
#                     val = dd.get_text(strip=True)
#                     result["traffic_rankings"][key] = None if val == "-" else val

#     # Convert complex fields to JSON strings for CSV
#     for key in ["telephone", "listed_contacts", "company_data", "google_data",
#                 "performance_data", "social_links", "emails", "traffic_rankings"]:
#         result[key] = json.dumps(result[key], ensure_ascii=False)

#     return result

# def get_technology_profile(soup: BeautifulSoup) -> list:
#     """
#     Clean parser for BuiltWith Technology Profile.
#     Returns: [ {"Analytics and Tracking": ["Hotjar", "Google Analytics", ...]}, ... ]
#     """
#     categories = {}
#     current_cat = "Other"

#     # Noise keywords to skip
#     NOISE = {
#         "usage statistics", "download list", "global trends",
#         "web technology trends", "investor", "websitelist",
#         "download list of all websites", "view more"
#     }

#     # Walk through the page in order
#     for el in soup.find_all(["h2", "h3", "h4", "h5", "h6", "div", "a"]):
#         text = el.get_text(strip=True)
#         classes = el.get("class") or []

#         # Detect category headers
#         if "Global Trends" in text:
#             cat = text.replace("Global Trends", "").strip()
#             if cat:
#                 current_cat = cat
#                 if current_cat not in categories:
#                     categories[current_cat] = []
#             continue

#         if "card-header" in classes and text and "Global Trends" not in text:
#             current_cat = text.strip()
#             if current_cat not in categories:
#                 categories[current_cat] = []
#             continue

#         # Collect technology links
#         if el.name == "a":
#             href = el.get("href") or ""
#             name = text

#             if not name or len(name) < 2:
#                 continue

#             # Skip noise
#             name_lower = name.lower()
#             if any(n in name_lower for n in NOISE):
#                 continue

#             # Only keep real technology links
#             if "trends.builtwith.com" in href or "/technology/" in href:
#                 # Prefer category from URL when possible
#                 # Example: /analytics/Hotjar → category = Analytics
#                 parts = [p for p in href.rstrip("/").split("/") if p]
#                 if len(parts) >= 2 and parts[-2] not in ("trends.builtwith.com", "www.builtwith.com"):
#                     url_cat = parts[-2].replace("-", " ").title()
#                 else:
#                     url_cat = current_cat

#                 if url_cat not in categories:
#                     categories[url_cat] = []

#                 if name not in categories[url_cat]:
#                     categories[url_cat].append(name)

#     # Build clean list of dicts (remove empty categories)
#     data = []
#     for cat, techs in categories.items():
#         # Remove very generic / empty categories
#         if not techs:
#             continue
#         if cat.lower() in ("other", "unknown", ""):
#             continue
#         data.append({cat: techs})

#     return data
# # ============================================================
# # Main processing
# # ============================================================
# def process_domain(page, domain: str, do_tech=True, do_meta=True):
#     result = {"domain": domain}

#     # ----- Technology Profile -----
#     if do_tech:
#         url = f"https://builtwith.com/{domain}"
#         print(f"\n→ Tech profile: {url}")
#         page.goto(url, wait_until="domcontentloaded", timeout=60000)
#         page.wait_for_timeout(3500)

#         if is_captcha_present(page):
#             solve_captcha(page)

#         soup = BeautifulSoup(page.content(), "html.parser")
#         tech_data = get_technology_profile(soup)
#         result["technology"] = json.dumps(tech_data)
#         print(f"  Technologies found: {len(tech_data)} categories")

#     # ----- Meta Information -----
#     if do_meta:
#         url = f"https://builtwith.com/meta/{domain}"
#         print(f"\n→ Meta page: {url}")
#         page.goto(url, wait_until="domcontentloaded", timeout=60000)
#         page.wait_for_timeout(2000)

#         if is_captcha_present(page):
#             solve_captcha(page)

#         soup = BeautifulSoup(page.content(), "html.parser")
#         meta = get_meta(soup)
#         result.update(meta)
#         print(f"  Company: {meta.get('company_name')}")

#     return result

# def wait_and_solve_captcha(page, timeout=8):
#     """Wait a bit and solve CAPTCHA if it appears."""
#     page.wait_for_timeout(1500)          # give page time to show CAPTCHA
#     if is_captcha_present(page):
#         print("  CAPTCHA detected → solving...")
#         return solve_captcha(page)
#     return True

# def main():
#     # ---------- CONFIG ----------
#     INPUT_CSV = "domains.csv"          # must have a column named "domain"
#     OUTPUT_CSV = "builtwith_results.csv"
#     DO_TECH = True
#     DO_META = True
#     # ----------------------------

#     if not Path(INPUT_CSV).exists():
#         print(f"Create {INPUT_CSV} with a column 'domain'")
#         print("Example:\ndomain\nexample.com\ngoogle.com")
#         sys.exit(1)

#     domains = []
#     with open(INPUT_CSV, newline="", encoding="utf-8") as f:
#         reader = csv.DictReader(f)
#         for row in reader:
#             d = row.get("domain", "").strip().lower()
#             if d:
#                 domains.append(d)

#     print(f"Loaded {len(domains)} domains from {INPUT_CSV}")

#     fieldnames = [
#         "domain", "company_name", "linkedin_site", "company_image", "location",
#         "telephone", "listed_contacts", "vertical", "company_data", "google_data",
#         "performance_data", "social_links", "emails", "traffic_rankings",
#         "technology_spend", "technology", "updated_at"
#     ]

#     results = []

#     with sync_playwright() as p:
#         browser = p.chromium.launch(
#             headless=False,
#             args=["--disable-blink-features=AutomationControlled"]
#         )
#         context = browser.new_context(
#             viewport={"width": 1280, "height": 900},
#             user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
#         )
#         page = context.new_page()
#         page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

#         for i, domain in enumerate(domains, 1):
#             print(f"\n{'='*60}")
#             print(f"[{i}/{len(domains)}] {domain}")
#             try:
#                 data = process_domain(page, domain, do_tech=DO_TECH, do_meta=DO_META)
#                 results.append(data)
#             except Exception as e:
#                 print(f"  Failed: {e}")
#                 results.append({"domain": domain, "error": str(e)})

#             # Save after every domain (safe against crashes)
#             with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
#                 writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
#                 writer.writeheader()
#                 writer.writerows(results)

#         browser.close()

#     print(f"\n✅ Finished. Results saved to {OUTPUT_CSV}")


# if __name__ == "__main__":
#     main()


#!/usr/bin/env python3
"""
BuiltWith scraper with automatic CAPTCHA solving.
- Reads domains from domains.csv
- Solves the human-test CAPTCHA when it appears
- Extracts Meta + Technology data
- Saves everything to CSV
"""

import sys
import time
import random
import io
import re
import json
import csv
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from PIL import Image
import torch
from transformers import CLIPProcessor, CLIPModel


# ============================================================
# CLIP model (loaded once)
# ============================================================
print("Loading CLIP model...")
device = "cuda" if torch.cuda.is_available() else "cpu"
clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").to(device)
clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
print(f"CLIP ready on {device}\n")


def human_delay(a=0.3, b=0.7):
    time.sleep(random.uniform(a, b))


def is_match(pil_image: Image.Image, target: str) -> float:
    texts = [
        f"a photo of a {target}",
        f"a close-up of a {target}",
        "a random object or animal",
    ]
    inputs = clip_processor(text=texts, images=pil_image, return_tensors="pt", padding=True).to(device)
    with torch.no_grad():
        outputs = clip_model(**inputs)
        probs = outputs.logits_per_image.softmax(dim=1)[0]
    return (probs[0] + probs[1]).item() / 2


def get_cell_boxes(img_w: int, img_h: int):
    cols, rows = 4, 3
    gap, pad = 8, 6
    cell_w = (img_w - 2 * pad - (cols - 1) * gap) // cols
    cell_h = (img_h - 2 * pad - (rows - 1) * gap) // rows
    boxes = []
    for r in range(rows):
        for c in range(cols):
            x1 = pad + c * (cell_w + gap)
            y1 = pad + r * (cell_h + gap)
            boxes.append((x1, y1, x1 + cell_w, y1 + cell_h))
    return boxes


def is_captcha_present(page) -> bool:
    try:
        if page.locator("#human-test-img").count() and page.locator("#human-test-img").is_visible():
            return True
        if page.locator("#target-display").count() and page.locator("#target-display").is_visible():
            return True
        return False
    except Exception:
        return False


def solve_captcha_once(page) -> bool:
    page.wait_for_selector("#human-test-img", timeout=15000)
    page.wait_for_timeout(1200)

    img_el = page.locator("#human-test-img")
    size = page.evaluate("""() => {
        const img = document.getElementById("human-test-img");
        return {w: img.naturalWidth, h: img.naturalHeight};
    }""")
    img_w, img_h = size["w"], size["h"]

    raw = page.locator("#target-display").inner_text().strip()
    target = " ".join(raw.split()[1:]) if raw and not raw[0].isalpha() else raw
    target = target.lower().strip()
    print(f"  Target: '{target}'")

    img_bytes = img_el.screenshot()
    full_img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    boxes = get_cell_boxes(img_w, img_h)

    scores = []
    for i, (x1, y1, x2, y2) in enumerate(boxes):
        cell = full_img.crop((x1, y1, x2, y2))
        score = is_match(cell, target)
        scores.append((i, score, x1, y1, x2, y2))

    scores.sort(key=lambda x: x[1], reverse=True)
    top2 = scores[:2]
    print(f"  Top cells: {[t[0] for t in top2]} scores={[round(t[1], 3) for t in top2]}")

    for rank, (i, score, x1, y1, x2, y2) in enumerate(top2, 1):
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        box = img_el.bounding_box()
        scale_x = box["width"] / img_w
        scale_y = box["height"] / img_h
        page.mouse.click(box["x"] + cx * scale_x, box["y"] + cy * scale_y)
        human_delay(0.9, 1.5)
        if rank == 1:
            page.wait_for_timeout(1400)

    page.wait_for_timeout(3500)
    return not is_captcha_present(page)


def solve_captcha(page, max_retries=3) -> bool:
    for attempt in range(1, max_retries + 1):
        if not is_captcha_present(page):
            return True
        print(f"  CAPTCHA attempt {attempt}/{max_retries}")
        try:
            if solve_captcha_once(page):
                print("  ✅ CAPTCHA solved")
                return True
        except Exception as e:
            print(f"  Error: {e}")
        if attempt < max_retries:
            page.reload(wait_until="domcontentloaded")
            page.wait_for_timeout(2500)
    print("  ❌ CAPTCHA failed after retries")
    return False


def wait_and_solve_captcha(page) -> bool:
    """Wait a bit and solve CAPTCHA if it appears."""
    page.wait_for_timeout(3000)
    if is_captcha_present(page):
        print("  CAPTCHA detected → solving...")
        return solve_captcha(page)
    return True


# ============================================================
# Parsing helpers
# ============================================================
def parse_value(value):
    """Extract numeric value from strings like '$5,000+', '₹282,530+ / month'"""
    value = str(value).strip()
    cleaned = value.replace("₹", "").replace("$", "").replace("€", "").replace(",", "")
    match = re.search(r"([\d.]+)\s*([KkMm]?)", cleaned)
    if match:
        try:
            num = float(match.group(1))
            suffix = match.group(2).lower()
            if suffix == "k":
                num *= 1_000
            elif suffix == "m":
                num *= 1_000_000
            return int(num)
        except ValueError:
            pass
    match = re.search(r"\d+", cleaned)
    return int(match.group(0)) if match else 0


def get_meta(soup: BeautifulSoup) -> dict:
    """Parse BuiltWith Meta Data Profile page."""
    result = {
        "company_name": None,
        "linkedin_site": None,
        "company_image": None,
        "location": None,
        "telephone": [],
        "listed_contacts": [],
        "vertical": None,
        "company_data": {},
        "google_data": {},
        "performance_data": {},
        "social_links": [],
        "emails": [],
        "traffic_rankings": {},
        "technology_spend": 0,
        "updated_at": datetime.now().isoformat(),
    }

    for card in soup.select("div.card"):
        header = card.select_one(".card-header")
        if not header:
            continue

        title = header.get_text(strip=True)
        body = card.select_one(".card-body")
        if not body:
            continue

        if title == "Company Name":
            name = body.get_text(strip=True)
            name = name.replace("Find People on LinkedIn", "").strip()
            result["company_name"] = None if name in ("-", "") else name

        elif title == "Location":
            loc = " ".join(body.stripped_strings)
            result["location"] = None if loc in ("-", "") else loc

        elif title == "Telephones":
            text = body.get_text(" ", strip=True)
            numbers = re.findall(r"\+\d[\d\- ]+\d", text)
            result["telephone"] = [n.strip() for n in numbers]

        elif title == "Publicly Listed Contacts":
            table = body.select_one("table")
            if table:
                for row in table.select("tbody tr"):
                    tds = row.find_all("td")
                    if len(tds) >= 2:
                        contact = {
                            "name": tds[0].get_text(strip=True),
                            "level": tds[2].get_text(strip=True) if len(tds) > 2 else None,
                        }
                        for a in row.select("a[href]"):
                            href = a.get("href", "")
                            if "linkedin" in href.lower():
                                contact["linkedin"] = href
                            elif "google" in href.lower():
                                contact["google"] = href
                        result["listed_contacts"].append(contact)

        elif title == "Website Information":
            labels = body.select(".info-label")
            if labels:
                for lab in labels:
                    key = lab.get_text(strip=True)
                    val_el = lab.find_next_sibling()
                    val = val_el.get_text(strip=True) if val_el else None
                    if not val:
                        parent_text = lab.parent.get_text(strip=True)
                        val = parent_text.replace(key, "", 1).strip() or None
                    if val in ("-", ""):
                        val = None
                    if "vertical" in key.lower():
                        result["vertical"] = val
                    else:
                        result["company_data"][key] = val
            else:
                for dt in body.select("dt"):
                    dd = dt.find_next_sibling("dd")
                    if dd:
                        key = dt.get_text(strip=True)
                        val = dd.get_text(strip=True)
                        if val == "-":
                            val = None
                        if "vertical" in key.lower():
                            result["vertical"] = val
                        else:
                            result["company_data"][key] = val

        elif title == "Technology Spend":
            text = body.get_text(strip=True)
            result["technology_spend"] = parse_value(text)

        elif title == "Social Links":
            links = []
            for a in body.select("a[href]"):
                href = a["href"].strip()
                if href.startswith("//"):
                    href = "https:" + href
                if href and not href.startswith("#") and href not in links:
                    links.append(href)
            if not links:
                text = body.get_text(" ", strip=True)
                for part in re.findall(r"(?:https?:)?//?[^\s]+|[\w\-]+\.(?:com|de|net|org|io|co)[^\s]*", text):
                    if part.startswith("//"):
                        part = "https:" + part
                    if part not in links:
                        links.append(part)
            result["social_links"] = links

        elif title == "Website Ranking":
            for dt in body.select("dt"):
                dd = dt.find_next_sibling("dd")
                if dd:
                    key = dt.get_text(strip=True)
                    val = dd.get_text(strip=True)
                    result["traffic_rankings"][key] = None if val == "-" else val

    for key in ["telephone", "listed_contacts", "company_data", "google_data",
                "performance_data", "social_links", "emails", "traffic_rankings"]:
        result[key] = json.dumps(result[key], ensure_ascii=False)

    return result


def get_technology_profile(soup: BeautifulSoup) -> list:
    """Clean parser for BuiltWith Technology Profile."""
    categories = {}
    current_cat = "Other"

    NOISE = {
        "usage statistics", "download list", "global trends",
        "web technology trends", "investor", "websitelist",
        "download list of all websites", "view more"
    }

    for el in soup.find_all(["h2", "h3", "h4", "h5", "h6", "div", "a"]):
        text = el.get_text(strip=True)
        classes = el.get("class") or []

        if "Global Trends" in text:
            cat = text.replace("Global Trends", "").strip()
            if cat:
                current_cat = cat
                categories.setdefault(current_cat, [])
            continue

        if "card-header" in classes and text and "Global Trends" not in text:
            current_cat = text.strip()
            categories.setdefault(current_cat, [])
            continue

        if el.name == "a":
            href = el.get("href") or ""
            name = text

            if not name or len(name) < 2:
                continue

            name_lower = name.lower()
            if any(n in name_lower for n in NOISE):
                continue

            if "trends.builtwith.com" in href or "/technology/" in href:
                parts = [p for p in href.rstrip("/").split("/") if p]
                if len(parts) >= 2 and parts[-2] not in ("trends.builtwith.com", "www.builtwith.com"):
                    url_cat = parts[-2].replace("-", " ").title()
                else:
                    url_cat = current_cat

                categories.setdefault(url_cat, [])
                if name not in categories[url_cat]:
                    categories[url_cat].append(name)

    data = []
    for cat, techs in categories.items():
        if not techs:
            continue
        if cat.lower() in ("other", "unknown", ""):
            continue
        data.append({cat: techs})

    return data


# ============================================================
# Main processing
# ============================================================
def process_domain(page, domain: str, do_tech=True, do_meta=True):
    result = {"domain": domain}

    # ----- Technology Profile -----
    if do_tech:
        url = f"https://builtwith.com/{domain}"
        print(f"\n→ Tech profile: {url}")
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        wait_and_solve_captcha(page)

        soup = BeautifulSoup(page.content(), "html.parser")
        tech_data = get_technology_profile(soup)
        result["technology"] = json.dumps(tech_data, ensure_ascii=False)
        print(f"  Technologies found: {len(tech_data)} categories")

    # ----- Meta Information -----
    if do_meta:
        url = f"https://builtwith.com/meta/{domain}"
        print(f"\n→ Meta page: {url}")
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        wait_and_solve_captcha(page)

        soup = BeautifulSoup(page.content(), "html.parser")
        meta = get_meta(soup)
        result.update(meta)
        print(f"  Company: {meta.get('company_name')}")

    return result


def main():
    # ---------- CONFIG ----------
    INPUT_CSV = "domains.csv"          # must have a column named "domain"
    OUTPUT_CSV = "builtwith_results.csv"
    DO_TECH = True
    DO_META = True
    # ----------------------------

    if not Path(INPUT_CSV).exists():
        print(f"Create {INPUT_CSV} with a column 'domain'")
        print("Example:\ndomain\nexample.com\ngoogle.com")
        sys.exit(1)

    domains = []
    with open(INPUT_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            d = row.get("domain", "").strip().lower()
            if d:
                domains.append(d)

    print(f"Loaded {len(domains)} domains from {INPUT_CSV}")

    fieldnames = [
        "domain", "company_name", "linkedin_site", "company_image", "location",
        "telephone", "listed_contacts", "vertical", "company_data", "google_data",
        "performance_data", "social_links", "emails", "traffic_rankings",
        "technology_spend", "technology", "updated_at"
    ]

    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        )
        page = context.new_page()
        page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        for i, domain in enumerate(domains, 1):
            print(f"\n{'='*60}")
            print(f"[{i}/{len(domains)}] {domain}")
            try:
                data = process_domain(page, domain, do_tech=DO_TECH, do_meta=DO_META)
                results.append(data)
            except Exception as e:
                print(f"  Failed: {e}")
                results.append({"domain": domain, "error": str(e)})

            # Save after every domain (safe against crashes)
            with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(results)

        browser.close()

    print(f"\n✅ Finished. Results saved to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()