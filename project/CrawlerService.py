import AppSettings
from datetime import datetime, date, timedelta
import time
import os
import threading
import xmltodict
import re
import json
from selenium.webdriver.common.by import By
import re


class CrawlerService(object):
    def __init__(self, service_inputs):
        self.kafka_producers = service_inputs["kafka_producers"]
        self.machine_name = service_inputs["machine_name"]
        self.environment = service_inputs["environment"]
        self.version = service_inputs["version"]
        self.send_msg = service_inputs["send_msg"]
        self.provider = service_inputs["provider"]
        self.open_web = service_inputs["open_web"]
        self.get_page = service_inputs["get_page"]
        self.heart_txt = service_inputs["heart_txt"]
        self.topic = service_inputs["topic"]
        self.setting = AppSettings.settings["service"]
        self.maintenance = "F"
        self.page_info = {'pregame': 0, "inplay": 0}
        self.page_name = ""
        self.account = ""
        self.password = ""
        self.user_uid = ""
        self.user_ver = ""
        self.driver = None
        self.VPNError = False
        self.start_time = time.time()
        self.pregame_first_run = True  #這個變數影響抓賽前數量的判斷
        self.pregame_count = 0 #算賽前數量
        threading.Thread(target=self.listen_status, args=()).start()
        threading.Thread(target=self.call_dashboard, args=()).start()
        threading.Thread(target=self.check_running_6H, args=()).start()



    def main(self):
        try:
            self.start_time = time.time()
            self.check_VPN()
            self.check_maintenance()
            self.web_login()
            self.get_user_config()
            if not self.user_uid or not self.user_ver:
                raise Exception("can't get uid or ver")
            self.driver.quit()
            self.driver = None
            threading.Thread(target=self.get_inplay_data).start()
            threading.Thread(target=self.get_pregame_service).start()
            threading.Thread(target=self.get_result_service).start()
        except:
            self.send_msg()
            self.remove_handle()

    def check_VPN(self):
        while True:
            site_page = self.provider.requests_data("https://hga030.com/")
            if "您所在的地區禁止訪問本網站" in site_page:
                print("VPNError: VPN need enabled!")
                self.VPNError = True
                time.sleep(30)
            else:
                self.VPNError = False
                return

    def check_maintenance(self):
        payload = {
            "p": "service_mainget",
            "langx": "zh-tw",
            "login": "N"
        }
        while True:
            xml_data = self.provider.requests_data(self.setting['web_api'], method="post", post_data=payload)
            web_status = xmltodict.parse(xml_data)
            if web_status['serverresponse']['maintain_sw'] == "Y":
                print("HGA Site is maintenance")
                self.maintenance = "T"
            else:
                self.maintenance = "F"
                return
            time.sleep(60)


    def web_login(self, use_test_account=False):
        """
        call API獲得帳號密碼，然後登入網站

        Args:
            use_test_account (bool):是否使用固定的測試號(僅在開發/維護情況下使用)

        login_info example:
            {'pageName': 'ALL_allgame',
            'pageType': None,
            'account': 'aaa1234',
            'password': 'bbb4567',
            'phone': None,
            'userName': None}
        """
        try:
            if not use_test_account:
                login_info = self.get_page.get_page()
                # login_info = json.loads(login_info)
                self.page_name = login_info['pageName']
                self.account = login_info['account']
                self.password = login_info['password']
                print(f"login info:\naccount:{self.account}\npassword:{self.password}\npage_name:{self.page_name}\n")

            self.driver = self.open_web.get_driver(self.setting["home_page"])
            username_input = self.driver.find_element(By.ID, 'usr')
            if use_test_account:
                username_input.send_keys(self.setting['test_account'])
            else:
                username_input.send_keys(self.account)

            password_input = self.driver.find_element(By.ID, 'pwd')
            if use_test_account:
                password_input.send_keys(self.setting['test_password'])
            else:
                password_input.send_keys(self.password)

            login_button = self.driver.find_element(By.ID, 'btn_login')
            login_button.click()
            time.sleep(5)
            page = self.driver.page_source
            if "您輸入的帳號或密碼不正確" in page:
                if use_test_account:
                    raise Exception(f"帳號:{self.setting['test_account']} 登入失敗(密碼錯誤)")
                else:
                    raise Exception(f"帳號:{self.account} 登入失敗(密碼錯誤)")
            #問你要不要設置簡易密碼，點選否
            ez_password_button = self.driver.find_element(By.ID, 'C_no_btn')
            ez_password_button.click()
        except:
            self.send_msg("login failed")
            self.remove_handle()

    def get_user_config(self):
        """
        拿用戶的uid跟ver，請求會需要
        """
        retry_times = 0
        while True:
            page_source = self.driver.page_source
            uid_match = re.search(r"_CHDomain.uid = '(.*?)';", page_source)
            ver_match = re.search(r"_CHDomain.ver = '(.*?)';", page_source)
            if uid_match and ver_match: break
            retry_times += 1
            if retry_times >= 25: return None #重試25次還沒拿到就return None
            time.sleep(1)
        uid = uid_match.group(1)
        ver = ver_match.group(1)
        print(f"uid:{uid}  ver:{ver}")
        self.user_uid = uid
        self.user_ver = ver

    def get_pregame_service(self):
        while True:
            try:
                self.pregame_count = 0
                lid_list = self.get_pregame_lid_list()
                for lid_data in lid_list:
                    self.get_pregame_gamelist(lid_data)
                    time.sleep(1)
            except:
                self.send_msg()
            self.pregame_first_run = False
            self.page_info['pregame'] = self.pregame_count #更新比賽數量
            time.sleep(60)

    def get_pregame_lid_list(self):
        """
        獲取賽前聯盟ID列表
        """
        payload = {
            "p": "get_league_list_All",
            "uid": self.user_uid,
            "ver": self.user_ver,
            "langx": "zh-tw",
            "gtype": "FT",
            "FS": "N",
            "showtype": "", #fu=早盤 ft=今日
            "date": "", #all=所有比賽,0=今天 1=明天
            "nocp": "N"
        }
        try:
            league_id_list = []
            payload["ts"] = int(datetime.now().timestamp() * 1000),
            for date in [0, 1]: #抓今天跟明天
                payload["showtype"] = "ft" if date == 0 else "fu"
                payload["date"] = date
                showtype = "today" if date == 0 else "early"
                xml_data = self.provider.requests_data(self.setting['web_api'], method="post", post_data=payload)
                if not xml_data: return []
                if "&#20320;&#30340;&#22320;&#21312;&#23660;&#26044;&#19981;&#21512;&#27861;&#22320;&#21312;" in xml_data:
                    raise Exception("VPNError")
                if "doubleLogin" in xml_data:
                    raise Exception("Double login error!")
                league_list_detail = xmltodict.parse(xml_data)
                if 'classifier' not in league_list_detail['serverresponse']: continue #這一天沒有任何比賽(通常是換日前1小時，站台的"今日"比賽都開打了)
                if isinstance(league_list_detail['serverresponse']['classifier']['region'], dict): #dict代表現在只有一個國家有比賽
                    league_list_detail['serverresponse']['classifier']['region'] = [league_list_detail['serverresponse']['classifier']['region']]
                for region_detail in league_list_detail['serverresponse']['classifier']['region']:
                    if isinstance(region_detail['league'], dict): #dict代表這個國家現在只有1個聯盟有比賽
                        region_detail['league'] = [region_detail['league']]
                    for league_detail in region_detail['league']:
                        if any(keyword in league_detail['@name'] for keyword in self.setting['ignore_league']): continue #不要的聯盟
                        league_id_list.append({
                            "date":date,
                            "lid":league_detail['@id'],
                            "type": showtype,
                        })
            return league_id_list
        except Exception as error:
            if "VPNError" == str(error):
                self.send_msg("VPN need enabled!", level="Warning")
            elif "Double login error!" == str(error):
                self.send_msg("Double login error!", level="Warning")
                self.remove_handle()
            else:
                self.send_msg(f"get pregame league list error! show type:{showtype} xml data:{xml_data}")
            return []

    def get_pregame_gamelist(self, lid_data):
        """
        使用聯盟ID請求該聯盟底下的比賽(比賽為簡易資訊)
        Args:
            lid_data (dict):{
                "date":0,
                "lid":123456,
                "type":"today"
            }
        """
        payload = {
            "uid": self.user_uid,
            "ver": self.user_ver,
            "langx": "zh-tw",
            "p": "get_game_list",
            "p3type": "",
            "date": lid_data['date'], #all=所有比賽,0=今天 1=明天
            "gtype": "ft",
            "showtype": lid_data['type'],#early=早盤 today=今日
            "rtype": "r",
            "ltype": 4,
            "cupFantasy": "N",
            "lid": lid_data['lid'], #填入LID
            "action": "click_league",
            "sorttype": "L",
            "specialClick": "",
            "isFantasy": "N",
            "ts": int(datetime.now().timestamp() * 1000),
        }
        try:
            xml_data = self.provider.requests_data(self.setting['web_api'], method="post", post_data=payload)
            if "&#20320;&#30340;&#22320;&#21312;&#23660;&#26044;&#19981;&#21512;&#27861;&#22320;&#21312;" in xml_data:
                raise Exception("VPNError")
            if "doubleLogin" in xml_data:
                raise Exception("Double login error!")
            if not xml_data: return
            gamelist_detail = xmltodict.parse(xml_data)
            self.send_data("SC-pregame-List", gamelist_detail)

            if int(gamelist_detail["serverresponse"]['totalDataCount']) == 0:
                self.send_msg(f"there are no matches under this league. plz check->league id:{lid_data['lid']} showtype:{lid_data['type']}", level="Trace")
                return
            #dict = 這個聯盟只有一場比賽
            try:
                if isinstance(gamelist_detail['serverresponse']['ec'], dict):
                    gamelist_detail['serverresponse']['ec'] = [gamelist_detail['serverresponse']['ec']]
            except:
                raise Exception(f"unknown key error, plz check data: {gamelist_detail}")
            self.pregame_count += len(gamelist_detail['serverresponse']['ec'])
            if self.pregame_first_run: #爬蟲剛開的時候即時更新比賽數量(不然數量一直掛0會以為壞掉)
                self.page_info['pregame'] += len(gamelist_detail['serverresponse']['ec'])
            for ec_detail in gamelist_detail['serverresponse']['ec']:
                ecid = ec_detail['@id'][2:] #@ID值為"ec8583978"格式，只取後面的數字部份
                self.get_single_pregame(lid_data['lid'], ecid, lid_data['type'])
                time.sleep(1)
        except Exception as error:
            if "VPNError" == str(error):
                self.send_msg("VPN need enabled!", level="Warning")
            elif "Double login error!" == str(error):
                self.send_msg("Double login error!", level="Warning")
                self.remove_handle()
            else:
                self.send_msg()

    def get_single_pregame(self, league_id, ecid, showtype):
        """
        使用比賽簡易資訊內的ecid去請求單一場比賽的詳細資訊
        """
        payload = {
            "uid": self.user_uid,
            "ver": self.user_ver,
            "langx": "zh-tw",
            "p": "get_game_more",
            "gtype": "ft",
            "showtype": showtype,#early=早盤 today=今日
            "ltype": 4,
            "isRB": "N",
            "lid": league_id,
            "specialClick": "",
            "mode": "NORMAL",
            "ts": int(datetime.now().timestamp() * 1000),
            "ecid": ecid  #比賽的ID
        }
        try:
            xml_data = self.provider.requests_data(self.setting['web_api'], method="post", post_data=payload)
            if not xml_data: return
            if "&#20320;&#30340;&#22320;&#21312;&#23660;&#26044;&#19981;&#21512;&#27861;&#22320;&#21312;" in xml_data:
                raise Exception("VPNError")
            if "error@connect fail" in xml_data:
                raise Exception("connect error from xml response")
            game_detail = xmltodict.parse(xml_data)
            self.send_data("SC-pregame-Single", game_detail)
        except Exception as error:
            if "VPNError" == str(error):
                self.send_msg("VPN need enabled!", level="Warning")
            else:
                self.send_msg(f"show type:{showtype}, lid:{league_id}, ecid(gameid):{ecid}")


    def get_inplay_data(self):
        """
        獲取足球賽中的比賽
        """
        payload = {
            "uid": self.user_uid,
            "ver": self.user_ver,
            "langx": "zh-tw",
            "p": "get_game_list",
            "p3type": "",
            "date": "",
            "gtype": "ft", #ft=足球
            "showtype": "live", #inplay
            "rtype": "rb",
            "ltype": 4,
            "cupFantasy": "N",
            "sorttype": "L",
            "specialClick": "",
            "isFantasy": "N",
        }
        while True:
            try:
                payload["ts"] = int(datetime.now().timestamp() * 1000)
                xml_data = self.provider.requests_data(self.setting['web_api'], method="post", post_data=payload)
                if xml_data:
                    if "&#20320;&#30340;&#22320;&#21312;&#23660;&#26044;&#19981;&#21512;&#27861;&#22320;&#21312;" in xml_data:
                        raise Exception("VPNError")
                    SC_inplay_data = xmltodict.parse(xml_data)
                    self.page_info['inplay'] = int(SC_inplay_data['serverresponse']['totalDataCount'])
                    if int(SC_inplay_data['serverresponse']['totalDataCount']) >= 1:
                        self.send_data("SC-inplay-List", SC_inplay_data)
            except Exception as error:
                #有時候會莫名其妙跳重複登入錯誤，直接重開爬蟲
                if "doubleLogin" in xml_data:
                    self.send_msg("Double login error!", level="Warning")
                    self.remove_handle()
                if "VPNError" == str(error):
                    self.send_msg("VPN need enabled!", level="Warning")
                else:
                    self.send_msg(f"get inplay data error! plz check: {SC_inplay_data}")
                    os._exit(0)

            time.sleep(15)

    def get_result_service(self):
        """
        獲取今天、昨天的賽果頁面(丟整個HTML)
        """
        while True:
            try:
                all_gameinfo_list = []
                print("get result data...")
                #今天
                payload = {
                    "game_type": "FT",
                    "today": str(date.today()),
                    "uid": self.user_uid,
                    "langx": "zh-tw"
                }
                html_data = self.provider.requests_data(self.setting['main_result_api'], post_data=payload)
                if "這個日期沒有賽果" in html_data:
                    print("今日目前無賽果")
                if html_data:
                    self.send_data("result", html_data)
                    all_gameinfo_list.extend(self.get_result_gameid_list(html_data))

                #昨天
                payload = {
                    "game_type": "FT",
                    "list_date": str(date.today() - timedelta(days=1)),
                    "uid": self.user_uid,
                    "langx": "zh-tw"
                }
                html_data = self.provider.requests_data(self.setting['main_result_api'], post_data=payload)
                if "這個日期沒有賽果" in html_data:
                    print("昨日目前無賽果")
                if html_data:
                    self.send_data("result", html_data)
                    all_gameinfo_list.extend(self.get_result_gameid_list(html_data))

                #抓單場賽果
                print(f"get single result data... game count:{len(all_gameinfo_list)}")
                for game_info in all_gameinfo_list:
                    self.get_single_result(game_info)
                    time.sleep(1)
            except:
                self.send_msg()
            time.sleep(600)

    def get_result_gameid_list(self, html_page):
        """
        在賽果頁中拿所有比賽的ID，還有page type(FullTime,Cornor)

        Args:
            html_page (str): 賽果頁HTML

        Returns:
            list[tuple]: 所有打完的比賽的page type, ID
        """
        tr_pattern = r'<tr class="acc_result_tr_top(?:BL)?".*?>(.*?)</tr>'

        tr_matches = re.findall(tr_pattern, html_page, re.DOTALL)

        result = []

        game_id_pattern = r"'FT','(\d+)'"

        for tr in tr_matches:
            game_id_match = re.search(game_id_pattern, tr)
            game_id = game_id_match.group(1)

            page_type = "Cornor" if "角球數" in tr else "FullTime"

            if any(keyword in tr for keyword in ["加時賽", "點球(讓球盤)", "點球(大小盤)"]): continue #不需要抓的

            # 將頁面類型和 game_id 作為 tuple 加入結果列表
            result.append((page_type, game_id))

        return result

    def get_single_result(self, game_info):
        """
        取得單場賽果的資訊，然後用正則拿需要的東西

        Args:
            game_info (tuple): ("FullTime","7250103")
        """
        try:
            payload = {
                'uid': self.user_uid,
                'gtype': 'FT',
                'game_id': game_info[1],
                'langx': 'zh-tw'
            }
            result = self.provider.requests_data(self.setting['single_result_api'], post_data=payload)
            if not result: return

            gdata_match = re.search(r"var\s+gdata\s*=\s*Array\(([^;]+)\);", result)
            heads_match = re.search(r"var\s+heads\s*=\s*Array\(([^;]+)\);", result)

            if gdata_match and heads_match:
                gdata = gdata_match.group(0)
                heads = heads_match.group(0)
            else: #站台換日的時候會抓不到資料
                return

            need_send_data = f"type:{game_info[0]},{gdata}{heads}"
            self.send_data("singleresult", need_send_data)
        except:
            self.send_msg()

    def send_data(self, page_type:str, data):
        """送出資料到Game Data

        Args:
            page_type (str): 賽事狀態
            data (str / dict): 賽事資料
        """
        try:
            result = {
                "tczb": page_type,
                "machinename": self.machine_name,
                "timestamp": int(datetime.now().timestamp() * 1000),
                "data": data,
            }
            result_string = json.dumps([result], ensure_ascii=False)
            result_string = result_string.replace("null", '""')
            #針對賽果的kafka data(包含result、singleresult)，轉換成舊的parser可以接起來的格式(result kafka data為非JSON支援格式)
            if 'result' in page_type:
                result_string = result_string.replace(', "data": "', ',"data":').replace('"}]', '\n\n}]')
                #主賽果頁的html不需經過json dumps處理
                if page_type == "result":
                    front_kafka_data = result_string.split(',"data":')[0]
                    result_string = f"""{front_kafka_data},"data":{data}}}]"""
            for kafka in self.kafka_producers:
                kafka.send(self.topic, result_string)
        except:
            self.send_msg(msg=page_type)


    def listen_status(self):
        while True:
            try:
                with open(self.heart_txt, 'r') as f:
                    status = f.read()
                if status == "0":
                    msg = "Control close program."
                    self.send_msg(msg=msg, level="Information")
                    self.remove_handle()
                    os._exit(0)
                time.sleep(5)
            except:
                self.send_msg()
                time.sleep(5)
                continue


    def check_running_6H(self):
        while True:
            now = time.time()
            if self.page_name:
                if self.start_time != "":
                    if (now-self.start_time) > 21600:
                        msg = "Running 6H, close program."
                        self.send_msg(msg=msg, level="Information")
                        self.remove_handle()
            time.sleep(5)


    def remove_handle(self):
        try:
            if self.driver:
                self.driver.quit()
            time.sleep(2)
            os._exit(0)
        except:
            self.send_msg()


    def call_dashboard(self):
        need_send = 0
        while True:
            try:
                if self.page_name:
                    dashboard_msg = f"PC:{self.page_info['pregame']},IC:{self.page_info['inplay']}"
                elif self.VPNError:
                    dashboard_msg = "VPNError" #VPN有問題
                else:
                    dashboard_msg = "waithandle..." #還沒有拿到帳密登入的情況
                print(dashboard_msg)
                need_send += 1
                if need_send == 10:
                    msg = f"{datetime.now()} program alive, version is {self.version}, requests count: {self.provider.requests_count}, dashboard_msg: {dashboard_msg}"
                    self.send_msg(msg=msg, level="Information")
                    need_send = 0
                self.provider.requests_count = 0
            except:
                self.send_msg()
            time.sleep(60)