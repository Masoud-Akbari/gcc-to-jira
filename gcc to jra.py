import requests
import json
import os
from datetime import datetime
from requests.auth import HTTPBasicAuth

# --- تنظیمات پیکربندی (Configuration) ---
# توجه: اطلاعات حساس از متغیرهای محیطی خوانده می‌شوند.
# (Environment Variables)
CONFIG = {
    # اطلاعات GCC
    "GCC_ADDRESS": "http://192.168.34.31",
    # خواندن از متغیرهای محیطی (با استفاده از مقادیر قبلی به عنوان پیش‌فرض برای تست)
    "GCC_USERNAME": os.getenv("GCC_USERNAME", "probe184"),
    "GCC_PASSWORD": os.getenv("GCC_PASSWORD", "123456"),

    # اطلاعات Jira
    "JIRA_URL": "http://10.187.120.81",
    # خواندن از متغیرهای محیطی (با استفاده از مقادیر قبلی به عنوان پیش‌فرض برای تست)
    "JIRA_USERNAME": os.getenv("JIRA_USERNAME", "m.akbari"),
    "JIRA_PASSWORD": os.getenv("JIRA_PASSWORD", "Qq@123456789"),
    "JIRA_PROJECT_KEY": "SSD",
    "JIRA_ISSUETYPE_ID": "10408",  # Support

    # شناسه فیلدهای سفارشی Jira
    "CUSTOM_FIELDS": {
        "LETTER_ID": "customfield_10670",       # Letter ID (GCC tickID)
        "RELATED_PROJECT": "customfield_10627", # Related Project
        "REQUEST_UNIT": "customfield_10644",    # Request Unit
        "OPERATING_SYSTEM": "customfield_10643", # Operating System/Platform
        "DEVICE_CATEGORY": "customfield_10803", # Device Category
        "ENVIRONMENT": "customfield_10823",     # Environment
        "BUG_TYPE": "customfield_10505",        # Bug Type
    },

    # مقادیر ثابت برای فیلدهای Jira
    "FIXED_VALUES": {
        "PRIORITY": {"name": "Medium"},
        # مقادیر پیش‌فرض برای فیلدهای سفارشی - بر اساس شناسه‌هایی که در اسکریپت اصلی شما بود.
        "RELATED_PROJECT_ID": {"id": "10510"},
        "REQUEST_UNIT_ID": {"id": "10554"},
        "OPERATING_SYSTEM_ID": {"id": "10541"},  # Android
        "DEVICE_CATEGORY_ID": [{"id": "10746"}], # موبایل (به صورت آرایه‌ای)
        "ENVIRONMENT_ID": [{"id": "10617"}],      # Live (به صورت آرایه‌ای)
        "BUG_TYPE_ID": {"id": "10780"},           # سایر
    },

    # فایل ذخیره tickIDهای ساخته شده
    "PROCESSED_TICKETS_FILE": "processed_tickets.txt",
}

# --- متغیرهای سراسری (Global Variables) ---
session = requests.Session()

# --- توابع مدیریت فایل (File Management Functions) ---
def load_processed_tickets():
    """تیکت‌های پردازش شده قبلی را از فایل می‌خواند."""
    file_path = CONFIG['PROCESSED_TICKETS_FILE']
    if not os.path.exists(file_path):
        return set()
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f.readlines())
    except IOError as e:
        print(f"خطا در خواندن فایل {file_path}: {e}")
        return set()

def save_processed_ticket(tick_id):
    """شناسه یک تیکت پردازش شده را در فایل ذخیره می‌کند."""
    file_path = CONFIG['PROCESSED_TICKETS_FILE']
    try:
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(f"{tick_id}\n")
    except IOError as e:
        print(f"خطا در نوشتن در فایل {file_path}: {e}")

# --- توابع GCC (GCC Functions) ---
def login_gcc():
    """ورود به سیستم GCC و ذخیره کوکی سشن."""
    params = {
        "action": "login",
        "un": CONFIG['GCC_USERNAME'],
        "pw": CONFIG['GCC_PASSWORD']
    }
    # استفاده از سشن سراسری
    response = session.get(f"{CONFIG['GCC_ADDRESS']}/GPTicketing/ws/wservice", params=params, timeout=10)

    if response.status_code == 200 and response.text.strip() == "OK":
        print("✅ ورود به GCC موفقیت‌آمیز بود.")
        return True
    else:
        print("❌ ورود به GCC ناموفق:", response.text)
        return False

def get_my_tickets():
    """لیست تیکت‌های کاربر را از GCC دریافت می‌کند."""
    params = {
        "action": "getmytickets"
    }
    response = session.get(f"{CONFIG['GCC_ADDRESS']}/GPTicketing/ws/wservice", params=params, timeout=10)

    if response.status_code == 200:
        try:
            tickets_data = response.json()
            return tickets_data.get("records", [])
        except json.JSONDecodeError:
            print("خطا: پاسخ از GCC یک JSON معتبر نیست.")
            return []
    else:
        print(f"❌ خطا در دریافت تیکت‌ها: وضعیت {response.status_code} - {response.text}")
        return []

# --- تابع Jira (Jira Function) ---
def create_jira_issue(ticket):
    """یک تیکت GCC را به عنوان Issue جدید در Jira ثبت می‌کند."""
    
    # ساخت شرح Issue
    description_parts = [
        f"**شناسه تیکت GCC:** {ticket.get('tickID', '---')}",
        f"**تاریخ/زمان ثبت:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "---",
        f"**ثبت کننده (GCC):** {ticket.get('tickSender', '---')}",
        f"**موضوع:** {ticket.get('tickShMesdagh', '---')}",
        f"**شرح مشکل:**\n{ticket.get('tickDescription', '---')}",
        "---",
        f"**نام مشتری:** {ticket.get('contactName', '---')}",
        f"**شماره تماس:** {ticket.get('contactCellPhone', '---')}",
        f"**کد ملی:** {ticket.get('nationalCode', '---')}",
    ]
    description_text = "\n".join(description_parts)

    # بدنه درخواست JSON برای Jira
    fields_config = CONFIG['CUSTOM_FIELDS']
    fixed_values = CONFIG['FIXED_VALUES']

    payload = {
        "fields": {
            "project": {"key": CONFIG['JIRA_PROJECT_KEY']},
            "summary": ticket.get("tickShMesdagh", f"تیکت GCC: {ticket.get('tickID', 'نامشخص')}"),
            "description": description_text,
            "issuetype": {"id": CONFIG['JIRA_ISSUETYPE_ID']},
            "priority": fixed_values['PRIORITY'],

            # فیلدهای سفارشی
            fields_config['LETTER_ID']: ticket.get("tickID", ""),
            fields_config['RELATED_PROJECT']: fixed_values['RELATED_PROJECT_ID'],
            fields_config['REQUEST_UNIT']: fixed_values['REQUEST_UNIT_ID'],
            fields_config['OPERATING_SYSTEM']: fixed_values['OPERATING_SYSTEM_ID'],
            fields_config['DEVICE_CATEGORY']: fixed_values['DEVICE_CATEGORY_ID'],
            fields_config['ENVIRONMENT']: fixed_values['ENVIRONMENT_ID'],
            fields_config['BUG_TYPE']: fixed_values['BUG_TYPE_ID'],
        }
    }

    try:
        response = requests.post(
            f"{CONFIG['JIRA_URL']}/rest/api/2/issue",
            auth=HTTPBasicAuth(CONFIG['JIRA_USERNAME'], CONFIG['JIRA_PASSWORD']),
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload),
            timeout=10
        )
        response.raise_for_status() # بررسی خطاهای HTTP مانند 4xx یا 5xx

        issue_key = response.json()['key']
        print(f"⭐ Issue با موفقیت ساخته شد: {issue_key} برای تیکت GCC به شناسه {ticket.get('tickID', '')}")
        return True

    except requests.exceptions.HTTPError as errh:
        print(f"❌ خطای HTTP در ساخت Issue برای تیکت {ticket.get('tickID', '')}: {errh}")
        print(f"پاسخ کامل خطا: {response.text}")
    except requests.exceptions.ConnectionError as errc:
        print(f"❌ خطای اتصال به Jira برای تیکت {ticket.get('tickID', '')}: {errc}")
    except requests.exceptions.Timeout as errt:
        print(f"❌ خطای زمان‌بندی (Timeout) برای تیکت {ticket.get('tickID', '')}: {errt}")
    except Exception as e:
        print(f"❌ خطای ناشناخته در ساخت Issue برای تیکت {ticket.get('tickID', '')}: {e}")

    return False

# --- تابع اصلی (Main Function) ---
def main():
    """نقطه شروع اجرای اسکریپت."""
    # لاگ کردن زمان اجرا (اختیاری)
    print(f"شروع اجرای همگام‌سازی در: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 1. بررسی اعتبارات
    if not CONFIG['GCC_USERNAME'] or not CONFIG['JIRA_USERNAME']:
        print("\n❌ خطای امنیتی: نام‌های کاربری GCC یا Jira تنظیم نشده‌اند.")
        print("لطفاً متغیرهای محیطی GCC_USERNAME و JIRA_USERNAME را تنظیم کنید.")
        if CONFIG['GCC_USERNAME'] == "probe184" or CONFIG['JIRA_USERNAME'] == "m.akbari":
             print("توجه: اسکریپت در حال استفاده از مقادیر پیش‌فرض قدیمی است. برای امنیت، متغیرهای محیطی را تنظیم کنید.")


    # 2. ورود به GCC
    if not login_gcc():
        return

    # 3. دریافت لیست تیکت‌ها و تیکت‌های پردازش شده
    tickets = get_my_tickets()
    print(f"{len(tickets)} تیکت از GCC دریافت شد.")
    
    if not tickets:
        print("لیست تیکت‌ها خالی است. پایان.")
        return

    processed_tickets = load_processed_tickets()
    print(f"{len(processed_tickets)} تیکت قبلاً پردازش شده‌اند.")

    # 4. پردازش تیکت‌ها
    new_tickets_count = 0
    for ticket in tickets:
        tick_id = ticket.get('tickID')
        if tick_id and tick_id not in processed_tickets:
            new_tickets_count += 1
            print(f"\nتیکت جدید شناسایی شد: {tick_id}. در حال ساخت Issue در Jira...")
            
            # 5. ساخت Issue
            success = create_jira_issue(ticket)
            
            # 6. ذخیره شناسه در صورت موفقیت
            if success:
                save_processed_ticket(tick_id)
            else:
                # اگر ساخت Issue ناموفق بود، نیازی به ذخیره آن نیست تا در اجرای بعدی مجددا امتحان شود.
                print(f"⚠️ ساخت Issue برای {tick_id} ناموفق بود. در اجرای بعدی مجددا تلاش خواهد شد.")
        elif tick_id in processed_tickets:
            print(f"تیکت {tick_id} قبلاً پردازش شده است. رد شد.")
        else:
            print("⚠️ یک تیکت بدون شناسه 'tickID' یافت شد. نادیده گرفته شد.")

    print(f"\nعملیات به پایان رسید. تعداد تیکت‌های جدید پردازش شده: {new_tickets_count}.")

if __name__ == "__main__":

    main()
