import os
import datetime
import time
import sys
import json
import requests
import easyocr

from datetime import datetime, timezone, timedelta

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# 0. 변수 선언 
KST = timezone('Asia/Seoul')
TARGET_TIME = datetime.now(KST).replace(hour=9, minute=0, second=0, microsecond=0)

login_id = os.environ.get("LOGIN_ID")
login_pw = os.environ.get("LOGIN_PASSWORD")
login_url = os.environ.get("LOGIN_URL")
base_url = os.environ.get("BASE_URL")
slack_url = os.environ.get("SLACK_URL")
kakao_access_token = os.environ.get("KAKAO_ACCESS_TOKEN")

# 0. 함수 정의
def msgInfo(msg):
    pStr = "\t[INFO]>> [{}] : {}\n".format(datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S'), msg)
    sys.stdout.write(pStr)

def send_slack_message(status, msg):
    title = "Reservation Success" if status == 0 else "Reservation Failed"
    color = "#2EB67D" if status == 0 else "#E01E5A"

    data = {
        "attachments": [
            {
                "title": title,
                "title_link": base_url,
                "text": msg,
                "color": color
            }
        ]
    }

    response = requests.post(slack_url, json=data)
    if response.status_code == 200:
        msgInfo("Slack 메시지 전송 성공")
    else:
        msgInfo(f"Slack 메시지 전송 실패: {response.status_code}, {response.text}")

def send_kakao_message(status, msg):
    kakao_url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    headers = {"Authorization": f"Bearer {kakao_access_token}"}

    title = "Reservation Success" if status == 0 else "Reservation Failed"
    message = f"{title}\n{msg}"

    data = {
        "template_object": json.dumps({
            "object_type": "text",
            "text": message,
            "link": {
                "web_url": base_url,
                "model_web_url": base_url,
            },
            "buttons": [
                {
                    "title": "예약하러 가기",
                    "link": {
                        "web_url": base_url,
                        "mobile_web_url": base_url,
                    }
                }
            ]
        })
    }
    response = requests.post(kakao_url, headers=headers, data=data)
    if response.status_code == 200:
        msgInfo("Kakao 메시지 전송 성공")
    else:
        msgInfo(f"Kakao 메시지 전송 실패: {response.status_code}, {response.text}")
    


def main():
    # 1. Selenium으로 로그인
    msgInfo("Chrome Driver 설정")
    options = Options()
    options.add_argument("--headless")  # 중요: GUI 없이 실행
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=options)

    # 2. 로그인
    msgInfo("로그인 페이지로 이동")
    driver.get(login_url)
    driver.find_element(By.NAME, 'login_id').send_keys(login_id)
    driver.find_element(By.NAME, 'login_pwd').send_keys(login_pw)
    driver.find_element(By.XPATH, '//*[@id="content"]/div/div/div/button').click()

    try:
        driver.switch_to.alert.accept() # 이미 로그인 되어있는 경우 처리
        msgInfo("이미 로그인 되어있었습니다.")
    except:
        pass

    # 3. 예약하기 버튼 클릭
    msgInfo("메인 홈페이지에서 예약하기 버튼 클릭")
    element = driver.find_element(By.XPATH, '//*[@id="container"]/div[2]/div/div/div/div/div[1]/a')
    driver.execute_script("arguments[0].click();", element)

    # 4. 9시 정각에 예약하기
    # 4.1 9시까지 대기하기
    count = 0
    while datetime.now(KST) < TARGET_TIME:
        time.sleep(0.01)
        count += 1
        if count % 3000 == 0:
            msgInfo(f"9시 정각 대기중...")
        if count > 100000:
            msgInfo("대기 시간이 너무 길어 종료합니다.")
            driver.quit()
            return 1

    # 3.2 9시 정각에 새로고침
    driver.refresh()
    msgInfo("페이지 새로고침 완료")

    # 3.3 예약 가능한 날짜가 나타날 때까지 대기하기
    WebDriverWait(driver, 300).until(
        EC.presence_of_all_elements_located(
            (By.XPATH, "//tbody//a[starts-with(@href, 'javascript:fn_tennis_time_list')]")
        )
    )
    msgInfo("예약 가능한 날짜 확인 완료")

    # 4. 예약 페이지 진입
    # 4.1 날짜 선택
    clickable_dates = driver.find_elements(By.XPATH, "//tbody//a[starts-with(@href, 'javascript:fn_tennis_time_list')]")
    if clickable_dates:
        target = clickable_dates[-1]
        driver.execute_script("arguments[0].scrollIntoView(true);", target)
        time.sleep(0.1)
        driver.execute_script("arguments[0].click();", target)
    else:
        msgInfo("클릭 가능한 날짜가 없음")
        return 1
    msgInfo("예약 가능한 날짜 클릭 : ", clickable_dates[-1].text)
        
    # 4.2 시간 선택 리스트 요소들 가져오기
    time_slots = driver.find_elements(By.CSS_SELECTOR, 'ul#time_con li')
    click_count = 0
    for slot in reversed(time_slots):
        try:
            checkbox = slot.find_element(By.CSS_SELECTOR, 'input[type="checkbox"]')
            label = slot.find_element(By.CSS_SELECTOR, 'span.label')

            if checkbox.is_enabled() and "신청가능" in label.text:
                driver.execute_script("arguments[0].click();", checkbox)
                click_count += 1
                if click_count == 2:
                    break
        except Exception as e:
            # 예외 무시하고 다음으로
            continue
    else:
        msgInfo("예약 가능한 시간이 없음")
        return 1
    msgInfo(f"예약 가능한 시간 클릭 : {click_count}개 선택됨.")

    # 4.3 코트 목록 가져오기
    WebDriverWait(driver, 10).until(
        EC.presence_of_all_elements_located(
            (By.CSS_SELECTOR, 'ul.court_list li')
        )
    )
    court_list = driver.find_elements(By.CSS_SELECTOR, 'ul.court_list li')
    driver.execute_script("arguments[0].scrollIntoView(true);", court_list[0])

    available_courts = [19, 18, 2, 13, 17, 16, 15, 14, 12, 11, 10, 9, 8, 4, 3, 7, 5, 6]

    for court_num in available_courts:
        try:
            # 각 코트 항목 찾기
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located(
                    (By.ID, f'tennis_court_img_a_1_{court_num}')
                )
            )
            court = driver.find_element(By.ID, f'tennis_court_img_a_1_{court_num}')
            img_element = court.find_element(By.TAG_NAME, 'img')
            
            # 이미지의 'src' 속성 확인해서 예약 상태 확인
            if 'btn_tennis_noreserve' not in img_element.get_attribute('src'):
                # 예약 가능하면 클릭
                court.click()
                msgInfo(f"코트 {court_num} 선택됨.")
                break  # 5번 코트를 선택했으면 더 이상 클릭하지 않음
        except Exception as e:
            # 예외 발생시 계속 진행
            continue
    else:
        msgInfo("예약 가능한 코트가 없음")
        return 1

    msgInfo("코트 선택 완료, OCR 처리 시작")

    # 5. 자동입력 방지문자
    WebDriverWait(driver, 60).until(
            EC.presence_of_all_elements_located(
                (By.XPATH, '//*[@id="layer_captcha_wrap"]/div/img')
            )
    )
    captcha_png = driver.find_element(By.XPATH, '//*[@id="layer_captcha_wrap"]/div/img')
    reader = easyocr.Reader(['en'])
    result = reader.readtext(captcha_png.screenshot_as_png, detail=0)[0]
    driver.find_element(By.ID, 'captcha').send_keys(result)
    driver.find_element(By.ID, 'date_confirm').click()

    # 6. 예약하기
    driver.switch_to.alert.accept()

    # 7. 장바구니 담기는게 성공했는지 확인
    try:
        basket = driver.find_element(By.XPATH, '//*[@id="aplictn_info"]/ul')
        lst = basket.find_elements(By.TAG_NAME, 'li')
        content = []
        for l in lst:
            content.append(l.text.split('\n')[-1])
        message = '\n'.join(content)
        msgInfo("장바구니 담기 성공")
        send_slack_message(0, message)
        send_kakao_message(0, message)
        return 0
    except:
        msgInfo("장바구니 담기 실패")
        send_slack_message(1, "장바구니 담기 실패")
        return 1


if __name__ == "__main__":
    try:
        exit_code = main()
        if exit_code != 0:
            send_slack_message(1, "예약 실패")
    except Exception as e:
        print(f"예외 발생: {e}")
        send_slack_message(1, f"예약 실패: {e}")