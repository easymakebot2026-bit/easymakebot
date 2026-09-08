# راهنمای کامل easymakebot | easymakebot Full Help

> این سند به همان دو زبانی است که نمونه‌ی اکسل ایمپورت محصولات ساخته می‌شود: فارسی و انگلیسی.
> This document is written in the same two languages the product-import sample Excel is generated in: Persian and English.

---

# بخش فارسی

## ۱. نقش‌ها (Roles)

| نقش | یعنی چی |
|---|---|
| **ادمین پلتفرم** | فقط یک نفر — همان که `PLATFORM_ADMIN_ID` است. دسترسی به `/easybotadmin` و `/send_to_all`. |
| **صاحب ربات** | هرکسی که یک ربات ساخته (با `/newbot`). داخل همان ربات، همه‌ی ابزارهای ساخت را می‌بیند. |
| **کاربر/مشترک ربات ساخته‌شده** | کسی که `/start` یک ربات ساخته‌شده را زده — مشتری نهایی. |

---

## ۲. دستورهای سطح بالا (روی ربات‌ساز اصلی)

| دستور | برای کی | کاربرد |
|---|---|---|
| `/start` | همه | نمایش منوی خوش‌آمد؛ بار اول شماره تلفن (اختیاری) می‌پرسد. |
| `/help` | همه | لیست همین دستورها. |
| `/mybots` | صاحب ربات | لیست ربات‌هایی که ساختی؛ با زدن روی هرکدوم وارد محیط ویرایش همون میشی. |
| `/newbot` | همه | ساخت ربات جدید. باید اول از **@BotFather** توکن بگیری (چیزی شبیه `123456:ABC-...`) و همون رو بفرستی. |
| `/live` | صاحب ربات (روی یک ربات انتخاب‌شده) | لایو‌کردن ربات: تست رایگان ۷۲ساعته یک‌باره، یا خرید پلن. |
| `/cancel` | همه | لغو هر ویزارد نیمه‌کاره و برگشت به منو — همیشه کار می‌کند، هر وضعیتی که باشی. |
| `/easybotadmin` | فقط ادمین پلتفرم | پنل مدیریت کل پلتفرم. |
| `/send_to_all` | فقط ادمین پلتفرم | پیام همگانی به همه‌ی **سازنده‌های ربات** (نه کاربران نهایی). |

**مثال:** برای ساخت اولین ربات: پیام `/newbot` را بفرست، بعد توکنی که از BotFather گرفتی (مثلاً `123456789:AAExampleTokenxxx`) را کپی-پیست کن. ربات تازه‌ساخته‌شده بلافاصله وارد منوی ابزارها می‌شود، ولی هنوز روی تلگرام «زنده» نیست تا `/live` بزنی.

---

## ۳. منوی «Build & Edit Tools» — پنج ابزار ساخت ربات

بعد از انتخاب یک ربات از «My Bots»، این پنج ابزار در دسترس‌اند:

### 1️⃣ Define Command (تعریف دستور)
دستورهای دلخواه برای ربات ساخته‌شده می‌سازی — مثل `/menu` یا `/about`. اولین باری که هیچ دستوری نداری، پیشنهاد می‌شود اول `/start` را بسازی؛ ساخت `/start` یک ویزارد چندمرحله‌ای دارد (متن خوش‌آمد، آیدی/شماره تماس ادمین، لینک‌های شبکه‌اجتماعی — همه اختیاری).
**مثال:** دستور `/rules` بساز که وقتی کاربر بزندش، قوانین گروه را نشانش دهد.

### 2️⃣ Force Join (عضویت اجباری)
کانال(های)ی که کاربر باید عضو شود تا ربات جوابش را بدهد. ربات باید در آن کانال ادمین باشد.
**مثال:** یوزرنیم `@my_channel` را اضافه کن و «🔒 Enable Force Join» را بزن؛ از این به بعد هرکس بدون عضویت در `@my_channel`، به‌جای پاسخ ربات، دکمه‌ی «✅ عضو شدم» را می‌بیند.

### 3️⃣ Broadcast (پیام همگانی مخصوص این ربات)
یک دستور دلخواه می‌سازی (مثلاً `/news`) که وقتی خودت بعداً آن را بزنی و پیامت را بفرستی، به همه‌ی مشترکین **همین ربات** ارسال می‌شود.
**مثال:** دستور `/news` بساز؛ بعداً هر وقت خواستی خبر جدید بدهی، `/news` را بزن، متن/عکس/ویدیوت را بفرست — برای همه‌ی کسانی که تا الان `/start` این ربات را زده‌اند ارسال می‌شود.

### 4️⃣ Content List (لیست محتوا)
لیست قابل‌مرور از آیتم‌ها — خبر، محصول، درس، آهنگ، هرچی. بار اول باید بین دو حالت انتخاب کنی (بعداً قابل تغییر نیست):
- **Shop mode:** آیتم‌ها می‌توانند «برای فروش» باشند (قیمت + دکمه‌ی خرید).
- **Subscription mode:** آیتم‌ها می‌توانند «Premium» باشند (بعد از تمام‌شدن سهمیه‌ی رایگان، نیاز به اشتراک یا خرید تک‌آیتمی).

می‌توانی تک‌تک اضافه کنی، یا یک اکسل/CSV یک‌جا آپلود کنی (نمونه‌ی آماده به ۱۰ زبان قابل دانلود است: فارسی، انگلیسی، عربی، ترکی، روسی، فرانسه، آلمانی، اسپانیایی، ایتالیایی، کره‌ای). ستون **Category** برای دسته‌بندی تودرتو، ستون **Code** برای آپدیت بدون تکرار (آپلود دوباره با همان کد = ویرایش)، ستون **Action=Delete** برای حذف.

قابلیت‌های دیگر همین ابزار: **Add Post** (یک پست عکس/ویدیو+کپشن که فوراً به همه‌ی مشترکین ارسال می‌شود و می‌توانند لایک/کامنت بگذارند — مثل کانال، ولی داخل خودِ ربات)، ویرایش/حذف/جابه‌جایی آیتم‌ها.

**مثال:** برای یک فروشگاه لباس، ۲۰ محصول با عکس و قیمت را در یک فایل اکسل آماده کن، ستون Category را «مردانه»/«زنانه» بگذار، آپلود کن — همه یک‌جا اضافه می‌شوند و در منوی دکمه‌ای دسته‌بندی‌شده نمایش داده می‌شوند.

### 5️⃣ Shop (فروشگاه)
مدیریت محصولات مستقل (غیر از آنهایی که از دل Content List برای فروش گذاشته‌ای)، روش‌های پرداخت، سفارش‌ها، کمپین تخفیف — و این چهار قابلیت تازه:

#### 📥 Import Products (ایمپورت محصول با قیمت و موجودی) — تازه
اکسل/CSV با ستون‌های: **Name / Description / Price / Cost Price / Stock / Image URL / Code / Action** (فارسی یا انگلیسی — فقط این دو زبان). ردیف با Code تکراری = آپدیت آن محصول؛ ردیف با Action=Delete = حذف آن محصول. نمونه‌ی آماده هم فارسی هم انگلیسی از خود منو قابل دانلود است.
**مثال:** یک انبار ۵۰ کالایی داری. یک ردیف اکسل: `کفش اسپرت | کفش اسپرت مردانه سایز ۴۰-۴۴ | 850000 | 600000 | 12 | https://.../shoe.jpg | SKU-101 | ` → محصول «کفش اسپرت» با قیمت ۸۵۰٬۰۰۰ تومان، قیمت‌تمام‌شده ۶۰۰٬۰۰۰ (برای محاسبه‌ی سود)، و ۱۲ عدد موجودی ساخته می‌شود. وقتی موجودی به صفر برسد، محصول خودکار از لیست خرید مخفی می‌شود (بدون اینکه حذفش کنی).

#### 📊 Sales & Stock (آمار فروش و موجودی) — تازه
یک نگاه سریع به وضعیت همین یک ربات: تعداد محصول، تعداد کل سفارش، تعداد سفارش پرداخت‌شده، مجموع درآمد، سود (فقط اگر برای حداقل یک محصول «قیمت‌تمام‌شده» ثبت کرده باشی)، ۵ محصول پرفروش، و لیست محصولات با موجودی ≤۵ عدد (هشدار کمبود موجودی).
**مثال:** بعد از یک هفته فروش، «📊 Sales & Stock» را بزن تا ببینی کدام محصول بیشتر فروش رفته و کدام‌ها دارند تمام می‌شوند تا سفارش تازه بدهی.

#### 🧾 Invoice Branding (برندسازی فاکتور) — تازه
فاکتور PDF که بعد از هر خرید برای مشتری صادر می‌شود را با نام کسب‌وکار، لوگو (لینک عکس)، آدرس، و یک یادداشت پایین فاکتور (مثلاً «هزینه ارسال به عهده خریدار است») شخصی‌سازی کن. هرکدام را نگذاری، فاکتور به حالت ساده‌ی پیش‌فرض برمی‌گردد — چیزی خراب نمی‌شود.
**مثال:** نام کسب‌وکار را «فروشگاه آنلاین رزا» بگذار، لینک لوگو را وارد کن، آدرس فروشگاه فیزیکی را بنویس — از این به بعد هر فاکتوری که مشتری‌هایت می‌گیرند، این اطلاعات را بالای صفحه دارد.

#### قابلیت‌های قبلی Shop
- **💳 Payment Methods:** درگاه‌های پرداخت — زرین‌پال (فقط ایران)، کارت‌به‌کارت (تأیید دستی خودت)، Stripe (بین‌الملل، قیمت به دلار)، کریپتو/TON.
- **📋 Recent Orders:** آخرین سفارش‌ها؛ سفارش‌های کارت‌به‌کارت را همین‌جا تأیید/رد می‌کنی.
- **🎁 Free Preview Limit / 💰 Default Unlock Price** (فقط حالت Subscription): چند آیتم رایگان قبل از نیاز به اشتراک، و قیمت پیش‌فرض باز کردن تک‌آیتمی.
- **📈 Price Campaign:** تخفیف یا افزایش موقت روی همه‌ی قیمت‌ها؛ سر موعد خودکار برمی‌گردد.

---

## ۴. ربات‌ساز بصری (Visual Builder)

از داخل «My Bots» بعد از انتخاب یک ربات، اگر دکمه‌ی «🎨 Visual Builder» را ببینی (وابسته به تنظیمات سرور)، یک صفحه‌ی داخل تلگرام باز می‌شود که در آن با درگ‌ودراپ بلاک‌ها (پیام، عضویت اجباری، راهنما، لیست محتوا، فروشگاه، ...) جریان `/start` یا هر دستور دیگری را بدون تایپ کردن هیچ کدی طراحی می‌کنی. نسخه‌ی فعلی فقط زنجیره‌ی خطی می‌سازد (بدون شاخه‌ی if/else).

---

## ۵. پنل مدیریت پلتفرم (`/easybotadmin`) — فقط ادمین

آمار کل پلتفرم، لیست تمام کاربران و ربات‌ها، تعلیق/رفع‌تعلیق یک ربات (کلید خاموشی اضطراری، مستقل از پرداخت)، اعطای دسترسی رایگان (چند روز یا همیشگی)، تغییرنام، حذف کامل یک ربات (با تایپ‌کردن یوزرنیم دقیق ربات برای تأیید نهایی — غیرقابل‌بازگشت)، خروجی اکسل کامل، و پیام همگانی به همه‌ی سازنده‌های ربات.

---

# English Section

## 1. Roles

| Role | Meaning |
|---|---|
| **Platform Admin** | A single person — whoever `PLATFORM_ADMIN_ID` is. Has access to `/easybotadmin` and `/send_to_all`. |
| **Bot Owner** | Anyone who has built a bot (via `/newbot`). Sees all the build tools inside that bot's editing environment. |
| **End User / Subscriber** | Someone who has sent `/start` to a built bot — the final customer. |

---

## 2. Top-Level Commands (on the main builder bot)

| Command | For whom | What it does |
|---|---|---|
| `/start` | Everyone | Shows the welcome menu; asks for a phone number (optional) the first time. |
| `/help` | Everyone | Lists these same commands. |
| `/mybots` | Bot owner | Lists the bots you've built; tap one to enter its editing environment. |
| `/newbot` | Everyone | Create a new bot. First get a token from **@BotFather** (looks like `123456:ABC-...`), then send it. |
| `/live` | Bot owner (on a selected bot) | Go live: a one-time 72-hour free trial, or buying a plan. |
| `/cancel` | Everyone | Cancels any half-finished wizard and returns to the menu — works in any state. |
| `/easybotadmin` | Platform admin only | The whole-platform admin console. |
| `/send_to_all` | Platform admin only | Broadcasts to every **bot creator** on the platform (not end users). |

**Example:** To build your first bot, send `/newbot`, then paste the token you got from BotFather (e.g. `123456789:AAExampleTokenxxx`). The new bot immediately enters its tools menu, but isn't "live" on Telegram yet until you use `/live`.

---

## 3. "Build & Edit Tools" Menu — Five Building Tools

Once you select a bot from "My Bots", these five tools are available:

### 1️⃣ Define Command
Create custom commands for your built bot — like `/menu` or `/about`. The very first time you have no commands yet, it suggests building `/start` first; `/start` has its own multi-step wizard (welcome text, admin contact, social links — all optional).
**Example:** Create a `/rules` command that shows your group's rules when a user taps it.

### 2️⃣ Force Join
Channel(s) a user must join before the bot responds. The bot must be an admin in that channel.
**Example:** Add `@my_channel` and tap "🔒 Enable Force Join"; from now on, anyone not in `@my_channel` sees an "✅ I've Joined" button instead of the bot's reply.

### 3️⃣ Broadcast
Create a custom command (e.g. `/news`) that, when you later send it yourself followed by your message, delivers that message to every subscriber of **this specific bot**.
**Example:** Create `/news`; whenever you want to announce something, send `/news`, then your text/photo/video — it goes out to everyone who has ever sent `/start` to this bot.

### 4️⃣ Content List
A browsable list of items — news, products, lessons, tracks, anything. The first time, you pick one of two modes (can't be changed later):
- **Shop mode:** items can be marked "for sale" (price + Buy button).
- **Subscription mode:** items can be marked "Premium" (needs an active subscription or single-item purchase once the free-preview quota is used up).

Add items one by one, or bulk-upload an .xlsx/.csv (a ready-made sample is downloadable in 10 languages: Persian, English, Arabic, Turkish, Russian, French, German, Spanish, Italian, Korean). Use the **Category** column for nested grouping, the **Code** column to update instead of duplicate on re-upload, and **Action=Delete** to remove an item.

Other features in this tool: **Add Post** (a photo/video + caption sent immediately to every subscriber, with likes/comments — like a channel, but inside the bot itself), and edit/delete/re-group existing items.

**Example:** For a clothing store, prepare 20 products with photos and prices in one spreadsheet, set the Category column to "Men's"/"Women's", upload it — all 20 are added at once and shown in a categorized button menu.

### 5️⃣ Shop
Manage standalone products (separate from ones marked "for sale" inside Content List), payment methods, orders, discount campaigns — plus these four newly added features:

#### 📥 Import Products (with price & stock) — New
Upload an .xlsx/.csv with columns: **Name / Description / Price / Cost Price / Stock / Image URL / Code / Action** (Persian or English only). A row with a matching Code updates that product; a row with Action=Delete removes it. Ready-made samples in both Persian and English are downloadable right from the menu.
**Example:** You manage a 50-item inventory. One spreadsheet row: `Running Shoes | Men's running shoes, sizes 40-44 | 850000 | 600000 | 12 | https://.../shoe.jpg | SKU-101 | ` → creates "Running Shoes" priced at 850,000 Toman, cost price 600,000 (used for profit reporting), and 12 units in stock. Once stock hits zero, the product is automatically hidden from the buyer's list without you having to delete it.

#### 📊 Sales & Stock — New
A quick snapshot of this one bot: product count, total orders, paid orders, total revenue, profit (only if at least one product has a cost price set), the top 5 best sellers, and any products at 5 units or fewer (a low-stock warning).
**Example:** After a week of sales, tap "📊 Sales & Stock" to see which product is selling best and which ones are running low so you can reorder in time.

#### 🧾 Invoice Branding — New
Customize the PDF invoice issued to a buyer after each purchase: business name, logo (an image URL), address, and a footer note (e.g. "Buyer covers shipping cost"). Leaving any of these unset just falls back to the plain default invoice — nothing breaks.
**Example:** Set the business name to "Rosa Online Store", add your logo's URL, write your store's address — from then on, every invoice your customers receive carries this branding at the top.

#### Existing Shop features
- **💳 Payment Methods:** Zarinpal (Iran only), card-to-card (you approve manually), Stripe (international, priced in USD), crypto/TON.
- **📋 Recent Orders:** Recent orders; you approve or reject card-to-card payments here.
- **🎁 Free Preview Limit / 💰 Default Unlock Price** (Subscription mode only): how many free items before a subscription is needed, and the default price to unlock a single item.
- **📈 Price Campaign:** A temporary discount or markup across every price; auto-reverts when time is up.

---

## 4. Visual Builder

From "My Bots" after selecting a bot, if you see the "🎨 Visual Builder" button (depends on server configuration), it opens an in-Telegram page where you drag-and-drop blocks (message, force-join, guide, content list, shop, ...) to design the `/start` flow (or any other command) without writing any code. The current version only builds a linear chain (no if/else branching yet).

---

## 5. Platform Admin Console (`/easybotadmin`) — Admin Only

Whole-platform stats, a list of every user and bot, suspending/unsuspending a bot (an emergency kill switch, independent of payment), granting free access (a number of days, or permanent), renaming, fully deleting a bot (requires typing the bot's exact username to confirm — irreversible), a full Excel export, and a broadcast to every bot creator on the platform.
