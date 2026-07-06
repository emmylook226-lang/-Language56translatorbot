import os
import logging
import re
from typing import Dict, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from deep_translator import GoogleTranslator
from langdetect import detect, DetectorFactory
from langdetect.lang_detect_exception import LangDetectException

# Set seed for consistent language detection
DetectorFactory.seed = 0

# ============ CONFIGURATION ============
TOKEN = os.environ.get("TOKEN")
PORT = int(os.environ.get("PORT", 8080))
ENVIRONMENT = os.environ.get("ENVIRONMENT", "production")

if not TOKEN:
    raise ValueError("❌ TOKEN environment variable not set!")

# ============ LOGGING ============
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO if ENVIRONMENT == "production" else logging.DEBUG
)
logger = logging.getLogger(__name__)

# ============ LANGUAGE DATA ============
LANGUAGES = {
    "🇺🇸 English": "en",
    "🇪🇸 Spanish": "es",
    "🇫🇷 French": "fr",
    "🇩🇪 German": "de",
    "🇮🇳 Hindi": "hi",
    "🇯🇵 Japanese": "ja",
    "🇨🇳 Chinese (Simplified)": "zh-CN",
    "🇨🇳 Chinese (Traditional)": "zh-TW",
    "🇷🇺 Russian": "ru",
    "🇮🇹 Italian": "it",
    "🇵🇹 Portuguese": "pt",
    "🇰🇷 Korean": "ko",
    "🇸🇦 Arabic": "ar",
    "🇹🇷 Turkish": "tr",
    "🇳🇱 Dutch": "nl",
    "🇻🇳 Vietnamese": "vi",
    "🇮🇩 Indonesian": "id",
    "🇹🇭 Thai": "th",
    "🇵🇱 Polish": "pl",
    "🇺🇦 Ukrainian": "uk",
    "🇷🇴 Romanian": "ro",
    "🇬🇷 Greek": "el",
    "🇨🇿 Czech": "cs",
    "🇸🇪 Swedish": "sv",
    "🇭🇺 Hungarian": "hu",
}

# Reverse mapping for language code to name
LANG_CODE_TO_NAME = {code: name for name, code in LANGUAGES.items()}

# User preferences storage (in-memory, resets on bot restart)
user_preferences: Dict[int, str] = {}

# ============ HELPER FUNCTIONS ============
def get_language_name(lang_code: str) -> str:
    """Get the display name of a language from its code."""
    return LANG_CODE_TO_NAME.get(lang_code, lang_code)

def detect_text_language(text: str) -> Optional[str]:
    """Detect the language of a text string."""
    try:
        if len(text.strip()) < 3:
            return None
        detected = detect(text)
        return detected
    except LangDetectException:
        return None
    except Exception as e:
        logger.error(f"Language detection error: {e}")
        return None

def format_translation_response(
    original_text: str,
    translated_text: str,
    source_lang: str,
    target_lang: str
) -> str:
    """Format the translation response message."""
    source_name = get_language_name(source_lang) if source_lang else "Unknown"
    target_name = get_language_name(target_lang)
    
    # Truncate long texts for display
    original_preview = original_text[:100] + "..." if len(original_text) > 100 else original_text
    
    return f"""
🌐 *Translation Complete*

📝 *Original:* 
`{original_preview}`

🔄 *From:* {source_name}
🎯 *To:* {target_name}

✨ *Result:*
{translated_text}
"""

# ============ COMMAND HANDLERS ============
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    user = update.effective_user
    welcome_message = f"""
👋 *Welcome to Language56 Translator Bot, {user.first_name}!*

🌍 I can translate between {len(LANGUAGES)} languages instantly!

📌 *Quick Start:*
• Send any text → Auto-translate to your preferred language
• Reply with /translate → Translate a specific message
• Use "text to fr" → Translate to French instantly

⚡ *Commands:*
/start - Show this message
/help - Detailed help guide
/languages - List all supported languages
/setlang - Set your default language
/translate - Translate replied message
/detect - Detect language of a message
/clear - Clear your preferences

🎯 *Try it now!* Send me any text to start translating.
"""
    keyboard = [
        [InlineKeyboardButton("🌍 View Languages", callback_data="show_languages")],
        [InlineKeyboardButton("⚙️ Set Default Language", callback_data="set_language")],
        [InlineKeyboardButton("❓ Help", callback_data="show_help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        welcome_message,
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    help_text = """
🤖 *Language56 Translator Bot Help*

📖 *Basic Usage:*

1️⃣ *Direct Translation*
Just send any text message and I'll translate it to your default language.

2️⃣ *Specific Language Translation*
Send: `Hello to es` → Translates "Hello" to Spanish
Send: `Good morning to fr` → Translates to French

3️⃣ *Reply Translation*
Reply to any message with `/translate` to translate that message.

4️⃣ *Language Detection*
Reply to any message with `/detect` to detect its language.

⚙️ *Settings:*
• /setlang - Change your default translation language
• /languages - See all supported languages
• /clear - Clear your preferences

💡 *Tips:*
• Language codes: en, es, fr, de, hi, ja, zh-CN, etc.
• Your default language is English unless changed
• All translations are powered by Google Translate

🔗 *Support:*
For issues or suggestions, contact the bot developer.
"""
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def languages_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /languages command."""
    # Organize languages in columns for better display
    lang_list = []
    for i, (name, code) in enumerate(LANGUAGES.items()):
        lang_list.append(f"• {name} (`{code}`)")
    
    # Split into chunks for better readability
    chunks = [lang_list[i:i+8] for i in range(0, len(lang_list), 8)]
    
    message = f"""
🌍 *Supported Languages* ({len(LANGUAGES)} languages)

{chr(10).join(chunks[0])}

Send: `text to code` to translate directly to any language.
Example: `Hello to es` → translates to Spanish

Use /setlang to set your default translation language.
"""
    
    # Add pagination for many languages
    keyboard = []
    if len(chunks) > 1:
        for i in range(1, min(len(chunks), 4)):
            keyboard.append([InlineKeyboardButton(
                f"📄 Page {i+1}", 
                callback_data=f"lang_page_{i}"
            )])
    
    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    await update.message.reply_text(message, parse_mode="Markdown", reply_markup=reply_markup)

async def setlang_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /setlang command - Show language selection keyboard."""
    keyboard = []
    row = []
    for i, (name, code) in enumerate(LANGUAGES.items()):
        row.append(InlineKeyboardButton(name, callback_data=f"setlang_{code}"))
        if len(row) == 2:  # 2 columns for better mobile display
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    
    # Add cancel button
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🌍 *Select your default translation language:*\n\n"
        "All translations will be in this language unless you specify otherwise.",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

async def translate_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /translate command - Translate a replied message."""
    if not update.message.reply_to_message:
        await update.message.reply_text(
            "❌ Please reply to a message with `/translate` to translate it.",
            parse_mode="Markdown"
        )
        return
    
    text_to_translate = update.message.reply_to_message.text
    if not text_to_translate:
        await update.message.reply_text(
            "❌ The replied message has no text to translate.",
            parse_mode="Markdown"
        )
        return
    
    # Get user's default language or fallback to English
    user_id = update.effective_user.id
    target_lang = user_preferences.get(user_id, "en")
    
    try:
        translator = GoogleTranslator(target=target_lang)
        translated = translator.translate(text_to_translate)
        
        # Detect source language
        source_lang = detect_text_language(text_to_translate) or "en"
        
        response = format_translation_response(
            text_to_translate,
            translated,
            source_lang,
            target_lang
        )
        
        # Add quick action buttons
        keyboard = [
            [InlineKeyboardButton(
                "🔄 Translate to another language",
                callback_data="translate_more"
            )]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            response,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error(f"Translation error: {e}")
        await update.message.reply_text(
            f"❌ Translation failed: {str(e)}",
            parse_mode="Markdown"
        )

async def detect_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /detect command - Detect language of a replied message."""
    if not update.message.reply_to_message:
        await update.message.reply_text(
            "❌ Please reply to a message with `/detect` to detect its language.",
            parse_mode="Markdown"
        )
        return
    
    text = update.message.reply_to_message.text
    if not text:
        await update.message.reply_text(
            "❌ The replied message has no text to detect.",
            parse_mode="Markdown"
        )
        return
    
    detected = detect_text_language(text)
    if detected:
        lang_name = get_language_name(detected)
        confidence = "high" if len(text) > 20 else "medium"
        await update.message.reply_text(
            f"🔍 *Language Detection Result*\n\n"
            f"📝 Text: `{text[:50]}...`\n"
            f"🌐 Language: *{lang_name}*\n"
            f"📊 Code: `{detected}`\n"
            f"⚡ Confidence: *{confidence}*",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "❌ Could not detect the language. Please try with a longer text.",
            parse_mode="Markdown"
        )

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /clear command - Clear user preferences."""
    user_id = update.effective_user.id
    if user_id in user_preferences:
        del user_preferences[user_id]
        await update.message.reply_text(
            "✅ Your preferences have been cleared. Default language is now English.",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "ℹ️ You don't have any saved preferences.",
            parse_mode="Markdown"
        )

# ============ MESSAGE HANDLER ============
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle regular text messages - Auto-translate."""
    text = update.message.text
    user_id = update.effective_user.id
    
    if not text:
        return
    
    # Check for "text to lang" pattern
    # Pattern: "something to fr" or "Hello to es"
    match = re.search(r"\s+to\s+([a-z]{2}(-[A-Z]{2})?)$", text.lower())
    target_lang = None
    clean_text = text
    
    if match:
        lang_code = match.group(1)
        # Validate language code
        if any(code == lang_code for code in LANGUAGES.values()):
            target_lang = lang_code
            clean_text = text[:match.start()].strip()
    
    # If no specific language requested, use user's default
    if not target_lang:
        target_lang = user_preferences.get(user_id, "en")
    
    try:
        translator = GoogleTranslator(target=target_lang)
        translated = translator.translate(clean_text)
        
        # Detect source language
        source_lang = detect_text_language(clean_text) or "en"
        
        response = format_translation_response(
            clean_text,
            translated,
            source_lang,
            target_lang
        )
        
        # Add interactive buttons
        keyboard = [
            [
                InlineKeyboardButton("🔄 Swap", callback_data=f"swap_{source_lang}_{target_lang}"),
                InlineKeyboardButton("📋 Copy", callback_data=f"copy_{translated[:20]}")
            ],
            [InlineKeyboardButton("⚙️ Change Language", callback_data="set_language")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            response,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error(f"Message translation error: {e}")
        await update.message.reply_text(
            f"❌ Translation failed: {str(e)}",
            parse_mode="Markdown"
        )

# ============ CALLBACK QUERY HANDLER ============
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button callbacks."""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    data = query.data
    
    try:
        if data == "show_languages":
            await languages_command(update, context)
            
        elif data == "set_language":
            await setlang_command(update, context)
            
        elif data == "show_help":
            await help_command(update, context)
            
        elif data == "translate_more":
            await query.edit_message_text(
                "🌍 *Translate to which language?*\n\n"
                "Use `/setlang` to change your default language, "
                "or send `text to code` for instant translation.",
                parse_mode="Markdown"
            )
            
        elif data == "cancel":
            await query.edit_message_text(
                "✅ Operation cancelled.",
                parse_mode="Markdown"
            )
            
        elif data.startswith("setlang_"):
            lang_code = data.split("_")[1]
            user_preferences[user_id] = lang_code
            lang_name = get_language_name(lang_code)
            await query.edit_message_text(
                f"✅ *Default language set to: {lang_name}*\n\n"
                f"All future translations will be in {lang_name}.\n"
                f"Send any text to try it out!",
                parse_mode="Markdown"
            )
            
        elif data.startswith("swap_"):
            parts = data.split("_")
            if len(parts) == 3:
                source = parts[1]
                target = parts[2]
                await query.edit_message_text(
                    f"🔄 *Language Swap*\n\n"
                    f"Source: {get_language_name(source)}\n"
                    f"Target: {get_language_name(target)}\n\n"
                    f"Use `/setlang` to permanently change your default language.",
                    parse_mode="Markdown"
                )
                
        elif data.startswith("lang_page_"):
            page = int(data.split("_")[2])
            # Return to language list with page
            await languages_command(update, context)
            
        elif data.startswith("copy_"):
            await query.edit_message_text(
                "📋 *Copy to clipboard*\n\n"
                "Use the copy button in the Telegram app to copy the text.",
                parse_mode="Markdown"
            )
            
    except Exception as e:
        logger.error(f"Callback error: {e}")
        await query.edit_message_text(
            f"❌ Operation failed: {str(e)}",
            parse_mode="Markdown"
        )

# ============ ERROR HANDLER ============
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors."""
    logger.error(f"Update {update} caused error: {context.error}")
    
    # Send error message to user if possible
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "⚠️ Something went wrong. Please try again later.",
            parse_mode="Markdown"
        )

# ============ WEBHOOK SETUP (for Railway) ============
async def setup_webhook(application: Application) -> None:
    """Set up webhook for Railway deployment."""
    if ENVIRONMENT == "production":
        webhook_url = os.environ.get("RAILWAY_PUBLIC_DOMAIN")
        if not webhook_url:
            logger.warning("RAILWAY_PUBLIC_DOMAIN not set, falling back to polling")
            return
            
        webhook_url = f"https://{webhook_url}/webhook"
        await application.bot.set_webhook(webhook_url)
        logger.info(f"Webhook set to: {webhook_url}")

# ============ MAIN FUNCTION ============
def main():
    """Start the bot."""
    logger.info("🚀 Starting Language56 Translator Bot...")
    logger.info(f"Environment: {ENVIRONMENT}")
    
    # Create application
    application = Application.builder().token(TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("languages", languages_command))
    application.add_handler(CommandHandler("setlang", setlang_command))
    application.add_handler(CommandHandler("translate", translate_command))
    application.add_handler(CommandHandler("detect", detect_command))
    application.add_handler(CommandHandler("clear", clear_command))
    
    # Add message handler for text messages (not commands)
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )
    
    # Add callback query handler for inline buttons
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    # Start the bot
    if ENVIRONMENT == "production":
        # Use webhook for production
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            webhook_url=None  # Will be set in setup_webhook
        )
    else:
        # Use polling for development
        logger.info("Starting bot in polling mode...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
