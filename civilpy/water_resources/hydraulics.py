from civilpy import driver
from selenium.webdriver.common.by import By
import time

driver.get("https://streamstats.usgs.gov/ss/")
time.sleep(.1)
driver.find_element(By.XPATH, "/html/body/div[7]/div/div/div[1]/button").click()
