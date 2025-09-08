import re
import pandas as pd
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from linebot.exceptions import LineBotApiError
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ตั้งค่า Line Bot
line_bot_api = LineBotApi('m5JJxtf5Dwh/vy6V3kKhs5ClXLraMumyAbDUgKDt3FSXOXPMUL8LSMsyecRtwWHGUomZsfXBE5ofH9xzMu3x3jN2a3TiN+lr95DC0oxzVwmt2/oeKkrxZP5HJc3wYh+D2GezTSar/VOHr5N48jg61wdB04t89/1O/w1cDnyilFU=')
handler = WebhookHandler('0cd96d62ba67bcad21bf985da88c57d4')

# ตั้งค่า Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)

# เปิดชีต "ข้อมูลบริษัท"
spreadsheet = client.open("ข้อมูลบริษัท")
worksheet = spreadsheet.sheet1

# ฟังก์ชันค้นหาบริษัทจากคำค้นหา
def search_company(keyword):
    # ดึงข้อมูลทั้งหมดจากชีต
    data = worksheet.get_all_values()
    df = pd.DataFrame(data[1:], columns=data[0])  # แถวแรกเป็นหัวคอลัมน์
    
    # ค้นหาบริษัทที่ตรงกับคำค้นหา (ค้นในคอลัมน์ D: ชื่อบริษัทภาษาไทย)
    matches = []
    for idx, row in df.iterrows():
        if keyword.lower() in row[3].lower():  # คอลัมน์ D (index 3)
            matches.append((idx, row))
    
    # เรียงลำดับตามความใกล้เคียง (ง่ายๆ แบบนี้ก่อน)
    matches.sort(key=lambda x: len(x[1][3]), reverse=False)
    
    return matches[:3]  # ส่งกลับ 3 บริษัทที่ใกล้เคียงที่สุด

# ฟังก์ชันจัดรูปแบบข้อมูลบริษัท
def format_company_info(company_data):
    # company_data เป็น list ของข้อมูลในแต่ละคอลัมน์
    info = f"- {company_data[0]} : {company_data[1]} : {company_data[2]} : \n"  # ลำดับ : ว/ด/ป : เลขนิติบุคคล
    info += f"- {company_data[3]}\n"  # ชื่อบริษัทภาษาไทย
    info += f"- {company_data[4]}\n"  # ชื่อบริษัทภาษาอังกฤษ
    info += f"- {company_data[5]}\n\n"  # ที่ตั้งบริษัท
    
    # กรรมการ
    directors = company_data[6].split('\n') if company_data[6] else []
    info += "- กรรมการ\n"
    for i, director in enumerate(directors, 1):
        info += f"  {i}. {director.strip()}\n"
    
    # หุ้นส่วน
    shareholders = company_data[7].split('\n') if company_data[7] else []
    info += "\n- หุ้นส่วน\n"
    for i, shareholder in enumerate(shareholders, 1):
        info += f"  {i}. {shareholder.strip()}\n"
    
    # ข้อมูลเพิ่มเติม
    info += f"\n- {company_data[8]}\n"  # วันปิดงบประจำปี
    info += f"- Password DBD e-Filing: {company_data[9]}\n"
    info += f"- Password สรรพากร e-Filing: {company_data[10]}\n"
    info += f"- ID sso e-service: {company_data[11]}\n"
    info += f"- Password sso e-service: {company_data[12]}\n"
    info += f"- อำนาจกรรมการตามข้อบังคับ: {company_data[13]}\n"
    
    return info

# ฟังก์ชันจัดการข้อความจาก Line
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text.strip()
    
    # ตรวจสอบว่าข้อความขึ้นต้นด้วย "หาบริษัท" หรือไม่
    if text.startswith("หาบริษัท"):
        keyword = text.replace("หาบริษัท", "").strip()
        
        if not keyword:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="กรุณาระบุชื่อบริษัทที่ต้องการค้นหา เช่น 'หาบริษัท ไทย'")
            )
            return
        
        # ค้นหาบริษัท
        companies = search_company(keyword)
        
        if not companies:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f"ไม่พบบริษัทที่ตรงกับ '{keyword}'")
            )
            return
        
        # ส่งข้อมูลบริษัทที่พบ
        for idx, company in companies:
            company_info = format_company_info(company)
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=company_info)
            )
    else:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="พิมพ์ 'หาบริษัท [ชื่อบริษัท]' เพื่อค้นหาข้อมูลบริษัท")
        )

# ตัวอย่างการใช้งาน (ต้องนำไปใส่ใน Flask App)
"""
from flask import Flask, request, abort

app = Flask(__name__)

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    
    try:
        handler.handle(body, signature)
    except LineBotApiError as e:
        abort(400)
    
    return 'OK'

if __name__ == "__main__":
    app.run()
"""
