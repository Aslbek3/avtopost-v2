from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
import database as db
import config

settings_router = Router()

# ==================== HOLATLAR (FSM) ====================
class SettingsState(StatesGroup):
    waiting_for_new_admin_id = State()

# ==================== SOZLAMALAR MENYUSI ====================
@settings_router.message(F.text == "⚙️ Sozlamalar")
async def settings_menu(message: Message):
    uid = message.from_user.id
    if not await db.is_admin(uid): return
    
    # Tugmalarni yig'ish
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🆔 Mening ID raqamim", callback_data="set_my_id")],
        [InlineKeyboardButton(text="🗑 Barcha Navbatdagi Postlarni O'chirish", callback_data="set_clear_posts")]
    ])
    
    # Agar foydalanuvchi Super Admin bo'lsa (config.py dagi birinchi admin), unga yangi admin qo'shish huquqi beriladi
    if uid == config.ADMINS[0]:
        kb.inline_keyboard.append([InlineKeyboardButton(text="➕ Yangi Admin Qo'shish", callback_data="set_add_admin")])
        
    await message.answer("⚙️ **Sozlamalar bo'limiga xush kelibsiz!**\nNima qilamiz?", reply_markup=kb)

# ==================== MENING ID RAQAMIM ====================
@settings_router.callback_query(F.data == "set_my_id")
async def show_my_id(call: CallbackQuery):
    uid = call.from_user.id
    await call.message.edit_text(f"🆔 **Sizning Telegram ID raqamingiz:**\n`{uid}`\n\n*(Nusxalash uchun ustiga bosing)*", 
                                 reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Orqaga", callback_data="set_back")]]))

# ==================== POSTLARNI TOZALASH ====================
@settings_router.callback_query(F.data == "set_clear_posts")
async def confirm_clear_posts(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Yo'q, bekor qilish", callback_data="set_back")],
        [InlineKeyboardButton(text="✅ Ha, hammasini o'chirish", callback_data="set_clear_posts_confirm")]
    ])
    await call.message.edit_text("⚠️ **DIQQAT!**\n\nBu amal sizning navbatda turgan **BARCHA** postlaringizni o'chirib yuboradi. Buni ortga qaytarib bo'lmaydi.\n\nTasdiqlaysizmi?", reply_markup=kb)

@settings_router.callback_query(F.data == "set_clear_posts_confirm")
async def clear_posts_confirmed(call: CallbackQuery):
    uid = call.from_user.id
    # Foydalanuvchining barcha pending postlarini o'chirish
    await db.db.posts.delete_many({"owner_id": uid, "status": "pending"})
    await call.message.edit_text("✅ Barcha navbatdagi postlar muvaffaqiyatli o'chirildi!",
                                 reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Orqaga", callback_data="set_back")]]))

# ==================== YANGI ADMIN QO'SHISH (SUPER ADMIN UCHUN) ====================
@settings_router.callback_query(F.data == "set_add_admin")
async def add_admin_start(call: CallbackQuery, state: FSMContext):
    uid = call.from_user.id
    if uid != config.ADMINS[0]:
        await call.answer("❌ Bu funksiya faqat Asosiy Admin uchun!", show_alert=True)
        return
        
    await call.message.edit_text("👤 **Yangi adminning Telegram ID raqamini yuboring:**\n\n*(Masalan: 123456789)*",
                                 reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="set_back_clear_state")]]))
    await state.set_state(SettingsState.waiting_for_new_admin_id)

@settings_router.message(StateFilter(SettingsState.waiting_for_new_admin_id))
async def save_new_admin(message: Message, state: FSMContext):
    new_admin_id = message.text.strip()
    
    if not new_admin_id.isdigit():
        await message.answer("❌ Xato! ID faqat raqamlardan iborat bo'lishi kerak. Qaytadan yuboring:")
        return
        
    new_admin_id = int(new_admin_id)
    
    # Bazada bormi tekshiramiz
    existing = await db.db.admins.find_one({"user_id": new_admin_id})
    if existing or new_admin_id in config.ADMINS:
        await message.answer("ℹ️ Bu foydalanuvchi allaqachon admin!")
    else:
        await db.db.admins.insert_one({"user_id": new_admin_id})
        await message.answer(f"✅ **Yangi admin qo'shildi!**\nID: `{new_admin_id}`")
        
    await state.clear()

# ==================== ORQAGA QAYTISH ====================
@settings_router.callback_query(F.data == "set_back")
async def back_to_settings(call: CallbackQuery):
    uid = call.from_user.id
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🆔 Mening ID raqamim", callback_data="set_my_id")],
        [InlineKeyboardButton(text="🗑 Barcha Navbatdagi Postlarni O'chirish", callback_data="set_clear_posts")]
    ])
    if uid == config.ADMINS[0]:
        kb.inline_keyboard.append([InlineKeyboardButton(text="➕ Yangi Admin Qo'shish", callback_data="set_add_admin")])
        
    await call.message.edit_text("⚙️ **Sozlamalar bo'limiga xush kelibsiz!**\nNima qilamiz?", reply_markup=kb)

@settings_router.callback_query(F.data == "set_back_clear_state")
async def back_and_clear_state(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await back_to_settings(call)
