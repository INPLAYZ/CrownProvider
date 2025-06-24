from selenium import webdriver
from selenium.webdriver.chrome.service import Service
import os
import re
import requests
import zipfile
import tempfile
import shutil
import psutil
import time

class OpenWeb(object):
    def __init__(self, send_msg, project_folder, driver_executable):
       self.send_msg = send_msg
       self.project_folder = project_folder
       self.driver_executable = driver_executable

    def get_driver(self, url):
        try:
            options = webdriver.ChromeOptions()
            options.add_experimental_option("excludeSwitches", ["enable-logging"]) #關閉除錯LOG(selenium自帶的,並非程式碼錯誤)
            prefs = {"profile.managed_default_content_settings.images": 2} #不顯示圖片
            options.add_experimental_option("prefs", prefs)
            driver = self.check_driver_version(options)
            driver.implicitly_wait(30) #隱式等待(30秒)是在嘗試發現某個元素的時候，如果沒能立刻發現，就等待固定長度的時間，等時間到了還未發現則直接報錯.
            if not driver: raise
            driver.get(url)
            return driver
        except :
            self.send_msg()



    def check_driver_version(self, options):
        error_msg = ""
        try:
            driver = webdriver.Chrome(service=Service(executable_path=self.driver_executable), options=options)
            browser_version = driver.capabilities['browserVersion']
            driver_version = driver.capabilities['chrome']['chromedriverVersion']
            if browser_version.rsplit(".", 1)[0] != driver_version.rsplit(".", 1)[0]:
                driver.quit()
                error_msg = f"driver only supports {driver_version}, Current browser version is {browser_version} with"
                raise
            return driver
        except:
            if error_msg:
                msg = error_msg
            else:
                msg = self.send_msg()
            self.check_error(msg)


    def check_error(self, msg):
        """
        不能直接拿瀏覽器的版本號去下載driver 有時並不會有剛好對應的版本
        Google Chrome	119.0.6045.160 (正式版本) (64 位元) (cohort: Stable)
        driver: "119.0.6045.105"
        上面的範例如果值接用瀏覽器的版本號去載driver是找不到的
        後3碼的版號不可使用
        """
        if 'only supports' in msg:
            browser_version = re.findall(r'Current browser version is (.*) ', msg)[0].rsplit(".", 1)[0]
            version_list = requests.get("https://googlechromelabs.github.io/chrome-for-testing/known-good-versions.json").json()
            download_version = ""
            for driver_version in version_list["versions"]:
                if browser_version in driver_version["version"]:
                    download_version = driver_version["version"]
        else:
            download_list_page = requests.get("https://googlechromelabs.github.io/chrome-for-testing/#stable").text
            download_version = re.search(r'Stable</a><td><code>(.*?)</code>', download_list_page).group(1)
        download_url = f'https://storage.googleapis.com/chrome-for-testing-public/{download_version}/win64/chromedriver-win64.zip'
        self.download_driver(download_url)


    def download_driver(self, url):
        if os.path.isfile(self.driver_executable): #如果已經有舊的driver
            try:
                os.remove(self.driver_executable) #先刪除舊的
            except PermissionError:
                self.send_msg("download driver failed! reason:權限不足，通常是driver正在執行中無法砍掉舊的driver")
                self.force_delete_driver()
                time.sleep(3)
                os._exit(0)
        file = requests.get(url).content
        tmp_file = tempfile.TemporaryFile()
        tmp_file.write(file)
        zf = zipfile.ZipFile(tmp_file, mode='r') #以上下載檔案到記憶體
        for name in zf.namelist():
            if "driver.exe" in name:
                f = zf.extract(name, self.project_folder) #解壓縮
                os.rename(f, self.driver_executable) #將預設的driver.exe改成專案用的
                break
        zf.close()
        shutil.rmtree(f"{self.project_folder}//{name.split('/')[0]}")


    def force_delete_driver(self):
        print("try to kill driver process...")
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if proc.info['name'] == "HGAdriver.exe":
                    print(f"delete {proc.info}")
                    proc.terminate()  # 終止該程序
                    proc.wait()       # 等待程序終止
                    break
            except:
                self.send_msg()

