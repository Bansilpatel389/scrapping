# last updated on 24/07/2025 
# Change : added client job mapping logic 

import re
import json 
import time as time_module
import random
import threading
import pickle
import traceback
import pyautogui
import numpy as np
import mysql.connector
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from datetime import datetime,timedelta, timezone,  time as dt_time
from upwork_NUXT import NUXT_function
import sys
import os

sys.stdout.reconfigure(line_buffering=True)

def cubic_bezier_curve(start, end, control1, control2, t):
    """Generates a point on a cubic Bézier curve"""
    return ((1 - t) ** 3 * start +
            3 * (1 - t) ** 2 * t * control1 +
            3 * (1 - t) * t ** 2 * control2 +
            t ** 3 * end)

# Auto Mouse Moments
def smooth_human_mouse_movement(min,max):
    screen_width, screen_height = pyautogui.size()

    for _ in range(random.randint(min,max)):  # Random number of movements
        start_x, start_y = pyautogui.position()
        end_x = random.randint(0, screen_width)
        end_y = random.randint(0, screen_height)

        # Control points for a natural movement curve
        control1_x = (start_x + end_x) // 2 + random.randint(-150, 150)
        control1_y = (start_y + end_y) // 2 + random.randint(-150, 150)
        control2_x = (start_x + end_x) // 2 + random.randint(-150, 150)
        control2_y = (start_y + end_y) // 2 + random.randint(-150, 150)

        steps = random.randint(40, 70)  # Random number of steps per movement
        for t in np.linspace(0, 1, num=steps):
            x = int(cubic_bezier_curve(start_x, end_x, control1_x, control2_x, t) + random.uniform(-1, 1))
            y = int(cubic_bezier_curve(start_y, end_y, control1_y, control2_y, t) + random.uniform(-1, 1))
            
            duration = random.uniform(0.02, 0.06)  # Random duration for smoothness
            pyautogui.moveTo(x, y, duration=duration)
            
            if random.random() < 0.1:  # Occasionally pause for realism
                time_module.sleep(random.uniform(0.1, 0.3))


def setup_driver():
    options = uc.ChromeOptions()

    # Browser configuration
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--disable-logging")
    options.add_argument("--log-level=3")
    options.add_argument("--remote-debugging-port=0")   # let it choose a free port

    # Performance
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-backgrounding-occluded-windows")
    options.add_argument("--disable-ipc-flooding-protection")
    options.add_argument("--enable-features=NetworkService,NetworkServiceInProcess")
    options.add_argument("--disable-renderer-backgrounding")

    # Random User-Agent
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    ]
    options.add_argument(f"user-agent={random.choice(user_agents)}")

    # Use the ChromeDriver we installed in the workflow
    driver = uc.Chrome(
        options=options,
        driver_executable_path="/usr/local/bin/chromedriver",
        browser_executable_path="/usr/bin/google-chrome",
        use_subprocess=True,
        version_main=None
    )

    # Block heavy resources
    try:
        driver.execute_cdp_cmd("Network.enable", {})
        driver.execute_cdp_cmd("Network.setBlockedURLs", {
            "urls": [
                "*.jpg", "*.jpeg", "*.png", "*.gif", "*.webp", "*.svg",
                "*.woff", "*.woff2", "*.ttf", "*.ico",
                "*tiktok.com/*",
                "*googletagmanager.com/*",
                "*doubleclick.net/*",
                "*facebook.net/*"
            ]
        })
    except:
        pass

    # Match your local resolution
    try:
        driver.set_window_size(1600, 900)
        driver.set_window_position(0, 0)
    except:
        pass

    return driver
def driver_get(url):
    driver.get(url)
    try :
        element = driver.title
        count = 1
        i = 0
        while "just a moment" in element.lower() :
            smooth_human_mouse_movement(1,1)
            try:
                if i % 4 == 0:
                    i = 1
                else : 
                    i += 1
                test = y + (i * 8)
                print(test)
                pyautogui.moveTo(x,test, duration=2) # You need to give position 
                time_module.sleep(1)
                pyautogui.click()
                print('clicked')
                smooth_human_mouse_movement(1,1)
            except :
                pass
            finally :
                element = driver.title
                if count % 2 == 0:
                    driver.refresh()
                    time_module.sleep(0.3)
                count+=1

    except Exception as e: 
        print(e)
    time_module.sleep(2.5)

def convert_to_json(dict_data):
    return json.dumps(dict_data, indent=4)

def convert_to_ist(utc_timestamp):
    try:
        # Parse UTC time
        utc_time = datetime.strptime(utc_timestamp, "%Y-%m-%dT%H:%M:%S.%fZ")
        utc_time = utc_time.replace(tzinfo=timezone.utc)

        # Convert to IST
        ist_time = utc_time.astimezone(timezone(timedelta(hours=5, minutes=30)))

        # Return as string
        return ist_time.strftime("%Y-%m-%d %H:%M:%S")

    except Exception as e:
        return None
        
def fetch_data(nuxt):
    try :
        job_activity = nuxt['vuex'][1]['jobDetails']['job']['clientActivity']
        if job_activity : 
            return (job_activity['totalApplicants'],job_activity['totalInvitedToInterview'],job_activity['invitationsSent'],job_activity['unansweredInvites'],job_activity['totalHired'],convert_to_ist(job_activity['lastBuyerActivity']),convert_to_json(job_activity))
        return None
    except Exception as e: 
       print(e)  
       return None



# def fetch_hourly_ids():
#     cursor = conn.cursor()
#     query = f"""
#         SELECT profile_url_id
#         FROM up_work_profiles
#         WHERE 
#             (is_favourite = 1 OR is_bid = 1)
#             AND is_closed = 0
#             AND is_removed = 0
#             AND is_rejected = 0
#             AND (
#                 (
#                     DATE(posted_on) = DATE(CONVERT_TZ(NOW(), '+00:00', '+05:30'))
#                     AND (
#                         last_scraped_at IS NULL
#                         OR TIMESTAMPDIFF(MINUTE, last_scraped_at, CONVERT_TZ(NOW(), '+00:00', '+05:30')) >= 60
#                     )
#                 )
#                 OR (
#                     DATE(posted_on) = DATE(CONVERT_TZ(NOW(), '+00:00', '+05:30')) - INTERVAL 1 DAY
#                     AND (
#                         last_scraped_at IS NULL
#                         OR TIMESTAMPDIFF(MINUTE, last_scraped_at, CONVERT_TZ(NOW(), '+00:00', '+05:30')) >= 120
#                     )
#                 )
#                 OR (
#                     DATE(posted_on) >= DATE(CONVERT_TZ(NOW(), '+00:00', '+05:30')) - INTERVAL 7 DAY
#                     AND DATE(posted_on) < DATE(CONVERT_TZ(NOW(), '+00:00', '+05:30')) - INTERVAL 1 DAY
#                     AND (
#                         last_scraped_at IS NULL
#                         OR TIMESTAMPDIFF(MINUTE, last_scraped_at, CONVERT_TZ(NOW(), '+00:00', '+05:30')) >= 360
#                     )
#                 )
#             )
#         ORDER BY posted_on DESC;
#         """
#     cursor.execute(query)
#     results = cursor.fetchall()
#     profile_ids = [row[0] for row in results]
#     cursor.close()
#     return profile_ids

def fetch_hourly_ids():
    cursor = conn.cursor()
    query = f"""
        SELECT profile_url_id
        FROM up_work_profiles
        WHERE 
            (is_favourite = 1 OR is_bid = 1)
            AND is_closed = 0
            AND is_removed = 0
            AND is_rejected = 0
            AND DATE(posted_on) >= DATE(CONVERT_TZ(NOW(), '+00:00', '+05:30')) - INTERVAL 7 DAY
            AND (
                last_scraped_at IS NULL
                OR TIMESTAMPDIFF(MINUTE, last_scraped_at, CONVERT_TZ(NOW(), '+00:00', '+05:30')) >= 60
            )
        ORDER BY posted_on DESC;
        """
    cursor.execute(query)
    results = cursor.fetchall()
    profile_ids = [row[0] for row in results]
    cursor.close()
    return profile_ids

def fetch_daily_ids():
    cursor = conn.cursor()
    query = f"""SELECT profile_url_id
                FROM up_work_profiles
                WHERE 
                    (is_favourite = 1 OR is_bid = 1)
                    AND is_closed = 0
                    AND is_removed = 0
                    AND is_rejected = 0
                    AND DATE(posted_on) < DATE(CONVERT_TZ(NOW(), '+00:00', '+05:30')) - INTERVAL 7 DAY
                    AND (
                        last_scraped_at IS NULL
                        OR last_scraped_at < (CONVERT_TZ(NOW(), '+00:00', '+05:30') - INTERVAL 24 HOUR)
                    )
                ORDER BY posted_on DESC;
        """
    cursor.execute(query)
    results = cursor.fetchall()
    profile_ids = [row[0] for row in results]
    cursor.close()
    return profile_ids
    
def format_sql(query, params):
    try:
        formatted = query
        for param in params:
            if isinstance(param, str):
                safe_param = param.replace("'", "\\'")
                formatted = formatted.replace("%s", f"'{safe_param}'", 1)
            elif param is None:
                formatted = formatted.replace("%s", "NULL", 1)
            else:
                formatted = formatted.replace("%s", str(param), 1)
        return formatted
    except Exception as e:
        return f"[Error formatting SQL: {e}]"


def insert_data(data, id, id_type):
    cursor = None
    
    try:
        cursor = conn.cursor()
        today_date = datetime.now()
        new_last_viewed = data[5]

        # Convert string to datetime if necessary
        if isinstance(new_last_viewed, str):
            try:
                new_last_viewed = datetime.strptime(new_last_viewed, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                new_last_viewed = None
        # cursor.execute(f'SELECT last_viewed_by_client FROM {upwork_profile_data} WHERE product_key = %s', (id,))
        # old_view = cursor.fetchone()
        # Get current datetime
        now = datetime.now()
        print("Current time : ", now)
        # if old_view :
        #     print("OLD last view : ",old_view[0])
        print("New last view : ",new_last_viewed)
        # Check if the difference is ≤ 60 minutes
        if now - new_last_viewed <= timedelta(minutes=60):
            notification_status = 3
            print("Viewed within the last 60 minutes.")
        else : 
            cursor.execute(f'SELECT send_notification FROM {upwork_profiles} WHERE profile_url_id = %s', (id,))
            status = cursor.fetchone() 
            notification_status = status[0]
    # MySQL-compatible UPDATE only
        if id_type == "hourly" : 
            update_query = f"""
            UPDATE {upwork_profiles} p
            JOIN upwork_profile_data d ON d.product_key = %s
            SET 
                d.proposals = %s,
                d.interviewing = %s,
                d.invites_sent = %s,
                d.unanswered_invites = %s,
                d.hires = %s,
                d.last_viewed_by_client = %s,
                d.job_activity = %s,
                p.last_scraped_at = %s,
                p.send_notification = %s
            WHERE p.profile_url_id = %s;
            """
        else :
            update_query = f"""
            UPDATE {upwork_profiles} p
            JOIN {upwork_profile_data} d ON d.product_key = %s
            SET 
                d.proposals = %s,
                d.interviewing = %s,
                d.invites_sent = %s,
                d.unanswered_invites = %s,
                d.hires = %s,
                d.last_viewed_by_client = %s,
                d.job_activity = %s,
                p.last_scraped_at = %s,
                p.send_notification = %s
            WHERE p.profile_url_id = %s;
            """

        params = (
            id,
            data[0], data[1], data[2], data[3], data[4], new_last_viewed, data[6],
            today_date,
            notification_status,
            id
        )

        cursor.execute(update_query, params)
        conn.commit()
        if notification_status == 3:
            print("✅ Notification sent.")
    except:
        traceback.print_exc()
    finally:
        if cursor:
            cursor.close()
  
 
   
def set_is_removed(id,status):
    cursor = conn.cursor()
    query = f"UPDATE {upwork_profiles} SET is_removed = %s,is_fetch = 0 WHERE profile_url_id = %s"
    cursor.execute(query,(status,id))
    conn.commit()
    cursor.close()

def set_is_closed(id):
    cursor = conn.cursor()
    query = f"UPDATE {upwork_profiles} SET is_closed = %s,is_fetch = 0 WHERE profile_url_id = %s"
    cursor.execute(query,(3,id))
    conn.commit()
    cursor.close()

def execute(id, id_type):
    global ids_count 
    print('id : ', id)
    url = 'https://www.upwork.com/jobs/~' + id
    time_module.sleep(random.uniform(3, 10))
    driver_get(url)
    try : 
        nuxt = NUXT_function(driver)
    except : return
    try :
        try : 
            status = nuxt['vuex'][1]['jobDetails']['job']['status']
            if status == 2 : 
                set_is_closed(id)
                set_is_removed(id,1)
                print("closed")
                return
        except : 
            try : 
                status = nuxt['vuex'][1]['job']['errorResponse']['status']
                if status == 403:
                    set_is_removed(id,3)
                    print("Private")
                    return
            except : 
                set_is_removed(id,3)
                print("Private")
                return
        try :
            status = driver.find_element(By.XPATH, '//*[@id="main"]/div/div/div/div[1]/div[2]/h4').text.strip()
        except : 
            status = driver.find_element(By.XPATH,'//*[@id="main"]/div[3]/div[4]/h1').text.strip()
        # 1 : no longer available, 2 : denied, 3 : private, 4 : not found 
        if ('no longer available' in status) or ('not found' in status):
            set_is_removed(id,1)
            return
        elif ('denied' in status) :
            set_is_removed(id,2)
            return
        elif ('private' in status):
            set_is_removed(id,3)
            return
    except : pass
    time_module.sleep(random.uniform(1, 3))
    try :
        result = fetch_data(nuxt)
        if result:
            result += (id,)
        else : 
            print('None found')
            return
        insert_data(result, id, id_type)
        print('updated')
        ids_count += 1
        time_module.sleep(random.uniform(2, 4))
        return 'successful'
    except Exception as e :
        set_is_removed(id,3)
        traceback.print_exc()

def priority():
    global ids_count,last_run_date
    hourly_ids = fetch_hourly_ids()
    if len(hourly_ids) != 0 :
        print(f"Updating hourly {len(hourly_ids)} fav id")
        for id in hourly_ids:
            execute(id, "hourly")
            ids_count+=1
    return 
       
def upwork_specific(daily_ids):
    global ids_count
    ids_count = 0
    try : 
        priority()
        if daily_ids :
            for index, id in enumerate(daily_ids) : 
                if index % 10 == 0:
                    priority()
                execute(id, "daily")
    except :
        driver.quit()
        print('driver closed')
        traceback.print_exc()
    return 


def is_night_time(check_time=None):
    if check_time is None:
        check_time = datetime.now().time()
    start = dt_time(21, 0)  # 8:00 PM
    end = dt_time(7, 0)     # 8:00 AM

    # Time is in the overnight range if it's >= 8 PM or < 8 AM
    return check_time >= start or check_time < end

def is_driver_alive(driver):
    try:
        driver.title  # or any simple command
        return True
    except:
        return False

x = 900
y = 392
driver = None
except_count = 0
pre_count = 0
print("User : ",os.getenv("MYSQL_USER", "scraper"))
print("Pass : ",os.getenv("MYSQL_PASS") or os.getenv("MYSQL_PASSWORD", ""))
conn = mysql.connector.connect(
    host=os.getenv("MYSQL_HOST", "2.24.198.101"),
    port=int(os.getenv("MYSQL_PORT", "3306")),
    user=os.getenv("MYSQL_USER", "scraper"),
    password=os.getenv("MYSQL_PASS") or os.getenv("MYSQL_PASSWORD", ""),
    database=os.getenv("MYSQL_DB") or os.getenv("MYSQL_DATABASE", "scrapping")
)
print('connection Successfull')
try : 
    while True :
        try:
            now = datetime.now().time()
            today = datetime.now().date()
            if not is_driver_alive(driver):
                # Reinitialize the driver here
                driver = setup_driver()
            if not conn.is_connected():
                conn.reconnect(attempts=3, delay=2)
            upwork_profiles = 'up_work_profiles'
            upwork_profile_data = 'upwork_profile_data'
            upwork_client_info='upwork_client_info'
            upwork_client_jobs_posted='upwork_client_jobs_posted'
            # daily_ids = fetch_daily_ids()
            daily_ids = []
            if len(daily_ids) > 0:
                print('Daily Update ids : ',len(daily_ids))
            else : daily_ids = []
            hourly_ids = fetch_hourly_ids()
            print('Hourly Update ids :',len(hourly_ids))
            if len(hourly_ids) == 0 and len(daily_ids) == 0:
                break
                if is_night_time(now):
                    print('night')
                    # driver.quit()
                    # print('driver closed')
                    time_module.sleep(random.randint(350,360))
                    # driver = setup_driver()
                    # print('driver created')
                else :
                    print('Sleeping..')
                    time_module.sleep(random.randint(100,160))
            else :
                upwork_specific(daily_ids)
            
            if except_count >= 5:
                break
            pre_count = len(hourly_ids) + len(daily_ids)
            # time_module.sleep(random.randint(200,300))
        except:
            traceback.print_exc()
            except_count += 1
            if except_count >= 5:
                break
            try : 
                last_run_date = None
                driver.quit()
            except : pass
except : traceback.print_exc()



# is_favourite = 1 OR is_bid = 1
# is_removed NOT IN (1,2)
# is_closed = 0 if closed then mark is_closed = 3
# is_rejected = 0

# Fetch frequency based on posted_on date

# if today then every hour
# if yesterday then every 2 hours
# if this week then every 6 hours
# else daily once at 7 AM 
 

