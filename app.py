import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

# --- ส่วนตั้งค่า (กรุณาแก้ไขข้อมูลในส่วนนี้) ---

# ตั้งค่า LINE Bot
CHANNEL_ACCESS_TOKEN = 'n1vorbwHeYMPtZkpEFyZfkUmYL97ThlNM1mlmqoml5uuCC6sTbwtzdEwvtOTPE0z8/kGYb7c1UAbULJwU0SM/8rOUHTrIAa0uYMTbh+DmCsAR8i5i/WUXC/a/3YsAS3gC1jaeAY26/h/InrN1prqkgdB04t89/1O/w1cDnyilFU='
CHANNEL_SECRET = '5823e71cf9d214f199a4cb5981e65d1d'

# ตั้งค่า Google Sheets
GOOGLE_SHEET_NAME = 'ข้อมูลบริษัท' # ชื่อชีตของคุณ
GOOGLE_CREDENTIALS_FILE = 'credentials.json' # ชื่อไฟล์ credentials ที่ดาวน์โหลดมา

# ----------------------------------------------

# สร้าง instance ของ Flask app
app = Flask(__name__)

# สร้าง instance ของ LINE Bot API และ Webhook Handler
line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# ฟังก์ชันสำหรับเชื่อมต่อและดึงข้อมูลทั้งหมดจาก Google Sheet
def get_sheet_data():
    """เชื่อมต่อกับ Google Sheets และดึงข้อมูลทั้งหมดออกมาเป็น List of Dictionaries"""
    try:
        scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/spreadsheets',
                 "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_CREDENTIALS_FILE, scope)
        client = gspread.authorize(creds)
        sheet = client.open(GOOGLE_SHEET_NAME).sheet1
        # .get_all_records() จะดึงข้อมูลทั้งหมดและแปลงเป็น list ของ dictionary โดยใช้แถวแรกเป็น key
        return sheet.get_all_records()
    except Exception as e:
        print(f"Error accessing Google Sheet: {e}")
        return None

# Webhook สำหรับรับข้อมูลจาก LINE
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

# จัดการกับข้อความที่ส่งเข้ามา
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_message = event.message.text.strip()
    
    # ตรวจสอบว่าข้อความขึ้นต้นด้วย "หาบริษัท" หรือไม่
    if user_message.startswith("หาบริษัท"):
        # ตัดคำว่า "หาบริษัท" และช่องว่างออกไปเพื่อเอาเฉพาะชื่อที่ใช้ค้นหา
        search_query = user_message[len("หาบริษัท"):].strip()
        
        if not search_query:
            reply_text = "กรุณาระบุชื่อบริษัทที่ต้องการค้นหาด้วยครับ\nตัวอย่าง: หาบริษัท เทส จำกัด"
        else:
            # ดึงข้อมูลจาก Google Sheet
            company_data = get_sheet_data()
            
            if company_data is None:
                reply_text = "ขออภัยครับ ไม่สามารถเชื่อมต่อกับฐานข้อมูลบริษัทได้"
            else:
                found_company = None
                # วนลูปหาบริษัทที่ชื่อใกล้เคียง
                for company in company_data:
                    # ตรวจสอบว่า search_query เป็นส่วนหนึ่งของชื่อบริษัทหรือไม่ (ไม่ต้องพิมพ์เต็ม)
                    if search_query.lower() in company.get('ชื่อ บริษัทภาษาไทย', '').lower():
                        found_company = company
                        break # เจอแล้วให้หยุดค้นหาทันที
                
                if found_company:
                    # จัดรูปแบบข้อความตอบกลับตามที่ต้องการ
                    try:
                        # จัดการรายชื่อกรรมการและหุ้นส่วนให้ขึ้นบรรทัดใหม่สวยงาม
                        # โดยการแทนที่ตัวเลขลำดับ (2., 3., 4., ...) ด้วยการขึ้นบรรทัดใหม่
                        directors = str(found_company.get('กรรมการ', ''))
                        for i in range(10, 1, -1):
                            directors = directors.replace(f'{i}.', f'\n- {i}.')

                        partners = str(found_company.get('หุ้นส่วน', ''))
                        for i in range(10, 1, -1):
                            partners = partners.replace(f'{i}.', f'\n- {i}.')

                        # สร้างข้อความตอบกลับ
                        reply_text = f"""
ข้อมูลบริษัทที่คุณค้นหา:

{found_company.get('ลำดับ', '')} : {found_company.get('ว/ด/ป /ที่จดทะเบียน', '')} : {found_company.get('เลขนิติบุคล', '')} :
- บริษัท {found_company.get('ชื่อ บริษัทภาษาไทย', '')}
- {found_company.get('ชื่อบริษัท ภาษาอังกฤษ', '')}
- {found_company.get('ที่ตั้งบริษัท', '')}
- กรรมการ {directors}
- หุ้นส่วน {partners}
- วันปิดงบประจำปี: {found_company.get('วันปิดงบประจำปี', '')}
- Password DBD e-Filing: {found_company.get('Password DBD e-Filing', '')}
- Password สรรพากร e-Filing: {found_company.get('Password สรรพากร e-Filing', '')}
- ID sso e-service: {found_company.get('ID sso e-service', '')}
- Password sso e-service: {found_company.get('Passerord sso e-service', '')}
- อำนาจกรรมการตามข้อบังคับ: {found_company.get('อำนาจกรรมการตามข้อบังคับ', '')}
                        """.strip()

                    except Exception as e:
                        reply_text = f"เกิดข้อผิดพลาดในการจัดรูปแบบข้อมูล: {e}"
                else:
                    reply_text = f"ไม่พบข้อมูลบริษัทที่ชื่อใกล้เคียงกับ '{search_query}'"

        # ส่งข้อความตอบกลับไปที่ LINE
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=reply_text)
        )

# สั่งให้ Flask app เริ่มทำงาน
if __name__ == "__main__":
    # ใช้ port ที่ Heroku หรือ Cloud Run กำหนดให้ หรือใช้ 5000 สำหรับทดสอบในเครื่อง
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
