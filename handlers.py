import logging
from datetime import datetime
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

# Asosiy menyu (Adminlar uchun)
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📥 Post yuklash")],
        [KeyboardButton(text="📅 Reja"), KeyboardButton(text="⚙️ Kanallar")],
        [KeyboardButton(text="🚀 PRO Versiyaga o'tish")] # Yangi tugma!
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

MENU_BUTTONS = ["📥 Post yuklash", "📅 Reja", "⚙️ Kanallar", "🚀 PRO Versiyaga o'tish", "/start"]

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
            "Batafsil ma'lumot va bot xarid qilish uchun adminga yozing: @Sukuna_5288" # O'zingizning usernamengizni qo'ying
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

@router.message(F.text == "🚀 PRO Versiyaga o'tish")
async def pro_ad(message: types.Message):
    if message.from_user.id not in ADMINS: return
    text = (
        "🚀 **PRO Versiya Afzalliklari:**\n\n"
        "✅ Birdaniga yuzlab postlarni vergul orqali oson rejalashtirish;\n"
        "✅ Har bir post tagiga chiroyli ssilka tugmalari qo'shish;\n"
        "✅ Kanallar va postlar sonida umuman cheklov yo'q;\n"
        "✅ Interval taymer (har X minutda avtomatik post tashlash).\n\n"
        "Tarifni yangilash uchun adminga yozing: @Sukuna_5288"
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

# ==================== POST YUKLASH (BASIC VERSIYA) ====================
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
    
    # Tugma so'ramaymiz, to'g'ridan-to'g'ri kanal tanlashga o'tamiz
    channels = await db.channels.find().to_list(length=100)
    
    if not channels:
        await message.answer("❌ Bazada kanallar yo'q! Avval kanal qo'shing.")
        await state.clear()
        return
        
    builder = [[InlineKeyboardButton(text=c['channel_name'], callback_data=f"ch_{c['channel_id']}")] for c in channels]
    await message.answer("Qaysi kanalga joylaymiz?", reply_markup=InlineKeyboardMarkup(inline_keyboard=builder))
    await state.set_state(PostState.waiting_for_channel)

@router.callback_query(PostState.waiting_for_channel, F.data.startswith("ch_"))
async def ch_select(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(target=callback.data.split("ch_")[1])
    # Vaqtni faqat bittadan yozish so'raladi
    await callback.message.answer(
        "Vaqtni kiriting (Masalan: `15:00` yoki `04-01 16:30`).\n\n"
        "*(Diqqat: Basic versiyada vaqtlarni bittadan kiritish mumkin)*"
    )
    await state.set_state(PostState.waiting_for_time)

@router.message(PostState.waiting_for_time)
async def process_single_time(message: types.Message, state: FSMContext):
    if message.text in MENU_BUTTONS:
        await state.clear()
        return
        
    data = await state.get_data()
    t_str = message.text.strip()
    
    # Vergul bor-yo'qligini tekshirish (ommaviy kiritishni bloklash)
    if "," in t_str or "\n" in t_str:
        await message.answer("❌ Basic versiyada bir nechta vaqt kiritish mumkin emas! Faqat bitta vaqt yozing (masalan: `15:00`).\n\nLimitlarni olib tashlash uchun 🚀 PRO versiyaga o'ting.")
        return

    try:
        if len(t_str) <= 5: 
            parsed_dt = datetime.strptime(f"{datetime.now().strftime('%m-%d')} {t_str}", "%m-%d %H:%M")
        else: 
            parsed_dt = datetime.strptime(t_str, "%m-%d %H:%M")
        
        final_dt = TIMEZONE.localize(parsed_dt.replace(year=2026))
        
        await db.posts.insert_one({
            "message_id": data['msg_id'], 
            "from_chat_id": data['chat_id'],
            "target": data['target'], 
            "time": final_dt.isoformat(),
            "status": "pending",
            "is_pro": False # Statistika va kelajak uchun belgi
        })
        
        await message.answer(f"✅ Post muvaffaqiyatli rejalashtirildi!", reply_markup=main_menu)
        await state.clear()
        
    except Exception as e:
        await message.answer(f"❌ Xato format. Iltimos, `15:00` yoki `03-31 15:00` ko'rinishida yozing.")
