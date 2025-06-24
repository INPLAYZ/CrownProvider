site = 'hga'
project_name = "HGAProvider"
# topic = f"{site}html"
topic = "test01"
heart = f'C:\Heart\heartHGAV2.txt'
#kafka集群
kafka_9 = []
kafka_10 = []
kafka_11 = []

environment_path = {
    "Local":{
        "send_html_data": [kafka_9]
    },
    "PRD":{
        "send_html_data": [kafka_9]
    },
    "PRD2":{
        "send_html_data": [kafka_10]
    },
    "PRD3":{
        "send_html_data": [kafka_11]
    },
}

settings = {
    "service":{
        "price_center_api":{
            "dashboard":"",
            "remove_handler": "",
            "heart_beat": "",
            "get_page": "",
        },
        "home_page": "https://hga030.com/",#https://hga030.com，https://hga038.com，https://mos011.com
        "web_api": "https://hga030.com/transform.php",
        "main_result_api": "https://125.252.69.119/app/member/account/result/result.php",
        "single_result_api": "https://125.252.69.119/app/member/account/result/FT_result_new.php",
        "test_account": "",
        "test_password": "",
        "ignore_league": ["特別投注", "電競足球", "特别投注"]
    },
    "transformer":{},
}
