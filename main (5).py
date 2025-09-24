
import os
import json
import time
import secrets
import asyncio
import logging
import re
from pathlib import Path
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, ContextTypes, filters
)

# ─── إعداد الملفات واللوجينج ────────────────────────────────────────────
DATA_DIR = Path(__file__).parent / "data"
USERS_FILE = DATA_DIR / "users.json"
PEND_WDR = DATA_DIR / "pending_withdrawals.json"
PEND_DEP = DATA_DIR / "pending_deposits.json"
ADMIN_LOG = DATA_DIR / "admin_log.json"
WORK_WITHDRAWALS = DATA_DIR / "work_withdrawals.json"
CERTIFICATES_FILE = DATA_DIR / "certificates.json"
BAN_LOG = DATA_DIR / "ban_log.json"
os.makedirs(DATA_DIR, exist_ok=True)

# إعداد اللوجينج
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    filename='bot.log'
)
logger = logging.getLogger(__name__)

# تعريف هوية الأدمن
ADMIN_IDS = [7952226615]

# ─── دالة تحميل البيانات المحسنة ───────────────────────────────────────
def load_data(path: Path, default=None, ensure_list=False):
    if not path.exists():
        return default if default is not None else ([] if ensure_list else {})
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
            if ensure_list and not isinstance(data, list):
                logger.warning(f"File {path} is not a list, returning default")
                return default if default is not None else []
            return data
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error in {path}: {e}")
        backup_path = path.with_suffix('.json.backup')
        try:
            path.rename(backup_path)
            logger.info(f"Created backup at {backup_path}")
        except Exception:
            pass
        return default if default is not None else ([] if ensure_list else {})
    except Exception as e:
        logger.error(f"Error loading {path}: {e}")
        return default if default is not None else ([] if ensure_list else {})

def save_data(path: Path, obj):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error saving {path}: {e}")

# ─── ثوابت عامة ──────────────────────────────────────────────
TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    print("❌ خطأ: لم يتم العثور على BOT_TOKEN في متغيرات البيئة!")
    print("تأكد من إضافة BOT_TOKEN في قسم Secrets")
    exit(1)

# تعريف الخطط الاستثمارية
PLANS = {
    "daily": {
        "label": "يومي",
        "duration": 40,
        "monthly_profit": 5.0,
        "daily_profit": 0.1667,
        "payout_interval": 24 * 60 * 60  # 24 ساعة
    },
    "weekly": {
        "label": "أسبوعي", 
        "duration": 40,
        "monthly_profit": 6.0,
        "weekly_profit": 1.4,
        "payout_interval": 7 * 24 * 60 * 60  # 7 أيام
    },
    "monthly": {
        "label": "شهري",
        "duration": 40,
        "monthly_profit": 10.0,
        "payout_interval": 30 * 24 * 60 * 60  # 30 يوم
    }
}

# أسعار تحويل العملات
CONVERSION_RATES = {
    ('EGP', 'USDT'): 0.02,
    ('USDT', 'EGP'): 50.0
}

CONTRACT_TEXT = """
عقد اتفاق شروط استخدام Asser Platform

---

المادة (1): موضوع العقد

يهدف هذا العقد إلى تحديد شروط استخدام منصة Asser Platform من قبل الطرف الثاني، ويقر الطرف الثاني بالتزامه الكامل بالشروط المذكورة أدناه طوال فترة استخدامه للمنصة.


---

المادة (2): طبيعة منصة Asser Platform

1. Asser Platform هي منصة رقمية تعمل كوسيط مالي بين المستخدمين والمواقع الأجنبية الخاضعة لهيئة التسجيل الفيدرالية (Federal Registration Authority).


2. تتيح للمستخدمين تحويل أرباحهم من تلك المواقع إلى الجنيه المصري من خلال وسائل الدفع المحلية (فودافون كاش - إنستاباي - التحويل البنكي المصري).


3. توفر المنصة شهادات ادخار وعوائد متغيرة بحد أقصى 10% شهريًا (قابلة للتغيير وفقًا للأداء)، مع عوائد أعلى فقط لفئة "العملاء المميزين".


4. مصادر أرباح المنصة الرئيسية:

صناديق استثمار "بريق"

تداولات الـ P2P

البورصة المصرية (ليس بشكل دائم)





---

المادة (3): الالتزام باستخدام قانوني وأخلاقي

1. يلتزم الطرف الثاني بعدم استخدام المنصة لأي نشاط غير قانوني.


2. يُمنع إرسال أو نشر أي محتوى مسيء أو تحريضي.


3. يحافظ الطرف الثاني على سرية حسابه وبياناته وعدم مشاركتها مع الغير.





---

المادة (4): حقوق الملكية الفكرية

جميع حقوق المحتوى، البرمجة، التصميم، الاسم التجاري، تعود للطرف الأول. ويُمنع النسخ أو التعديل أو النشر بدون إذن رسمي.

---

المادة (5): خصوصية البيانات

1. تلتزم المنصة بحماية بيانات الطرف الثاني وعدم مشاركتها مع أطراف خارجية إلا في الحالات القانونية.


2. تُستخدم البيانات داخليًا لتحسين الأداء والخدمة فقط.





---

المادة (6): حدود المسؤولية

لا يتحمل الطرف الأول مسؤولية عن:

الأعطال التقنية المؤقتة

فقدان البيانات بسبب خطأ من المستخدم

أي ضرر ناتج عن الاستخدام غير السليم للمنصة

---

المادة (7): إيقاف الحساب

يحق للطرف الأول إيقاف أو حذف حساب الطرف الثاني إذا خالف شروط الاستخدام.

يتم إرسال تحذير قبل الإيقاف بـ 72 ساعة (باستثناء المادة 10 التي يتم الحظر فيها فورًا).

في حال التوقف، يلتزم الطرف الأول برد أي مبالغ مستحقة للطرف الثاني (عدا ما خالف الشروط).

---

المادة (8): تعديل الشروط

يحق للطرف الأول تعديل الشروط في أي وقت، ويُعتبر استمرار الطرف الثاني في استخدام المنصة موافقة ضمنية على التعديلات، بعد إخطاره بها.

---

المادة (9): القانون الحاكم

يخضع هذا العقد للقانون المصري، وتكون محاكم جمهورية مصر العربية هي المختصة بأي نزاع.

---

المادة (10): المسؤولية الجنائية وسوء الاستخدام

في حال استخدام المنصة في نشاطات غير قانونية مثل:

الاحتيال، الابتزاز، التهديد، إساءة استخدام البيانات أو أموال المستخدمين
يحتفظ الطرف الأول بالحق في:

1. إنهاء الحساب فورًا دون إشعار

2. اتخاذ الإجراءات القانونية

3. مشاركة بيانات المستخدم مع الجهات المختصة



---

المادة (11): أحكام عامة

1. العقد ملزم بمجرد الموافقة الإلكترونية من المستخدم.

2. لا يجوز التنازل عن الحقوق لأي طرف دون موافقة مكتوبة.



---

المادة (12): التوثيق والقبول الإلكتروني

تُعتبر الموافقة الإلكترونية عبر البوت أو النموذج الرسمي، بمثابة توقيع قانوني طبقًا لقانون التوقيع الإلكتروني رقم 15 لسنة 2004 بجمهورية مصر العربية.

---

المادة (13): ضوابط الإيداع والسحب
1. الإيداعات داخل المنصة تُعد مشاركة في نشاط تجاري، وليست وديعة بنكية.
.2مضمونةالأرباح غير مضمونة وتعتمد على الأداء الفعلي لصناديق الاستثمار.

3. لا يمكن سحب الأرباح إلا بعد بلوغ الحد الأدنى المُعلن في المنصة.

4. السحب العاجل ممكن فقط في حالات استثنائية موثقة (طبية/قضائية/كوارث).


المادة (14): نظام العملاء المميزين

1. توفر المنصة نظام "العملاء المميزين" لعدد محدود من المشتركين الموثوقين.


2. يحصل العميل المميز على:

دعم مباشر عبر WhatsApp

شارة ذهبية داخل البوت

أولوية في عمليات السحب

عوائد استثمارية أعلى (وفقًا لخطة متفق عليها)
"""

# حالات المحادثة
(REG_NAME, REG_EMAIL, REG_PASS, REG_PHONE,
 LOGIN_EMAIL, LOGIN_PASSWORD,
 DEP_CURR, DEP_NAME, DEP_PHONE, DEP_AMOUNT, DEP_SCREENSHOT, DEP_METHOD,
 WDR_CURR, WDR_AMT, WDR_METHOD,
 TRANSFER_AMOUNT, TRANSFER_CURR, TRANSFER_TARGET,
 TRANSFER_TYPE, TRANSFER_CONVERT_CURR_SOURCE, TRANSFER_CONVERT_AMOUNT, 
 TRANSFER_CONVERT_CURR_TARGET, TRANSFER_USER_CURR, TRANSFER_USER_AMOUNT, 
 TRANSFER_USER_TARGET, PLAN_CHOOSE, PLAN_AMOUNT,
 ADMIN_SEND_MONEY_USER, ADMIN_SEND_MONEY_AMOUNT,
 ADMIN_SEND_MONEY_TYPE, ADMIN_SEND_MONEY_CONFIRM, ADMIN_APPROVE_DUPLICATE) = range(32)

# حالات لوحة الأدمن الجديدة
(ADMIN_MAIN, ADMIN_BAN_USER, ADMIN_BAN_REASON, ADMIN_UNBAN_USER,
 ADMIN_EDIT_USER, ADMIN_EDIT_BALANCE, ADMIN_EDIT_FIELD, 
 ADMIN_BROADCAST, ADMIN_STATS, ADMIN_REQUESTS, ADMIN_PREMIUM, ADMIN_PREMIUM_USER,
 ADMIN_DEPOSIT_CHOICE, ADMIN_CUSTOM_REASON, ADMIN_SEARCH, ADMIN_SEARCH_INPUT) = range(33, 49)

# ─── نظام الدفع التلقائي للشهادات ─────────────────────────────────────
async def process_automatic_payouts(context=None):
    """معالجة الأرباح التلقائية لجميع المستخدمين"""
    users = load_data(USERS_FILE, {})
    current_time = time.time()
    
    for uid, user_data in users.items():
        if "plans" not in user_data or user_data.get("banned", False):
            continue
            
        total_profit_added = 0
        
        for plan in user_data["plans"]:
            plan_type = plan["type"]
            plan_config = PLANS[plan_type]
            
            # حساب الوقت المطلوب للدفع التالي
            payout_interval = plan_config["payout_interval"]
            
            # حساب معدل الربح
            if plan_type == "daily":
                profit_rate = plan_config["daily_profit"] / 100
                period_name = "يومية"
            elif plan_type == "weekly":
                profit_rate = plan_config["weekly_profit"] / 100
                period_name = "أسبوعية"
            elif plan_type == "monthly":
                profit_rate = plan_config["monthly_profit"] / 100
                period_name = "شهرية"
            else:
                continue
                
            # التحقق من إذا كان الوقت قد حان للدفع
            last_payout = plan.get("last_payout", plan["join_date"])
            time_since_last_payout = current_time - last_payout
            
            if time_since_last_payout >= payout_interval:
                # حساب عدد الدفعات المستحقة
                num_payouts = int(time_since_last_payout // payout_interval)
                
                # حساب الربح
                profit_amount = plan["amount"] * profit_rate * num_payouts
                
                # إضافة الربح للرصيد
                users[uid]["balance"]["EGP"] += profit_amount
                total_profit_added += profit_amount
                
                # تحديث وقت آخر دفع
                plan["last_payout"] = last_payout + (num_payouts * payout_interval)
                
                logger.info(f"تم دفع {profit_amount:.2f} EGP للمستخدم {uid} من خطة {plan_type}")
        
        # إرسال إشعار للمستخدم في حالة إضافة أرباح
        if total_profit_added > 0 and context:
            try:
                # تحديد نوع الشهادة والمعاد القادم
                next_payout_info = ""
                if user_data["plans"]:
                    plan = user_data["plans"][0]  # أول شهادة للمثال
                    plan_type = plan["type"]
                    next_payout = plan.get("last_payout", plan["join_date"]) + PLANS[plan_type]["payout_interval"]
                    next_payout_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(next_payout))
                    
                    if plan_type == "daily":
                        period_name = "يومية"
                    elif plan_type == "weekly":
                        period_name = "أسبوعية"
                    else:
                        period_name = "شهرية"
                    
                    next_payout_info = f"\n📅 <b>الدفعة القادمة:</b> {next_payout_str}\n🔄 <b>نوع الشهادة:</b> {period_name}"
                
                new_balance = users[uid]["balance"]["EGP"]
                
                profit_message = (
                    f"🎉 <b>مبروك! تم إضافة الأرباح بنجاح!</b>\n\n"
                    f"💰 <b>المبلغ المضاف:</b> {total_profit_added:.2f} EGP\n"
                    f"📈 من استثماراتك في Asser Platform\n"
                    f"💳 <b>رصيدك الجديد:</b> {new_balance:.2f} EGP"
                    f"{next_payout_info}\n\n"
                    f"🌟 <b>مبروك! استثمارك يحقق عوائد رائعة!</b>\n"
                    f"استمر في الاستثمار معنا لتحقيق المزيد من الأرباح\n\n"
                    f"💙 شكراً لثقتك في Asser Platform"
                )
                
                await context.bot.send_message(
                    chat_id=int(uid),
                    text=profit_message,
                    parse_mode=ParseMode.HTML
                )
            except Exception as e:
                logger.error(f"فشل في إرسال إشعار الأرباح للمستخدم {uid}: {e}")
    
    save_data(USERS_FILE, users)

# ─── دوال التسجيل المحسنة ─────────────────────────────────────────────
async def check_user_ban(uid, update, context):
    """فحص حالة حظر المستخدم"""
    users = load_data(USERS_FILE, {})
    if uid in users and users[uid].get("banned", False):
        ban_reason = users[uid].get("ban_reason", "غير محدد")
        ban_time = users[uid].get("ban_time", 0)
        ban_time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ban_time))
        
        ban_message = (
            f"🚫 <b>حسابك محظور!</b>\n\n"
            f"📋 <b>السبب:</b> {ban_reason}\n"
            f"📅 <b>وقت الحظر:</b> {ban_time_str}\n\n"
            f"يرجى الاتصال بالمالك: @Asser_EG"
        )
        
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(ban_message, parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text(ban_message, parse_mode=ParseMode.HTML)
        return True
    return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    users = load_data(USERS_FILE, {})

    # معالجة الأرباح التلقائية عند بدء البوت
    await process_automatic_payouts(context)

    # التحقق من وجود رابط دعوة
    args = context.args
    inviter_id = None
    if args and args[0].startswith("invite_"):
        try:
            inviter_id = args[0].split("_")[1]
        except (IndexError, ValueError):
            pass

    if uid in users:
        # التحقق من الحظر
        if await check_user_ban(uid, update, context):
            return ConversationHandler.END
        
        # إذا كان المستخدم مسجل وغير محظور، الدخول للقائمة الرئيسية
        await show_main_menu(update, context)
        return ConversationHandler.END

    # إذا لم يكن مسجل، عرض خيارات التسجيل
    context.user_data.clear()

    # إذا كان هناك مدعٍ صالح، حفظ معرفه
    if inviter_id and inviter_id in users:
        context.user_data["inviter_id"] = inviter_id

    keyboard = [
        [InlineKeyboardButton("👤 تسجيل مستخدم جديد", callback_data="new_register")],
        [InlineKeyboardButton("🔑 تسجيل الدخول", callback_data="login")],
        [InlineKeyboardButton("📋 معلومات تخزين البيانات", callback_data="data_storage_info")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    welcome_text = (
        "أهلاً وسهلاً بك في Asser Platform! 🎉\n\n"
        "نوني    \n\n"
        "اختر ما تريد:"
    )

    await update.message.reply_text(welcome_text, reply_markup=reply_markup)
    return ConversationHandler.END

async def handle_start_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "new_register":
        context.user_data.clear()
        await query.edit_message_text("👤 ما اسمك الكامل؟")
        return REG_NAME
    elif query.data == "login":
        await query.edit_message_text("📧 أدخل بريدك الإلكتروني:")
        return LOGIN_EMAIL
    elif query.data == "data_storage_info":
        await show_data_storage_info(update, context)
        return ConversationHandler.END
    else:
        await query.edit_message_text("⚠️ خطأ غير متوقع. يرجى المحاولة مرة أخرى.")
        return ConversationHandler.END

async def show_data_storage_info(update, context):
    message = (
        "🔒 <b>معلومات تخزين البيانات</b>\n\n"
        "🛡️ <b>الأمان والخصوصية:</b>\n"
        "• جميع بياناتك مشفرة بالكامل\n"
        "• حتى الموظفين في Asser Platform لا يمكنهم رؤية بياناتك\n"
        "• الشخص الوحيد الذي يمكنه رؤية بياناتك هو المالك\n\n"
        "🔑 <b>ماذا يحدث إذا نسيت كلمة السر أو البريد الإلكتروني؟</b>\n\n"
        "👑 <b>للعملاء المميزين:</b>\n"
        "• اتصل بالمالك بشكل مباشر\n"
        "• سيتصل بك أحد أفراد خدمة العملاء عبر رقم خط أرضي\n"
        "• ⚠️ لن يتصل بك فرد خدمة العملاء من رقم موبايل إطلاقاً\n"
        "• سيسألك أسئلة أمان تخص الحساب وعمليات التحويل\n"
        "• عند التأكد من أنك مالك الحساب بنفسك\n"
        "• سيتم إرسال لك ملف PDF بكلمة سر لا يعرفها غير المستخدم والمالك فقط\n\n"
        "👤 <b>للمستخدمين العاديين:</b>\n"
        "• نفس الخطوات ولكن عبر خدمة العملاء عبر الواتساب\n"
        "• نفس إجراءات الأمان والتحقق"
    )

    keyboard = [[InlineKeyboardButton("🔙 العودة", callback_data="back_to_start")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if hasattr(update, 'callback_query') and update.callback_query:
        await update.callback_query.edit_message_text(
            message, 
            reply_markup=reply_markup, 
            parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text(
            message, 
            reply_markup=reply_markup, 
            parse_mode=ParseMode.HTML
        )

async def back_to_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await start(update, context)

# ─── تسجيل مستخدم جديد ─────────────────────────────────────────────
async def reg_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text.strip()
    await update.message.reply_text("📧 بريدك الإلكتروني:")
    return REG_EMAIL

def is_valid_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def check_duplicate_data(email, phone, uid=None):
    """التحقق من تكرار البريد الإلكتروني أو رقم الهاتف"""
    users = load_data(USERS_FILE, {})

    for user_id, user_data in users.items():
        if uid and user_id == uid:
            continue

        if user_data.get("email") == email:
            return f"البريد الإلكتروني {email} مستخدم بالفعل"
        if user_data.get("phone") == phone:
            return f"رقم الهاتف {phone} مستخدم بالفعل"

    return None

def is_admin_approved_duplicate(uid):
    """التحقق من موافقة الأدمن على البيانات المكررة"""
    admin_approvals = load_data(DATA_DIR / "admin_duplicate_approvals.json", {})
    return admin_approvals.get(uid, False)

async def reg_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    email = update.message.text.strip()

    if not is_valid_email(email):
        await update.message.reply_text("⚠️ يرجى كتابة بريدك الإلكتروني بشكل صحيح (مثال: user@gmail.com)")
        return REG_EMAIL

    duplicate_check = check_duplicate_data(email, "")
    if duplicate_check and "البريد الإلكتروني" in duplicate_check:
        uid = str(update.effective_user.id)
        if not is_admin_approved_duplicate(uid):
            await update.message.reply_text(
                "❌ هذا البريد الإلكتروني مستخدم بالفعل!\n"
                "إذا كان هذا بريدك الشخصي، يرجى التواصل مع الإدارة."
            )
            return REG_EMAIL

    context.user_data["email"] = email
    await update.message.reply_text("🔒 اختر كلمة مرور:")
    return REG_PASS

async def reg_pass(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["password"] = update.message.text.strip()
    await update.message.reply_text("📱 رقم هاتفك (مع كود الدولة):")
    return REG_PHONE

async def reg_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    phone = update.message.text.strip()

    duplicate_check = check_duplicate_data("", phone)
    if duplicate_check and "رقم الهاتف" in duplicate_check:
        if not is_admin_approved_duplicate(uid):
            await update.message.reply_text(
                "❌ هذا الرقم مستخدم بالفعل!\n"
                "إذا كان هذا رقمك الشخصي، يرجى التواصل مع الإدارة."
            )
            return REG_PHONE

    users = load_data(USERS_FILE, {})
    invite_code = secrets.token_urlsafe(8)

    users[uid] = {
        "name": context.user_data["name"],
        "email": context.user_data["email"],
        "phone": phone,
        "password": context.user_data["password"],
        "balance": {"EGP": 0.0, "USDT": 0.0},
        "plans": [],
        "accepted_terms": False,
        "acceptance_time": None,
        "team_count": 0,
        "invite_code": invite_code,
        "inviter_id": context.user_data.get("inviter_id", None),
        "banned": False,
        "ban_reason": "",
        "ban_time": None,
        "premium": False,
        "registration_date": int(time.time())
    }

    if context.user_data.get("inviter_id") and context.user_data["inviter_id"] in users:
        users[context.user_data["inviter_id"]]["team_count"] = users[context.user_data["inviter_id"]].get("team_count", 0) + 1

    save_data(USERS_FILE, users)

    await update.message.reply_text("✅ تم إنشاء حسابك بنجاح!")
    await show_main_menu(update, context)
    return ConversationHandler.END

# ─── تسجيل الدخول ─────────────────────────────────────────────
async def login_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    email = update.message.text.strip()
    context.user_data["login_email"] = email
    await update.message.reply_text("🔒 أدخل كلمة المرور:")
    return LOGIN_PASSWORD

async def login_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    users = load_data(USERS_FILE, {})

    email = context.user_data["login_email"]
    password = update.message.text.strip()

    if uid in users:
        user = users[uid]
        if user["email"] == email and user["password"] == password:
            # التحقق من الحظر
            if user.get("banned", False):
                ban_reason = user.get("ban_reason", "غير محدد")
                ban_time = user.get("ban_time", 0)
                ban_time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ban_time))
                
                await update.message.reply_text(
                    f"🚫 <b>حسابك محظور!</b>\n\n"
                    f"📋 <b>السبب:</b> {ban_reason}\n"
                    f"📅 <b>وقت الحظر:</b> {ban_time_str}\n\n"
                    f"للاستفسار، تواصل مع الإدارة.",
                    parse_mode=ParseMode.HTML
                )
                return ConversationHandler.END
            
            await update.message.reply_text(
                "🎉 تم تسجيل الدخول بنجاح!\n\n"
                "سعدنا بلقائك من جديد يا عميلنا المميز! ✨"
            )
            await show_main_menu(update, context)
            return ConversationHandler.END

    await update.message.reply_text("❌ معلومات تسجيل الدخول غير صحيحة!")
    return ConversationHandler.END

async def show_main_menu(update, context):
    """عرض القائمة الرئيسية للبوت"""
    uid = str(update.effective_user.id)
    
    # فحص الحظر
    if await check_user_ban(uid, update, context):
        return
    
    await process_automatic_payouts(context)
    
    users = load_data(USERS_FILE, {})

    is_premium = users.get(uid, {}).get("premium", False)
    premium_icon = "👑" if is_premium else ""

    keyboard = [
        [InlineKeyboardButton(f"{premium_icon} بياناتك", callback_data="profile")],
        [InlineKeyboardButton("💰 أرصدتك", callback_data="balance")],
        [InlineKeyboardButton("💼 العمل-Work", callback_data="work_sites")],
        [InlineKeyboardButton("📈 التقديم على شهادة", callback_data="invest")],
        [InlineKeyboardButton("💰 سحب", callback_data="withdraw"),
         InlineKeyboardButton("📤 إيداع", callback_data="deposit")],
        [InlineKeyboardButton("💱 تحويل الأموال", callback_data="transfer")],
        [InlineKeyboardButton("👥 دعوة الأصدقاء", callback_data="invite_friends")],
        [InlineKeyboardButton("📋 عقد الاستخدام", callback_data="terms")],
        [InlineKeyboardButton("📱 تابعنا على مواقع التواصل", callback_data="social_media")]
    ]

    if not is_premium:
        keyboard.insert(-3, [InlineKeyboardButton("👑 كيف تصبح حساب مميز؟", callback_data="premium_info")])

    if uid == str(ADMIN_IDS[0]):
        keyboard.append([InlineKeyboardButton("🔧 لوحة الأدمن", callback_data="admin_panel")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    welcome_text = f"مرحبًا بك في Asser Platform! {premium_icon}\n\nاختر ما تريد:"

    if hasattr(update, 'callback_query') and update.callback_query:
        await update.callback_query.edit_message_text(welcome_text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(welcome_text, reply_markup=reply_markup)

# ─── قسم العمل المحدث ────────────────────────────────────────────
async def show_work_sites(update, context):
    keyboard = [
        [InlineKeyboardButton("📖 كيفية العمل", callback_data="how_to_work")],
        [InlineKeyboardButton("🌐 VKserfing", url="https://vkserfing.ru/?ref=551025727")],
        [InlineKeyboardButton("🚀 SMM Fast", url="https://fastsmm.ru/u/256485")],
        [InlineKeyboardButton("🎵 Asser Platform", url="https://taskpay.ru/?ref=4041472")],
        [InlineKeyboardButton("💰 سحب الأصول", callback_data="assets_withdrawal")],
        [InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = (
        "💼 <b>العمل على المواقع الخارجية</b>\n\n"
        "اختر من القائمة أدناه:"
    )

    await update.callback_query.edit_message_text(
        message,
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

async def show_how_to_work(update, context):
    message = (
        "📖 <b>كيفية العمل على المواقع</b>\n\n"
        "🔸 <b>الخطوة الأولى:</b> سجل في المواقع المتاحة\n"
        "🔸 <b>الخطوة الثانية:</b> اكمل المهام المطلوبة\n"
        "🔸 <b>الخطوة الثالثة:</b> اجمع أرباحك\n"
        "🔸 <b>الخطوة الرابعة:</b> استخدم خاصية 'سحب الأصول' لتحويل أرباحك إلى منصة Asser Platform\n\n"
        "💡 <b>نصائح مهمة:</b>\n"
        "• تأكد من إتمام المهام بشكل صحيح\n"
        "• احرص على متابعة أرباحك يومياً\n"
        "• استخدم روابط الدعوة المتاحة لزيادة الأرباح"
    )

    keyboard = [
        [InlineKeyboardButton("🔙 العودة لقسم العمل", callback_data="work_sites")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.callback_query.edit_message_text(
        message,
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

async def start_assets_withdrawal(update, context):
    uid = str(update.callback_query.from_user.id)
    
    # فحص الحظر
    if await check_user_ban(uid, update, context):
        return ConversationHandler.END

    context.user_data["is_assets_withdrawal"] = True

    keyboard = [
        [InlineKeyboardButton("🔙 العودة لقسم العمل", callback_data="work_sites")]
    ]

    message = (
        "🎉 <b>احنا مبسوطين انك وصلت لهنا!</b>\n\n"
        "💰 <b>شرح اللي المفيد:</b>\n\n"
        "يمكنك العمل علي المواقع المتاحة وسحب ارباحك عبر حساب Payeer الخاص بـ Asser Platform\n\n"
        "💳 <b>حساب Payeer:</b> <code>P1127257126</code>\n"
        "📋 (اضغط على الرقم لنسخه)\n\n"
        "وإرسال لقطة شاشة بعملية التحويل وفي خلال يوم عمل سيتم تحويل المبلغ لرصيدك في Asser Platform بنجاح\n\n"
        "📸 <b>يرجي إرسال لقطة شاشة موضح بها التاريخ ومبلغ التحويل سؤا كان بالروبل الروسي او الدولار الامريكي</b>"
    )

    await update.callback_query.edit_message_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )
    return DEP_SCREENSHOT

# ─── دالة بدء الإيداع المحدثة ────────────────────────────────────────────
async def start_deposit(update, context):
    uid = str(update.callback_query.from_user.id)
    
    # فحص الحظر
    if await check_user_ban(uid, update, context):
        return ConversationHandler.END

    keyboard = [
        [InlineKeyboardButton("💵 EGP", callback_data="EGP")],
        [InlineKeyboardButton("💲 USDT", callback_data="USDT")],
        [InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="back_to_main")]
    ]
    await update.callback_query.edit_message_text("اختر العملة:", reply_markup=InlineKeyboardMarkup(keyboard))
    return DEP_CURR

async def dep_curr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "back_to_main":
        await show_main_menu(update, context)
        return ConversationHandler.END

    context.user_data["curr"] = query.data

    if query.data == "EGP":  
        await query.edit_message_text("اكتب اسمك الثلاثي:")  
        return DEP_NAME  
    else:
        await query.edit_message_text(f"💵 المبلغ الذي تريد إيداعه ({query.data}):")  
        return DEP_AMOUNT

async def dep_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text.strip()
    await update.message.reply_text("📱 رقم هاتفك:")
    return DEP_PHONE

async def dep_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["phone"] = update.message.text.strip()
    await update.message.reply_text("💵 المبلغ الذي تريد إيداعه (EGP):")
    return DEP_AMOUNT

async def dep_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text.strip())
        if amount <= 0:
            raise ValueError
    except Exception:
        await update.message.reply_text("❌ أدخل رقمًا صحيحًا أكبر من صفر.")
        return DEP_AMOUNT

    context.user_data["amount"] = amount
    curr = context.user_data["curr"]

    if curr == "EGP":
        keyboard = [
            [InlineKeyboardButton("📱 محفظة إلكترونية", callback_data="wallet")],
            [InlineKeyboardButton("💳 انستاباي (قريباً)", callback_data="instapay_soon")],
            [InlineKeyboardButton("🏦 تحويل بنكي (قريباً)", callback_data="bank_soon")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("اختر طريقة الدفع:", reply_markup=reply_markup)
        return DEP_METHOD
    else:
        await update.message.reply_text(  
            "أرسل المبلغ إلى:\n`0x02918e6191c1d4d223031e87e221de8f32cb2bd8`\n(BEP 20)\nثم أرسل لقطة شاشة للتحويل.",  
            parse_mode=ParseMode.MARKDOWN
        )
        return DEP_SCREENSHOT

async def dep_method(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "wallet":
        await query.edit_message_text(  
            "حوِّل على *01227911081* (≥50 EGP)\nثم أرسل لقطة شاشة للتحويل.",  
            parse_mode=ParseMode.MARKDOWN
        )
        return DEP_SCREENSHOT
    elif query.data in ["instapay_soon", "bank_soon"]:
        await query.answer("قريباً...")
        return DEP_METHOD

async def dep_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("⚠️ يرجى إرسال لقطة شاشة (صورة) للتحويل.")
        return DEP_SCREENSHOT

    uid = str(update.effective_user.id)
    users = load_data(USERS_FILE, {})

    is_assets_withdrawal = context.user_data.get("is_assets_withdrawal", False)

    photo_file = await update.message.photo[-1].get_file()
    if is_assets_withdrawal:
        photo_path = f"data/assets_withdrawal_{uid}_{int(time.time())}.jpg"
    else:
        photo_path = f"data/deposit_{uid}_{int(time.time())}.jpg"
    await photo_file.download_to_drive(photo_path)

    if is_assets_withdrawal:
        if ADMIN_IDS:
            user_name = users.get(uid, {}).get("name", "غير معروف")
            user_email = users.get(uid, {}).get("email", "غير معروف")
            user_phone = users.get(uid, {}).get("phone", "غير معروف")

            caption = (
                f"💼 <b>طلب سحب الأصول جديد!</b>\n\n"
                f"🆔 UID: <code>{uid}</code>\n"
                f"👤 الاسم: {user_name}\n"
                f"📧 البريد: {user_email}\n"
                f"📱 الهاتف: {user_phone}\n"
                f"💳 حساب Payeer المستقبل: P1127257126\n"
                f"📅 الوقت: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"💰 <b>نوع الطلب:</b> سحب أصول من العمل الخارجي"
            )

            keyboard = [
                [InlineKeyboardButton("✅ موافقة", callback_data=f"approve_assets_{uid}")],
                [InlineKeyboardButton("❌ رفض", callback_data=f"reject_assets_{uid}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            for admin_id in ADMIN_IDS:
                try:
                    await context.bot.send_photo(
                        chat_id=admin_id,
                        photo=open(photo_path, 'rb'),
                        caption=caption,
                        reply_markup=reply_markup,
                        parse_mode=ParseMode.HTML
                    )
                except Exception as e:
                    logger.error(f"فشل في إرسال إشعار الأدمن: {e}")

        success_message = (
            "✅ <b>تم إرسال طلب سحب الأصول بنجاح!</b>\n\n"
            "🔄 <b>خطوات المعالجة:</b>\n"
            "1️⃣ يتم الآن مراجعة طلبك من قبل الإدارة\n"
            "2️⃣ سيتم التحقق من صحة التحويل\n"
            "3️⃣ سيتم إضافة المبلغ إلى رصيدك في Asser Platform\n\n"
            "⏰ <b>المدة المتوقعة:</b> خلال يوم عمل واحد\n\n"
            "💰 <b>بعد الموافقة يمكنك سحب أموالك عبر:</b>\n"
            "• فودافون كاش 📱\n"
            "• انستاباي 💳\n"
            "• تحويل بنكي 🏦\n\n"
            "شكراً لك على استخدام Asser Platform! 💙"
        )
        await update.message.reply_text(success_message, parse_mode=ParseMode.HTML)

    else:
        curr = context.user_data["curr"]
        amount = context.user_data["amount"]

        pend = load_data(PEND_DEP, [], ensure_list=True)  
        req = {  
            "uid": uid,
            "currency": curr,  
            "amount": amount,  
            "time": int(time.time()),
            "user_name": context.user_data.get("name", users.get(uid, {}).get("name", "غير معروف")),
            "user_phone": context.user_data.get("phone", users.get(uid, {}).get("phone", "غير معروف")),
            "status": "pending",
            "screenshot_path": photo_path,
            "type": "normal"
        }  

        pend.append(req)  
        save_data(PEND_DEP, pend)  

        if ADMIN_IDS:
            user_info = f"👤: {req['user_name']}\n📱: {req['user_phone']}" if curr == "EGP" else ""
            caption = (
                f"4️⃣ طلب إيداع جديد!\n\n"
                f"🆔 UID: {req['uid']}\n"
                f"💰 العملة: {curr}\n"
                f"💵 المبلغ: {amount}\n"
                f"{user_info}\n"
                f"📅 الوقت: {time.strftime('%Y-%m-%d %H:%M:%S')}"
            )

            keyboard = [
                [InlineKeyboardButton("✅ موافقة", callback_data=f"approve_deposit_{len(pend)-1}")],
                [InlineKeyboardButton("❌ رفض", callback_data=f"reject_deposit_{len(pend)-1}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            for admin_id in ADMIN_IDS:
                try:
                    await context.bot.send_photo(
                        chat_id=admin_id,
                        photo=open(photo_path, 'rb'),
                        caption=caption,
                        reply_markup=reply_markup,
                        parse_mode=ParseMode.HTML
                    )
                except Exception as e:
                    logger.error(f"فشل في إرسال إشعار الأدمن: {e}")

        await update.message.reply_text("✅ تم إرسال طلب الإيداع بنجاح! سيتم مراجعته قريباً.")

    return ConversationHandler.END

# ─── دالة بدء السحب المحدثة ────────────────────────────────────────────
async def start_withdraw(update, context):
    uid = str(update.callback_query.from_user.id)
    
    # فحص الحظر
    if await check_user_ban(uid, update, context):
        return ConversationHandler.END

    keyboard = [
        [InlineKeyboardButton("💵 EGP", callback_data="EGP")],
        [InlineKeyboardButton("💲 USDT", callback_data="USDT")],
        [InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="back_to_main")]
    ]
    await update.callback_query.edit_message_text("عملة السحب:", reply_markup=InlineKeyboardMarkup(keyboard))
    return WDR_CURR

async def wdr_curr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "back_to_main":
        await show_main_menu(update, context)
        return ConversationHandler.END

    context.user_data["wc"] = query.data

    if query.data == "EGP":
        keyboard = [
            [InlineKeyboardButton("📱 محفظة إلكترونية", callback_data="wallet")],
            [InlineKeyboardButton("💳 انستاباي (قريباً)", callback_data="instapay_soon")],
            [InlineKeyboardButton("🏦 تحويل بنكي (قريباً)", callback_data="bank_soon")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("اختر طريقة السحب:", reply_markup=reply_markup)
        return WDR_METHOD
    else:
        await query.edit_message_text("💵 اكتب المبلغ:")
        return WDR_AMT

async def wdr_method(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "wallet":
        await query.edit_message_text("💵 اكتب المبلغ:")
        return WDR_AMT
    elif query.data in ["instapay_soon", "bank_soon"]:
        await query.answer("قريباً...")
        return WDR_METHOD

async def wdr_amt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amt = float(update.message.text.strip())
        if amt <= 0:
            raise ValueError
    except Exception:
        await update.message.reply_text("❌ أدخل رقمًا صحيحًا أكبر من صفر.")
        return WDR_AMT

    uid = str(update.effective_user.id)  
    currency = context.user_data["wc"]  
    users = load_data(USERS_FILE, {})  

    if uid not in users:  
        await update.message.reply_text("❌ سجل أولًا باستخدام /start.")  
        return ConversationHandler.END  

    if users[uid]["balance"].get(currency, 0) < amt:  
        await update.message.reply_text(f"❌ رصيد {currency} غير كافٍ.")  
        return ConversationHandler.END  

    fee = round(amt * 0.02, 2)  
    net = amt - fee  

    users[uid]["balance"][currency] -= amt  
    save_data(USERS_FILE, users)  

    pend = load_data(PEND_WDR, [], ensure_list=True)  
    wdr_request = {  
        "uid": uid,  
        "currency": currency,  
        "amount": net,
        "fee": fee,  
        "time": int(time.time()),
        "user_name": users[uid]["name"],
        "user_phone": users[uid]["phone"],
        "status": "pending"
    }  
    pend.append(wdr_request)  
    save_data(PEND_WDR, pend)  

    if ADMIN_IDS:
        caption = (
            f"📤 طلب سحب جديد!\n\n"
            f"🆔 UID: {uid}\n"
            f"👤: {wdr_request['user_name']}\n"
            f"📱: {wdr_request['user_phone']}\n"
            f"💰 العملة: {currency}\n"
            f"💵 المبلغ: {net} (صافي بعد رسوم 2%)\n"
            f"📅 الوقت: {time.strftime('%Y-%m-%d %H:%M:%S')}"
        )

        keyboard = [
            [InlineKeyboardButton("✅ موافقة", callback_data=f"approve_withdrawal_{len(pend)-1}")],
            [InlineKeyboardButton("❌ رفض", callback_data=f"reject_withdrawal_{len(pend)-1}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=caption,
                    reply_markup=reply_markup
                )
            except Exception as e:
                logger.error(f"فشل في إرسال إشعار الأدمن: {e}")

    await update.message.reply_text(  
        f"✅ تم طلب السحب.\n"  
        f"المبلغ: {amt:.2f} {currency}\n"  
        f"صافي بعد الرسوم (2%): {net:.2f} {currency}"  
    )  
    return ConversationHandler.END

# ─── لوحة الأدمن المحسنة مع جميع المميزات ────────────────────────────────────────────
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id

    if user_id != ADMIN_IDS[0]:
        await query.edit_message_text("❌ ليس لديك صلاحيات الوصول لهذا الأمر.")
        return ConversationHandler.END

    keyboard = [
        [InlineKeyboardButton("💰 إرسال أموال لمستخدم", callback_data="admin_send_money")],
        [InlineKeyboardButton("4️⃣ إيداع خاص", callback_data="admin_special_deposit")],
        [InlineKeyboardButton("🚫 حظر/فك حظر مستخدم", callback_data="admin_ban")],
        [InlineKeyboardButton("💼 تعديل الأرصدة", callback_data="admin_edit")],
        [InlineKeyboardButton("🔍 البحث عن مستخدم", callback_data="admin_search")],
        [InlineKeyboardButton("📊 الإحصائيات", callback_data="admin_stats")],
        [InlineKeyboardButton("📋 الطلبات المعلقة", callback_data="admin_requests")],
        [InlineKeyboardButton("👑 إدارة الحساب المميز", callback_data="admin_premium")],
        [InlineKeyboardButton("📨 إرسال إشعار عام", callback_data="admin_broadcast")],
        [InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "👑 <b>لوحة تحكم الأدمن الرئيسي</b>\n\n"
        "اختر الإدارة التي تريدها:",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )
    return ADMIN_MAIN

# ─── نظام الإيداع الخاص (أيقونة 4) ────────────────────────────────────────────
async def admin_special_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "4️⃣ <b>الإيداع الخاص</b>\n\n"
        "أرسل UID المستخدم لإضافة إيداع خاص له:",
        parse_mode=ParseMode.HTML
    )
    return ADMIN_SEND_MONEY_USER

async def admin_special_deposit_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.text.strip()
    users = load_data(USERS_FILE, {})

    if uid not in users:
        await update.message.reply_text("❌ المستخدم غير موجود!")
        return ADMIN_SEND_MONEY_USER

    context.user_data["target_uid"] = uid
    context.user_data["is_special_deposit"] = True
    user_name = users[uid]["name"]

    await update.message.reply_text(
        f"👤 <b>المستخدم المختار:</b> {user_name}\n\n"
        f"💵 أدخل المبلغ (EGP):",
        parse_mode=ParseMode.HTML
    )
    return ADMIN_SEND_MONEY_AMOUNT

# ─── نظام الحظر المحسن ────────────────────────────────────────────
async def admin_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("🚫 حظر مستخدم", callback_data="ban_user")],
        [InlineKeyboardButton("✅ فك حظر مستخدم", callback_data="unban_user")],
        [InlineKeyboardButton("🔙 العودة للوحة الأدمن", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "🚫 <b>إدارة حظر المستخدمين</b>\n\n"
        "اختر العملية:",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )
    return ADMIN_BAN_USER

async def ban_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "admin_panel":
        await admin_panel(update, context)
        return ADMIN_MAIN

    context.user_data["ban_action"] = query.data

    await query.edit_message_text(
        "🆔 أرسل UID المستخدم:",
        parse_mode=ParseMode.HTML
    )
    return ADMIN_BAN_USER

async def admin_ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.text.strip()
    users = load_data(USERS_FILE, {})

    if uid not in users:
        await update.message.reply_text("❌ المستخدم غير موجود!")
        return ADMIN_BAN_USER

    context.user_data["target_uid"] = uid
    action = context.user_data["ban_action"]

    if action == "ban_user":
        if users[uid].get("banned", False):
            await update.message.reply_text("⚠️ هذا المستخدم محظور بالفعل!")
            return ConversationHandler.END

        keyboard = [
            [InlineKeyboardButton("💼 عملية احتيال", callback_data="fraud")],
            [InlineKeyboardButton("⏰ مؤقت حتى الموافقة على العقد", callback_data="contract_pending")],
            [InlineKeyboardButton("✏️ أخرى (كتابة يدوية)", callback_data="custom_reason")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"👤 <b>المستخدم:</b> {users[uid]['name']}\n\n"
            "🚫 اختر سبب الحظر:",
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
        return ADMIN_BAN_REASON

    elif action == "unban_user":
        if not users[uid].get("banned", False):
            await update.message.reply_text("⚠️ هذا المستخدم غير محظور!")
            return ConversationHandler.END

        users[uid]["banned"] = False
        users[uid]["ban_reason"] = ""
        users[uid]["ban_time"] = None
        save_data(USERS_FILE, users)

        # إشعار المستخدم
        try:
            await context.bot.send_message(
                chat_id=int(uid),
                text="🎉 <b>تم فك الحظر عن حسابك!</b>\n\n"
                     "يمكنك الآن استخدام جميع خدمات Asser Platform بشكل طبيعي.\n\n"
                     "💙 مرحباً بك مرة أخرى!",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"فشل في إرسال إشعار فك الحظر: {e}")

        await update.message.reply_text(
            f"✅ تم فك الحظر عن المستخدم {users[uid]['name']} بنجاح!"
        )
        return ConversationHandler.END

async def admin_ban_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    uid = context.user_data["target_uid"]
    users = load_data(USERS_FILE, {})

    reason_map = {
        "fraud": "عملية احتيال",
        "contract_pending": "مؤقت حتى الموافقة على العقد"
    }

    if query.data == "custom_reason":
        await query.edit_message_text(
            "✏️ اكتب سبب الحظر:",
            parse_mode=ParseMode.HTML
        )
        return ADMIN_CUSTOM_REASON
    else:
        reason = reason_map[query.data]
        
        # تطبيق الحظر
        users[uid]["banned"] = True
        users[uid]["ban_reason"] = reason
        users[uid]["ban_time"] = int(time.time())
        save_data(USERS_FILE, users)

        # حفظ في سجل الحظر
        ban_log = load_data(BAN_LOG, [], ensure_list=True)
        ban_log.append({
            "uid": uid,
            "user_name": users[uid]["name"],
            "reason": reason,
            "time": int(time.time()),
            "admin_id": update.effective_user.id
        })
        save_data(BAN_LOG, ban_log)

        # إشعار المستخدم
        try:
            await context.bot.send_message(
                chat_id=int(uid),
                text=f"🚫 <b>تم حظر حسابك!</b>\n\n"
                     f"📋 <b>السبب:</b> {reason}\n"
                     f"📅 <b>التاريخ:</b> {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                     f"للاستفسار، تواصل مع الإدارة.",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"فشل في إرسال إشعار الحظر: {e}")

        await query.edit_message_text(
            f"✅ تم حظر المستخدم {users[uid]['name']} بسبب: {reason}"
        )
        return ConversationHandler.END

async def admin_custom_ban_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reason = update.message.text.strip()
    uid = context.user_data["target_uid"]
    users = load_data(USERS_FILE, {})

    # تطبيق الحظر
    users[uid]["banned"] = True
    users[uid]["ban_reason"] = reason
    users[uid]["ban_time"] = int(time.time())
    save_data(USERS_FILE, users)

    # حفظ في سجل الحظر
    ban_log = load_data(BAN_LOG, [], ensure_list=True)
    ban_log.append({
        "uid": uid,
        "user_name": users[uid]["name"],
        "reason": reason,
        "time": int(time.time()),
        "admin_id": update.effective_user.id
    })
    save_data(BAN_LOG, ban_log)

    # إشعار المستخدم
    try:
        await context.bot.send_message(
            chat_id=int(uid),
            text=f"🚫 <b>تم حظر حسابك!</b>\n\n"
                 f"📋 <b>السبب:</b> {reason}\n"
                 f"📅 <b>التاريخ:</b> {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                 f"للاستفسار، تواصل مع الإدارة.",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"فشل في إرسال إشعار الحظر: {e}")

    await update.message.reply_text(
        f"✅ تم حظر المستخدم {users[uid]['name']} بسبب: {reason}"
    )
    return ConversationHandler.END

# ─── إضافة باقي وظائف الأدمن المفقودة ────────────────────────────────────────────

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض إحصائيات المنصة"""
    query = update.callback_query
    await query.answer()
    
    users = load_data(USERS_FILE, {})
    deposits = load_data(PEND_DEP, [], ensure_list=True)
    withdrawals = load_data(PEND_WDR, [], ensure_list=True)
    
    total_users = len(users)
    banned_users = sum(1 for user in users.values() if user.get("banned", False))
    premium_users = sum(1 for user in users.values() if user.get("premium", False))
    
    total_egp = sum(user["balance"]["EGP"] for user in users.values())
    total_usdt = sum(user["balance"]["USDT"] for user in users.values())
    
    pending_deposits = len(deposits)
    pending_withdrawals = len(withdrawals)
    
    stats_text = (
        f"📊 <b>إحصائيات المنصة</b>\n\n"
        f"👥 <b>المستخدمين:</b>\n"
        f"  - إجمالي: {total_users}\n"
        f"  - محظورين: {banned_users}\n"
        f"  - مميزين: {premium_users}\n\n"
        f"💰 <b>الأرصدة الإجمالية:</b>\n"
        f"  - EGP: {total_egp:.2f}\n"
        f"  - USDT: {total_usdt:.2f}\n\n"
        f"📋 <b>الطلبات المعلقة:</b>\n"
        f"  - إيداعات: {pending_deposits}\n"
        f"  - سحوبات: {pending_withdrawals}"
    )
    
    keyboard = [[InlineKeyboardButton("🔙 العودة للوحة الأدمن", callback_data="admin_panel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(stats_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

async def admin_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض الطلبات المعلقة"""
    query = update.callback_query
    await query.answer()
    
    deposits = load_data(PEND_DEP, [], ensure_list=True)
    withdrawals = load_data(PEND_WDR, [], ensure_list=True)
    
    requests_text = f"📋 <b>الطلبات المعلقة</b>\n\n"
    requests_text += f"💰 إيداعات معلقة: {len(deposits)}\n"
    requests_text += f"📤 سحوبات معلقة: {len(withdrawals)}\n\n"
    
    if deposits:
        requests_text += "<b>آخر 3 إيداعات:</b>\n"
        for i, dep in enumerate(deposits[-3:]):
            requests_text += f"  {i+1}. {dep['currency']} {dep['amount']:.2f} - UID: {dep['uid']}\n"
    
    if withdrawals:
        requests_text += "\n<b>آخر 3 سحوبات:</b>\n"
        for i, wdr in enumerate(withdrawals[-3:]):
            requests_text += f"  {i+1}. {wdr['currency']} {wdr['amount']:.2f} - UID: {wdr['uid']}\n"
    
    keyboard = [[InlineKeyboardButton("🔙 العودة للوحة الأدمن", callback_data="admin_panel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(requests_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

async def admin_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إدارة الحساب المميز"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("👑 منح حساب مميز", callback_data="grant_premium")],
        [InlineKeyboardButton("❌ إلغاء حساب مميز", callback_data="revoke_premium")],
        [InlineKeyboardButton("🔙 العودة للوحة الأدمن", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "👑 <b>إدارة الحساب المميز</b>\n\n"
        "اختر العملية:",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )
    return ADMIN_PREMIUM

async def admin_premium_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج إجراءات الحساب المميز"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "admin_panel":
        await admin_panel(update, context)
        return ADMIN_MAIN
    
    context.user_data["premium_action"] = query.data
    
    await query.edit_message_text(
        "🆔 أرسل UID المستخدم:",
        parse_mode=ParseMode.HTML
    )
    return ADMIN_PREMIUM_USER

async def admin_premium_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج المستخدم للحساب المميز"""
    uid = update.message.text.strip()
    users = load_data(USERS_FILE, {})
    
    if uid not in users:
        await update.message.reply_text("❌ المستخدم غير موجود!")
        return ADMIN_PREMIUM_USER
    
    action = context.user_data["premium_action"]
    user_name = users[uid]["name"]
    
    if action == "grant_premium":
        users[uid]["premium"] = True
        save_data(USERS_FILE, users)
        
        # إشعار المستخدم
        try:
            await context.bot.send_message(
                chat_id=int(uid),
                text="🎉 <b>مبروك! تم ترقية حسابك إلى حساب مميز!</b>\n\n"
                     "👑 يمكنك الآن الاستفادة من جميع مميزات الحساب المميز\n\n"
                     "💙 شكراً لثقتك في Asser Platform",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"فشل في إرسال إشعار الحساب المميز: {e}")
        
        await update.message.reply_text(f"✅ تم منح {user_name} حساب مميز!")
        
    elif action == "revoke_premium":
        users[uid]["premium"] = False
        save_data(USERS_FILE, users)
        
        # إشعار المستخدم
        try:
            await context.bot.send_message(
                chat_id=int(uid),
                text="📢 <b>تم إلغاء الحساب المميز</b>\n\n"
                     "تم إلغاء مميزات الحساب المميز من حسابك\n\n"
                     "للاستفسار، تواصل مع الإدارة",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"فشل في إرسال إشعار إلغاء الحساب المميز: {e}")
        
        await update.message.reply_text(f"✅ تم إلغاء الحساب المميز من {user_name}")
    
    return ConversationHandler.END

async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إرسال إشعار عام"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "📨 <b>إرسال إشعار عام</b>\n\n"
        "اكتب الرسالة التي تريد إرسالها لجميع المستخدمين:",
        parse_mode=ParseMode.HTML
    )
    return ADMIN_BROADCAST

async def admin_broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إرسال الإشعار العام"""
    message = update.message.text.strip()
    users = load_data(USERS_FILE, {})
    
    sent_count = 0
    failed_count = 0
    
    for uid in users.keys():
        try:
            await context.bot.send_message(
                chat_id=int(uid),
                text=f"📢 <b>إشعار من إدارة Asser Platform</b>\n\n{message}",
                parse_mode=ParseMode.HTML
            )
            sent_count += 1
        except Exception as e:
            failed_count += 1
            logger.error(f"فشل إرسال الإشعار للمستخدم {uid}: {e}")
    
    await update.message.reply_text(
        f"✅ <b>تم إرسال الإشعار!</b>\n\n"
        f"📤 تم الإرسال: {sent_count}\n"
        f"❌ فشل: {failed_count}",
        parse_mode=ParseMode.HTML
    )
    return ConversationHandler.END

async def admin_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """البحث عن مستخدم"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "🔍 <b>البحث عن مستخدم</b>\n\n"
        "أدخل واحد من التالي للبحث:\n"
        "• UID المستخدم\n"
        "• الاسم الكامل\n"
        "• البريد الإلكتروني\n"
        "• رقم الهاتف",
        parse_mode=ParseMode.HTML
    )
    return ADMIN_SEARCH_INPUT

async def admin_search_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج البحث عن المستخدم"""
    search_term = update.message.text.strip()
    users = load_data(USERS_FILE, {})
    
    found_users = []
    
    # البحث في جميع المستخدمين
    for uid, user_data in users.items():
        if (uid == search_term or 
            user_data.get('name', '').lower() == search_term.lower() or
            user_data.get('email', '').lower() == search_term.lower() or
            user_data.get('phone', '') == search_term):
            found_users.append((uid, user_data))
    
    if not found_users:
        await update.message.reply_text(
            "❌ لم يتم العثور على أي مستخدم بهذه البيانات!"
        )
        return ConversationHandler.END
    
    # عرض نتائج البحث
    for uid, user in found_users:
        # حساب إجمالي الاستثمارات
        total_investments = sum(plan['amount'] for plan in user.get('plans', []))
        
        # حساب الشهادات النشطة
        active_plans = []
        current_time = time.time()
        
        for plan in user.get('plans', []):
            elapsed_days = (current_time - plan['join_date']) / (24 * 3600)
            remaining_days = max(0, plan['duration'] - elapsed_days)
            
            if remaining_days > 0:
                plan_info = f"  - {PLANS[plan['type']]['label']}: {plan['amount']:.2f} EGP (متبقي: {remaining_days:.1f} أيام)"
                active_plans.append(plan_info)
        
        plans_text = "\n".join(active_plans) if active_plans else "لا توجد شهادات نشطة"
        
        # حالة الحظر
        ban_status = ""
        if user.get("banned", False):
            ban_status = f"\n\n🚫 <b>محظور!</b> - {user.get('ban_reason', 'غير محدد')}"
        
        # تاريخ التسجيل
        registration_date = "غير محدد"
        if user.get("registration_date"):
            registration_date = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(user["registration_date"]))
        
        # حالة الموافقة على العقد
        terms_status = "نعم ✅" if user.get("accepted_terms", False) else "لا ❌"
        
        # نوع الحساب
        account_type = "مميز 👑" if user.get("premium", False) else "عادي"
        
        search_result = (
            f"🔍 <b>نتيجة البحث</b>\n\n"
            f"🆔 <b>UID:</b> <code>{uid}</code>\n"
            f"👤 <b>الاسم:</b> {user['name']}\n"
            f"📧 <b>البريد:</b> {user['email']}\n"
            f"📱 <b>الهاتف:</b> {user['phone']}\n"
            f"📅 <b>تاريخ التسجيل:</b> {registration_date}\n"
            f"👑 <b>نوع الحساب:</b> {account_type}\n"
            f"⚖️ <b>موافقة على العقد:</b> {terms_status}\n\n"
            f"💰 <b>الأرصدة:</b>\n"
            f"  - EGP: {user['balance']['EGP']:.2f}\n"
            f"  - USDT: {user['balance']['USDT']:.2f}\n\n"
            f"💼 <b>إجمالي الاستثمارات:</b> {total_investments:.2f} EGP\n\n"
            f"📈 <b>الشهادات النشطة:</b>\n{plans_text}\n\n"
            f"👥 <b>الفريق:</b> {user.get('team_count', 0)} عضو\n"
            f"🔑 <b>كود الدعوة:</b> <code>{user.get('invite_code', '')}</code>"
            f"{ban_status}"
        )
        
        await update.message.reply_text(search_result, parse_mode=ParseMode.HTML)
    
    return ConversationHandler.END

async def admin_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تعديل الأرصدة"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "💼 <b>تعديل الأرصدة</b>\n\n"
        "أرسل UID المستخدم:",
        parse_mode=ParseMode.HTML
    )
    return ADMIN_EDIT_USER

async def admin_edit_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """اختيار المستخدم لتعديل رصيده"""
    uid = update.message.text.strip()
    users = load_data(USERS_FILE, {})
    
    if uid not in users:
        await update.message.reply_text("❌ المستخدم غير موجود!")
        return ADMIN_EDIT_USER
    
    context.user_data["edit_uid"] = uid
    user = users[uid]
    
    keyboard = [
        [InlineKeyboardButton("💵 EGP", callback_data="edit_EGP")],
        [InlineKeyboardButton("💲 USDT", callback_data="edit_USDT")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"👤 <b>المستخدم:</b> {user['name']}\n\n"
        f"💰 <b>الأرصدة الحالية:</b>\n"
        f"  - EGP: {user['balance']['EGP']:.2f}\n"
        f"  - USDT: {user['balance']['USDT']:.2f}\n\n"
        "اختر العملة المراد تعديلها:",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )
    return ADMIN_EDIT_FIELD

async def admin_edit_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """اختيار العملة لتعديلها"""
    query = update.callback_query
    await query.answer()
    
    currency = query.data.split("_")[1]  # EGP أو USDT
    context.user_data["edit_currency"] = currency
    
    await query.edit_message_text(
        f"💰 <b>تعديل رصيد {currency}</b>\n\n"
        f"أدخل الرصيد الجديد:",
        parse_mode=ParseMode.HTML
    )
    return ADMIN_EDIT_BALANCE

async def admin_edit_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تطبيق تعديل الرصيد"""
    try:
        new_balance = float(update.message.text.strip())
        if new_balance < 0:
            raise ValueError
    except Exception:
        await update.message.reply_text("❌ أدخل رقماً صحيحاً غير سالب!")
        return ADMIN_EDIT_BALANCE
    
    uid = context.user_data["edit_uid"]
    currency = context.user_data["edit_currency"]
    users = load_data(USERS_FILE, {})
    
    old_balance = users[uid]["balance"][currency]
    users[uid]["balance"][currency] = new_balance
    save_data(USERS_FILE, users)
    
    # إشعار المستخدم
    try:
        await context.bot.send_message(
            chat_id=int(uid),
            text=f"💰 <b>تم تحديث رصيدك!</b>\n\n"
                 f"العملة: {currency}\n"
                 f"الرصيد الجديد: {new_balance:.2f}\n\n"
                 f"من إدارة Asser Platform 💙",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"فشل في إرسال إشعار تحديث الرصيد: {e}")
    
    await update.message.reply_text(
        f"✅ <b>تم تحديث الرصيد!</b>\n\n"
        f"👤 المستخدم: {users[uid]['name']}\n"
        f"💰 العملة: {currency}\n"
        f"📊 من {old_balance:.2f} إلى {new_balance:.2f}",
        parse_mode=ParseMode.HTML
    )
    return ConversationHandler.END

# ─── باقي دوال الأدمن ────────────────────────────────────────────
async def admin_send_money(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "💰 <b>إرسال أموال لمستخدم</b>\n\n"
        "أرسل UID المستخدم:",
        parse_mode=ParseMode.HTML
    )
    return ADMIN_SEND_MONEY_USER

async def admin_send_money_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.text.strip()
    users = load_data(USERS_FILE, {})

    if uid not in users:
        await update.message.reply_text("❌ المستخدم غير موجود!")
        return ADMIN_SEND_MONEY_USER

    context.user_data["target_uid"] = uid
    user_name = users[uid]["name"]

    await update.message.reply_text(
        f"👤 <b>المستخدم المختار:</b> {user_name}\n\n"
        f"💵 أدخل المبلغ (EGP):",
        parse_mode=ParseMode.HTML
    )
    return ADMIN_SEND_MONEY_AMOUNT

async def admin_send_money_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text.strip())
        if amount <= 0:
            raise ValueError
    except Exception:
        await update.message.reply_text("❌ أدخل مبلغاً صحيحاً!")
        return ADMIN_SEND_MONEY_AMOUNT

    context.user_data["amount"] = amount

    # التحقق من نوع العملية
    if context.user_data.get("is_special_deposit", False):
        # إيداع خاص مباشر
        uid = context.user_data["target_uid"]
        users = load_data(USERS_FILE, {})
        
        users[uid]["balance"]["EGP"] += amount
        save_data(USERS_FILE, users)

        # إرسال إشعار مخصص للإيداع الخاص
        try:
            await context.bot.send_message(
                chat_id=int(uid),
                text=f"4️⃣ <b>تهانينا! تم قبول الإيداع الخاص بك.</b>\n\n"
                     f"تم إضافة <b>{amount:.2f} EGP</b> إلى رصيدك\n\n"
                     f"من إدارة Asser Platform 💙",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"فشل في إرسال إشعار المستخدم: {e}")

        await update.message.reply_text(
            f"✅ <b>تم الإيداع الخاص بنجاح!</b>\n\n"
            f"تم إضافة {amount:.2f} EGP للمستخدم {users[uid]['name']}",
            parse_mode=ParseMode.HTML
        )
        
        # مسح البيانات
        context.user_data.clear()
        return ConversationHandler.END
    else:
        # إرسال أموال عادي
        keyboard = [
            [InlineKeyboardButton("🎁 مكافأة", callback_data="reward")],
            [InlineKeyboardButton("💸 تعويض", callback_data="compensation")],
            [InlineKeyboardButton("🎉 هدية", callback_data="gift")],
            [InlineKeyboardButton("💰 إيداع", callback_data="deposit_transfer")],
            [InlineKeyboardButton("💼 سحب الأصول", callback_data="assets_withdrawal_transfer")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"💰 المبلغ: {amount:.2f} EGP\n\n"
            "اختر نوع التحويل:",
            reply_markup=reply_markup
        )
        return ADMIN_SEND_MONEY_TYPE

async def admin_send_money_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    type_map = {
        "reward": "مكافأة",
        "compensation": "تعويض", 
        "gift": "هدية",
        "deposit_transfer": "إيداع",
        "assets_withdrawal_transfer": "سحب الأصول"
    }

    transfer_type = type_map[query.data]
    context.user_data["transfer_type"] = transfer_type

    uid = context.user_data["target_uid"]
    amount = context.user_data["amount"]
    users = load_data(USERS_FILE, {})
    user_name = users[uid]["name"]

    keyboard = [
        [InlineKeyboardButton("✅ تأكيد", callback_data="confirm_send")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"📋 <b>تأكيد التحويل</b>\n\n"
        f"👤 المستخدم: {user_name}\n"
        f"🆔 UID: <code>{uid}</code>\n"
        f"💰 المبلغ: {amount:.2f} EGP\n"
        f"🏷️ النوع: {transfer_type}\n\n"
        "هل أنت متأكد؟",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )
    return ADMIN_SEND_MONEY_CONFIRM

async def admin_send_money_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "confirm_send":
        uid = context.user_data["target_uid"]
        amount = context.user_data["amount"]
        transfer_type = context.user_data["transfer_type"]

        users = load_data(USERS_FILE, {})
        users[uid]["balance"]["EGP"] += amount
        save_data(USERS_FILE, users)

        # إرسال إشعار للمستخدم
        try:
            await context.bot.send_message(
                chat_id=int(uid),
                text=f"🎉 <b>تهانينا!</b>\n\n"
                     f"تم إضافة <b>{amount:.2f} EGP</b> إلى رصيدك\n"
                     f"السبب: {transfer_type}\n\n"
                     f"من إدارة Asser Platform 💙",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"فشل في إرسال إشعار المستخدم: {e}")

        await query.edit_message_text(
            f"✅ <b>تم التحويل بنجاح!</b>\n\n"
            f"تم إضافة {amount:.2f} EGP للمستخدم {users[uid]['name']}",
            parse_mode=ParseMode.HTML
        )
        return ConversationHandler.END
    else:
        await admin_panel(update, context)
        return ADMIN_MAIN

# ─── معالجة موافقة/رفض الطلبات ────────────────────────────────────────────
async def handle_admin_approval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action, request_type, request_id = query.data.split("_", 2)

    if request_type == "deposit":
        deposits = load_data(PEND_DEP, [], ensure_list=True)
        try:
            request_index = int(request_id)
            if request_index >= len(deposits):
                await query.edit_message_text("❌ الطلب غير موجود!")
                return

            deposit_request = deposits[request_index]
            uid = deposit_request["uid"]
            amount = deposit_request["amount"]
            currency = deposit_request["currency"]

            users = load_data(USERS_FILE, {})

            if action == "approve":
                # إضافة المبلغ للرصيد
                users[uid]["balance"][currency] += amount
                save_data(USERS_FILE, users)

                # إشعار المستخدم
                try:
                    await context.bot.send_message(
                        chat_id=int(uid),
                        text=f"✅ <b>تم قبول إيداعك!</b>\n\n"
                             f"💰 تم إضافة {amount:.2f} {currency} إلى رصيدك\n\n"
                             f"💙 شكراً لثقتك في Asser Platform",
                        parse_mode=ParseMode.HTML
                    )
                except Exception as e:
                    logger.error(f"فشل في إرسال إشعار الموافقة: {e}")

                # حذف الطلب
                deposits.pop(request_index)
                save_data(PEND_DEP, deposits)

                await query.edit_message_text(f"✅ تم قبول الإيداع وإضافة {amount:.2f} {currency}")

            elif action == "reject":
                # إشعار المستخدم
                try:
                    await context.bot.send_message(
                        chat_id=int(uid),
                        text=f"❌ <b>تم رفض إيداعك</b>\n\n"
                             f"💵 المبلغ: {amount:.2f} {currency}\n"
                             f"📝 يرجى التأكد من البيانات والمحاولة مرة أخرى\n\n"
                             f"للاستفسار، تواصل مع الإدارة",
                        parse_mode=ParseMode.HTML
                    )
                except Exception as e:
                    logger.error(f"فشل في إرسال إشعار الرفض: {e}")

                # حذف الطلب
                deposits.pop(request_index)
                save_data(PEND_DEP, deposits)

                await query.edit_message_text(f"❌ تم رفض الإيداع")

        except (ValueError, IndexError):
            await query.edit_message_text("❌ خطأ في معالجة الطلب!")

    elif request_type == "withdrawal":
        withdrawals = load_data(PEND_WDR, [], ensure_list=True)
        try:
            request_index = int(request_id)
            if request_index >= len(withdrawals):
                await query.edit_message_text("❌ الطلب غير موجود!")
                return

            withdrawal_request = withdrawals[request_index]
            uid = withdrawal_request["uid"]
            amount = withdrawal_request["amount"]
            currency = withdrawal_request["currency"]

            users = load_data(USERS_FILE, {})

            if action == "approve":
                # إشعار المستخدم
                try:
                    await context.bot.send_message(
                        chat_id=int(uid),
                        text=f"✅ <b>تم قبول طلب السحب!</b>\n\n"
                             f"💰 المبلغ: {amount:.2f} {currency}\n"
                             f"📱 سيتم التحويل خلال 24 ساعة\n\n"
                             f"💙 شكراً لثقتك في Asser Platform",
                        parse_mode=ParseMode.HTML
                    )
                except Exception as e:
                    logger.error(f"فشل في إرسال إشعار الموافقة: {e}")

                # حذف الطلب
                withdrawals.pop(request_index)
                save_data(PEND_WDR, withdrawals)

                await query.edit_message_text(f"✅ تم قبول السحب {amount:.2f} {currency}")

            elif action == "reject":
                # إعادة المبلغ للرصيد
                original_amount = amount + withdrawal_request.get("fee", 0)
                users[uid]["balance"][currency] += original_amount
                save_data(USERS_FILE, users)

                # إشعار المستخدم
                try:
                    await context.bot.send_message(
                        chat_id=int(uid),
                        text=f"❌ <b>تم رفض طلب السحب</b>\n\n"
                             f"💵 المبلغ: {amount:.2f} {currency}\n"
                             f"💰 تم إعادة المبلغ إلى رصيدك\n"
                             f"📝 يرجى التأكد من البيانات والمحاولة مرة أخرى\n\n"
                             f"للاستفسار، تواصل مع الإدارة",
                        parse_mode=ParseMode.HTML
                    )
                except Exception as e:
                    logger.error(f"فشل في إرسال إشعار الرفض: {e}")

                # حذف الطلب
                withdrawals.pop(request_index)
                save_data(PEND_WDR, withdrawals)

                await query.edit_message_text(f"❌ تم رفض السحب وإعادة المبلغ")

        except (ValueError, IndexError):
            await query.edit_message_text("❌ خطأ في معالجة الطلب!")

    elif request_type == "assets":
        # معالجة سحب الأصول
        if action == "approve":
            await query.edit_message_text("✅ تم قبول طلب سحب الأصول! يرجى إضافة المبلغ يدوياً للمستخدم.")
        elif action == "reject":
            await query.edit_message_text("❌ تم رفض طلب سحب الأصول.")

# ─── باقي الدوال الأساسية ────────────────────────────────────────────
async def handle_main_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "profile":
        await show_profile(update, context)
    elif query.data == "balance":
        await show_balance(update, context)
    elif query.data == "work_sites":
        await show_work_sites(update, context)
    elif query.data == "back_to_main":
        await show_main_menu(update, context)
    elif query.data == "back_to_start":
        await back_to_start(update, context)
    elif query.data == "invest":
        await start_invest(update, context)
    elif query.data == "deposit":
        await start_deposit(update, context)
    elif query.data == "withdraw":
        await start_withdraw(update, context)
    elif query.data == "transfer":
        await start_transfer(update, context)
    elif query.data == "invite_friends":
        await show_invite_friends(update, context)
    elif query.data == "terms":
        await show_terms(update, context)
    elif query.data == "social_media":
        await show_social_media(update, context)
    elif query.data == "premium_info":
        await show_premium_info(update, context)
    elif query.data == "admin_panel":
        await admin_panel(update, context)

async def show_profile(update, context):
    uid = str(update.callback_query.from_user.id)
    users = load_data(USERS_FILE, {})

    if uid not in users:
        await update.callback_query.edit_message_text("❌ لست مسجَّلًا. استخدم /start أولًا.")
        return

    user = users[uid]
    terms_status = "نعم ✅" if user["accepted_terms"] else "لا ❌"
    terms_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(user["acceptance_time"])) if user["acceptance_time"] else "N/A"
    
    # تاريخ التسجيل في البوت
    registration_date = "غير محدد"
    if user.get("registration_date"):
        registration_date = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(user["registration_date"]))

    ban_status = ""
    if user.get("banned", False):
        ban_status = f"\n\n🚫 <b>حساب محظور!</b>\n"
        ban_status += f"السبب: {user.get('ban_reason', 'غير محدد')}\n"
        ban_status += f"الوقت: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(user.get('ban_time', 0)))}"

    active_plans = []
    now = time.time()

    for plan in user.get("plans", []):
        elapsed_days = (now - plan["join_date"]) / (24 * 3600)
        remaining_days = max(0, plan["duration"] - elapsed_days)

        plan_info = (
            f"  - {PLANS[plan['type']]['label']}: {plan['amount']:.2f} EGP\n"
            f"    المتبقي: {remaining_days:.1f} أيام\n"
            f"    آخر صرف: {time.strftime('%Y-%m-%d', time.localtime(plan.get('last_payout', plan['join_date'])))}"
        )
        active_plans.append(plan_info)

    plans_text = "\n".join(active_plans) if active_plans else "لا توجد شهادات نشطة"
    premium_status = "نعم 👑" if user.get("premium", False) else "لا"

    text = (
        f"👤 ملفّك الشخصي\n"
        f"الاسم: {user['name']}\n"
        f"الإيميل: {user['email']}\n"
        f"الهاتف: {user['phone']}\n"
        f"حساب مميز: {premium_status}\n"
        f"📅 تاريخ التسجيل في البوت: {registration_date}\n"
        f"موافقة على العقد: {terms_status}\n"
        f"وقت الموافقة: {terms_time}\n\n"
        f"🔰 فريقك:\n"
        f"  - عدد الأعضاء: {user.get('team_count', 0)}\n"
        f"  - كود الدعوة: {user.get('invite_code', '')}\n\n"
        f"الرصيد:\n"
        f"  - EGP: {user['balance']['EGP']:.2f}\n"
        f"  - USDT: {user['balance']['USDT']:.2f}\n\n"
        f"📈 الشهادات النشطة:\n{plans_text}"
        f"{ban_status}"
    )

    keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="back_to_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

async def show_balance(update, context):
    uid = str(update.callback_query.from_user.id)
    users = load_data(USERS_FILE, {})

    if uid not in users:
        await update.callback_query.edit_message_text("❌ لست مسجَّلًا. استخدم /start أولًا.")
        return

    bal = users[uid]["balance"]  
    text = (  
        f"💰 أرصدتك الحالية:\n"  
        f"  - EGP: {bal['EGP']:.2f}\n"  
        f"  - USDT: {bal['USDT']:.2f}"  
    )

    keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="back_to_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.callback_query.edit_message_text(text, reply_markup=reply_markup)

async def show_invite_friends(update, context):
    uid = str(update.callback_query.from_user.id)
    users = load_data(USERS_FILE, {})

    if uid not in users:
        await update.callback_query.edit_message_text("❌ لست مسجَّلًا. استخدم /start أولًا.")
        return

    user = users[uid]
    bot_username = context.bot.username
    invite_link = f"https://t.me/{bot_username}?start=invite_{uid}"

    message = (
        "🔰 <b>دعوة الأصدقاء</b>\n\n"
        f"👥 عدد الأعضاء في فريقك: <b>{user.get('team_count', 0)}</b>\n"
        f"🔑 كود الدعوة: <code>{user.get('invite_code', '')}</code>\n"
        f"📥 رابط الدعوة: <code>{invite_link}</code>\n\n"
        "كلما دخل عضو جديد عن طريق الرابط، يزداد عدد فريقك!"
    )

    keyboard = [
        [InlineKeyboardButton("💡 كيفية الربح من دعوة الأصدقاء", callback_data="referral_earnings")],
        [InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.callback_query.edit_message_text(
        text=message,
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

async def show_referral_earnings(update, context):
    message = (
        "💡 <b>كيفية الربح من دعوة الأصدقاء</b>\n\n"
        "🎯 <b>من العمل على المواقع:</b>\n"
        "عن طريق العمل على المواقع من أعضاء فريقك ستحصل أنت على 20% إحالة\n\n"
        "📈 <b>من التقديم على الشهادات:</b>\n"
        "على التقديم على شهادة ستحصل على 10% من أرباح صديقك\n\n"
        "⚠️ <b>ملاحظة مهمة:</b>\n"
        "المبلغ الذي صديقك قام بإيداعه لا يتم خصم أي شيء منه، هو للعمل فقط ولا يخص ذلك\n\n"
        "💰 <b>مثال:</b>\n"
        "إذا قام صديقك بربح شهرياً 1000 EGP ستحصل على 200 EGP"
    )

    keyboard = [
        [InlineKeyboardButton("🔙 العودة لدعوة الأصدقاء", callback_data="invite_friends")],
        [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.callback_query.edit_message_text(
        message, 
        reply_markup=reply_markup, 
        parse_mode=ParseMode.HTML
    )

async def show_terms(update, context):
    for i in range(0, len(CONTRACT_TEXT), 4096):
        part = CONTRACT_TEXT[i:i+4096]
        await update.callback_query.message.reply_text(part)
        time.sleep(0.5)

    keyboard = [
        [InlineKeyboardButton("موافــــق ✅", callback_data="accept_terms")],
        [InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.callback_query.message.reply_text(
        "إذا كنت موافقًا اضغط الزر:", 
        reply_markup=reply_markup
    )

async def accept_terms(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(query.from_user.id)
    users = load_data(USERS_FILE, {})

    if uid in users:
        users[uid]["accepted_terms"] = True
        users[uid]["acceptance_time"] = int(time.time())
        save_data(USERS_FILE, users)
        await query.edit_message_text("✅ تم التوقيع على العقد.")
    else:
        await query.edit_message_text("❌ يجب التسجيل أولاً!")

async def show_social_media(update, context):
    message = (
        "📱 <b>تابعنا على مواقع التواصل الاجتماعي</b>\n\n"
        "اختر المنصة التي تريد زيارتها:"
    )

    keyboard = [
        [InlineKeyboardButton("📱 Telegram", url="https://t.me/Asser_Platform")],
        [InlineKeyboardButton("🎥 YouTube", url="https://www.youtube.com/@Asser-Platform")],
        [InlineKeyboardButton("🎵 TikTok", url="https://tiktok.com/@asser_platform")],
        [InlineKeyboardButton("📷 Instagram", callback_data="instagram_soon")],
        [InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.callback_query.edit_message_text(
        message, 
        reply_markup=reply_markup, 
        parse_mode=ParseMode.HTML
    )

async def instagram_soon(update, context):
    await update.callback_query.answer("قريباً...")

async def show_premium_info(update, context):
    message = (
        "👑 <b>كيف تصبح حساب مميز؟</b>\n\n"
        "🌟 <b>مميزات العميل المميز/الحساب المميز:</b>\n\n"
        "📋 شهادة مخصصة مع عائد أكبر من الطبيعي (وثابت) لا يقل العائد المتفق عليه\n"
        "📄 يتم كتابة عقد ينص على ذلك\n"
        "💬 خدمة عملاء عبر WhatsApp مخصصة للعملاء المميزين فقط\n"
        "📞 إمكانية طلب دعم مباشر عبر مكالمة هاتفية\n"
        "⏰ أولوية في السحب وتحويل الأرباح\n"
        "🔗 إنشاء حملات إحالة خاصة برابط مخصص\n\n"
        "📋 <b>المتطلبات (سيتم تغييرها قريباً):</b>\n\n"
        "📅 حسابك يكون مدته أكثر من 40 يوم\n"
        "💰 حسابك تتعدى قيمته 5000 EGP\n"
        "✅ تفعيل البريد الإلكتروني ورقم الهاتف\n"
        "⚖️ ألا يكون قد خالف شروط الاستخدام أو تم الإبلاغ عنه"
    )

    keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="back_to_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.callback_query.edit_message_text(
        message, 
        reply_markup=reply_markup, 
        parse_mode=ParseMode.HTML
    )

# دوال الاستثمار المحسنة
async def start_invest(update, context):
    uid = str(update.callback_query.from_user.id)
    
    # فحص الحظر
    if await check_user_ban(uid, update, context):
        return ConversationHandler.END

    keyboard = [
        [InlineKeyboardButton("يومي (5% شهريًا)", callback_data="daily")],
        [InlineKeyboardButton("أسبوعي (6% شهريًا)", callback_data="weekly")],
        [InlineKeyboardButton("شهري (10% شهريًا)", callback_data="monthly")],
        [InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.callback_query.edit_message_text(
        "📊 اختر نوع الشهادة:",
        reply_markup=reply_markup
    )
    return PLAN_CHOOSE

async def plan_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "back_to_main":
        await show_main_menu(update, context)
        return ConversationHandler.END

    plan_type = query.data
    context.user_data["plan_type"] = plan_type

    plan = PLANS[plan_type]
    daily_profit = plan.get("daily_profit", 0)
    weekly_profit = plan.get("weekly_profit", 0)
    monthly_profit = plan["monthly_profit"]

    message = (
        f"📈 شهادة {plan['label']}:\n"
        f"  - المدة: {plan['duration']} يوم\n"
        f"  - العائد الشهري: {monthly_profit}%\n"
    )

    if plan_type == "daily":
        message += f"  - العائد اليومي: {daily_profit:.4f}%\n"
        message += f"  - الدفع: كل 24 ساعة\n"
    elif plan_type == "weekly":
        message += f"  - العائد الأسبوعي: {weekly_profit}%\n"
        message += f"  - الدفع: كل 7 أيام\n"
    else:
        message += f"  - الدفع: كل 30 يوم\n"

    message += "\n💵 الرجاء إدخال المبلغ الذي تريد استثماره (EGP):"

    await query.edit_message_text(message)
    return PLAN_AMOUNT

async def plan_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    users = load_data(USERS_FILE, {})

    if uid not in users:
        await update.message.reply_text("❌ لست مسجلًا. استخدم /start أولًا.")
        return ConversationHandler.END

    try:
        amount = float(update.message.text.strip())
        if amount <= 0:
            raise ValueError
    except Exception:
        await update.message.reply_text("❌ أدخل رقمًا صحيحًا أكبر من صفر.")
        return PLAN_AMOUNT

    if users[uid]["balance"]["EGP"] < amount:
        await update.message.reply_text("❌ رصيد EGP غير كافٍ.")
        return ConversationHandler.END

    plan_type = context.user_data["plan_type"]
    plan = PLANS[plan_type]

    new_plan = {
        "type": plan_type,
        "amount": amount,
        "join_date": int(time.time()),
        "duration": plan["duration"],
        "last_payout": int(time.time())
    }

    users[uid]["balance"]["EGP"] -= amount

    if "plans" not in users[uid]:
        users[uid]["plans"] = []
    users[uid]["plans"].append(new_plan)

    save_data(USERS_FILE, users)

    # حساب الجدول الزمني للدفع
    payout_schedule = ""
    if plan_type == "daily":
        payout_schedule = "كل 24 ساعة"
    elif plan_type == "weekly":
        payout_schedule = "كل 7 أيام"
    else:
        payout_schedule = "كل 30 يوم"

    success_message = (
        f"🎉 <b>مبروك! تم شراء شهادة {plan['label']} بنجاح!</b>\n\n"
        f"💰 المبلغ المستثمر: <b>{amount:.2f} EGP</b>\n"
        f"📈 العائد المتوقع: <b>{plan['monthly_profit']}% شهرياً</b>\n"
        f"⏰ مدة الاستثمار: <b>{plan['duration']} يوم</b>\n"
        f"💳 جدولة الدفع: <b>{payout_schedule}</b>\n\n"
        f"🌟 <b>نهنئك على اتخاذ هذه الخطوة الذكية!</b>\n"
        f"ستبدأ أرباحك في التراكم تلقائياً وفقاً لجدول الدفع المحدد.\n\n"
        f"💙 شكراً لثقتك في Asser Platform"
    )

    await update.message.reply_text(success_message, parse_mode=ParseMode.HTML)
    return ConversationHandler.END

# ─── تحويل الأموال المحسن ────────────────────────────────────────────
async def start_transfer(update, context):
    uid = str(update.callback_query.from_user.id)
    
    # فحص الحظر
    if await check_user_ban(uid, update, context):
        return ConversationHandler.END

    keyboard = [
        [InlineKeyboardButton("تحويل عملات 💱", callback_data="convert")],
        [InlineKeyboardButton("تحويل بين المستخدمين 👤", callback_data="user_transfer")],
        [InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.callback_query.edit_message_text(
        "📤 <b>تحويل الأموال</b>\n\n"
        "اختر نوع التحويل:",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )
    return TRANSFER_TYPE

async def transfer_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "back_to_main":
        await show_main_menu(update, context)
        return ConversationHandler.END
    elif query.data == "convert":
        await query.edit_message_text("💱 تحويل العملات قريباً...")
        return ConversationHandler.END
    elif query.data == "user_transfer":
        await query.edit_message_text(
            "👤 <b>تحويل بين المستخدمين</b>\n\n"
            "أدخل UID المستخدم المراد التحويل إليه:",
            parse_mode=ParseMode.HTML
        )
        return TRANSFER_USER_TARGET

async def transfer_user_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_uid = update.message.text.strip()
    users = load_data(USERS_FILE, {})

    if target_uid not in users:
        await update.message.reply_text("❌ المستخدم غير موجود!")
        return TRANSFER_USER_TARGET

    sender_uid = str(update.effective_user.id)
    if target_uid == sender_uid:
        await update.message.reply_text("❌ لا يمكنك التحويل لنفسك!")
        return TRANSFER_USER_TARGET

    context.user_data["target_uid"] = target_uid
    target_user = users[target_uid]

    await update.message.reply_text(
        f"👤 <b>بيانات المستخدم المحول إليه:</b>\n\n"
        f"📋 الاسم الكامل: {target_user['name']}\n"
        f"🆔 UID المستخدم: <code>{target_uid}</code>\n\n"
        f"💵 أدخل المبلغ المراد تحويله (EGP):",
        parse_mode=ParseMode.HTML
    )
    return TRANSFER_USER_AMOUNT

async def transfer_user_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text.strip())
        if amount <= 0:
            raise ValueError
    except Exception:
        await update.message.reply_text("❌ أدخل مبلغاً صحيحاً!")
        return TRANSFER_USER_AMOUNT

    sender_uid = str(update.effective_user.id)
    target_uid = context.user_data["target_uid"]
    users = load_data(USERS_FILE, {})

    if users[sender_uid]["balance"]["EGP"] < amount:
        await update.message.reply_text("❌ رصيدك غير كافٍ!")
        return ConversationHandler.END

    # تحويل المبلغ
    users[sender_uid]["balance"]["EGP"] -= amount
    users[target_uid]["balance"]["EGP"] += amount
    save_data(USERS_FILE, users)

    # إشعار المرسل
    await update.message.reply_text(
        f"✅ <b>تم التحويل بنجاح!</b>\n\n"
        f"💰 المبلغ: {amount:.2f} EGP\n"
        f"👤 إلى: {users[target_uid]['name']}\n"
        f"🆔 UID: {target_uid}",
        parse_mode=ParseMode.HTML
    )

    # إشعار المستقبل
    try:
        await context.bot.send_message(
            chat_id=int(target_uid),
            text=f"💰 <b>تم استلام تحويل!</b>\n\n"
                 f"💵 المبلغ: {amount:.2f} EGP\n"
                 f"👤 من: {users[sender_uid]['name']}\n"
                 f"🆔 UID المرسل: {sender_uid}\n\n"
                 f"💙 شكراً لاستخدام Asser Platform",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"فشل في إرسال إشعار المستقبل: {e}")

    return ConversationHandler.END

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # معالج المحادثات للتسجيل
    auth_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(handle_start_buttons, pattern="^(new_register|login|data_storage_info)$")
        ],
        states={
            REG_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_name)],
            REG_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_email)],
            REG_PASS: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_pass)],
            REG_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_phone)],
            LOGIN_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, login_email)],
            LOGIN_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, login_password)]
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
        per_message=False
    )

    # معالج الودائع
    dep_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_deposit, pattern="deposit")],
        states={
            DEP_CURR: [CallbackQueryHandler(dep_curr)],
            DEP_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, dep_name)],
            DEP_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, dep_phone)],
            DEP_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, dep_amount)],
            DEP_METHOD: [CallbackQueryHandler(dep_method)],
            DEP_SCREENSHOT: [MessageHandler(filters.PHOTO, dep_screenshot)]
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
        per_message=False
    )

    # معالج سحب الأصول
    assets_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_assets_withdrawal, pattern="assets_withdrawal")],
        states={
            DEP_SCREENSHOT: [MessageHandler(filters.PHOTO, dep_screenshot)]
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
        per_message=False
    )

    # معالج السحب
    wdr_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_withdraw, pattern="withdraw")],
        states={
            WDR_CURR: [CallbackQueryHandler(wdr_curr)],
            WDR_METHOD: [CallbackQueryHandler(wdr_method)],
            WDR_AMT: [MessageHandler(filters.TEXT & ~filters.COMMAND, wdr_amt)]
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
        per_message=False
    )

    # معالج التحويلات المحسن
    transfer_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_transfer, pattern="transfer")],
        states={
            TRANSFER_TYPE: [CallbackQueryHandler(transfer_type)],
            TRANSFER_USER_TARGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, transfer_user_target)],
            TRANSFER_USER_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, transfer_user_amount)]
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
        per_message=False
    )

    # معالج الاستثمار
    invest_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_invest, pattern="invest")],
        states={
            PLAN_CHOOSE: [CallbackQueryHandler(plan_chosen)],
            PLAN_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, plan_amount)]
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
        per_message=False
    )

    # معالج لوحة الأدمن المحسن
    admin_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_panel, pattern="admin_panel")],
        states={
            ADMIN_MAIN: [
                CallbackQueryHandler(admin_send_money, pattern="admin_send_money"),
                CallbackQueryHandler(admin_special_deposit, pattern="admin_special_deposit"),
                CallbackQueryHandler(admin_ban, pattern="admin_ban"),
                CallbackQueryHandler(admin_edit, pattern="admin_edit"),
                CallbackQueryHandler(admin_search, pattern="admin_search"),
                CallbackQueryHandler(admin_stats, pattern="admin_stats"),
                CallbackQueryHandler(admin_requests, pattern="admin_requests"),
                CallbackQueryHandler(admin_premium, pattern="admin_premium"),
                CallbackQueryHandler(admin_broadcast, pattern="admin_broadcast")
            ],
            ADMIN_PREMIUM: [CallbackQueryHandler(admin_premium_action, pattern="^(grant_premium|revoke_premium|admin_panel)$")],
            ADMIN_PREMIUM_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_premium_user)],
            ADMIN_BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_broadcast_send)],
            ADMIN_SEARCH_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_search_input)],
            ADMIN_EDIT_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_edit_user)],
            ADMIN_EDIT_FIELD: [CallbackQueryHandler(admin_edit_field, pattern="^edit_(EGP|USDT)$")],
            ADMIN_EDIT_BALANCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_edit_balance)],
            ADMIN_BAN_USER: [
                CallbackQueryHandler(ban_user_start, pattern="^(ban_user|unban_user|admin_panel)$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_ban_user)
            ],
            ADMIN_BAN_REASON: [CallbackQueryHandler(admin_ban_reason, pattern="^(fraud|contract_pending|custom_reason)$")],
            ADMIN_CUSTOM_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_custom_ban_reason)],
            ADMIN_SEND_MONEY_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_send_money_user)],
            ADMIN_SEND_MONEY_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_send_money_amount)],
            ADMIN_SEND_MONEY_TYPE: [CallbackQueryHandler(admin_send_money_type, pattern="^(reward|compensation|gift|deposit_transfer|assets_withdrawal_transfer)$")],
            ADMIN_SEND_MONEY_CONFIRM: [CallbackQueryHandler(admin_send_money_confirm, pattern="^(confirm_send|admin_panel)$")]
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
        per_message=False
    )

    # إضافة المعالجات
    app.add_handler(auth_handler)
    app.add_handler(dep_handler)
    app.add_handler(assets_handler)
    app.add_handler(wdr_handler)
    app.add_handler(transfer_handler)
    app.add_handler(invest_handler)
    app.add_handler(admin_handler)

    # معالجات الأزرار
    app.add_handler(CallbackQueryHandler(handle_main_buttons, pattern="^(profile|balance|work_sites|back_to_main|back_to_start|invest|deposit|withdraw|transfer|invite_friends|terms|social_media|premium_info|admin_panel)$"))
    app.add_handler(CallbackQueryHandler(show_how_to_work, pattern="how_to_work"))
    app.add_handler(CallbackQueryHandler(accept_terms, pattern="accept_terms"))
    app.add_handler(CallbackQueryHandler(show_referral_earnings, pattern="referral_earnings"))
    app.add_handler(CallbackQueryHandler(instagram_soon, pattern="instagram_soon"))
    
    # معالجات موافقة/رفض الطلبات
    app.add_handler(CallbackQueryHandler(handle_admin_approval, pattern="^(approve|reject)_(deposit|withdrawal|assets)_"))

    print("🚀 Bot started successfully with all features!")
    app.run_polling()

if __name__ == '__main__':
    main()
