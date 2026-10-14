# Renders a sample invoice with the bot's real invoice code (bot/shop.py),
# stubbing only the DB-backed shop settings lookup.
import asyncio, os, sys, uuid, types
from datetime import datetime
sys.path.insert(0, sys.argv[1])
os.environ.setdefault("BOT_TOKEN", "1:x"); os.environ.setdefault("PLATFORM_ADMIN_ID", "1")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
os.environ.setdefault("ENCRYPTION_KEY", "ZmDfcTF7_60GrrY167zsiPd67pEvs0aGOv2oasOM1Pg=")
from bot import shop

async def fake_settings(bot_id):
    return types.SimpleNamespace(invoice_business_name="فروشگاه گل رز", invoice_logo_url=None,
        invoice_address="تهران، خیابان ولیعصر، پلاک ۱۲", invoice_footer_note="از خریدتون ممنونیم 🌹",
        invoice_business_phone="021-12345678", invoice_signature_url=None, tax_enabled=False)
shop.get_shop_settings = fake_settings

async def main():
    pdf = await shop._render_invoice_pdf(
        bot_id=uuid.UUID("5a1e0117-4c84-4cf9-a178-dc3440bf7f15"), invoice_number="5A1E01-C000042",
        date=datetime(2026, 10, 14, 18, 30), payment_label="کارت به کارت", buyer_telegram_id=482915736,
        items=[("دسته‌گل عروس", 1, 1200000)], subtotal=1200000, tax_amount=0,
        shipping={"method": "🛵 پیک اسنپ", "name": "سارا محمدی", "phone": "09121234567",
                  "address": "تهران، سعادت‌آباد، خیابان سرو، پلاک ۸", "postal_code": "1998765432"},
        has_physical=True)
    open(sys.argv[2], "wb").write(pdf)
asyncio.run(main())
