import logging
from datetime import datetime, timedelta
from aiogram import Router, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

from config import MONGO_URL, ADMINS, TIMEZONE

router = Router()
cluster = AsyncIOMotorClient(MONGO_URL)
db = cluster["avto_post_db"]

# ==================== MENYULAR ====================
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📥 Post yuklash")],
        [KeyboardButton(text="📅 Reja"), KeyboardButton(text="📊 Statistika")],
        [KeyboardButton(text="⚙️ Sozlamalar"), KeyboardButton(text="🚀 PRO Versiya")]
    ],
    resize_keyboard=True
)

time_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Hozir (+1 min)"), KeyboardButton(text="Hozir (+5 min)")],
        [KeyboardButton(text="09:00"), KeyboardButton(text="12:00"), KeyboardButton(text="15:00")],
        [KeyboardButton(text="18:00"), KeyboardButton(text="21:00"), KeyboardButton(text="23:00")],
        [KeyboardButton(text="Bekor qilish")]
    ],
    resize_keyboard=True
)

# ==================== HOLATLAR (STATES) ====================
class PostState(StatesGroup):
    waiting_for_post = State()
    waiting_for_channel = State()
    waiting_for_time = State()

class SettingsState(StatesGroup):
    waiting_for_ch_name = State()
    waiting_for_ch_id = State()
    waiting_for_admin_id = State()

MENU_BUTTONS = ["📥 Post yuklash", "📅 Reja", "⚙️ Sozlamalar", "📊 Statistika", "🚀 PRO Versiya", "Bekor qilish", "/start"]

# ==================== YORDAMCHI FUNKSIYALAR ====================
async def is_admin(user_id):
    if user_id in ADMINS: return True
    doc = await db.admins.find_one({"user_id": user_id})
    return bool(doc)

# ==================== START VA REKLAMA ====================
@router.message(F.text == "/start")
async def start_cmd(message: types.Message, state: FSMContext):
    await state.clear()
    if not await is_admin(message.from_user.id):
        reklama_matni = (
            "👋 Assalomu alaykum!\n\n"
            "🤖 Bu bot Telegram kanallarga xabarlarni avtomatik joylash uchun mo'ljallangan.\n\n"
            "💎 **Shaxsiy Avto-Post botga ega bo'lishni xohlaysizmi?**\n"
            "Kanallaringizni avtomatlashtiring, vaqtni tejang va ishingizni osonlashtiring!\n\n"
            "Batafsil ma'lumot va bot xarid qilish uchun adminga yozing."
        )
        await message.answer(reklama_matni)
        return
    await message.answer("👋 Assalomu alaykum, Admin!\nSiz botning **Basic** versiyasidasiz. Nima qilamiz?", reply_markup=main_menu)

@router.message(F.text == "🚀 PRO Versiya")
async def pro_ad(message: types.Message):
    if not await is_admin(message.from_user.id): return
    text = (
        "🚀 **PRO Versiya Afzalliklari:**\n\n"
        "✅ Birdaniga yuzlab postlarni oson rejalashtirish;\n"
        "✅ Postlarga chiroyli ssilka tugmalari qo'shish;\n"
        "✅ Rasmlarga avtomatik Watermark (Suv belgisi) yozish;\n"
        "✅ Kanallar va postlar sonida umuman cheklov yo'q;\n"
        "✅ Interval taymer (har X minutda avtomatik post tashlash).\n\n"
        "Tarifni yangilash uchun adminga yozing."
    )
    await message.answer(text)

# ==================== STATISTIKA ====================
@router.message(F.text == "📊 Statistika")
async def show_stats(message: types.Message):
    if not await is_admin(message.from_user.id): return
    channels = await db.channels.find().to_list(length=100)
    pending_total = await db.posts.count_documents({"status": "pending"})
    sent_total = await db.posts.count_documents({"status": "sent"})
    
    text = f"📊 **Umumiy Statistika:**\n\n📢 Kanallar: **{len(channels)} ta**\n⏳ Kutmoqda: **{pending_total} ta**\n✅ Yuborildi: **{sent_total} ta**\n\n📈 **Kanallar kesimida:**\n\n"
    if not channels:
        text += "Hozircha kanallar ulanmagan."
    for ch in channels:
        p = await db.posts.count_documents({"status": "pending", "target": ch['channel_id']})
        s = await db.posts.count_documents({"status": "sent", "target": ch['channel_id']})
        text += f"🔹 {ch['channel_name']}\n   ⏳ Kutmoqda: {p} | ✅ Yuborildi: {s}\n\n"
    await message.answer(text)

# ==================== SOZLAMALAR (Kanallar va Adminlar) ====================
@router.message(F.text == "⚙️ Sozlamalar")
async def settings_menu(message: types.Message, state: FSMContext):
    if not await is_admin(message.from_user.id): return
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Kanallar", callback_data="set_channels"), InlineKeyboardButton(text="👥 Adminlar", callback_data="set_admins")]
    ])
    await message.answer("⚙️ **Sozlamalar bo'limi:**", reply_markup=kb)

# --- Adminlar ---
@router.callback_query(F.data == "set_admins")
async def set_admins(call: types.CallbackQuery):
    admins_db = await db.admins.find().to_list(length=100)
    text = "👥 **Qo'shimcha Adminlar:**\n"
    if not admins_db: text += "Hozircha faqat Asosiy Admin bor.\n"
    for a in admins_db: text += f"🔸 ID: `{a['user_id']}`\n"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Admin qo'shish", callback_data="add_admin"), InlineKeyboardButton(text="➖ O'chirish", callback_data="del_admin_list")]
    ])
    await call.message.edit_text(text, reply_markup=kb)

@router.callback_query(F.data == "add_admin")
async def add_admin(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("Yangi adminning Telegram ID raqamini yuboring:")
    await state.set_state(SettingsState.waiting_for_admin_id)

@router.message(SettingsState.waiting_for_admin_id)
async def save_admin(msg: types.Message, state: FSMContext):
    if msg.text in MENU_BUTTONS: await state.clear(); return
    try:
        await db.admins.insert_one({"user_id": int(msg.text.strip())})
        await msg.answer("✅ Admin muvaffaqiyatli qo'shildi!")
        await state.clear()
    except:
        await msg.answer("❌ Noto'g'ri ID format!")

@router.callback_query(F.data == "del_admin_list")
async def del_admin_list(call: types.CallbackQuery):
    admins_db = await db.admins.find().to_list(length=100)
    if not admins_db:
        await call.answer("O'chirish uchun admin yo'q!", show_alert=True)
        return
    kb = [[InlineKeyboardButton(text=f"❌ ID: {a['user_id']}", callback_data=f"deladm_{a['user_id']}")] for a in admins_db]
    await call.message.edit_text("O'chirmoqchi bo'lgan adminni tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@router.callback_query(F.data.startswith("deladm_"))
async def del_adm(call: types.CallbackQuery):
    aid = int(call.data.split("_")[1])
    await db.admins.delete_one({"user_id": aid})
    await call.answer("✅ Admin o'chirildi!", show_alert=True)
    await set_admins(call)

# --- Kanallar ---
@router.callback_query(F.data == "set_channels")
async def set_channels(call: types.CallbackQuery):
    channels = await db.channels.find().to_list(length=100)
    text = "📢 **Sizning kanallaringiz:**\n"
    if not channels: text += "Hozircha yo'q.\n"
    for c in channels: text += f"🔹 {c['channel_name']} ({c['channel_id']})\n"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="add_ch"), InlineKeyboardButton(text="➖ O'chirish", callback_data="del_ch_list")]
    ])
    await call.message.edit_text(text, reply_markup=kb)

@router.callback_query(F.data == "add_ch")
async def add_ch_start(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("Kanal nomini yozing (Masalan: Asosiy kanal):")
    await state.set_state(SettingsState.waiting_for_ch_name)

@router.message(SettingsState.waiting_for_ch_name)
async def add_ch_name(msg: types.Message, state: FSMContext):
    if msg.text in MENU_BUTTONS: await state.clear(); return
    await state.update_data(name=msg.text)
    await msg.answer("Kanal ID'sini (-100...) yoki Usernameni (@kanal_nomi) yuboring:")
    await state.set_state(SettingsState.waiting_for_ch_id)

@router.message(SettingsState.waiting_for_ch_id)
async def add_ch_id(msg: types.Message, state: FSMContext):
    if msg.text in MENU_BUTTONS: await state.clear(); return
    if not (msg.text.startswith("-100") or msg.text.startswith("@")):
        await msg.answer("❌ Xato! Kanal ID doim '-100' yoki username '@' bilan boshlanishi kerak. Qaytadan yozing:")
        return 
    data = await state.get_data()
    await db.channels.insert_one({"channel_name": data['name'], "channel_id": msg.text.strip()})
    await msg.answer(f"✅ Kanal '{data['name']}' muvaffaqiyatli saqlandi!")
    await state.clear()

@router.callback_query(F.data == "del_ch_list")
async def del_ch_list(call: types.CallbackQuery):
    channels = await db.channels.find().to_list(length=100)
    if not channels:
        await call.answer("O'chirish uchun kanal yo'q!", show_alert=True)
        return
    kb = [[InlineKeyboardButton(text=f"❌ {c['channel_name']}", callback_data=f"delch_{c['_id']}")] for c in channels]
    await call.message.edit_text("O'chirmoqchi bo'lgan kanalni tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@router.callback_query(F.data.startswith("delch_"))
async def del_ch(call: types.CallbackQuery):
    cid = call.data.split("_")[1]
    await db.channels.delete_one({"_id": ObjectId(cid)})
    await call.answer("✅ Kanal o'chirildi!", show_alert=True)
    await set_channels(call)

# ==================== REJA (KUTISH ZALI) ====================
@router.message(F.text == "📅 Reja")
async def show_schedule(message: types.Message):
    if not await is_admin(message.from_user.id): return
    posts = await db.posts.find({"status": "pending"}).sort("time", 1).to_list(length=20)
    if not posts:
        await message.answer("Hozircha navbatda postlar yo'q.")
        return
    text = "📅 **Yaqin xabarlar rejasini:**\n\n"
    for i, p in enumerate(posts, 1):
        dt = datetime.fromisoformat(p['time'])
        text += f"{i}. ⏰ {dt.strftime('%m-%d %H:%M')} | Kanal: `{p['target']}`\n"
        btn = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"delpost_{p['_id']}")]])
        await message.answer(text if i==1 else f"Post #{i} ({dt.strftime('%H:%M')})", reply_markup=btn)

@router.callback_query(F.data.startswith("delpost_"))
async def delete_post(call: types.CallbackQuery):
    pid = call.data.split("_")[1]
    await db.posts.delete_one({"_id": ObjectId(pid)})
    await call.message.delete()
    await call.answer("✅ Post o'chirildi.")

# ==================== POST YUKLASH TIZIMI ====================
@router.message(F.text == "📥 Post yuklash")
async def post_start(message: types.Message, state: FSMContext):
    if not await is_admin(message.from_user.id): return
    await state.clear()
    await message.answer("Postni yuboring (rasm/video/matn):", reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Bekor qilish")]], resize_keyboard=True))
    await state.set_state(PostState.waiting_for_post)

@router.message(PostState.waiting_for_post)
async def post_get(message: types.Message, state: FSMContext):
    if message.text in MENU_BUTTONS:
        await message.answer("Jarayon bekor qilindi.", reply_markup=main_menu); await state.clear(); return
        
    await state.update_data(msg_id=message.message_id, chat_id=message.chat.id)
    channels = await db.channels.find().to_list(length=100)
    
    if not channels:
        await message.answer("❌ Kanallar yo'q! Sozlamalardan kanal qo'shing.", reply_markup=main_menu)
        await state.clear()
        return
        
    builder = [[InlineKeyboardButton(text=c['channel_name'], callback_data=f"ch_{c['channel_id']}")] for c in channels]
    await message.answer("Qaysi kanalga joylaymiz?", reply_markup=InlineKeyboardMarkup(inline_keyboard=builder))
    await state.set_state(PostState.waiting_for_channel)

@router.callback_query(PostState.waiting_for_channel, F.data.startswith("ch_"))
async def ch_select(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(target=callback.data.split("ch_")[1])
    await callback.message.delete()
    
    await callback.message.answer(
        "⏰ **Vaqtni tanlang yoki qo'lda yozing:** ",
        reply_markup=time_menu
    )
    await state.set_state(PostState.waiting_for_time)

@router.message(PostState.waiting_for_time)
async def save_post_time(message: types.Message, state: FSMContext):
    if message.text in MENU_BUTTONS:
        await message.answer("Bekor qilindi.", reply_markup=main_menu); await state.clear(); return
        
    data = await state.get_data()
    t_str = message.text.strip()
    now = datetime.now(TIMEZONE)
    final_dt = None
    
    try:
        # 1. Tezkor test tugmalari
        if t_str == "Hozir (+1 min)":
            final_dt = now + timedelta(minutes=1)
        elif t_str == "Hozir (+5 min)":
            final_dt = now + timedelta(minutes=5)
            
        # 2. Qo'lda soat yozish yoki tayyor soat tugmalari (Masalan: "15:00" yoki "08:00")
        elif len(t_str) <= 5: 
            parsed_dt = datetime.strptime(f"{now.strftime('%m-%d')} {t_str}", "%m-%d %H:%M")
            if parsed_dt.time() <= now.time():
                parsed_dt += timedelta(days=1)
            final_dt = TIMEZONE.localize(parsed_dt.replace(year=now.year))
            
        # 3. Aniq sana va soat bilan yozish (Masalan: "04-15 15:00")
        else:
            parsed_date = datetime.strptime(t_str.replace(".", "-"), "%m-%d %H:%M")
            target = now.replace(month=parsed_date.month, day=parsed_date.day, hour=parsed_date.hour, minute=parsed_date.minute, second=0, microsecond=0)
            if target < now - timedelta(days=1): 
                target = target.replace(year=now.year + 1)
            final_dt = TIMEZONE.localize(target.replace(tzinfo=None)) if target.tzinfo is None else target

        # Bazaga saqlash
        await db.posts.insert_one({
            "message_id": data['msg_id'], "from_chat_id": data['chat_id'],
            "target": data['target'], "time": final_dt.isoformat(),
            "status": "pending", "is_pro": False
        })
        
        await message.answer(f"✅ **Post saqlandi!**\nKanal: {data['target']}\nVaqti: {final_dt.strftime('%d-%m-%Y %H:%M')}", reply_markup=main_menu)
        await state.clear()
        
    except Exception as e:
        await message.answer("❌ Noto'g'ri vaqt! Iltimos, tugmalardan birini bosing yoki `15:00` deb yozing.")
