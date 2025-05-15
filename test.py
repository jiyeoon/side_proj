import os
import json
import datetime
import time
import sys
import requests
import easyocr

from datetime import datetime, timezone, timedelta

# 0. 변수 선언 
slack_url = os.environ.get("SLACK_URL")
base_url = os.environ.get("BASE_URL")
kakao_access_token = os.environ.get("KAKAO_ACCESS_TOKEN")

def send_kakao_message(status, message):
    # 1. 카카오톡 메시지 전송
    kakao_url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    headers = {
        "Authorization": f"Bearer {kakao_access_token}"
    }

    if status == 0: msg = "Reservation Success!\n" + message
    elif status == -1: msg = "Reservation Test\n" + message
    else: msg = "Reservation Failed\n" + message
    
    data = {
        "template_object": json.dumps({
            "object_type": "text",
            "text": msg,
            "link": {
                "web_url": base_url,
                "model_web_url": base_url,
            }
        })
    }
    response = requests.post(kakao_url, headers=headers, data=data)
    if response.status_code == 200:
        print("카카오톡 메시지 전송 성공")
        sys.exit(0)
    else:
        print(f"카카오톡 메시지 전송 실패: {response.status_code}, {response.text}")
        sys.exit(1)

def send_slack_message(status, message):
    # 2. 슬랙 메시지 전송
    data = {}
    if status == 0:
        data['attachments'] = [
            {
                "title": f"예약 성공!",
                "title_link": base_url,
                "text": message,
                "color": "#2EB67D"
            }
        ]
    elif status == -1:
        data['attachments'] = [
            {
                "title": f"예약 테스트",
                "title_link": base_url,
                "text": message,
                "color": "#36C5FO"
            }
        ]
    else:
        data['attachments'] = [
            {
                "title": f"예약 실패",
                "title_link": base_url,
                "text": message,
                "color": "E01E5A"
            }
        ]
    response = requests.post(slack_url, json=data)
    if response.status_code == 200:
        print("Slack 메시지 전송 성공")
    else:
        print(f"Slack 메시지 전송 실패: {response.status_code}, {response.text}")

if __name__ == "__main__":
    # send_kakao_message(-1, "Test message")
    send_slack_message(1, "Test message")