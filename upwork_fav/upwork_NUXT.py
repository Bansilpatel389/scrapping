import re
import json 
import time as time_module
import random
import traceback
import pyautogui
import numpy as np
import mysql.connector
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from datetime import datetime,timedelta, timezone, time as dt_time
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
import sys
import re
import json 
import time as time_module
import random
import traceback
import pyautogui
import numpy as np
import mysql.connector
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from datetime import datetime,timedelta, timezone, time as dt_time
import sys

# Increase the recursion limit for deeply nested data
sys.setrecursionlimit(2000)

def dereference(item, data_list, memo):
    """
    Recursively replaces integer references with their actual values,
    with robust handling for circular references.
    """
    # If the item is an integer, it's a pointer. Replace it with the actual value it points to.
    if isinstance(item, int) and 0 <= item < len(data_list):
        item = data_list[item]

    # For dicts and lists, use a cache (memo) to handle circular references.
    # We use the object's memory id() as a unique key.
    if isinstance(item, (dict, list)):
        if id(item) in memo:
            # If we've already started processing this object, return the cached reference to break the loop.
            return memo[id(item)]

        if isinstance(item, dict):
            # --- This is the crucial fix ---
            # 1. Create a new, empty dictionary.
            new_obj = {}
            # 2. Immediately cache it. If the recursion loops back to this 'item',
            #    this new_obj will be returned, correctly breaking the circular reference.
            memo[id(item)] = new_obj
            # 3. Now, populate the dictionary by recursively calling this function.
            for key, value in item.items():
                new_obj[key] = dereference(value, data_list, memo)
            return new_obj
            
        elif isinstance(item, list):
            # The same logic applies to lists.
            new_obj = []
            memo[id(item)] = new_obj
            for element in item:
                new_obj.append(dereference(element, data_list, memo))
            return new_obj

    # If it's a simple type (string, bool, etc.), return it directly.
    return item

# --- Main part of the script ---

output_filename = "job_data_mapped.json"

def map_data(raw_data):
    """
    Takes raw serialized data, maps it, and saves it to a file.
    """
    try:
        if not isinstance(raw_data, list) or len(raw_data) < 2:
            raise ValueError("Input data must be a non-empty list.")
            
        # Start the process from the main application object (usually at index 1).
        mapped_data = dereference(raw_data[1], raw_data, {})

        return mapped_data

    except Exception as e:
        print(f"❌ An error occurred: {e}")
        return None


def NUXT_function(driver):
    try:
        wait = WebDriverWait(driver, 15)
        script_tag = wait.until(
            EC.presence_of_element_located((By.ID, '__NUXT_DATA__'))
        )
        json_string = script_tag.get_attribute('innerHTML')
        data = json.loads(json_string)
        mapped_data = map_data(data)
        return mapped_data
    except Exception as e:
        print(f"❌ An error occurred: {e}")