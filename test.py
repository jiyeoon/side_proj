import os
import json
import datetime
import time
import sys
import requests
import easyocr

from datetime import datetime, timezone, timedelta

# 0. 변수 선언 
base_url = os.environ.get("BASE_URL")
kakao_access_token = os.environ.get("KAKAO_ACCESS_TOKEN")

if __name__ == "__main__":
    # 1. 카카오톡 메시지 전송
    kakao_url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    headers = {
        "Authorization": f"Bearer {kakao_access_token}"
    }
    data = {
        "template_object": json.dumps({
            "object_type": "text",
            "text": "Github Action Test\n\nThis is test message.",
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