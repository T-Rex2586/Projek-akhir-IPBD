"""
🤖 Start Telegram Bot Listener

This script starts the Telegram bot to listen for commands:
- /predict - Get AI trading signal (BUY/SELL/HOLD)
- /status - System status and stats
- /help - Show available commands

Also enables auto-alerts for:
- Positive news (sentiment > 0.5)
- Negative news (sentiment < -0.5)
- Price spikes and anomalies

Usage: python start_telegram_bot.py
"""
import sys
import os

sys.path.insert(0, '.')

from monitoring.telegram_alert import start_bot_listener, _is_configured

def main():
    print("\n" + "="*70)
    print("  🤖 Telegram Bot for Bitcoin Analytics")
    print("="*70)
    
    if not _is_configured():
        print("\n❌ Telegram bot not configured!")
        print("\n📝 Setup Instructions:")
        print("1. Create bot with @BotFather on Telegram")
        print("2. Get your chat ID from @userinfobot")
        print("3. Add to .env file:")
        print("   TELEGRAM_BOT_TOKEN=your_bot_token_here")
        print("   TELEGRAM_CHAT_ID=your_chat_id_here")
        print("\n💡 Then run this script again.")
        return False
    
    print("\n✅ Configuration found!")
    print("\n📱 Bot Features:")
    print("  • /predict - Get AI trading signal")
    print("  • /status - System status")
    print("  • /help - Show all commands")
    print("\n🔔 Auto-alerts enabled:")
    print("  • Positive/Negative news sentiment")
    print("  • Price spike alerts")
    print("  • Anomaly detections")
    print("\n⏹️  Press Ctrl+C to stop the bot")
    print("="*70 + "\n")
    
    # Start bot listener
    try:
        start_bot_listener()
    except KeyboardInterrupt:
        print("\n\n🛑 Bot stopped by user")
        return True
    except Exception as e:
        print(f"\n❌ Bot error: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
