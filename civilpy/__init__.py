## Imports 3 libraries to be able to load user config values from secrets.json
#import json
#import os
#from pathlib import Path
#
## Setups up the selenium environment for data collection
#from selenium import webdriver
#from selenium.webdriver.chrome.options import Options
#from selenium.webdriver.chrome.service import Service
#from webdriver_manager.chrome import ChromeDriverManager
#
#options = Options()
#options.add_argument("start-maximized")
#options.add_experimental_option("detach", True)
#driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
#driver.get("https://www.google.com")
#
## Looks for secrets.json in the parent directory
#cwd = Path(os.getcwd()).parent / 'secrets.json'
#
#with open(cwd, "r") as read_content:
#    config_values = json.load(read_content)
#
## Check to see if user has modified default config values
#if config_values['CHROME_DRIVER_PATH'] == "C:\\PATH\\TO\\CHROME\\DRIVER":
#    print("WARN: Default Chrome path found, some tools may not work without config values set")
#else:
#    print("Config Values Loaded...\n\n")