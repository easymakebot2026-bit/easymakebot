# مستند فنی Visual Flow Builder (easymakebot)

این مستند هفت فایل اصلیِ Mini App تلگرامیِ «Visual Flow Builder» را که در `webapp/src/` قرار دارند، به‌طور کامل بررسی می‌کند. این Mini App با React و کتابخانه‌ی `@xyflow/react` (نسخه‌ی جدید `react-flow`) ساخته شده و از طریق دکمه‌ی «Visual Builder» در چت ربات باز می‌شود تا صاحب ربات بتواند بدون کدنویسی، جریان دستورهای ربات را به‌صورت بصری (drag-and-drop) طراحی کند.

---

## `webapp/src/main.jsx`

این فایل نقطه‌ی ورود (entry point) کل اپلیکیشن React است. کارش صرفاً «بوت‌استرپ» کردن برنامه است: با `createRoot` از `react-dom/client`، به المنت DOM با `id="root"` (که در `index.html` تعریف شده) متصل می‌شود و کامپوننت `App` را داخل `<StrictMode>` رندر می‌کند. `StrictMode` فقط در حالت توسعه (development) اثر دارد و با اجرای دوباره‌ی برخی توابع (مثل effectها) کمک می‌کند باگ‌های جانبی زودتر کشف شوند؛ در build نهایی (production) هیچ اثری ندارد. این فایل هیچ منطق تجاری‌ای ندارد و تنها فایل CSS پایه (`index.css`) را هم import می‌کند.

### فایل به‌عنوان یک کل
- **چه‌کار می‌کند:** `createRoot(...).render(<StrictMode><App /></StrictMode>)`.
- **ارتباط با فایل‌های دیگر:** فقط `App.jsx` را import و رندر می‌کند؛ هیچ ارتباط مستقیمی با بک‌اند ندارد.
- **موارد خاص:** اگر عنصر `#root` در `index.html` وجود نداشته باشد، `createRoot` خطا می‌دهد؛ اما چون این بخش از build خود Vite کنترل می‌شود، عملاً چنین حالتی رخ نمی‌دهد.

---

## `webapp/src/App.jsx`

این فایل «قلب» اپلیکیشن است: کامپوننت اصلی `App` و کامپوننت داخلی `Canvas` را تعریف می‌کند که کل بوم (canvas) طراحی جریان، نوار ابزار بلوک‌ها (`Palette`)، و مدیریت state گره‌ها (`nodes`) و یال‌ها (`edges`) را در بر می‌گیرد. این فایل مسئول ارتباط با بک‌اند از طریق `/api/flow` (بارگذاری و ذخیره‌ی جریان)، مدیریت drag-and-drop بلوک‌ها از `Palette` به داخل بوم، و باز/بسته کردن پنل `ContentManager` است.

### `newNodeId()`
- **چه‌کار می‌کند:** یک شناسه‌ی یکتای رشته‌ای برای گره‌های جدید تولید می‌کند، به‌صورت ``node-${Date.now()}-${nextId++}``. متغیر `nextId` یک شمارنده‌ی ماژول-سطح (module-level) خارج از هر کامپوننت است که در طول عمر صفحه افزایش می‌یابد.
- **موارد خاص:** ترکیب `Date.now()` (میلی‌ثانیه) با شمارنده‌ی افزایشی تضمین می‌کند حتی اگر دو گره در همان میلی‌ثانیه ساخته شوند (مثلاً drop سریع پشت‌سرهم)، شناسه‌ها تکراری نشوند. این شناسه فقط سمت کلاینت معنا دارد؛ در بک‌اند (`flow_engine.py`) صرفاً به‌عنوان یک رشته‌ی مرجع برای اتصال یال‌ها استفاده می‌شود و نیازی به فرمت خاصی ندارد.

### `Canvas()`
کامپوننت اصلیِ داخل `ReactFlowProvider` که کل منطق تعاملی بوم را در بر دارد.

- **State‌ها:**
  - `nodes, setNodes, onNodesChange` — از هوک `useNodesState([])` کتابخانه‌ی `@xyflow/react` گرفته می‌شود؛ آرایه‌ی گره‌های فعلی روی بوم را نگه می‌دارد و `onNodesChange` هندلر استانداردی است که برای جابه‌جایی/تغییر اندازه/انتخاب گره‌ها مستقیماً به `<ReactFlow>` داده می‌شود.
  - `edges, setEdges, onEdgesChange` — مشابه بالا اما برای یال‌های اتصال بین گره‌ها (`useEdgesState([])`).
  - `status` — رشته‌ای برای نمایش وضعیت (Loading…، خطا، Saving…، Saved ✅) در نوار بالای بوم.
  - `managingContent` — بولین که تعیین می‌کند آیا پنل `ContentManager` باز باشد یا نه.
  - `wrapperRef` — رفرنس DOM به `div.canvas-area` که برای محاسبه‌ی مرزهای بوم (bounding box) هنگام drop استفاده می‌شود.
  - `screenToFlowPosition` از هوک `useReactFlow()` گرفته می‌شود.

- **`useEffect` بارگذاری اولیه:**
  - **چه‌کار می‌کند:** با mount شدن کامپوننت، ابتدا `getBotId()` را از `telegram.js` صدا می‌زند. اگر `bot_id` در URL نباشد، پیام خطای «Missing bot_id…» را در `status` می‌گذارد و متوقف می‌شود (بدون تلاش برای فراخوانی API). در غیر این صورت `loadFlow()` (که یک درخواست `GET /api/flow` است) را صدا می‌زند؛ در صورت موفقیت، `nodes` و `edges` دریافتی را در state می‌ریزد و `status` را خالی می‌کند؛ در صورت شکست، پیام `Failed to load: ...` را نمایش می‌دهد.
  - **جزئیات مهم:** روی یال‌های دریافتی یک `map` اعمال می‌شود تا اگر `id` نداشتند (که طبق مدل داده‌ی بک‌اند در `flow_engine.py` واقعاً هم ندارند — یال‌ها فقط `source`/`target` دارند)، یک `id` مصنوعی به‌صورت `${e.source}-${e.target}` برایشان ساخته شود؛ این `id` صرفاً برای React key و منطق حذف در سمت کلاینت لازم است و هرگز به بک‌اند فرستاده نمی‌شود.
  - **ارتباط با بک‌اند:** به `bot/webapp_server.py`، تابع `get_flow` که `built_bot.flow_definition` (یا در نبود آن `{"nodes": [], "edges": []}`) را برمی‌گرداند، پس از عبور از `_authenticated_bot`.

### `updateNodeData(id, patch)`
- **چه‌کار می‌کند:** یک `useCallback` که با گرفتن `id` گره و یک شیء `patch`، آرایه‌ی `nodes` را map می‌کند و برای گره‌ی هم‌نام، `data` را با `{ ...n.data, ...patch }` merge (نه جایگزین کامل) می‌کند. این تابع از طریق `NodeActionsContext` در اختیار همه‌ی کامپوننت‌های گره در `nodes.jsx` قرار می‌گیرد تا مثلاً `TriggerNode` بتواند مقدار `command` را، یا `SendMessageNode` مقدار `text` را، بدون نیاز به prop-drilling عمیق تغییر دهد.
- **موارد خاص:** اگر `id` مطابقتی نداشته باشد (مثلاً گره قبلاً حذف شده) هیچ تغییری اعمال نمی‌شود؛ خطایی هم پرتاب نمی‌شود.

### `deleteNode(id)`
- **چه‌کار می‌کند:** گره‌ی موردنظر را از `nodes` فیلتر می‌کند و همزمان همه‌ی یال‌هایی که `source` یا `target`شان برابر `id` است را از `edges` حذف می‌کند — تا هیچ یال «آویزان» (dangling) به گره‌ی حذف‌شده باقی نماند. این تابع از دکمه‌ی ✕ در `NodeCard` (تعریف‌شده در `nodes.jsx`) صدا زده می‌شود.

### `openContentManager()`
- **چه‌کار می‌کند:** صرفاً `setManagingContent(true)` را صدا می‌زند. از طریق context به دکمه‌ی «🛠 Manage Content» در `ContentListNode` وصل است.

### `nodeActions` (useMemo)
- شیء `{ updateNodeData, deleteNode, openContentManager }` را memo می‌کند تا وقتی هیچ‌کدام از این سه callback تغییر نکرده، مقدار context عوض نشود و رندرهای غیرضروری در مصرف‌کننده‌های `NodeActionsContext` رخ ندهد.

### `onConnect(params)`
- **چه‌کار می‌کند:** وقتی کاربر با کشیدن از یک Handle به Handle دیگر دو گره را متصل می‌کند، `@xyflow/react` این تابع را با `params` (شامل `source`، `target`، و در صورت وجود `sourceHandle`/`targetHandle`) صدا می‌زند. با `addEdge(params, eds)` یال جدید را به آرایه‌ی `edges` اضافه می‌کند. `addEdge` یک تابع کمکی خود کتابخانه است که یک `id` منحصربه‌فرد برایش می‌سازد و از افزودن اتصال تکراری جلوگیری می‌کند.

### `onEdgeClick(_event, edge)`
- **چه‌کار می‌کند:** با کلیک/تپ روی یک یال، همان یال بلافاصله و **بدون هیچ تأییدیه‌ای** از `edges` حذف می‌شود (`eds.filter((e) => e.id !== edge.id)`).
- **چرا بدون تأیید:** طبق کامنت داخل کد، چون یال‌ها روی موبایل منوی راست‌کلیک/context menu لمسی ندارند، ساده‌ترین تعامل «تپ = حذف» انتخاب شده؛ چون وصل کردن دوباره‌ی دو گره هزینه‌ی کمی دارد (صرفاً یک درگ دیگر)، ریسک از دست دادن کار کاربر ناچیز در نظر گرفته شده است. این تفاوت آشکاری با حذف یک **گره** دارد که دکمه‌ی ✕ اختصاصی خودش را دارد اما آن هم بدون تأیید انجام می‌شود (برخلاف حذف آیتم محتوا در `ContentManager.jsx` که از `window.confirm` استفاده می‌کند).

### `handleDropBlock(blockType, clientX, clientY)`
- **چه‌کار می‌کند:** وقتی کاربر رها کردن یک بلوک از `Palette` را تمام می‌کند (`onDropBlock` prop که به `Palette` پاس داده شده)، این تابع صدا زده می‌شود.
  1. با `BLOCK_DEFS.find((b) => b.type === blockType)` تعریف بلوک را از `nodes.jsx` پیدا می‌کند؛ اگر پیدا نشود یا `wrapperRef.current` (یعنی DOM بوم) هنوز آماده نباشد، بی‌صدا خارج می‌شود.
  2. با `wrapperRef.current.getBoundingClientRect()` مستطیل بوم را در مختصات صفحه (viewport) می‌گیرد و چک می‌کند آیا نقطه‌ی رهاسازی (`clientX`, `clientY`) داخل این مستطیل است. اگر بیرون از بوم رها شده باشد (مثلاً روی خود Palette یا بیرون صفحه)، هیچ گره‌ای ساخته نمی‌شود — این جلوی ساخت گره‌های «گمشده» با مختصات نامعتبر را می‌گیرد.
  3. **تبدیل مختصات صفحه به مختصات بوم:** با `screenToFlowPosition({ x: clientX, y: clientY })` — تابعی از هوک `useReactFlow()` کتابخانه‌ی `@xyflow/react` — مختصات پیکسلیِ صفحه (که به pan/zoom فعلی بوم وابسته نیست) به مختصات منطقی داخل سیستم فلو (که با توجه به میزان zoom و جابه‌جایی/pan فعلی بوم محاسبه می‌شود) تبدیل می‌شود. این ضروری است چون کاربر ممکن است بوم را zoom کرده یا جابه‌جا کرده باشد؛ بدون این تبدیل، گره دقیقاً زیر انگشت/ماوس کاربر قرار نمی‌گرفت.
  4. گره‌ی جدید را با `newNodeId()`، `type: blockDef.type`، `position` محاسبه‌شده، و `data: { ...blockDef.defaultData }` (یک کپیِ سطحی از مقادیر پیش‌فرض تعریف‌شده در `nodes.jsx`، نه رفرنس مستقیم — تا تغییر `data` یک گره روی گره‌های دیگر از همان نوع اثر نگذارد) به آرایه‌ی `nodes` اضافه می‌کند.

### `handleSave()`
- **چه‌کار می‌کند:** یک تابع async که فرآیند ذخیره‌ی جریان را انجام می‌دهد.
  1. `status` را به `'Saving…'` تنظیم می‌کند.
  2. `saveFlow(...)` را از `telegram.js` صدا می‌زند (`POST /api/flow`) و **payload را budget می‌کند**: از هر گره فقط `{ id, type, data, position }` (بدون فیلدهای داخلی react-flow مثل `width`, `height`, `selected`, `dragging` که خودِ کتابخانه به هر گره اضافه می‌کند) و از هر یال فقط `{ source, target }` (بدون `id` مصنوعی‌ای که در بارگذاری ساخته شده بود) استخراج و ارسال می‌شود — این دقیقاً با ساختار موردانتظار `bot/flow_engine.py` (که فقط این فیلدها را می‌خواند) هم‌خوان است و از آلوده‌شدن `flow_definition` در دیتابیس با داده‌های اضافی جلوگیری می‌کند.
  3. در موفقیت: `status` را به `'Saved ✅'` می‌گذارد و با `setTimeout` بعد از ۲ ثانیه پاکش می‌کند.
  4. در خطا: پیام `Failed to save: ${err.message}` را نمایش می‌دهد (بدون timeout — پیام خطا می‌ماند).
- **ارتباط با بک‌اند:** به `save_flow` در `bot/webapp_server.py` که بعد از احراز هویت، JSON دریافتی را اعتبارسنجی می‌کند (باید dict با کلیدهای `nodes` و `edges` باشد)، در دیتابیس ذخیره می‌کند و سپس `sync_bot_commands` را صدا می‌زند تا دستورهای ربات (مثل لیست `/start`, `/menu` که در BotFather یا منوی تلگرام دیده می‌شود) بر اساس گره‌های `trigger` جدید به‌روزرسانی شود.

### بخش JSX رندر `Canvas`
- ساختار: `NodeActionsContext.Provider` کل درخت را در بر می‌گیرد تا `updateNodeData`/`deleteNode`/`openContentManager` در دسترس همه‌ی گره‌ها باشد؛ داخل آن یک `div.builder` شامل `Palette` (سمت چپ/بالا) و `div.canvas-area` (که `wrapperRef` رویش قرار دارد) شامل نوار وضعیت + دکمه‌ی Save و خود `<ReactFlow>` با `Background`, `Controls`, `MiniMap` است. `fitView` باعث می‌شود در بار اول بارگذاری، همه‌ی گره‌ها در دید جا شوند. اگر `managingContent` true باشد، `ContentManager` به‌صورت overlay روی همه چیز رندر می‌شود.

### `App()`
- **چه‌کار می‌کند:** کامپوننت export-شده‌ی پیش‌فرض. در یک `useEffect` (فقط یک‌بار در mount) تابع `initTelegramApp()` از `telegram.js` را صدا می‌زند (که SDK تلگرام را `ready()` و `expand()` می‌کند). سپس `Canvas` را داخل `ReactFlowProvider` (context لازم برای هوک‌های `@xyflow/react` مثل `useReactFlow`) رندر می‌کند.
- **چرا `ReactFlowProvider` بیرون از `Canvas`:** چون `useReactFlow()` داخل `Canvas` استفاده می‌شود و این هوک نیاز دارد کامپوننتش فرزند یک `ReactFlowProvider` باشد؛ اگر `Canvas` خودش `ReactFlowProvider` را می‌ساخت، `useReactFlow` در همان کامپوننت کار نمی‌کرد.

---

## `webapp/src/nodes.jsx`

این فایل تعریف بصری و رفتاری هر یک از انواع بلوک (node type) روی بوم را نگه می‌دارد: هم فهرست `BLOCK_DEFS` (که `Palette.jsx` برای نمایش آیتم‌های قابل درگ استفاده می‌کند) و هم کامپوننت‌های React واقعیِ هر گره (که `App.jsx` از طریق `nodeTypes` به `<ReactFlow>` می‌دهد). **این فایل باید همیشه با منطق سمت پایتون در `bot/flow_engine.py` هم‌گام (in sync) بماند** — چون خروجی این فایل (فیلد `type` و `data` هر گره) دقیقاً همان چیزی است که `flow_engine.py` هنگام اجرای واقعیِ ربات تفسیر می‌کند؛ اگر اینجا نوع جدیدی اضافه شود ولی در `flow_engine.py` تعریف نشود، آن بلوک در بوم قابل‌ساخت است اما در اجرای واقعی ربات به‌سادگی نادیده گرفته می‌شود (چون حلقه‌ی `run_flow` فقط `if/elif` برای انواع شناخته‌شده دارد و برای بقیه هیچ کاری نمی‌کند، هرچند از آن گره رد می‌شود).

### `BLOCK_DEFS`
آرایه‌ای ثابت (constant) از تعاریف هفت نوع بلوک؛ هر آیتم `{ type, label, defaultData }` دارد:

1. **`guide_video`** («📖 Guide & Video»، `defaultData: {}`) — معادل بلوک `guide_video` در `flow_engine.py`: یک‌بار شماره‌ی تلفن کاربر را (اختیاری) می‌پرسد، از روی آن کشور را حدس می‌زند، و راهنمای «چطور از ربات استفاده کنید» + لینک ویدیوی آموزشیِ محلی‌سازی‌شده را می‌فرستد. اگر شماره‌ی مشترک هنوز ثبت نشده، حالت FSM را روی `SubscriberOnboardingStates.waiting_for_phone` می‌گذارد و اجرای فلو را همان‌جا متوقف می‌کند تا بعد از پاسخ کاربر ادامه یابد.
2. **`trigger`** («▶️ Trigger»، `defaultData: { command: '/start' }`) — نقطه‌ی ورودِ فلو؛ خودش هرگز «اجرا» نمی‌شود، فقط با دستور ورودی کاربر (مثل `/start`) مطابقت داده می‌شود (`find_trigger_node` در `flow_engine.py`، که نرمال‌سازی case-insensitive و بدون‌نیاز-به-اسلش هم انجام می‌دهد).
3. **`send_message`** («💬 Send Message»، `defaultData: { text: '' }`) — متن `data.text` را مستقیم برای کاربر می‌فرستد.
4. **`force_join_gate`** («🔒 Force Join Gate»، `defaultData: {}`) — بررسی می‌کند کاربر عضو همه‌ی کانال‌های اجباریِ تنظیم‌شده در ابزار «Force Join» چت ربات هست یا نه؛ اگر نه، پیام عضویت را می‌فرستد و همان‌جا متوقف می‌شود.
5. **`content_list`** («📚 Content List»، `defaultData: {}`) — آیتم‌های محتوایی سطح بالا (که از طریق همین بلوک/`ContentManager`، ابزار «Content List» در چت ربات، یا آپلود اکسل مدیریت می‌شوند) را به‌صورت دکمه نشان می‌دهد؛ اگر محتوایی نباشد، بی‌صدا رد می‌شود (skip).
6. **`shop`** («🛍 Shop»، `defaultData: {}`) — محصولات **مستقل** (standalone، یعنی به هیچ `ContentItem`ای وصل نیستند) را با قیمت نشان می‌دهد؛ پرداخت با زرین‌پال یا کارت‌به‌کارت و ارسال/فاکتور به‌صورت خودکار مدیریت می‌شود.
7. **`broadcast`** («📢 Broadcast»، `defaultData: {}`) — فقط یک نشانگر (marker) است؛ ارسال واقعیِ پیام همگانی از ابزار «Broadcast» در چت خود ربات انجام می‌شود، نه از این بلوک.

### `NodeCard({ id, accent, title, children, showTarget = true, showSource = true })`
کامپوننت کمکیِ مشترک (wrapper) که همه‌ی کامپوننت‌های گره از آن استفاده می‌کنند تا ظاهر یکسانی داشته باشند.
- **چه‌کار می‌کند:** `deleteNode` را از `NodeActionsContext` می‌گیرد. یک `div.flow-node` با رنگ حاشیه‌ی چپ برابر `accent` رندر می‌کند؛ شامل (به‌صورت شرطی) یک `Handle` ورودی سمت چپ (`Position.Left`، نوع `target`) و یک `Handle` خروجی سمت راست (`Position.Right`، نوع `source`) از `@xyflow/react`، یک دکمه‌ی حذف (✕) که با کلیک `deleteNode(id)` را صدا می‌زند، عنوان، و `children` دلخواه.
- **Props:** `id` (شناسه‌ی گره، برای پاس دادن به `deleteNode`)، `accent` (رنگ هگز حاشیه)، `title` (متن سربرگ)، `children` (محتوای اختصاصیِ هر نوع بلوک)، `showTarget`/`showSource` (پیش‌فرض true — برای مخفی کردن Handle ورودی یا خروجی در مواردی مثل `TriggerNode` که چون نقطه‌ی شروع است، Handle ورودی ندارد).
- **نکته‌ی کلاس `nodrag`:** دکمه‌ی حذف کلاس `nodrag` دارد — این یک قرارداد خود `@xyflow/react` است که رویدادهای pointer روی عناصر با این کلاس را از منطق «درگ کردن گره» مستثنی می‌کند، تا کلیک روی دکمه به‌جای جابه‌جایی گره باعث حذفش شود.

### `TriggerNode({ id, data })`
- **چه‌کار می‌کند:** `updateNodeData` را از context می‌گیرد و یک `<input>` (کلاس `nodrag` تا تایپ کردن باعث درگ‌شدن گره نشود) نمایش می‌دهد که مقدارش `data.command || ''` است؛ با هر تغییر، `updateNodeData(id, { command: e.target.value })` صدا زده می‌شود. `showTarget={false}` چون تریگر ورودی ندارد. یک راهنمای متنی («Any command, e.g. /start, /menu, /help») هم نشان می‌دهد.
- **ارتباط با بک‌اند:** مقدار `command` دقیقاً همان چیزی است که `_normalize_command` در `flow_engine.py` با پیام ورودی کاربر مقایسه می‌کند.

### `SendMessageNode({ id, data })`
- **چه‌کار می‌کند:** مشابه بالا اما با `<textarea>` برای `data.text`، از طریق `updateNodeData(id, { text: e.target.value })`.

### `ForceJoinGateNode({ id })`
- **چه‌کار می‌کند:** هیچ ورودی تعاملی ندارد (بدون `data` استفاده‌شده) — فقط یک توضیح ثابت نمایش می‌دهد. تنظیمات واقعیِ کانال‌های اجباری جای دیگری (ابزار «Force Join» در چت ربات) مدیریت می‌شود، نه این گره.

### `GuideVideoNode({ id })`
- **چه‌کار می‌کند:** مشابه بالا، فقط توضیح؛ بدون فیلد ورودی.

### `ContentListNode({ id })`
- **چه‌کار می‌کند:** `openContentManager` را از context می‌گیرد؛ توضیح ثابت + یک دکمه‌ی «🛠 Manage Content» که با کلیک، `openContentManager()` را صدا می‌زند — که در `App.jsx` باعث باز شدن overlay کامپوننت `ContentManager` می‌شود.

### `ShopNode({ id })` و `BroadcastNode({ id })`
- **چه‌کار می‌کند:** هر دو فقط توضیح ثابت نمایش می‌دهند؛ بدون state یا تعامل اضافه.

### `nodeTypes`
یک شیء map از نام نوع بلوک به کامپوننتش (`{ trigger: TriggerNode, send_message: SendMessageNode, ... }`) که مستقیماً به prop `nodeTypes` کامپوننت `<ReactFlow>` در `App.jsx` داده می‌شود؛ این نگاشت است که به react-flow می‌گوید هر گره با `type` مشخص را با کدام کامپوننت React رندر کند.

---

## `webapp/src/Palette.jsx`

این فایل نوار ابزار کناری/نواری (سایدبار روی دسکتاپ، نوار افقی قابل‌اسکرول روی موبایل — طبق `App.css`) را پیاده می‌کند که هفت بلوکِ `BLOCK_DEFS` را نشان می‌دهد و امکان کشیدن (drag) هرکدام به داخل بوم را فراهم می‌کند.

### چرا Pointer Events خام به‌جای HTML5 Drag-and-Drop API
کد به‌صراحت (در کامنت‌های خودش) توضیح می‌دهد: Telegram Mini App‌ها اغلب داخل webview موبایل تلگرام اجرا می‌شوند، جایی که رویدادهای بومیِ HTML5 Drag-and-Drop (مثل `dragstart`, `dragover`, `drop`) اصلاً fire نمی‌شوند — این API صرفاً برای درگ با ماوس روی مرورگرهای دسکتاپ طراحی شده و پشتیبانی لمسی (touch) استانداردی ندارد. به همین دلیل، `Palette.jsx` کاملاً به `pointerdown`/`pointermove`/`pointerup`/`pointercancel` (رویدادهای Pointer Events که هم ماوس، هم قلم، و هم لمس را پوشش می‌دهند) متکی است و خودش منطق «درگ» را از صفر پیاده‌سازی می‌کند: یک شیء وضعیت (`dragging` state) با مختصات فعلی نگه می‌دارد و یک عنصر «ghost» شناور (`div.palette-ghost`) را زیر انگشت/نشانگر رندر می‌کند تا بازخورد بصری بدهد، و در نهایت با `pointerup` مختصات نهایی را به `onDropBlock` (که `App.jsx` به‌صورت `handleDropBlock` پاس داده) می‌فرستد.

### الگوریتم تشخیص «اسکرول افقی در برابر درگ عمودی» (`DECISION_THRESHOLD`)
روی موبایل، `Palette` یک نوار **افقی** قابل‌اسکرول است (`touch-action: pan-x` در CSS، که فقط اسکرول افقیِ بومی را به مرورگر واگذار می‌کند و اسکرول عمودی/pinch را برای Palette.jsx باز می‌گذارد). وقتی یک لمس (touch) روی یک آیتم بلوک شروع می‌شود، ابهام وجود دارد: آیا کاربر می‌خواهد نوار را افقی اسکرول کند یا بلوک را به‌صورت عمودی به‌سمت بوم بکشد؟ کد این ابهام را با یک «تصمیم به‌تأخیرافتاده» (deferred decision) حل می‌کند:

1. ثابت `DECISION_THRESHOLD = 6` (پیکسل) تعریف شده — حداقل جابه‌جایی لازم قبل از تصمیم‌گیری.
2. برای پوینترهای **لمسی** (`event.pointerType === 'touch'`)، حالت اولیه `mode = 'pending'` است (نه بلافاصله درگ). برای پوینترهای **ماوس/قلم**، حالت بلافاصله `'dragging'` می‌شود و `startDragging` فوراً صدا زده می‌شود — چون توضیح داده شده که ماوس/قلم هرگز ژست اسکرول لمسیِ بومی مرورگر را فعال نمی‌کند، و چون در دسکتاپ Palette یک نوار **عمودی کناری** است (طبق CSS) که درگ کردن به‌سمت بوم (که در سمت راستش قرار دارد) خودش حرکتی **افقی** است — اگر منتظر تصمیم‌گیری می‌ماند، این حرکت افقی اشتباهاً به‌عنوان «اسکرول» تعبیر می‌شد و درگ اصلاً شروع نمی‌شد.
3. در `onMove`، وقتی `mode === 'pending'` است:
   - `dx` و `dy` نسبت به نقطه‌ی شروع (`startX`, `startY`) محاسبه می‌شود.
   - اگر هر دوی `|dx|` و `|dy|` هنوز از `DECISION_THRESHOLD` کمتر باشند، هیچ تصمیمی گرفته نمی‌شود (حرکت خیلی کوچک است، شاید فقط لرزش انگشت).
   - وقتی حرکت از آستانه عبور کرد: اگر `|dy| <= |dx|` (حرکت غالباً افقی یا مساوی)، `mode = 'scrolling'` می‌شود، `cleanup()` صدا زده می‌شود (یعنی listenerهای pointermove/pointerup/pointercancel حذف می‌شوند) و کنترل کامل به مرورگر برای اسکرول بومی افقی واگذار می‌شود — دیگر هیچ کد جاوااسکریپتی این ژست را دنبال نمی‌کند.
   - در غیر این صورت (`|dy| > |dx|`، یعنی حرکت غالباً عمودی)، `startDragging(e.clientX, e.clientY)` صدا زده می‌شود و از این لحظه به بعد `mode = 'dragging'` است.
4. وقتی `mode === 'dragging'` است، هر `onMove` باعث `e.preventDefault()` (جلوگیری از رفتار پیش‌فرض مرورگر مثل اسکرول صفحه) و به‌روزرسانی مختصات ghost می‌شود.

### `Palette({ onDropBlock })`
کامپوننت اصلی export-شده به‌صورت پیش‌فرض.
- **Props:** `onDropBlock(blockType, clientX, clientY)` — callback‌ای که `App.jsx` پاس می‌دهد و در پایان یک درگِ موفق صدا زده می‌شود.
- **State‌ها:** `dragging` (state React، برای رندر مجدد و نمایش ghost) و `draggingRef` (یک `useRef` موازی که همان مقدار را نگه می‌دارد؛ چون داخل closureهای event listener مثل `onMove`/`onUp` که خارج از چرخه‌ی رندر React اجرا می‌شوند، خواندن مستقیم `dragging` state ممکن است مقدار «بسته‌شده‌ی قدیمی» (stale closure) را بدهد؛ `ref` همیشه مقدار به‌روز را برمی‌گرداند).

### `onPointerDown(event, block)`
- **چه‌کار می‌کند:** برای هر آیتم Palette، با شروع pointerdown صدا زده می‌شود.
  - `isTouch` را از `event.pointerType` تشخیص می‌دهد؛ `mode` را بر این اساس اولیه‌سازی می‌کند (توضیح در بخش بالا).
  - `cleanup()` را تعریف می‌کند که سه listener سراسری (`window`) را حذف می‌کند: `pointermove` → `onMove`، `pointerup` → `onUp`، `pointercancel` → `onCancel`. این listenerها روی `window` (نه روی خود عنصر) ثبت می‌شوند تا حرکت پوینتر حتی وقتی بیرون از محدوده‌ی آیتم Palette (مثلاً روی بوم) می‌رود هم دنبال شود.
  - `startDragging(x, y)` یک شیء `{ type: block.type, label: block.label, x, y }` می‌سازد، در `draggingRef.current` و `dragging` state ذخیره می‌کند.
  - `onUp(e)`: اگر `mode === 'dragging'` بود، مقدار نهاییِ `draggingRef.current` را می‌گیرد، `draggingRef`/`dragging` را پاک می‌کند (null)، و اگر مقداری وجود داشت `onDropBlock(finished.type, e.clientX, e.clientY)` را صدا می‌زند — یعنی مختصات نهاییِ رهاسازی مستقیماً از رویداد `pointerup` گرفته می‌شود، نه از `draggingRef`. سپس `cleanup()`.
  - `onCancel()`: (مثلاً وقتی سیستم‌عامل ژست را قطع می‌کند — تماس تلفنی، اعلان، و غیره) درگ را بدون فراخوانی `onDropBlock` لغو می‌کند.
- **موارد خاص/edge case:**
  - اگر کاربر روی یک آیتم لمسی بزند و بلافاصله (بدون حرکت کافی) رها کند، `mode` هنوز `'pending'` است، پس در `onUp` شرط `mode === 'dragging'` false است و هیچ drop‌ای رخ نمی‌دهد (تپ ساده بدون اثر — چون بلوکی هم برای «تپ برای اضافه کردن» تعریف نشده).
  - اگر حرکت به‌سمت اسکرول تشخیص داده شود (`mode = 'scrolling'`)، دیگر `onUp` هرگز صدا زده نمی‌شود چون `cleanup()` قبلاً listenerها را حذف کرده — درست است، چون کنترل کامل به مرورگر واگذار شده.

### رندر (JSX)
یک `<aside className="palette">` شامل عنوان، لیست `BLOCK_DEFS.map` که هر کدام یک `div.palette-item` با `onPointerDown={(e) => onPointerDown(e, block)}` است، یک راهنمای متنی، و در صورت وجود `dragging`، یک `div.palette-ghost` که با `style={{ left: dragging.x, top: dragging.y }}` دقیقاً زیر پوینتر شناور می‌ماند و برچسب بلوک را نشان می‌دهد.

### ارتباط با فایل‌های دیگر
`BLOCK_DEFS` را از `nodes.jsx` می‌گیرد (منبع واحد حقیقت برای انواع بلوک). خروجی نهایی‌اش (`onDropBlock`) مستقیماً به `handleDropBlock` در `App.jsx` می‌رود که با `screenToFlowPosition` مختصات را تبدیل و گره‌ی جدید می‌سازد. هیچ ارتباط مستقیمی با بک‌اند ندارد.

---

## `webapp/src/FlowContext.js`

فایل بسیار کوچکی که فقط یک React Context تعریف می‌کند:

```js
export const NodeActionsContext = createContext({
  updateNodeData: () => {},
  deleteNode: () => {},
  openContentManager: () => {},
})
```

### `NodeActionsContext`
- **چه‌کار می‌کند:** یک context با مقدار پیش‌فرض شامل سه تابع no-op (خالی) که در `App.jsx` توسط `Canvas` با مقادیر واقعی (`updateNodeData`, `deleteNode`, `openContentManager`) پر می‌شود و در `nodes.jsx` توسط `useContext(NodeActionsContext)` مصرف می‌شود.
- **چرا این context لازم است (به‌جای پاس دادن props):** کامنت بالای فایل دلیل معماری را دقیق توضیح می‌دهد: چون `data` هر گره باید کاملاً **plain و JSON-serializable** بماند — چرا که همین `data` بدون تغییر مستقیماً در بدنه‌ی درخواست `POST /api/flow` (در `handleSave` ی `App.jsx`) به‌صورت JSON سریالایز می‌شود — نمی‌توان تابع callback (که JSON.stringify نمی‌تواند سریالایزش کند) را داخل `data` گره ذخیره کرد. به‌جای آن، `NodeActionsContext` این عملیات‌ها را بیرون از `data` نگه می‌دارد و کامپوننت‌های گره از طریق context به آن‌ها دسترسی می‌گیرند.
- **مقدار پیش‌فرض توابع خالی:** برای زمانی است که (نظری) یک کامپوننت گره خارج از `NodeActionsContext.Provider` رندر شود (مثلاً در تست‌های ایزوله) تا به‌جای خطای `undefined is not a function` بی‌صدا هیچ کاری نکند.

---

## `webapp/src/ContentManager.jsx`

این فایل پنل مدیریت محتوای «Content List» را پیاده می‌سازد — یک overlay مودال (modal) که از روی گره‌ی `ContentListNode` باز می‌شود و امکان افزودن، ویرایش، جابه‌جایی بین دسته‌بندی‌ها، و حذف آیتم‌های محتوا (خبر/محصول/درس و غیره) را می‌دهد. تمام این آیتم‌ها در جدول واقعیِ دیتابیس (`ContentItem`) ذخیره می‌شوند — نه بخشی از `flow_definition` JSON — و از طریق `/api/content` با بک‌اند در ارتباط‌اند.

### مدل «پوشه بر اساس وجود فرزند» و تابع `groupByParent(items)`
این بخش دقیقاً معادل منطق `bot/content_nav.py` پیاده‌سازی شده است. در این مدل، هیچ فیلد جداگانه‌ای مثل `is_folder` وجود ندارد؛ اینکه یک آیتم «پوشه» (folder) است یا «برگ» (leaf) صرفاً از روی این استنباط می‌شود که آیا آیتم دیگری `parent_id`اش به این آیتم اشاره می‌کند یا نه — دقیقاً همان الگویی که `bot/content_nav.py` در توضیح بالای فایلش می‌گوید: *«An item with children is a "folder" ... inferred from whether children exist, no separate flag needed»* و تابع `folder_ids_among` در همان فایل هم دقیقاً همین کار را در سمت پایتون انجام می‌دهد (پرس‌وجویی که مجموعه‌ی والدهایی که حداقل یک فرزند دارند را برمی‌گرداند).

```js
function groupByParent(items) {
  const map = new Map()
  for (const item of items) {
    const key = item.parent_id ?? null
    if (!map.has(key)) map.set(key, [])
    map.get(key).push(item)
  }
  return map
}
```

- **چه‌کار می‌کند:** یک `Map` می‌سازد که کلیدش `parent_id` (یا `null` برای سطح بالا) و مقدارش آرایه‌ای از آیتم‌های همان والد است. `item.parent_id ?? null` تضمین می‌کند اگر `parent_id` مقدار `undefined` یا `null` باشد، هر دو زیر کلید یکسان `null` گروه‌بندی شوند (نه این‌که `undefined` و `null` دو کلید متفاوت در Map ایجاد کنند).
- **چرا این تابع کلیدی است:** `ContentManager` (کامپوننت اصلی) این map را با `useMemo(() => groupByParent(items), [items])` می‌سازد؛ سپس `roots = byParent.get(null) || []` آیتم‌های سطح بالا را می‌گیرد، و `TreeNode` (زیر) با گرفتن `byParent.get(item.id) || []` به‌صورت بازگشتی فرزندان هر گره را پیدا می‌کند. در `TreeNode`، شرط `children.length > 0 ? '📁' : '📌'` دقیقاً همان قانون «اگر فرزند دارد پوشه است» را در UI پیاده می‌کند — کاملاً معادل نمایش 📂 در `bot/keyboards.py: content_menu_keyboard` که از `folder_ids_among` استفاده می‌کند.

### `ItemForm({ initial, onCancel, onSubmit, submitLabel, showCode })`
فرم مشترکِ افزودن/ویرایش یک آیتم محتوا.
- **State:** `form` (شیء فرم، مقدار اولیه از prop `initial`)، `error` (پیام خطای اعتبارسنجی یا خطای سرور)، `saving` (بولین در حین ارسال).
- **`set(key)`/`setChecked(key)`:** دو تابع کارخانه (factory) که یک event handler برمی‌گردانند تا فیلد متناظر در `form` را به‌روزرسانی کنند (کنترل‌شده/controlled inputs).
- **`submit()`:**
  - اگر `form.title.trim()` خالی باشد، `error = 'Title is required.'` و متوقف می‌شود — تنها اعتبارسنجیِ سمت کلاینت.
  - `saving = true`، سپس `await onSubmit(form)` (که از والد، مثلاً `createContent` یا `updateContent`، پاس داده شده) را صدا می‌زند؛ در صورت خطا (مثلاً کد تکراری از بک‌اند با status 409) پیام `err.message` را نمایش می‌دهد؛ در نهایت `saving = false`.
- **فیلدها:** `title` (اجباری)، `body` (textarea)، `image_url`، `link_url`، و در صورت `showCode` بودن یک فیلد `code` (فقط هنگام افزودن آیتم جدید نمایش داده می‌شود — `showCode={false}` هنگام ویرایش، چون کد شورتکات پس از ساخت آیتم قابل تغییر از این فرم نیست). یک چک‌باکس `is_premium`؛ اگر تیک خورده باشد، یک فیلد عددی `unlock_price` («قیمت خرید تک‌آیتمی به تومان، خالی = استفاده از پیش‌فرض ربات») نمایش داده می‌شود.
- **ارتباط با بک‌اند:** فیلد‌های `is_premium`/`unlock_price` مستقیماً با `_premium_fields` در `bot/webapp_server.py` و منطق `bot/premium_content.py` (که در کامنت‌های `webapp_server.py` اشاره شده) هم‌خوان‌اند.

### `GroupPicker({ item, items, onCancel, onSubmit })`
پنل جابه‌جایی یک آیتم بین دسته‌بندی‌ها (reparent).
- **State:** `target` (رشته؛ یا `'top'` یا `String(item.parent_id)`) که با `<select>` کنترل می‌شود، `error`, `saving`.
- **`options`:** همه‌ی `items` **به‌جز خود `item`** (`items.filter((i) => i.id !== item.id)`) — این جلوگیریِ سطحیِ اول از انتخاب خودِ آیتم به‌عنوان والدش است؛ اما جلوگیری از **حلقه‌های عمیق‌تر** (مثلاً انتخاب یکی از نوه‌های خودش به‌عنوان والد) در این کامپوننت انجام نمی‌شود — آن اعتبارسنجی کاملاً سمت بک‌اند در `bot/content_nav.py: would_cycle` انجام می‌شود که با پیمایش زنجیره‌ی والدها تا ۵۰ سطح، هر حلقه‌ای را رد می‌کند و `reparent_item` در آن صورت `False` برمی‌گرداند؛ `update_content` در `webapp_server.py` این `False` را به خطای HTTP 400 با پیام `"invalid parent (cycle, or not in this bot)"` تبدیل می‌کند که همان `err.message` در `submit()` نمایش داده می‌شود.
- **`submit()`:** `onSubmit(target === 'top' ? null : Number(target))` را صدا می‌زند — یعنی مقدار `'top'` به `null` (سطح بالا، بدون دسته) ترجمه می‌شود.

### `TreeNode({ item, depth, byParent, activePanel, setActivePanel, items, refresh })`
گره‌ی بازگشتیِ درخت محتوا — قلب رندر UI درختی.
- **`children`:** `byParent.get(item.id) || []`.
- **`isEditing`/`isGrouping`:** بر اساس `activePanel` (یک state سراسری در `ContentManager` به‌شکل `null | {type, id}`) تعیین می‌کنند آیا فرم ویرایش یا انتخاب گروه برای همین آیتم باز باشد.
- **`del()`:** ابتدا `window.confirm('Delete "..."؟ This cannot be undone.')` می‌پرسد (تنها جایی در کل مجموعه که پیش از حذف تأییدیه می‌گیرد — برخلاف حذف گره/یال در بوم که بدون تأیید انجام می‌شود). در صورت تأیید، `deleteContent(item.id)` را صدا می‌زند و `refresh()` می‌کند؛ در خطا `window.alert(err.message)`.
  - **ارتباط با بک‌اند:** `delete_content` در `webapp_server.py` اگر آیتم فرزند داشته باشد، حذف را با خطای 409 («has sub-items — delete those first») رد می‌کند — یعنی حذف فقط برای برگ‌ها مجاز است؛ `del()` در کلاینت این محدودیت را تکرار نمی‌کند، صرفاً پیام خطای سرور را با `alert` نشان می‌دهد.
- **رندر ردیف:** آیکون 📁/📌 بر اساس `children.length`، آیکون 🔒 اگر `is_premium`، برچسب `code` (اگر موجود)، برچسب قیمت (اگر premium و `unlock_price` دارد، با `Number(...).toLocaleString()` برای جداکننده‌ی هزارگان)، و سه دکمه: ✏️ (باز کردن ویرایش)، 🔀 (باز کردن انتخاب گروه)، 🗑 (حذف).
- **بخش `isEditing`:** یک `ItemForm` با `showCode={false}` رندر می‌کند؛ در `onSubmit`، `updateContent(item.id, {...})` را با تمام فیلدهای فرم (و تبدیل `unlock_price` خالی/غیر-premium به `null`) صدا می‌زند، سپس `activePanel` را می‌بندد و `refresh()` می‌کند.
- **بخش `isGrouping`:** یک `GroupPicker` رندر می‌کند؛ `onSubmit` مقدار `parentId` را به `reparentContent(item.id, parentId)` می‌فرستد.
- **بازگشتی:** برای هر `child` در `children`، یک `TreeNode` دیگر با `depth: depth + 1` رندر می‌کند (فاصله‌ی تورفتگی با `style={{ marginLeft: depth * 18 }}` در CSS اِعمال می‌شود) — پیمایش عمیق‌اول (depth-first) کل درخت.

### `ContentManager({ onClose })`
کامپوننت اصلی export-شده‌ی پیش‌فرض؛ overlay مودال کل مدیریت محتوا.
- **State:** `items` (آرایه‌ی مسطح همه‌ی آیتم‌ها، دقیقاً همان چیزی که `listContent()` برمی‌گرداند — بدون هیچ ساختار درختی از سمت سرور؛ درخت‌سازی کاملاً سمت کلاینت با `groupByParent` انجام می‌شود)، `status` (پیام وضعیت)، `activePanel` (`null | {type:'edit'|'group', id} | {type:'add'}`).
- **`refresh()`:** یک تابع async که `listContent()` (`GET /api/content`) را صدا می‌زند، `items` را ست می‌کند، `status` را پاک می‌کند؛ در خطا `Failed to load: ...`. این تابع پس از **هر** عملیات نوشتنی (add/edit/reparent/delete) دوباره صدا زده می‌شود تا کل درخت از سرور تازه‌سازی شود — به‌جای به‌روزرسانیِ خوش‌بینانه‌ی (optimistic) محلی؛ ساده‌تر و کمتر مستعد ناهم‌خوانی است، هرچند هر عملیات یک رفت‌وبرگشت شبکه‌ی اضافه دارد.
- **`useEffect`:** با mount شدن، `refresh()` را یک‌بار صدا می‌زند.
- **`byParent`/`roots`:** با `useMemo` روی `items` محاسبه می‌شوند (توضیح داده‌شده در بخش `groupByParent` بالا).
- **رندر:** یک `div.cm-overlay` تمام‌صفحه شامل `div.cm-panel` با هدر (عنوان + دکمه‌ی بستن ✕ که `onClose` را صدا می‌زند — `onClose` از `App.jsx` می‌آید و `managingContent` را به `false` برمی‌گرداند)، یک نوار ابزار با دکمه‌ی «➕ Add Item» (که `activePanel = {type: 'add'}` می‌کند)، و در صورت `activePanel?.type === 'add'` یک `ItemForm` با `showCode` (چون فقط هنگام افزودن، تعیین کد شورتکات مجاز است). بدنه‌ی اصلی وضعیت (`status`)، پیام «هنوز محتوایی نیست» (اگر `roots.length === 0`)، یا لیست `roots.map(item => <TreeNode .../>)` را رندر می‌کند.
- **افزودن آیتم (`onSubmit` فرم add):** `createContent({...})` را با همه‌ی فیلدهای فرم صدا می‌زند (شامل `code: form.code || null`)، سپس `refresh()`.

### ارتباط با بک‌اند و سایر فایل‌ها
- تمام توابع شبکه (`listContent`, `createContent`, `updateContent`, `deleteContent`, `reparentContent`) از `telegram.js` import شده‌اند.
- مسیرهای `/api/content` در `bot/webapp_server.py` هندلرهای `list_content`, `create_content`, `update_content`, `delete_content` را پیاده می‌کنند؛ همگی از `_authenticated_bot` عبور می‌کنند و در نهایت `sync_bot_commands` را (به‌جز `list_content`) صدا می‌زنند تا اگر دستور جدیدی به لیست دستورهای ربات اضافه/حذف شده باشد به‌روز شود.
- عملیات `upsert_item`, `reparent_item`, `get_item` در `bot/content_nav.py` منطق دیتابیسی واقعی (شامل جلوگیری از حلقه با `would_cycle`) را انجام می‌دهند.
- از `App.jsx` باز/بسته می‌شود: `ContentListNode` (در `nodes.jsx`) دکمه‌ی «🛠 Manage Content» دارد که `openContentManager` (از `NodeActionsContext`) را صدا می‌زند و `Canvas` در `App.jsx` با `managingContent` state این کامپوننت را شرطی رندر می‌کند.

---

## `webapp/src/telegram.js`

این فایل «چسبِ» بین SDK جاوااسکریپتیِ Telegram Mini App (`window.Telegram.WebApp`) و بک‌اند خودِ اپلیکیشن (`/api/flow` و `/api/content` در `bot/webapp_server.py`) است. طبق کامنت بالای فایل، دکمه‌ی «WebAppInfo» در ربات این صفحه را با آدرس ``${WEBAPP_URL}?bot_id=<uuid>`` باز می‌کند.

### `getTelegram()`
- **چه‌کار می‌کند:** `window.Telegram?.WebApp ?? null` را برمی‌گرداند — شیء SDK تلگرام، یا `null` اگر صفحه خارج از تلگرام (مثلاً مستقیم در مرورگر عادی، برای دیباگ) باز شده باشد. استفاده از optional chaining (`?.`) تضمین می‌کند اگر `window.Telegram` اصلاً تعریف نشده باشد (اسکریپت SDK لود نشده)، خطا پرتاب نشود.

### `getBotId()`
- **چه‌کار می‌کند:** با `new URLSearchParams(window.location.search).get('bot_id')`، مقدار پارامتر `bot_id` را از query string فعلیِ URL صفحه می‌خواند و برمی‌گرداند (یا `null` اگر وجود نداشته باشد).
- **ارتباط:** این همان `bot_id`ای است که دکمه‌ی «Visual Builder» در ربات هنگام باز کردن Mini App به URL اضافه می‌کند؛ `App.jsx` در `useEffect` بارگذاری، وجودش را چک می‌کند و اگر نباشد، بدون فراخوانی API پیام خطا نشان می‌دهد. همچنین `apiRequest` (زیر) این مقدار را در هر درخواست به query string می‌فرستد و بک‌اند از آن برای پیدا کردن `BuiltBot` مربوطه استفاده می‌کند.

### `getInitData()`
- **چه‌کار می‌کند:** `getTelegram()?.initData ?? ''` — رشته‌ی خام `initData` که Telegram SDK به‌صورت امضاشده (signed) در اختیار Mini App قرار می‌دهد و شامل اطلاعات کاربر تلگرام + یک هش HMAC است. اگر SDK در دسترس نباشد، رشته‌ی خالی برمی‌گردد.

### `initTelegramApp()`
- **چه‌کار می‌کند:** `getTelegram()` را می‌گیرد؛ اگر `null` بود (خارج از تلگرام باز شده)، بی‌صدا برمی‌گردد. در غیر این صورت `tg.ready()` (اعلام آماده بودن Mini App به کلاینت تلگرام، که باعث می‌شود splash screen را کنار بزند) و `tg.expand()` (تلاش برای بازکردن Mini App در حالت تمام‌صفحه/بزرگ‌ترین ارتفاع ممکن) را صدا می‌زند.
- **جای فراخوانی:** فقط یک‌بار، در `useEffect` کامپوننت `App` (در `App.jsx`).

### `apiRequest(path, method, body)`
تابع پایه‌ی داخلی (نه export شده) که همه‌ی توابع دیگرِ این فایل روی آن ساخته شده‌اند.
- **چه‌کار می‌کند:**
  1. `botId = getBotId()` را می‌گیرد.
  2. با `fetch` درخواستی به ``${path}?bot_id=${encodeURIComponent(botId ?? '')}`` می‌زند — یعنی **حتی اگر `botId` نال باشد**، درخواست همچنان با `bot_id=` (خالی) ارسال می‌شود؛ اعتبارسنجی نبودِ `bot_id` عملاً در بک‌اند رخ می‌دهد (`_authenticated_bot` که اگر `request.query.get("bot_id")` خالی/غایب باشد، `None` برمی‌گرداند و هندلر پاسخ 401 می‌دهد) — چون `App.jsx` از قبل جلوی این حالت را با چک `getBotId()` در `useEffect` گرفته، عملاً این مسیر کمتر پیموده می‌شود اما با این حال fallback درستی دارد.
  3. **هدر `X-Telegram-Init-Data`:** روی هر درخواست (چه GET چه POST/PUT/DELETE) این هدر با مقدار `getInitData()` تنظیم می‌شود — این همان رشته‌ی خام initData است که بک‌اند (`bot/webapp_auth.py: validate_init_data`) با یک الگوریتم HMAC-SHA256 دقیقاً طبق مستندات رسمی تلگرام اعتبارسنجی می‌کند: امضا را با `secret_key = HMAC-SHA256(key=b"WebAppData", msg=bot_token)` و سپس `HMAC-SHA256(key=secret_key, msg=data_check_string)` بازمحاسبه و با `hmac.compare_digest` (مقایسه‌ی زمان‌ثابت در برابر timing attack) با هش دریافتی مقایسه می‌کند؛ همچنین `auth_date` را چک می‌کند که بیش از ۲۴ ساعت (`MAX_AGE_SECONDS`) قدیمی نباشد تا از replay attack با یک initData قدیمیِ افشاشده جلوگیری شود. اگر initData نامعتبر/منقضی/خالی باشد، `_authenticated_bot` در `webapp_server.py` مقدار `None` برمی‌گرداند و همه‌ی هندلرهای API پاسخ `401 {"error": "unauthorized"}` می‌دهند.
  4. `Content-Type: application/json` همیشه تنظیم می‌شود؛ `body` فقط اگر مقدار داشته باشد `JSON.stringify` می‌شود (برای GET/DELETE بدون بدنه، `body` مقدار `undefined` می‌ماند).
  5. **مدیریت خطا:** اگر `res.ok` نبود (status خارج از 200-299)، تلاش می‌کند بدنه‌ی پاسخ را به‌عنوان JSON بخواند (`res.json().catch(() => ({}))` — اگر بدنه JSON معتبر نبود یا اصلاً بدنه‌ای نبود، به شیء خالی fallback می‌کند تا خواندن `detail.error` خطا ندهد)، سپس یک `Error` جدید پرتاب می‌کند با پیام `detail.error` (اگر بک‌اند پیام خطای دقیق فرستاده باشد، مثل `"title is required"` یا `"code \"...\" is already in use"`) یا در غیر این صورت پیام عمومیِ ``Request failed (${res.status})``.
  6. در موفقیت، `res.json()` را برمی‌گرداند (یک Promise که با بدنه‌ی JSON پاسخ resolve می‌شود).
- **الگوی مصرف در سراسر کد:** همه‌ی توابع بالادستی (`loadFlow`, `saveFlow`, `listContent`, ...) این خطاها را با `.catch` یا `try/catch` می‌گیرند و `err.message` را مستقیماً در UI (نوار `status`، یا `error` فرم‌ها) نمایش می‌دهند — یعنی متن خطای سمت پایتون معمولاً بدون تغییر تا چشم کاربر نهایی می‌رسد.

### `loadFlow()` و `saveFlow(flow)`
- **چه‌کار می‌کند:** `loadFlow` یک `apiRequest('/api/flow', 'GET')` است؛ `saveFlow(flow)` یک `apiRequest('/api/flow', 'POST', flow)` است.
- **ارتباط با بک‌اند:** به‌ترتیب `get_flow` (که `flow_definition` بات را برمی‌گرداند، یا `{"nodes": [], "edges": []}` اگر هنوز چیزی ذخیره نشده) و `save_flow` (که بدنه را اعتبارسنجی — باید dict با `nodes` و `edges` باشد — و در دیتابیس ذخیره می‌کند، سپس `sync_bot_commands` صدا می‌زند) در `webapp_server.py`.

### `listContent()`, `createContent(fields)`, `updateContent(id, fields)`, `deleteContent(id)`, `reparentContent(id, parentId)`
- **چه‌کار می‌کند:** پنج wrapper نازک روی `apiRequest` برای عملیات CRUD روی `/api/content`:
  - `listContent()` → `GET /api/content`
  - `createContent(fields)` → `POST /api/content`
  - `updateContent(id, fields)` → `PUT /api/content/${id}`
  - `deleteContent(id)` → `DELETE /api/content/${id}`
  - `reparentContent(id, parentId)` → `PUT /api/content/${id}` با بدنه‌ی `{ parent_id: parentId }` — یعنی جابه‌جایی دسته صرفاً یک فراخوانیِ خاص از همان اندپوینت آپدیت است، نه اندپوینت جداگانه.
- **کامنت مهم بالای این بخش:** توضیح می‌دهد چرا محتوا (بر خلاف `flow_definition`) یک جدول واقعیِ دیتابیس است نه بخشی از blob جریان: چون هم ویزارد چت ربات و هم این پنل Mini App مستقیماً همان جدول را می‌خوانند/می‌نویسند، «هرکدام آخرین‌بار استفاده شده، به‌سادگی همان state فعلی است» — نیازی به هیچ‌گونه reconciliation (آشتی‌دادنِ) بین دو منبع نیست.
- **ارتباط با بک‌اند:** این پنج تابع به‌ترتیب با `list_content`, `create_content`, `update_content`, `delete_content` در `webapp_server.py` مطابقت دارند (`reparentContent` هم از همان `update_content` عبور می‌کند)، که همگی در نهایت از توابع `bot/content_nav.py` (`upsert_item`, `reparent_item`, `get_item`) استفاده می‌کنند.
