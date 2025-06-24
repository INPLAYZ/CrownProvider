import CrawlerService
import AppSettings
from kafka import KafkaProducer
import socket
import traceback
import MachinePath
import os
import time
import OpenWeb
import GetPage
import DataProvider


def send_msg(msg = "", level = "Error"):
    """
    print錯誤訊息

    Args:
        level (str): 預設Error,報錯是最常用的其餘為Information,Warning,Critical,Trace,Debug
        msg (str): 預設空字串,報錯時可自行加入查看的訊息
    """
    sys_log = traceback.format_exc()
    send_message = msg if sys_log == "NoneType: None\n" else f"{sys_log}{msg}"
    if level in ["Error", "Warning"]:
        print("發生錯誤", send_message)
    else:
        print(send_message)
    return sys_log


def main():
    try:
        global environment
        machine_name = socket.gethostname()
        environment = MachinePath.machine_path.get(machine_name)
        if not environment: environment = "Local"
        environment_path = AppSettings.environment_path
        if environment not in environment_path : return
        project_path = environment_path[environment]
        project_name = AppSettings.project_name
        project_folder = os.environ["APPDATA"].split("AppData")[0] + "Desktop\\" + project_name
        project_executable = project_folder +  '\\' + project_name + '.exe'
        driver_executable =  project_folder +  '\\' + project_name.replace("Provider", "driver") + '.exe'
        version = "test"
        if os.path.isfile(project_executable):
            version = time.strftime("%m/%d %H:%M", time.localtime(os.path.getmtime(project_executable)))
        provider = DataProvider.DataProvider(send_msg)
        open_web = OpenWeb.OpenWeb(send_msg, project_folder, driver_executable)
        get_page = GetPage.GetPage(send_msg, provider, machine_name)
        with open(AppSettings.heart, 'w') as f:
            f.write("1")
        service_inputs = {
            "kafka_producers": [
                KafkaProducer(
                    bootstrap_servers=server,    # Broker 位置
                    value_serializer=lambda v: v.encode('utf-8')
                )
                for server in project_path["send_html_data"]
            ],
            "machine_name": machine_name,
            "environment": environment,
            "version": version,
            "send_msg": send_msg,
            "provider": provider,
            "open_web" :open_web,
            "get_page": get_page,
            "heart_txt": AppSettings.heart,
            "topic":AppSettings.topic
        }
        CrawlerService.CrawlerService(service_inputs).main()
    except:
        error_msg = f"{traceback.format_exc()}"
        print(error_msg)
        #send_msg()
        return

if __name__ == "__main__":
    main()