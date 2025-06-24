import requests
import os
import urllib3

class DataProvider(object):
    def __init__(self, send_msg):
        self.send_msg = send_msg
        self.session = None
        self.error_count = 0
        self.requests_count = 0
        self.headers = {
            "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
        }
        urllib3.disable_warnings(category=urllib3.exceptions.InsecureRequestWarning) #關閉SSL警告


    def requests_data(self, url, method="get", format="text", post_data=[]):
        try:
            resp_data = ""
            status_code = ""
            session = self.get_session()
            if method == "get":
                if post_data:
                    respone = session.get(url, timeout = 60, headers=self.headers, params=post_data, verify=False) #不驗證SSL
                else:
                    respone = session.get(url, timeout = 60, headers=self.headers)
            else:
                if post_data:
                    respone = session.post(url, params=post_data, timeout = 5, headers=self.headers)
                else:
                    respone = session.post(url, timeout = 60, headers=self.headers)
            self.requests_count += 1
            status_code = respone.status_code
            resp_data = eval(f"respone.{format}")
            if status_code in [200, 204]:
                self.error_count = 0
            else:
                raise
            return resp_data

        except requests.exceptions.SSLError: #SSL錯誤太多次才打log
            self.error_count += 1
            if self.error_count >= 50:
                msg = f"SSLError! url: {url}, method: {method} , format: {format}, post_data: {post_data}, status_code: {status_code}, error_count:{self.error_count}"
                self.send_msg(msg=msg, level="Warning")
                os._exit(0)
            self.close_session()
            return ""
        except requests.exceptions.ConnectionError as e:
            self.error_count += 1
            if "Remote end closed connection" in str(e):
                if self.error_count >= 40: self.send_msg("Connection aborted over 40 times, maybe site blocked!", level="Warning")
            if self.error_count >= 50: os._exit(0)
            return "" if format == "text" else {}
        except:
            self.error_count += 1
            if self.error_count >= 50:
                os._exit(0)
            self.close_session()
            msg = f"url: {url}, method: {method} , format: {format}, post_data: {post_data}, status_code: {status_code}, error_count:{self.error_count}"
            self.send_msg(msg=msg, level="Warning")
            return ""


    def get_session(self):
        if self.session is None:
            self.session = requests.Session()
        return self.session


    def close_session(self):
        if self.session is not None:
            self.session.close()
            self.session = None
