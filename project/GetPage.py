import time
import json
import AppSettings

class GetPage(object):
    def __init__(self, send_msg, provider, machine_name):
        self.send_msg = send_msg
        self.provider = provider
        self.machine_name = machine_name
        self.setting = AppSettings.settings["service"]

    def get_page(self):
        try:
            login_info = {
                'pageName': 'ALL_allgame',
                'pageType': None,
                'account': 'aaaCSAW1237774', #放你的帳號
                'password': 'bbb456A7', #放你的密碼
                'phone': None,
                'userName': None
            }
            return login_info

        except:
            self.send_msg()
