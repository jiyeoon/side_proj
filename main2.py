import os
import datetime
import time
import sys
import json
import requests
import pytesseract
from PIL import Image
import io
import ddddocr
import easyocr

def is_display_available():
    """디스플레이가 사용 가능한지 확인"""
    try:
        import subprocess
        result = subprocess.run(['pgrep', '-f', 'WindowServer'], capture_output=True, text=True)
        return result.returncode == 0
    except:
        return False

from datetime import datetime, timezone, timedelta

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# 0. 변수 선언 
KST = timezone(timedelta(hours=9))
TARGET_TIME = datetime.now(KST).replace(hour=9, minute=0, second=0)

login_id = os.environ.get("LOGIN_ID")
login_pw = os.environ.get("LOGIN_PASSWORD")
login_url = os.environ.get("LOGIN_URL")
base_url = os.environ.get("BASE_URL")
slack_url = os.environ.get("SLACK_URL")

buffer = []  # 로그 버퍼

# 0. 함수 정의
def msgInfo(msg):
    pStr = "\t[INFO]>> [{}] : {}\n".format(datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3], msg)
    sys.stdout.write(pStr)
    buffer.append(pStr)  # 로그 버퍼에 추가

def send_slack_message(status, msg):
    buffer_str = ''.join(buffer)

    if status == 0: # 성공
        title = "Reservation Success"
        color = "#2EB67D"
        message = f"예약에 성공했습니다.\n```{msg}```\n<{base_url}|예약 하러가기>\n**Log 출력**\n```{buffer_str}```"
    else:
        title = "Reservation Failed"
        color = "#E01E5A"
        message = f"예약에 실패했습니다.\n```{msg}```\n**Log 출력**\n```{buffer_str}```"

    data = {
        "attachments": [
            {
                "title": title,
                "title_link": "https://github.com/jiyeoon/side_proj/actions",
                "text": message,
                "color": color
            }
        ]
    }

    response = requests.post(slack_url, json=data)
    if response.status_code == 200:
        msgInfo("Slack 메시지 전송 성공")
    else:
        msgInfo(f"Slack 메시지 전송 실패: {response.status_code}, {response.text}")


def main():
    driver = None
    try:
        # 1. Selenium으로 로그인
        msgInfo("Chrome Driver 설정 시작")
        options = Options()
        
        # 디스플레이 상태에 따라 headless 모드 결정
        if is_display_available():
            msgInfo("🖥️ GUI 모드로 실행 (디스플레이 감지됨)")
            # GUI 모드 - headless 옵션 제거
            options.add_argument("--window-size=1920,1080")
        else:
            msgInfo("🔧 Headless 모드로 실행 (디스플레이 없음)")
            # Headless 모드
            options.add_argument("--headless=new")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--single-process")
            options.add_argument("--disable-software-rasterizer")
            options.add_argument("--window-size=1920,1080")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            # User-Agent 설정 (headless 감지 방지)
            options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        driver = webdriver.Chrome(options=options)
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"}
        )
        msgInfo("Chrome Driver 설정 완료")
    except Exception as e:
        msgInfo(f"❌ Chrome Driver 설정 실패: {e}")
        return 1

    # 2. 로그인
    try:
        msgInfo("🔐 로그인 페이지로 이동")
        driver.get(login_url)
        
        msgInfo("📝 로그인 정보 입력 중")
        driver.find_element(By.NAME, 'login_id').send_keys(login_id)
        driver.find_element(By.NAME, 'login_pwd').send_keys(login_pw)
        
        msgInfo("🔘 로그인 버튼 클릭")
        button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, '//*[@id="content"]/div/div/div/button'))
        )
        # 강제 클릭 시도
        driver.execute_script("arguments[0].scrollIntoView(true);", button)
        time.sleep(0.5)
        driver.execute_script("arguments[0].click();", button)

        try:
            driver.switch_to.alert.accept() # 이미 로그인 되어있는 경우 처리
            msgInfo("ℹ️ 이미 로그인 되어있었습니다.")
        except:
            msgInfo("✅ 로그인 완료")
            
    except Exception as e:
        msgInfo(f"❌ 로그인 실패: {e}")
        if driver:
            driver.quit()
        return 1

    # 3. 예약하기 버튼 클릭
    try:
        msgInfo("🏠 메인 홈페이지 로딩 대기")
        # 페이지 로딩 완료 대기
        WebDriverWait(driver, 60).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        
        msgInfo("🎾 예약하기 버튼 클릭")
        # 버튼 대기 및 클릭
        link = WebDriverWait(driver, 60).until(
            EC.element_to_be_clickable((By.LINK_TEXT, "일일입장 예약신청"))
        )
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", link)
        time.sleep(3) # JS 바인딩 대기
        driver.execute_script("arguments[0].click();", link)
        msgInfo("✅ 예약 페이지 진입 완료")
        
    except Exception as e:
        msgInfo(f"❌ 예약 페이지 진입 실패: {e}")
        # GitHub Actions 환경에서 디버깅 정보 수집
        try:
            if driver:
                current_url = driver.current_url
                page_title = driver.title
                msgInfo(f"📍 현재 URL: {current_url}")
                msgInfo(f"📄 페이지 제목: {page_title}")
                # 스크린샷 저장 (GitHub Actions에서도 확인 가능)
                screenshot_path = "/tmp/error_screenshot.png"
                driver.save_screenshot(screenshot_path)
                msgInfo(f"📸 에러 스크린샷 저장: {screenshot_path}")
                # 페이지의 모든 링크 확인
                try:
                    all_links = driver.find_elements(By.TAG_NAME, "a")
                    msgInfo(f"🔍 페이지의 링크 개수: {len(all_links)}")
                    for i, link_elem in enumerate(all_links[:20]):
                        try:
                            link_text = link_elem.text
                            if link_text and ("예약" in link_text or "입장" in link_text):
                                msgInfo(f"  링크 {i+1}: {link_text}")
                        except:
                            pass
                except:
                    pass
        except Exception as debug_e:
            msgInfo(f"⚠️ 디버깅 정보 수집 실패: {debug_e}")
        if driver:
            driver.quit()
        return 1

    # 4. 9시 정각에 예약하기
    # 4.1 9시까지 대기하기 (최적화된 타이밍)
    msgInfo("9시 정각까지 대기 시작...")
    current_time = datetime.now(KST)
    time_diff = (TARGET_TIME - current_time).total_seconds()
    
    if time_diff > 0:
        # 15초 전까지는 0.1초씩 대기
        if time_diff > 15:
            sleep_time = time_diff - 15
            msgInfo(f"9시 정각까지 {sleep_time:.1f}초 대기...")
            time.sleep(sleep_time)
        
        # 마지막 15초는 0.001초씩 정밀 대기
        msgInfo("🎯 마지막 15초 정밀 대기 시작...")
        loop_count = 0
        while True:
            current_time = datetime.now(KST)
            if current_time >= TARGET_TIME:
                break
            time.sleep(0.0001)
            loop_count += 1
            # 무한 루프 방지 (20초 = 200000번)
            if loop_count > 200000:
                msgInfo("⚠️ 대기 시간이 너무 길어 강제 종료합니다.")
                if driver:
                    driver.quit()
                return 1
        
        msgInfo("9시 정각 도달!")
    else:
        msgInfo("이미 9시가 지났습니다. 즉시 실행합니다.")

    # 3.2 9시 정각에 새로고침
    try:
        msgInfo("🔄 페이지 새로고침")
        driver.refresh()
        msgInfo("✅ 페이지 새로고침 완료")

        # 3.3 예약 가능한 날짜가 나타날 때까지 대기하기
        msgInfo("📅 예약 가능한 날짜 로딩 대기...")
        WebDriverWait(driver, 300).until(
            EC.presence_of_all_elements_located(
                (By.XPATH, "//tbody//a[starts-with(@href, 'javascript:fn_tennis_time_list')]")
            )
        )
        msgInfo("✅ 예약 가능한 날짜 확인 완료")
        
    except Exception as e:
        msgInfo(f"❌ 페이지 새로고침 또는 날짜 로딩 실패: {e}")
        if driver:
            driver.quit()
        return 1

    # 4. 예약 페이지 진입
    try:
        # 4.1 날짜 선택
        msgInfo("📅 예약 가능한 날짜 검색 중...")
        clickable_dates = driver.find_elements(By.XPATH, "//tbody//a[starts-with(@href, 'javascript:fn_tennis_time_list')]")
        
        if clickable_dates:
            target = clickable_dates[-1]
            driver.execute_script("arguments[0].scrollIntoView(true);", target)
            time.sleep(0.1)
            driver.execute_script("arguments[0].click();", target)
            txt = clickable_dates[-1].text.replace('\n', '/')
            msgInfo(f"✅ 예약 가능한 날짜 클릭: {txt}")
        else:
            msgInfo("❌ 클릭 가능한 날짜가 없음")
            if driver:
                driver.quit()
            return 1
            
    except Exception as e:
        msgInfo(f"❌ 날짜 선택 실패: {e}")
        if driver:
            driver.quit()
        return 1
        
    # 4.2 시간 선택 리스트 요소들 가져오기
    try:
        msgInfo("⏰ 예약 가능한 시간 검색 중...")
        time_slots = driver.find_elements(By.CSS_SELECTOR, 'ul#time_con li')
        click_count = 0
        
        for slot in reversed(time_slots):
            try:
                checkbox = slot.find_element(By.CSS_SELECTOR, 'input[type="checkbox"]')
                label = slot.find_element(By.CSS_SELECTOR, 'span.label')

                if checkbox.is_enabled() and "신청가능" in label.text:
                    driver.execute_script("arguments[0].click();", checkbox)
                    click_count += 1
                    msgInfo(f"✅ 시간 선택: {label.text}")
                    if click_count == 2:
                        break
            except Exception as e:
                # 예외 무시하고 다음으로
                continue
        else:
            msgInfo("❌ 예약 가능한 시간이 없음")
            if driver:
                driver.quit()
            return 1
            
        msgInfo(f"✅ 예약 가능한 시간 클릭 완료: {click_count}개 선택됨")
        
    except Exception as e:
        msgInfo(f"❌ 시간 선택 실패: {e}")
        if driver:
            driver.quit()
        return 1

    # 4.3 코트 목록 가져오기
    try:
        msgInfo("🏟️ 코트 목록 로딩 대기...")
        WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located(
                (By.CSS_SELECTOR, 'ul.court_list li')
            )
        )
        court_list = driver.find_elements(By.CSS_SELECTOR, 'ul.court_list li')
        driver.execute_script("arguments[0].scrollIntoView(true);", court_list[0])

        available_courts = [5, 6, 7, 8, 19, 18, 2, 13, 17, 16, 15, 14, 12, 11, 10, 9, 4, 3]
        msgInfo(f"🎾 코트 검색 시작 (우선순위: {available_courts[:5]}...)")

        court_selected = False
        for court_num in available_courts:
            try:
                msgInfo(f"🔍 코트 {court_num} 확인 중...")
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
                    # 예약 가능하면 JavaScript로 강제 클릭
                    driver.execute_script("arguments[0].click();", court)
                    msgInfo(f"✅ 코트 {court_num} 선택됨")
                    
                    # 알림창 확인 (예약 완료된 코트인지 체크)
                    try:
                        # 잠시 대기 후 알림창 확인
                        time.sleep(0.5)
                        alert = driver.switch_to.alert
                        alert_text = alert.text
                        msgInfo(f"⚠️ 알림창 감지: {alert_text}")
                        
                        if "예약이 완료된 코트입니다" in alert_text:
                            # 예약 완료된 코트면 알림창 닫고 다음 코트 시도
                            alert.accept()
                            msgInfo(f"❌ 코트 {court_num} 이미 예약 완료 - 다음 코트 시도")
                            continue
                        else:
                            # 다른 알림창이면 처리하고 계속 진행
                            alert.accept()
                            msgInfo(f"✅ 알림창 처리 완료: {alert_text}")
                            
                    except:
                        # 알림창이 없으면 정상적으로 선택된 것
                        msgInfo(f"ℹ️ 알림창 없음")
                    
                    court_selected = True
                    break  # 코트를 선택했으면 더 이상 클릭하지 않음
                else:
                    msgInfo(f"⏳ 코트 {court_num} 예약 불가")
            except Exception as e:
                # 예외 발생시 계속 진행
                msgInfo(f"⚠️ 코트 {court_num} 확인 중 오류: {e}")
                continue
        
        if not court_selected:
            msgInfo("❌ 예약 가능한 코트가 없음")
            if driver:
                driver.quit()
            return 1
            
    except Exception as e:
        msgInfo(f"❌ 코트 선택 실패: {e}")
        if driver:
            driver.quit()
        return 1

    msgInfo("✅ 코트 선택 완료, OCR 처리 시작")

    # 5. 자동입력 방지문자 (최적화된 OCR)
    try:
        msgInfo("🔍 캡차 이미지 로딩 대기...")
        WebDriverWait(driver, 60).until(
                EC.presence_of_all_elements_located(
                    (By.XPATH, '//*[@id="layer_captcha_wrap"]/div/img')
                )
        )
        
        captcha_png = driver.find_element(By.XPATH, '//*[@id="layer_captcha_wrap"]/div/img')
        
        # 캡차 이미지를 PIL Image로 변환
        captcha_image = Image.open(io.BytesIO(captcha_png.screenshot_as_png))
        
        # 이미지 전처리 생략 (ddddocr가 원본 이미지로도 잘 작동)
        msgInfo("⚡ 이미지 전처리 생략 - ddddocr 직접 처리")
        
        # ddddocr로 캡차 인식 (캡차 전용 모델)
        msgInfo("🤖 ddddocr로 캡차 인식 시작...")
        result = ""
        
        try:
            # ddddocr 초기화 (캡차 전용)
            ocr = ddddocr.DdddOcr()
            
            # PIL Image를 bytes로 변환
            img_byte_arr = io.BytesIO()
            captcha_image.save(img_byte_arr, format='PNG')
            img_byte_arr = img_byte_arr.getvalue()
            
            # 캡차 이미지 인식
            result = ocr.classification(img_byte_arr)
            msgInfo(f"🤖 ddddocr 결과: {result}")
            
            # 숫자만 추출
            import re
            result = re.sub(r'[^0-9]', '', result)
            msgInfo(f"🤖 ddddocr 결과 (숫자만): {result}")
            
            # 4자리 숫자가 아니면 EasyOCR로 fallback
            if not result or len(result) != 4:
                # 3자리인 경우 앞에 0 추가 시도
                if result and len(result) == 3:
                    result = "0" + result
                    msgInfo(f"🔧 3자리 숫자 감지 - 앞에 0 추가: {result}")
                else:
                    msgInfo(f"⚠️ ddddocr 실패 - {len(result) if result else 0}자리 숫자 (4자리 필요) - EasyOCR로 fallback")
                    result = ""
                
        except Exception as e:
            msgInfo(f"❌ ddddocr 오류: {e}")
            result = ""

        # ddddocr 실패 시 EasyOCR fallback
        if not result:
            msgInfo("🔄 EasyOCR fallback 시작...")
            
            try:
                # EasyOCR Reader 초기화 (영어만)
                reader = easyocr.Reader(['en'])
                
                # PIL Image를 numpy array로 변환
                import numpy as np
                captcha_array = np.array(captcha_image)
                
                # 캡차 이미지 인식 (숫자만 허용, 더 관대한 설정)
                results = reader.readtext(
                    captcha_array, 
                    allowlist='0123456789',
                    width_ths=0.7,  # 텍스트 박스 너비 임계값 낮춤
                    height_ths=0.7,  # 텍스트 박스 높이 임계값 낮춤
                    paragraph=False,  # 단락 모드 비활성화
                    batch_size=1  # 배치 크기 1로 설정
                )
                msgInfo(f"🔤 EasyOCR 원본 결과: {results}")
                
                # 결과에서 텍스트 추출
                if results:
                    # 가장 확신도가 높은 결과 선택
                    best_result = max(results, key=lambda x: x[2])  # confidence 기준
                    result = best_result[1]  # 텍스트 부분
                    confidence = best_result[2]  # 확신도
                    msgInfo(f"🔤 EasyOCR 최고 확신도 결과: {result} (확신도: {confidence:.2f})")
                
                # 숫자만 추출
                import re
                result = re.sub(r'[^0-9]', '', result)
                msgInfo(f"🔤 EasyOCR 결과 (숫자만): {result}")
                
                # 4자리 숫자가 아니면 pytesseract로 fallback
                if not result or len(result) != 4:
                    # 3자리인 경우 앞에 0 추가 시도
                    if result and len(result) == 3:
                        result = "0" + result
                        msgInfo(f"🔧 3자리 숫자 감지 - 앞에 0 추가: {result}")
                    else:
                        msgInfo(f"⚠️ EasyOCR 실패 - {len(result) if result else 0}자리 숫자 (4자리 필요) - pytesseract로 fallback")
                        result = ""
                        
            except Exception as e:
                msgInfo(f"❌ EasyOCR 오류: {e}")
                result = ""
        
        # EasyOCR 실패 시 pytesseract fallback
        if not result:
            msgInfo("🔄 pytesseract fallback 시작...")
            
            # 간단한 pytesseract 설정들
            configs = [
                r'--oem 3 --psm 8 -c tessedit_char_whitelist=0123456789',
                r'--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789',
                r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789',
                r'--oem 3 --psm 8',
                r'--oem 3 --psm 7'
            ]
            
            for i, config in enumerate(configs):
                try:
                    result = pytesseract.image_to_string(captcha_image, config=config).strip()
                    # 숫자만 추출
                    import re
                    result = re.sub(r'[^0-9]', '', result)
                    msgInfo(f"🔤 pytesseract 설정 {i+1} 결과 (숫자만): {result}")
                    if result and len(result) == 4:  # 4자리 숫자면 유효한 것으로 판단
                        break
                except:
                    continue
            
            if not result:
                msgInfo("❌ 모든 OCR 방법 실패")
                result = ""
        
        driver.find_element(By.ID, 'captcha').send_keys(result)
        driver.find_element(By.ID, 'date_confirm').click()
        msgInfo("✅ 캡차 입력 완료")
        
        # 결제대기 알림창 대기
        msgInfo("💳 결제대기 알림창 대기 중...")
        WebDriverWait(driver, 10).until(EC.alert_is_present())
        alert = driver.switch_to.alert
        alert_text = alert.text
        msgInfo(f"💳 결제대기 알림창 감지: {alert_text}")
        alert.accept()
        msgInfo("✅ 결제대기 알림창 확인 완료")
    
    except Exception as e:
        msgInfo(f"❌ OCR 처리 중 오류 발생: {e}")
        # OCR 오류 시에도 브라우저를 열어둠 (디버깅용)
        msgInfo("🔍 OCR 오류로 인해 브라우저를 열어둡니다. 100초 후 자동 종료됩니다.")
        time.sleep(100)
        if driver:
            driver.quit()
            msgInfo("🔚 브라우저 종료")
        return 1

    # 6. 예약하기
    try:
        msgInfo("📋 예약 확인 알림 처리")
        try:
            # 추가 알림창이 있는지 확인
            alert = driver.switch_to.alert
            alert_text = alert.text
            msgInfo(f"❌ 추가 알림창 감지: {alert_text}")
            msgInfo("⚠️ 추가 알림창이 있으면 보통 예약이 실패한 것입니다!")
            msgInfo("🔍 브라우저를 열어둡니다. 100초 후 자동 종료됩니다.")
            time.sleep(100)
            if driver:
                driver.quit()
                msgInfo("🔚 브라우저 종료")
            return 1
        except:
            msgInfo("ℹ️ 추가 알림창 없음 - 예약 진행 중")

        # 7. 장바구니 담기는게 성공했는지 확인
        msgInfo("🛒 장바구니 담기 확인 중...")
        try:
            # 페이지 로딩 대기
            time.sleep(2)
            basket = driver.find_element(By.XPATH, '//*[@id="aplictn_info"]/ul')
            lst = basket.find_elements(By.TAG_NAME, 'li')
            content = []
            for l in lst:
                content.append(l.text.split('\n')[-1])
            message = '\n'.join(content)
            msgInfo("🎉 장바구니 담기 성공!")
            msgInfo(f"📝 예약 내용: {message}")
            send_slack_message(0, message)
            if driver:
                driver.quit()
                msgInfo("🔚 브라우저 종료")
            return 0
        except Exception as e:
            # 장바구니 확인 실패해도 예약은 성공했을 가능성이 높음
            msgInfo(f"⚠️ 장바구니 확인 실패: {e}")
            msgInfo("⚠️ 장바구니 확인 실패했지만 예약은 성공했을 가능성이 높습니다")
            time.sleep(100)
            if driver:
                driver.quit()
                msgInfo("🔚 브라우저 종료")
            return 1
        
    except Exception as e:
        msgInfo(f"❌ 예약 처리 실패: {e}")
        # 실패 시 브라우저를 열어둠 (디버깅용)
        msgInfo("🔍 예약 처리 실패로 브라우저를 열어둡니다. 100초 후 자동 종료됩니다.")
        time.sleep(100)

        if driver:
            driver.quit()
            msgInfo("🔚 브라우저 종료")
        return 1

if __name__ == "__main__":
    try:
        msgInfo("🚀 테니스 예약 봇 시작")
        exit_code = main()
        if exit_code != 0:
            msgInfo("❌ 예약 실패")
            send_slack_message(1, f"예약 실패 (종료코드: {exit_code})")
        else:
            msgInfo("✅ 예약 성공")
    except Exception as e:
        msgInfo(f"💥 예외 발생: {e}")
        send_slack_message(1, f"예약 봇 실행 중 예외 발생: {e}")