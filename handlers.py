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

# Asosiy menyu (Statistika va Pro qo'shilgan)
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📥 Post yuklash")],
        [KeyboardButton(text="📅 Reja"), KeyboardButton(text="⚙️ Kanallar")],
        [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="🚀 PRO Versiya")]
    ],
    resize_keyboard=True
)

# Vaqt tanlash uchun maxsus tayyor tugmalar (Avto vaqt)
time_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Bugun 09:00"), KeyboardButton(text="Bugun 13:00")],
        [KeyboardButton(text="Bugun 18:00"), KeyboardButton(text="Bugun 21:00")],
        [KeyboardButton(text="Ertaga 09:00"), KeyboardButton(text="Ertaga 18:00")],
        [KeyboardButton(text="Bekor qilish")]
    ],
    resize_keyboard=True
)

class PostState(StatesGroup):
    waiting_for_post = State()
    waiting_for_channel = State()
    waiting_for_time = State()

class ChannelState(StatesGroup):
    waiting_for_name = State()
    waiting_for_id = State()

# Menyudagi tugmalar ro'yxati (Bekor qilish tizimi uchun)
MENU_BUTTONS = ["📥 Post yuklash", "📅 Reja", "⚙️ Kanallar", "📊 Statistika", "🚀 PRO Versiya", "Bekor qilish", "/start"]

# ==================== START VA REKLAMA ====================
@router.message(F.text == "/start")
async def start_cmd(message: types.Message, state: FSMContext):
    await state.clear()
    
    # Agar oddiy odam (admin bo'lmagan) kirsatsa:
    if message.from_user.id not in ADMINS:
        reklama_matni = (
            "👋 Assalomu alaykum!\n\n"
            "🤖 Bu bot Telegram kanallarga xabarlarni avtomatik joylash uchun mo'ljallangan.\n\n"
            "💎 **Shaxsiy Avto-Post botga ega bo'lishni xohlaysizmi?**\n"
            "Kanallaringizni avtomatlashtiring, vaqtni tejang va ishingizni osonlashtiring!\n\n"
            "Batafsil ma'lumot va bot xarid qilish uchun adminga yozing: @SizningUsername"
        )
        await message.answer(reklama_matni)
        return

    # Agar admin kirsatsa:
    await message.answer(
        "👋 Assalomu alaykum, Admin!\n\n"
        "Siz botning **Basic (Test)** versiyasidan foydalanyapsiz.\n"
        "Menyudan kerakli bo'limni tanlang:", 
        reply_markup=main_menu
    )

# ==================== PRO REKLAMASI ====================
@router.message(F.text == "🚀 PRO Versiya")
async def pro_ad(message: types.Message):
    if message.from_user.id not in ADMINS: return
    text = (
        "🚀 **PRO Versiya Afzalliklari:**\n\n"
        "✅ Birdaniga yuzlab postlarni vergul orqali oson rejalashtirish;\n"
        "✅ Har bir post tagiga chiroyli ssilka tugmalari qo'shish;\n"
        "✅ Rasmlarga avtomatik Watermark (Suv belgisi) yozish;\n"
        "✅ Kanallar va postlar sonida umuman cheklov yo'q;\n"
        "✅ Interval taymer (har X minutda avtomatik post tashlash).\n\n"
        "Tarifni yangilash uchun adminga yozing: @SizningUsername"
    )
    await message.answer(text)

# ==================== STATISTIKA ====================
@router.message(F.text == "📊 Statistika")
async def show_stats(message: types.Message):
    if message.from_user.id not in ADMINS: return
    
    # Bazadan shu adminga tegishli ma'lumotlarni sanaymiz
    channels_count = await db.channels.count_documents({})
    pending_posts = await db.posts.count_documents({"status": "pending"})
    sent_posts = await db.posts.count_documents({"status": "sent"})
    
    text = (
        "📊 **Sizning botingiz statistikasi:**\n\n"
        f"📢 Ulangan kanallar: **{channels_count} ta**\n"
        f"⏳ Navbatdagi postlar: **{pending_posts} ta**\n"
        f"✅ Muvaffaqiyatli yuborilganlar: **{sent_posts} ta**\n\n"
        "*(Limitlarni olib tashlash va ko'proq imkoniyatlar uchun PRO versiyaga o'ting)*"
    )
    await message.answer(text)

# ==================== KANALLAR ====================
@router.message(F.text == "⚙️ Kanallar")
async def channels_menu(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMINS: return
    await state.clear() 
    
    channels = await db.channels.find().to_list(length=100)
    text = "Sizning kanallaringiz:\n\n"
    if not channels: text += "Hozircha yo'q."
    for ch in channels: text += f"🔹 {ch['channel_name']} ({ch['channel_id']})\n"
    
    btn = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="add_channel")]])
    await message.answer(text, reply_markup=btn)

@router.callback_query(F.data == "add_channel")
async def add_ch(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Kanal nomini yozing (Masalan: Asosiy kanal):")
    await state.set_state(ChannelState.waiting_for_name)
    await callback.answer()

@router.message(ChannelState.waiting_for_name)
async def ch_name(message: types.Message, state: FSMContext):
    if message.text in MENU_BUTTONS:
        await state.clear()
        return
        
    await state.update_data(name=message.text)
    await message.answer("Endi Kanal ID'sini (masalan: -100123456789) yoki Usernameni (@kanal_nomi) yozing:")
    await state.set_state(ChannelState.waiting_for_id)

@router.message(ChannelState.waiting_for_id)
async def ch_id(message: types.Message, state: FSMContext):
    if message.text in MENU_BUTTONS:
        await state.clear()
        return
        
    # QAT'IY TEKSHIRUV: ID -100 yoki @ bilan boshlanishi shart
    if not (message.text.startswith("-100") or message.text.startswith("@")):
        await message.answer("❌ Xato! Kanal ID'si doim '-100' yoki username '@' bilan boshlanishi kerak. Qaytadan yozing:")
        return 
        
    data = await state.get_data()
    await db.channels.insert_one({"channel_name": data['name'], "channel_id": message.text})
    await message.answer(f"✅ Kanal '{data['name']}' muvaffaqiyatli saqlandi!")
    await state.clear()

# ==================== REJA (KUTISH ZALI) ====================
@router.message(F.text == "📅 Reja")
async def show_schedule(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMINS: return
    await state.clear()
    
    posts = await db.posts.find({"status": "pending"}).sort("time", 1).to_list(length=20)
    
    if not posts:
        await message.answer("Hozircha navbatda postlar yo'q.")
        return

    text = "📅 **Yaqin xabarlar rejasini:**\n\n"
    for i, p in enumerate(posts, 1):
        dt = datetime.fromisoformat(p['time'])
        time_str = dt.strftime("%m-%d %H:%M")
        text += f"{i}. ⏰ {time_str} | Kanal: `{p['target']}`\n"
        
        btn = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"del_{p['_id']}")]
        ])
        await message.answer(text if i==1 else f"Post #{i} ({time_str})", reply_markup=btn)

@router.callback_query(F.data.startswith("del_"))
async def delete_post(callback: types.CallbackQuery):
    post_id = callback.data.split("_")[1]
    await db.posts.delete_one({"_id": ObjectId(post_id)})
    await callback.message.delete()
    await callback.answer("Post rejadagi ro'yxatdan o'chirildi.")

# ==================== POST YUKLASH VA AVTO VAQT ====================
@router.message(F.text == "📥 Post yuklash")
async def post_start(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMINS: return
    await state.clear()
    await message.answer("Postni yuboring (rasm/video/matn):")
    await state.set_state(PostState.waiting_for_post)

@router.message(PostState.waiting_for_post)
async def post_get(message: types.Message, state: FSMContext):
    if message.text in MENU_BUTTONS:
        await state.clear()
        return
        
    await state.update_data(msg_id=message.message_id, chat_id=message.chat.id)
    channels = await db.channels.find().to_list(length=100)
    
    if not channels:
        await message.answer("❌ Kanallar yo'q! Avval kanal qo'shing.", reply_markup=main_menu)
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
        "⏰ **Vaqtni tanlang yoki o'zingiz yozing:**\n"
        "(Masalan, qo'lda yozsangiz: `15:00` yoki `04-15 15:00`)\n\n"
        "*Eslatma: Basic versiyada faqat bitta vaqt kiritish mumkin.*",
        reply_markup=time_menu 
    )
    await state.set_state(PostState.waiting_for_time)

@router.message(PostState.waiting_for_time)
async def process_smart_time(message: types.Message, state: FSMContext):
    if message.text in MENU_BUTTONS:
        await message.answer("Jarayon bekor qilindi.", reply_markup=main_menu)
        await state.clear()
        return
        
    data = await state.get_data()
    t_str = message.text.strip()
    
    if "," in t_str or "\n" in t_str:
        await message.answer("❌ Basic versiyada faqat bitta vaqt kiritish mumkin! Bitta vaqt yozing.", reply_markup=time_menu)
        return

    try:
        now = datetime.now(TIMEZONE)
        
        # Tugmalarni tushunish mantig'i
        if "Bugun" in t_str:
            soat = t_str.split(" ")[1] 
            parsed_dt = datetime.strptime(f"{now.strftime('%m-%d')} {soat}", "%m-%d %H:%M")
        elif "Ertaga" in t_str:
            soat = t_str.split(" ")[1]
            ertaga = now + timedelta(days=1)
            parsed_dt = datetime.strptime(f"{ertaga.strftime('%m-%d')} {soat}", "%m-%d %H:%M")
        elif len(t_str) <= 5: 
            parsed_dt = datetime.strptime(f"{now.strftime('%m-%d')} {t_str}", "%m-%d %H:%M")
            if parsed_dt.time() < now.time():
                parsed_dt = parsed_dt + timedelta(days=1)
        else: 
            parsed_dt = datetime.strptime(t_str, "%m-%d %H:%M")
        
        final_dt = TIMEZONE.localize(parsed_dt.replace(year=2026))
        
        await db.posts.insert_one({
            "message_id": data['msg_id'], 
            "from_chat_id": data['chat_id'],
            "target": data['target'], 
            "time": final_dt.isoformat(),
            "status": "pending",
            "is_pro": False
        })
        
        await message.answer(f"✅ Post saqlandi! Vaqti: {final_dt.strftime('%d-%m-%Y %H:%M')}", reply_markup=main_menu)
        await state.clear()
        
    except Exception as e:
        await message.answer(f"❌ Noto'g'ri vaqt formati. Tugmalardan foydalaning yoki to'g'ri yozing.")
