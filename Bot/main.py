from datetime import datetime
from time import time
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from Bot.flood_control import check_flood
from Bot.leveling import level_up
from Bot.daily import claim_daily_reward
from Bot.leaderboard import update_leaderboard_message, leaderboard_modes, prepare_leaderboard_message  # Import leaderboard functions
from Bot.poll import start_poll, handle_vote, show_poll_results, BOT_ADMIN_ID
from database.db_manager import create_db, add_user, ensure_user_exists, get_user, update_points, update_level, update_health, connect_db

API_ID = "21989020"
API_HASH = "3959305ae244126404702aa5068ba15c"
BOT_TOKEN = "8141351816:AAG1_YB0l88X0SLAHnos9iODdZuCdNEfuFo"

app = Client(
  name="Kaisen Ranking Bot",
  api_id=API_ID,
  api_hash=API_HASH,
  bot_token=BOT_TOKEN
)

# Create DB on bot startup
create_db()

@app.on_message(filters.command("start"))
def start_handler(client, message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name  # Use first name for the link
    username = message.from_user.username or first_name

    # Ensure user exists in the database
    ensure_user_exists(user_id, username)

    # Fetch user data from the database
    user_data = get_user(user_id)
    if user_data:
        user_id, username, points, level, exp, health, last_activity_time, last_claimed = user_data

      # Create a user link using the user's first name
        user_link = f'<a href="tg://user?id={user_id}">{first_name}</a>'

      # Inline keyboard with a button to your chat group
        chat_group_url = "https://t.me/KaisenWorld"  # Replace with your group link
        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("Join Chat Group", url=chat_group_url)]
            ]
        )

        # Send a welcome message with user data and the user link
        message.reply_photo(
            photo="https://imgur.com/a/hJU9sB4",
            caption=(
                f"Hey {user_link}, 𝖶𝖾𝗅𝖼𝗈𝗆𝖾 𝗍𝗈 𝗍𝗁𝖾 𝖯𝗒𝗑𝗇 𝖡𝗈𝗍 ! 🎉\n\n"
                f"<b>📜 ʜᴏᴡ ᴛᴏ ᴇᴀʀɴ ᴛᴏᴋᴇɴs ?</b>\n"
                f"- ᴊᴜsᴛ ᴄʜᴀᴛ ɪɴ ᴛʜᴇ ɢʀᴏᴜᴘ ! ᴇᴠᴇʀʏ ᴍᴇssᴀɢᴇ ʏᴏᴜ sᴇɴᴅ ɢᴇᴛs ʏᴏᴜ ᴄʟᴏsᴇʀ ᴛᴏ ᴇᴀʀɴɪɴɢ ᴋᴀɪᴢᴇɴ ᴛᴏᴋᴇɴs.\n\n"
                f"𝖦𝖾𝗍 𝗌𝗍𝖺𝗋𝗍𝖾𝖽 𝗇𝗈𝗐 ! 𝗍𝗒𝗉𝖾 /help 𝖿𝗈𝗋 𝗆𝗈𝗋𝖾 𝖼𝗈𝗆𝗆𝖺𝗇𝖽𝗌.\n\n"
                f"🎯 **ʏᴏᴜʀ sᴛᴀᴛs :**\n• ᴘᴏɪɴᴛs : {points}\n• ʟᴇᴠᴇʟ : {level}"
            ),
          reply_markup=keyboard,  # Attach the keyboard to the message
        )

    # If user data doesn't exist, add the user and fetch data again
    if user_data is None:
        add_user(user_id, username)
        user_data = get_user(user_id)

@app.on_message(filters.command("daily"))
def daily_handler(client, message):
    """Handle the /daily command to give daily rewards."""
    user_id = message.from_user.id
    response = claim_daily_reward(user_id)
    message.reply_text(response)

@app.on_message(filters.command("poll"))
def poll_handler(client, message):
    """Handle the /poll command to create polls."""
    user_id = message.from_user.id

    # Ensure only admin can create polls
    if user_id != BOT_ADMIN_ID:
        message.reply("You need to be a bot admin to create a poll.")
        return

    # Parse the command
    parts = message.text.split("\"")
    if len(parts) < 3:
        message.reply("Usage: /poll \"<question>\" \"<option1>\" \"<option2>\" ... [expiry_time_in_minutes]")
        return

    question = parts[1]  # Question inside quotes
    options = [opt.strip() for opt in parts[2].split() if opt.strip()]  # Options split by spaces
    expiry_time = int(parts[-1]) if parts[-1].isdigit() else None

    # Validate options
    if len(options) < 2:
        message.reply("Please provide at least two options for the poll.")
        return

    # Start the poll
    start_poll(client, message, question, options, expiry_time)

@app.on_callback_query(filters.regex(r"vote_\d+_.*"))
def vote_handler(client, callback_query):
    """Handle user votes."""
    handle_vote(client, callback_query)

@app.on_message(filters.command("results"))
def results_handler(client, message):
    """Show poll results."""
    try:
        poll_id = int(message.text.split()[1])  # Extract poll_id from the message
        show_poll_results(client, message, poll_id)
    except (ValueError, IndexError):
        message.reply("Usage: /results <poll_id>")
      
# Global dictionaries for leaderboard modes and message IDs
leaderboard_modes = {}  # Tracks current leaderboard type ("points" or "level") for each group
leaderboard_message_ids = {}  # Tracks message IDs of leaderboard messages for each group


@app.on_message(filters.command("leaderboard"))
async def leaderboard_handler(client, message):
    """Handle the /leaderboard command."""
    chat_id = message.chat.id

    # Default to points if no leaderboard mode is set
    if chat_id not in leaderboard_modes:
        leaderboard_modes[chat_id] = "points"  # Default mode is points

    leaderboard_type = leaderboard_modes[chat_id]  # Points or level

    # Prepare the leaderboard message and inline buttons
    leaderboard_text, reply_markup = prepare_leaderboard_message(chat_id, leaderboard_type)

    # Send the leaderboard message
    sent_message = await message.reply_text(leaderboard_text, reply_markup=reply_markup)

    # Save the message ID for future edits
    leaderboard_message_ids[chat_id] = sent_message.id


@app.on_callback_query(filters.regex("points|level"))
async def leaderboard_switch_handler(client, callback_query):
    """Handle the switching between points and level leaderboards."""
    chat_id = callback_query.message.chat.id
    leaderboard_type = callback_query.data  # Either "points" or "level"

    # Update the leaderboard mode for the group
    leaderboard_modes[chat_id] = leaderboard_type

    # Prepare the updated leaderboard message and inline buttons
    leaderboard_text, reply_markup = prepare_leaderboard_message(chat_id, leaderboard_type)

    # Edit the leaderboard message
    if chat_id in leaderboard_message_ids:
        try:
            await client.edit_message_text(
                chat_id=chat_id,
                message_id=leaderboard_message_ids[chat_id],  # Use the stored message ID
                text=leaderboard_text,
                reply_markup=reply_markup
            )
        except Exception as e:
            print(f"Error editing leaderboard message: {e}")

    # Acknowledge the callback query to remove the "loading" state
    await callback_query.answer()

@app.on_message(filters.command("help"))
def help_handler(client, message):
    # List of available commands and their descriptions
    help_text = (
        "Here are the commands you can use with the Kaisen Ranking Bot:\n\n"
        "💬 : General Commands\n"
        "/start - ɪɴɪᴛᴀʟɪᴢᴇ ʏᴏᴜʀ ᴘʀᴏғɪʟᴇ\n"
        "/profile - ᴠɪᴇᴡ ᴘʀᴏғɪʟᴇ\n"
        "/help - ᴅɪsᴘʟᴀʏ ᴛʜɪs ʜᴇʟᴘ ᴍᴇɴᴜ\n"
        "/daily - ᴄʟᴀɪᴍ ʏᴏᴜʀ ᴅᴀɪʟʏ ʀᴇᴡᴀʀᴅ ᴘᴏɪɴᴛs !\n\n"
        "🎯 **: Tips**\n"
        "- Claim your daily reward every 24 hours to keep progressing faster.\n"
        "- Avoid spamming, or the flood control will block your commands temporarily.\n"
    )
    
    # Send the help message to the user
    message.reply_text(help_text)

@app.on_message(filters.command("profile"))
async def profile_handler(client, message):
    """Handle the /profile command."""
    # Check if the command is replied to a message or tagged with @username
    if message.reply_to_message:
        # If the command is used by replying to another user's message
        target_user = message.reply_to_message.from_user
    elif message.entities and message.entities[0].type == "mention":
        # If the command is used by tagging a user (e.g., @username)
        target_user = message.entities[0].user
    else:
        # If no reply or mention, show the profile of the user who sent the command
        target_user = message.from_user

    # Check if the target is a bot
    if target_user.is_bot:
        await message.reply("You can't get the profile of a bot.")
        return

    # Fetch user data from the database for the target user
    user_data = get_user(target_user.id)
    if user_data:
        user_id, username, points, level, exp, health, last_activity_time, last_claimed = user_data

        # Create a user link using the user's first name
        user_link = f'<a href="tg://user?id={target_user.id}">{target_user.first_name}</a>'

        # Format the last activity time
        time_diff = int(time()) - last_activity_time
        last_activity = format_time_diff(time_diff)

        # Prepare the profile text
        profile_text = f"""
        **{user_link}'s Profile:**
💎 **Level** : {level}
🎮 **Exp** : {exp}/{level * 100}
💰 **Points** : {points}
❤️ **Health** : {health}%
        
🕛 **Last Checkin** : {last_activity}

- **You're doing great! Keep chatting to level up!**
        """

        # Send the profile details
        await message.reply_text(profile_text)
    else:
        # If user data doesn't exist
        await message.reply_text(f"Error fetching {target_user.first_name}'s profile. Please try again later or use /start!")


def format_time_diff(seconds):
    """Convert seconds into a readable time format."""
    if seconds < 60:
        return f"{seconds} seconds ago"
    elif seconds < 3600:
        return f"{seconds // 60} minutes ago"
    elif seconds < 86400:
        return f"{seconds // 3600} hours ago"
    else:
        return f"{seconds // 86400} days ago"

@app.on_message(filters.text)
async def handle_message(client, message):
    """Handle the flood control and leveling up based on chat activity."""
    # List of allowed group chat IDs (replace with your actual group IDs)
    ALLOWED_GROUPS = [-1002135192853, -1002324159284]  # Add your group IDs here

    # Ensure the message is from an allowed group
    if message.chat.id not in ALLOWED_GROUPS:
        return  # Ignore messages outside allowed groups

    user_id = message.from_user.id
  
    # Flood control logic
    if check_flood(user_id):
        await message.reply("You are sending messages too quickly. Please wait a few seconds!")
    else:
        # Increment experience and level based on the message content
        level_up(user_id, message.text)

if __name__ == "__main__":
    app.run()
