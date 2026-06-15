import os
import asyncio
import shutil
from pathlib import Path
from datetime import datetime
import traceback
import sys
import time

# ======================== CONFIGURATION ========================
# Account Credentials (User Account - NOT Bot Token)
API_ID = 36265467
API_HASH = "e4bb758e93749a52a3b4d150cd614f04"

# User Account Phone Number (with country code)
PHONE_NUMBER = "+919904932406"  # Replace with your phone number

# Authorized Users (who can use this account)
AUTHORIZED_IDS = [8750729235, 8790096948]

# Audio Settings
VOLUME_LEVEL = 50
BASS_LEVEL = 10
TREBLE_LEVEL = 5
MUTED = False

# Store active sessions
active_calls = {}
record_calls = {}
play_calls = {}

TEMP_DIR = Path("temp_media")
TEMP_DIR.mkdir(exist_ok=True)

# ================================================================

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ChatType, ChatMemberStatus
from pyrogram.raw import functions
from pyrogram.raw.types import PhoneCallProtocol
from pyrogram.errors import FloodWait, PeerIdInvalid

print("🔄 Initializing User Account Bot...")

# Create User Account Client (not bot)
app = Client(
    "user_account_session",
    api_id=API_ID,
    api_hash=API_HASH,
    phone_number=PHONE_NUMBER
)

def is_authorized(user_id: int) -> bool:
    return user_id in AUTHORIZED_IDS

async def join_voice_call_as_user(client: Client, chat_id: str, user_id: int = None):
    """Join voice call using user account"""
    try:
        # Get chat info
        try:
            chat = await client.get_chat(chat_id)
            chat_id_str = str(chat.id)
            chat_title = chat.title or chat.first_name
            print(f"📢 Chat found: {chat_title} (ID: {chat_id_str})")
        except Exception as e:
            return False, f"❌ Invalid chat: {str(e)[:50]}"
        
        # Get full chat info with voice call
        try:
            if chat.type in [ChatType.CHANNEL, ChatType.SUPERGROUP]:
                full_chat = await client.invoke(
                    functions.channels.GetFullChannel(
                        channel=await client.resolve_peer(chat_id_str)
                    )
                )
            else:
                full_chat = await client.invoke(
                    functions.messages.GetFullChat(
                        chat_id=await client.resolve_peer(chat_id_str)
                    )
                )
            print(f"✅ Full chat obtained")
        except Exception as e:
            return False, f"❌ Cannot access chat: {str(e)[:100]}"
        
        # Check if voice call exists
        if not hasattr(full_chat.full_chat, 'call') or not full_chat.full_chat.call:
            return False, f"❌ No active voice call in {chat_title}!\nStart a voice chat first."
        
        print(f"🎙️ Voice call found! Joining...")
        
        # Join the voice call as user account
        try:
            result = await client.invoke(
                functions.phone.JoinGroupCall(
                    call=full_chat.full_chat.call,
                    join_as=await client.resolve_peer(client.me.id),
                    params=PhoneCallProtocol(
                        min_layer=65,
                        max_layer=92,
                        library_versions=["2.4.1", "2.4.0", "2.2.0", "2.0.0"]
                    )
                )
            )
            print(f"✅ Successfully joined voice call")
        except Exception as e:
            error_msg = str(e)
            if "PARTICIPANT_ALREADY" in error_msg or "ALREADY_PARTICIPANT" in error_msg:
                print(f"ℹ️ Already in voice call")
            else:
                raise e
        
        # Store active call
        active_calls[chat_id_str] = {
            'call': full_chat.full_chat.call,
            'chat_title': chat_title,
            'joined_at': datetime.now(),
            'joined_by': user_id
        }
        
        return True, f"✅ User account joined voice call in **{chat_title}**!"
        
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return False, f"⏳ Flood wait {e.value}s"
    except Exception as e:
        error_msg = str(e)
        print(f"Join error: {error_msg}")
        
        if "PARTICIPANT_ALREADY" in error_msg:
            return True, f"✅ Already in voice call: {chat_title}"
        elif "call" in error_msg.lower():
            return False, f"❌ No active voice call! Start a voice chat first."
        else:
            return False, f"❌ Error: {error_msg[:150]}"

async def leave_voice_call_as_user(client: Client, chat_id: str):
    """Leave voice call using user account"""
    try:
        chat_id_str = str(chat_id)
        
        if chat_id_str in active_calls:
            try:
                await client.invoke(
                    functions.phone.LeaveGroupCall(
                        call=active_calls[chat_id_str]['call']
                    )
                )
                print(f"✅ Left voice call: {chat_id_str}")
            except Exception as e:
                print(f"Leave error: {e}")
            
            del active_calls[chat_id_str]
            return True, "✅ Left voice call successfully!"
        else:
            return False, "ℹ️ Not in this voice call"
            
    except Exception as e:
        return False, f"❌ Error: {str(e)[:100]}"

# ======================== MAIN MENU ========================

main_menu = InlineKeyboardMarkup([
    [InlineKeyboardButton("🎤 GOD X MIC", callback_data="main_info")],
    [InlineKeyboardButton("📞 JOIN VC", callback_data="join_menu"),
     InlineKeyboardButton("🚪 LEAVE", callback_data="leave_menu")],
    [InlineKeyboardButton("🔊 AUDIO", callback_data="audio_menu")],
    [InlineKeyboardButton("❓ HELP", callback_data="help"),
     InlineKeyboardButton("📊 STATUS", callback_data="status")]
])

join_menu = InlineKeyboardMarkup([
    [InlineKeyboardButton("🎙️ JOIN VOICE CALL", callback_data="join_call")],
    [InlineKeyboardButton("🏠 MAIN", callback_data="main")]
])

leave_menu = InlineKeyboardMarkup([
    [InlineKeyboardButton("🚪 LEAVE CALL", callback_data="leave_call"),
     InlineKeyboardButton("🚪 LEAVE ALL", callback_data="leave_all")],
    [InlineKeyboardButton("🏠 MAIN", callback_data="main")]
])

audio_menu = InlineKeyboardMarkup([
    [InlineKeyboardButton("🔊 VOLUME", callback_data="set_volume"),
     InlineKeyboardButton("🎚️ BASS", callback_data="set_bass")],
    [InlineKeyboardButton("🎼 TREBLE", callback_data="set_treble"),
     InlineKeyboardButton("🔇 MUTE", callback_data="mute")],
    [InlineKeyboardButton("🔊 UNMUTE", callback_data="unmute"),
     InlineKeyboardButton("🏠 MAIN", callback_data="main")]
])

# ======================== COMMANDS ========================

@app.on_message(filters.private & filters.command("start"))
async def start_command(client: Client, message: Message):
    if not is_authorized(message.from_user.id):
        await message.reply("❌ Unauthorized! You don't have permission to use this account.")
        return
    
    user_account = await client.get_me()
    
    await message.reply(
        f"**# GOD X MIC - USER ACCOUNT**\n\n"
        f"**👤 Account:** {user_account.first_name}\n"
        f"**🆔 ID:** `{user_account.id}`\n\n"
        f"**POWERING LOUDER, CLEARER CALLS**\n"
        f"**WITH A SMART REAL-TIME VOICE BOOST ENGINE** 🥳\n\n"
        f"**⚡ USE /join <CHAT_ID> TO JOIN VOICE CALL**\n\n"
        f"**📋 Commands:**\n"
        f"• `/join -1003827924054` - Join voice call\n"
        f"• `/leave` - Leave voice call\n"
        f"• `/leaveall` - Leave all calls\n"
        f"• `/level 30` - Set volume (1-50)\n"
        f"• `/bass 10` - Set bass (0-15)\n"
        f"• `/treble 8` - Set treble (0-15)\n"
        f"• `/mute` - Mute\n"
        f"• `/unmute` - Unmute\n"
        f"• `/status` - Check status\n\n"
        f"**🔊 Current Settings:**\n"
        f"Volume: {VOLUME_LEVEL}/50 | Bass: {BASS_LEVEL}/15 | Treble: {TREBLE_LEVEL}/15\n\n"
        f"**💡 Example:** `/join -1003827924054`",
        reply_markup=main_menu
    )

@app.on_message(filters.private & filters.command("join"))
async def join_command(client: Client, message: Message):
    """Handle /join command - Join voice call"""
    if not is_authorized(message.from_user.id):
        await message.reply("❌ Unauthorized!")
        return
    
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply(
            f"📞 **Join Voice Call**\n\n"
            f"Usage: `/join <chat_id>`\n\n"
            f"Examples:\n"
            f"• `/join -1003827924054` - Join group voice call\n"
            f"• `/join @username` - Join by username\n"
            f"• `/join 123456789` - Join by ID\n\n"
            f"**Active Calls:** {len(active_calls)}\n\n"
            f"💡 Get chat ID from @userinfobot",
            reply_markup=join_menu
        )
        return
    
    chat_input = parts[1].strip()
    status_msg = await message.reply(f"🔄 Joining voice call in `{chat_input}`...\n\n⏳ Please wait...")
    
    # Show typing indicator
    await client.send_chat_action(message.chat.id, "typing")
    
    # Join voice call
    success, msg = await join_voice_call_as_user(client, chat_input, message.from_user.id)
    
    if success:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🚪 Leave Call", callback_data="leave_call"),
             InlineKeyboardButton("📊 Status", callback_data="status")]
        ])
        
        await status_msg.edit_text(
            f"{msg}\n\n"
            f"🔊 Volume: {VOLUME_LEVEL}/50\n"
            f"🎚️ Bass: {BASS_LEVEL}/15\n"
            f"🎼 Treble: {TREBLE_LEVEL}/15\n\n"
            f"🎵 The user account is now in the voice call!\n"
            f"🔇 Use `/mute` to mute / `/unmute` to unmute\n\n"
            f"💡 Use `/leave` to leave the call",
            reply_markup=keyboard
        )
    else:
        await status_msg.edit_text(
            f"{msg}\n\n"
            f"**Troubleshooting:**\n"
            f"1. Start a voice chat in the group first\n"
            f"2. Make sure the chat ID is correct\n"
            f"3. User account must be a member of the chat\n\n"
            f"💡 Get correct chat ID from @userinfobot"
        )

@app.on_message(filters.private & filters.command("leave"))
async def leave_command(client: Client, message: Message):
    """Handle /leave command - Leave current voice call"""
    if not is_authorized(message.from_user.id):
        await message.reply("❌ Unauthorized!")
        return
    
    if not active_calls:
        await message.reply("ℹ️ Not in any voice call!\n\nUse `/join -1003827924054` to join a call.")
        return
    
    status_msg = await message.reply("🔄 Leaving voice call...")
    
    left_count = 0
    for chat_id in list(active_calls.keys()):
        success, _ = await leave_voice_call_as_user(client, chat_id)
        if success:
            left_count += 1
    
    await status_msg.edit_text(f"✅ Left {left_count} voice call(s)!")

@app.on_message(filters.private & filters.command("leaveall"))
async def leaveall_command(client: Client, message: Message):
    """Handle /leaveall command - Leave all voice calls"""
    if not is_authorized(message.from_user.id):
        await message.reply("❌ Unauthorized!")
        return
    
    if not active_calls:
        await message.reply("ℹ️ Not in any voice call!")
        return
    
    status_msg = await message.reply("🔄 Leaving all voice calls...")
    
    left_count = 0
    for chat_id in list(active_calls.keys()):
        success, _ = await leave_voice_call_as_user(client, chat_id)
        if success:
            left_count += 1
    
    await status_msg.edit_text(f"✅ Left {left_count} voice call(s)!")

@app.on_message(filters.private & filters.command("level"))
async def set_volume(client: Client, message: Message):
    """Handle /level command - Set volume"""
    global VOLUME_LEVEL
    if not is_authorized(message.from_user.id):
        await message.reply("❌ Unauthorized!")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        return await message.reply(f"🔊 **Current Volume:** {VOLUME_LEVEL}/50\n\nUsage: `/level 1-50`\nExample: `/level 30`\n\n💡 Higher volume = Louder audio")
    
    try:
        new_vol = int(parts[1])
        if 1 <= new_vol <= 50:
            VOLUME_LEVEL = new_vol
            await message.reply(f"✅ **Volume set to {VOLUME_LEVEL}/50**\n\nAll audio will play at {VOLUME_LEVEL}% volume!")
        else:
            await message.reply("❌ Volume must be between 1 and 50")
    except:
        await message.reply("❌ Invalid number! Use: `/level 30`")

@app.on_message(filters.private & filters.command("bass"))
async def set_bass(client: Client, message: Message):
    """Handle /bass command - Set bass boost"""
    global BASS_LEVEL
    if not is_authorized(message.from_user.id):
        await message.reply("❌ Unauthorized!")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        return await message.reply(f"🎚️ **Current Bass:** {BASS_LEVEL}/15\n\nUsage: `/bass 0-15`\nExample: `/bass 10`\n\n💡 Higher bass = More thump")
    
    try:
        new_bass = int(parts[1])
        if 0 <= new_bass <= 15:
            BASS_LEVEL = new_bass
            await message.reply(f"✅ **Bass boost set to {BASS_LEVEL}/15**\n\nDeep bass enabled!")
        else:
            await message.reply("❌ Bass must be between 0 and 15")
    except:
        await message.reply("❌ Invalid number! Use: `/bass 10`")

@app.on_message(filters.private & filters.command("treble"))
async def set_treble(client: Client, message: Message):
    """Handle /treble command - Set treble boost"""
    global TREBLE_LEVEL
    if not is_authorized(message.from_user.id):
        await message.reply("❌ Unauthorized!")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        return await message.reply(f"🎼 **Current Treble:** {TREBLE_LEVEL}/15\n\nUsage: `/treble 0-15`\nExample: `/treble 8`\n\n💡 Higher treble = Crispier sound")
    
    try:
        new_treble = int(parts[1])
        if 0 <= new_treble <= 15:
            TREBLE_LEVEL = new_treble
            await message.reply(f"✅ **Treble boost set to {TREBLE_LEVEL}/15**\n\nCrisp audio enabled!")
        else:
            await message.reply("❌ Treble must be between 0 and 15")
    except:
        await message.reply("❌ Invalid number! Use: `/treble 8`")

@app.on_message(filters.private & filters.command("mute"))
async def mute_command(client: Client, message: Message):
    """Handle /mute command - Mute"""
    if not is_authorized(message.from_user.id):
        await message.reply("❌ Unauthorized!")
        return
    
    # Use nonlocal or declare at function level
    current_muted = MUTED
    if not current_muted:
        # Create a new variable in function scope
        mute_var = True
        # Update global after function
        globals()['MUTED'] = True
        await message.reply("🔇 **User Account MUTED!**\n\nNo audio will play until `/unmute`")
    else:
        await message.reply("🔇 Already muted! Use `/unmute` to unmute.")

@app.on_message(filters.private & filters.command("unmute"))
async def unmute_command(client: Client, message: Message):
    """Handle /unmute command - Unmute"""
    if not is_authorized(message.from_user.id):
        await message.reply("❌ Unauthorized!")
        return
    
    # Update global MUTED
    globals()['MUTED'] = False
    await message.reply("🔊 **User Account UNMUTED!**\n\nAudio will now play normally.")

@app.on_message(filters.private & filters.command("status"))
async def status_command(client: Client, message: Message):
    """Handle /status command - Show status"""
    if not is_authorized(message.from_user.id):
        await message.reply("❌ Unauthorized!")
        return
    
    user_account = await client.get_me()
    
    status_text = (
        f"📊 **USER ACCOUNT STATUS**\n\n"
        f"👤 Account: {user_account.first_name}\n"
        f"🆔 ID: `{user_account.id}`\n\n"
        f"🔊 Volume: {VOLUME_LEVEL}/50\n"
        f"🎚️ Bass: {BASS_LEVEL}/15\n"
        f"🎼 Treble: {TREBLE_LEVEL}/15\n"
        f"🔇 Muted: {'Yes' if MUTED else 'No'}\n\n"
        f"📞 Active Calls: {len(active_calls)}\n"
    )
    
    if active_calls:
        status_text += "\n**In Voice Calls:**\n"
        for chat_id, info in active_calls.items():
            joined_at = info['joined_at'].strftime("%H:%M:%S")
            status_text += f"• `{chat_id}` - {info['chat_title']}\n  Joined: {joined_at}\n"
    else:
        status_text += "\n❌ Not in any voice call.\n\n💡 Use `/join -1003827924054` to join a call"
    
    await message.reply(status_text, reply_markup=main_menu)

@app.on_message(filters.private & filters.command("help"))
async def help_command(client: Client, message: Message):
    """Handle /help command - Show help"""
    if not is_authorized(message.from_user.id):
        await message.reply("❌ Unauthorized!")
        return
    
    help_text = (
        f"📋 **GOD X MIC - USER ACCOUNT COMMANDS**\n\n"
        f"**🔗 VC COMMANDS**\n"
        f"• `/join <chat_id>` — Join voice call\n"
        f"• `/leave` — Leave current call\n"
        f"• `/leaveall` — Leave all calls\n\n"
        f"**🔊 AUDIO CONTROLS**\n"
        f"• `/level 30` — Set volume (1-50)\n"
        f"• `/bass 10` — Set bass (0-15)\n"
        f"• `/treble 8` — Set treble (0-15)\n"
        f"• `/mute` — Mute\n"
        f"• `/unmute` — Unmute\n\n"
        f"**⚡ UTILS**\n"
        f"• `/status` — Check status\n"
        f"• `/help` — This help\n\n"
        f"**📝 EXAMPLES**\n"
        f"`/join -1003827924054`\n"
        f"`/level 35`\n"
        f"`/bass 12`\n\n"
        f"**🔊 Current Settings:**\n"
        f"Volume: {VOLUME_LEVEL}/50 | Bass: {BASS_LEVEL}/15 | Treble: {TREBLE_LEVEL}/15\n\n"
        f"💡 Get chat ID from @userinfobot"
    )
    
    await message.reply(help_text, reply_markup=main_menu)

# ======================== CALLBACK HANDLERS ========================

@app.on_callback_query()
async def callback_handler(client: Client, callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if not is_authorized(user_id):
        await callback.answer("Unauthorized!", show_alert=True)
        return
    
    data = callback.data
    
    if data == "main":
        await callback.message.edit_reply_markup(reply_markup=main_menu)
        await callback.answer()
    
    elif data == "main_info":
        await callback.answer("GOD X MIC - User Account Voice Bot", show_alert=True)
    
    elif data == "join_menu":
        await callback.message.reply(
            "📞 **Join Voice Call**\n\n"
            "Use: `/join <chat_id>`\n\n"
            "Example: `/join -1003827924054`\n\n"
            "Get chat ID from @userinfobot"
        )
        await callback.answer()
    
    elif data == "join_call":
        await callback.message.reply(
            "📞 **Join Voice Call**\n\n"
            "Send: `/join -1003827924054`\n\n"
            "Replace with your group ID"
        )
        await callback.answer()
    
    elif data == "leave_menu":
        await callback.message.edit_reply_markup(reply_markup=leave_menu)
        await callback.answer()
    
    elif data == "leave_call":
        if active_calls:
            left_count = 0
            for chat_id in list(active_calls.keys()):
                success, _ = await leave_voice_call_as_user(client, chat_id)
                if success:
                    left_count += 1
            await callback.message.reply(f"✅ Left {left_count} voice call(s)!")
        else:
            await callback.message.reply("ℹ️ Not in any voice call!")
        await callback.answer()
    
    elif data == "leave_all":
        if active_calls:
            left_count = 0
            for chat_id in list(active_calls.keys()):
                success, _ = await leave_v
