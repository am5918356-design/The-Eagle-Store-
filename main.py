import os
from datetime import datetime
from urllib.parse import quote
from flask import Flask, render_template, request, redirect, url_for, session, abort, Response, send_from_directory
from jinja2 import DictLoader
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "change-this-secret-text"

# مجلد حفظ صور المنتجات
UPLOAD_FOLDER = os.path.join(app.root_path, "static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# ========== إعدادات المتجر والأدمن (عدّل هنا) ==========
BRAND = "The Eagle Store"
WHATSAPP = "201094608364"  # رقم الواتساب الخاص بك لتلقي الطلبات
ADMIN_PASSWORD = "123456"  # كلمة السر الخاصة بصفحة الأدمن

# ----- التوصيل -----
FAST = ("القاهرة ", "القليوبية")  # المحافظات اللي توصيلها FEE_FAST
FEE_FAST = 60  # توصيل القاهرة والقليوبية
FEE_OTHER = 70  # توصيل باقي المحافظات
GOVERNORATES = ["القاهرة", "القليوبية", "الجيزة", "الإسكندرية", "الدقهلية", "البحيرة", "الفيوم", "الغربية",
                "الإسماعيلية", "المنوفية", "المنيا", "الوادي الجديد", "السويس", "أسوان", "أسيوط", "بني سويف",
                "بورسعيد", "دمياط", "الشرقية", "جنوب سيناء", "كفر الشيخ", "مطروح", "الأقصر", "قنا",
                "شمال سيناء", "سوهاج", "البحر الأحمر"]


def delivery_fee(gov):
    return FEE_FAST if gov in FAST else FEE_OTHER


CATEGORIES = {
    "jackets": {"name": "جواكت", "icon": "🧥", "color": "#2f3f66", "sizes": ["M", "L", "XL", "2XL", "3XL"],
                "products": [("جاكيت بومبر", 1450, 10, [])]},
    "pants": {"name": "بناطيل", "icon": "👖", "color": "#3d4f45", "sizes": [30, 32, 34, 36, 38],
              "products": [("بنطلون جينز", 750, 15, [])]},
    "tshirts": {"name": "تيشرتات", "icon": "👕", "color": "#6a5a2f", "sizes": ["M", "L", "XL", "2XL", "3XL"],
                "products": [("تيشرت أساسي", 320, 20, [])]},
    "shoes": {"name": "جزم", "icon": "👟", "color": "#5a3d3d", "sizes": [40, 41, 42, 43, 44, 45],
              "products": [("كوتشي سنيكرز", 1350, 8, [])]},
}
# ===============================================

PRODUCTS = {}


def refresh_products():
    global PRODUCTS
    PRODUCTS = {}
    for cat_id, cat in CATEGORIES.items():
        for number, item in enumerate(cat["products"], start=1):
            name, price = item[0], item[1]
            stock = item[2] if len(item) > 2 and item[2] is not None else 10
            images = item[3] if len(item) > 3 and item[3] is not None else []

            pid = f"{cat_id}-{number}"
            PRODUCTS[pid] = {
                "id": pid, "cat": cat_id, "name": name, "price": price, "model": number,
                "icon": cat["icon"], "color": cat["color"], "sizes": cat["sizes"], "stock": stock, "images": images
            }


refresh_products()


def get_cart():
    return session.get("cart", {})


def cart_lines():
    lines, total = [], 0
    for key, qty in get_cart().items():
        pid, size = key.split("|")
        p = PRODUCTS.get(pid)
        if not p:
            continue
        line_total = p["price"] * qty
        total += line_total
        img = p["images"][0] if p["images"] and len(p["images"]) > 0 else None
        lines.append({
            "key": key, "pid": pid, "cat": p["cat"], "name": p["name"], "size": size, "qty": qty,
            "price": p["price"], "line_total": line_total, "image": img, "color": p["color"], "icon": p["icon"]
        })
    return lines, total


@app.context_processor
def common():
    has_logo = os.path.exists(os.path.join(app.root_path, "logo.png"))
    return {"brand": BRAND, "cart_count": sum(get_cart().values()), "has_logo": has_logo}


@app.route("/")
def index():
    return render_template("home.html", categories=CATEGORIES)


@app.route("/category/<cat_id>")
def category(cat_id):
    cat = CATEGORIES.get(cat_id)
    if not cat:
        abort(404)
    products = [p for p in PRODUCTS.values() if p["cat"] == cat_id]
    return render_template("category.html", products=products, cat=cat)


@app.route("/add", methods=["POST"])
def add():
    pid = request.form.get("product_id")
    size = request.form.get("size")
    # إذا لم يتم اختيار مقاس (مثل الاقتراحات السريعة)، نختار أول مقاس متاح تلقائياً
    p = PRODUCTS.get(pid)
    if p:
        if not size and p["sizes"]:
            size = str(p["sizes"][0])

        if size in [str(s) for s in p["sizes"]]:
            cart = get_cart()
            key = f"{pid}|{size}"
            cart[key] = cart.get(key, 0) + 1
            session["cart"] = cart
    return redirect(request.referrer or url_for("index"))


@app.route("/cart")
def cart():
    lines, total = cart_lines()

    # محرك الذكاء الاصطناعي لاقتراح قطع تكملة الطقم بناءً على ما يوجد في العربة
    cart_categories = {l["cat"] for l in lines}
    ai_suggestions = []

    # لو العميل مختار جاكيت أو تيشرت، نقترح عليه بنطلون أو جزمة لتكملة الطقم
    for p in PRODUCTS.values():
        if p["cat"] not in cart_categories:
            ai_suggestions.append(p)
            if len(ai_suggestions) >= 2:  # عرض اقتراحين كحد أقصى
                break

    return render_template("cart.html", lines=lines, total=total, govs=GOVERNORATES,
                           fee_fast=FEE_FAST, fee_other=FEE_OTHER, fast=FAST, form={}, error="",
                           ai_suggestions=ai_suggestions)


@app.route("/order", methods=["POST"])
def order():
    lines, total = cart_lines()
    if not lines:
        return redirect(url_for("cart"))
    form = {k: request.form.get(k, "").strip() for k in ("name", "phone", "address", "gov")}
    error = ""
    if not form["name"] or not form["address"]:
        error = "اكتب الاسم والعنوان."
    elif not (form["phone"].isdigit() and len(form["phone"]) == 11):
        error = "رقم التليفون لازم يكون 11 رقم."
    elif form["gov"] not in GOVERNORATES:
        error = "اختار المحافظة."
    if error:
        return render_template("cart.html", lines=lines, total=total, govs=GOVERNORATES,
                               fee_fast=FEE_FAST, fee_other=FEE_OTHER, fast=FAST, form=form, error=error)
    fee = delivery_fee(form["gov"])
    grand = total + fee
    order_id = datetime.now().strftime("%y%m%d%H%M%S")

    items_list = [f"- {l['name']} (مقاس {l['size']}) × {l['qty']} = {l['line_total']} ج.م" for l in lines]

    orders_path = os.path.join(app.root_path, "orders.txt")
    with open(orders_path, "a", encoding="utf-8") as f:
        f.write(
            f"{order_id}***{form['name']}***{form['phone']}***{form['gov']}***{form['address']}***{total}***{fee}***{grand}***" + "|||".join(
                items_list) + "\n")

    text = (f"طلب جديد #{order_id} من {BRAND}\nالاسم: {form['name']}\nالتليفون: {form['phone']}\n"
            f"المحافظة: {form['gov']}\nالعنوان: {form['address']}\n\nالمنتجات:\n" + "\n".join(items_list) + f"\n\n"
                                                                                                            f"مجموع المنتجات: {total} ج.م\nالتوصيل: {fee} ج.م\nالإجمالي: {grand} ج.م")

    session["cart"] = {}
    wa_link = f"https://wa.me/{WHATSAPP}?text={quote(text)}"
    return render_template("thanks.html", order_id=order_id, text=text, wa_link=wa_link)


@app.route("/change", methods=["POST"])
def change():
    key = request.form.get("key")
    delta = int(request.form.get("delta", "0"))
    cart = get_cart()
    if key in cart:
        cart[key] += delta
        if cart[key] < 1:
            del cart[key]
        session["cart"] = cart
    return redirect(url_for("cart"))


@app.route("/remove", methods=["POST"])
def remove():
    key = request.form.get("key")
    cart = get_cart()
    if key in cart:
        del cart[key]
        session["cart"] = cart
    return redirect(url_for("cart"))


# ================= نظام تسجيل الدخول للأدمن =================
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = ""
    if request.method == "POST":
        password = request.form.get("password", "")
        if password == ADMIN_PASSWORD:
            session["is_admin"] = True
            return redirect(url_for("admin"))
        else:
            error = "كلمة السر غير صحيحة!"
    return render_template("admin_login.html", error=error)


@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("index"))


@app.route("/admin", methods=["GET", "POST"])
def admin():
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))

    msg = ""
    orders_path = os.path.join(app.root_path, "orders.txt")

    if request.method == "POST":
        action = request.form.get("action")

        if action == "delete":
            cat_id = request.form.get("cat_id")
            index = int(request.form.get("index"))
            if cat_id in CATEGORIES and 0 <= index < len(CATEGORIES[cat_id]["products"]):
                CATEGORIES[cat_id]["products"].pop(index)
                refresh_products()
                msg = "تم حذف المنتج بنجاح!"

        elif action == "edit":
            cat_id = request.form.get("cat_id")
            index = int(request.form.get("index"))
            name = request.form.get("name", "").strip()
            price = request.form.get("price", "").strip()
            stock = request.form.get("stock", "10").strip()

            if cat_id in CATEGORIES and 0 <= index < len(CATEGORIES[cat_id]["products"]) and name and price.isdigit():
                old_item = CATEGORIES[cat_id]["products"][index]
                old_images = old_item[3] if len(old_item) > 3 else []

                uploaded_images = list(old_images)
                if "images" in request.files:
                    files = request.files.getlist("images")
                    for file in files:
                        if file and file.filename != "":
                            filename = secure_filename(file.filename)
                            image_filename = datetime.now().strftime("%Y%m%d%H%M%S_") + filename
                            file.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))
                            uploaded_images.append(image_filename)

                stock_val = int(stock) if stock.isdigit() else 10
                CATEGORIES[cat_id]["products"][index] = (name, int(price), stock_val, uploaded_images)
                refresh_products()
                msg = "تم تعديل المنتج بنجاح!"
            else:
                msg = "خطأ في تعديل البيانات، تأكد من إدخال اسم وسعر صحيحين."

        elif action == "delete_order":
            order_id_to_delete = request.form.get("order_id")
            if os.path.exists(orders_path):
                with open(orders_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                with open(orders_path, "w", encoding="utf-8") as f:
                    for line in lines:
                        if not line.startswith(order_id_to_delete + "***"):
                            f.write(line)
                msg = f"تم حذف الطلب #{order_id_to_delete} بنجاح!"

        elif action == "add":
            cat_id = request.form.get("cat_id")
            name = request.form.get("name", "").strip()
            price = request.form.get("price", "").strip()
            stock = request.form.get("stock", "10").strip()

            uploaded_images = []
            if "images" in request.files:
                files = request.files.getlist("images")
                for file in files:
                    if file and file.filename != "":
                        filename = secure_filename(file.filename)
                        image_filename = datetime.now().strftime("%Y%m%d%H%M%S_") + filename
                        file.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))
                        uploaded_images.append(image_filename)

            if cat_id in CATEGORIES and name and price.isdigit():
                stock_val = int(stock) if stock.isdigit() else 10
                CATEGORIES[cat_id]["products"].append((name, int(price), stock_val, uploaded_images))
                refresh_products()
                msg = "تم إضافة المنتج مع الكمية والصور بنجاح!"
            else:
                msg = "خطأ في البيانات, تأكد من كتابة الاسم والسعر بشكل صحيح."

    parsed_orders = []
    if os.path.exists(orders_path):
        with open(orders_path, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split("***")
                if len(parts) >= 9:
                    parsed_orders.append({
                        "id": parts[0],
                        "name": parts[1],
                        "phone": parts[2],
                        "gov": parts[3],
                        "address": parts[4],
                        "total": parts[5],
                        "fee": parts[6],
                        "grand": parts[7],
                        "items_list": parts[8].split("|||")
                    })
        parsed_orders.reverse()

    return render_template("admin.html", categories=CATEGORIES, products=PRODUCTS, orders=parsed_orders, msg=msg)


@app.route("/logo.png")
def logo():
    return send_from_directory(app.root_path, "logo.png")


@app.route("/style.css")
def style():
    return Response(CSS, mimetype="text/css")


# ================= الصفحات (HTML) =================
app.jinja_loader = DictLoader({
    "base.html": """<!doctype html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ brand }}</title>
<link rel="stylesheet" href="/style.css">
</head>
<body>
<header>
  <span></span>
  <a class="brand" href="/">{{ brand }}</a>
  <a class="cartbtn" href="/cart">العربة <i>{{ cart_count }}</i></a>
</header>
{% block content %}{% endblock %}
</body>
</html>""",
    "home.html": """{% extends "base.html" %}
{% block content %}
<section class="hero">
  {% if has_logo %}<img class="logo-img" src="/logo.png" alt="{{ brand }}">{% endif %}
</section>
<main class="boxes">
  {% for cid, c in categories.items() %}
  <a class="box" href="/category/{{ cid }}" style="background: {{ c.color }}"><span>{{ c.icon }}</span>{{ c.name }}</a>
  {% endfor %}
</main>
{% endblock %}""",
    "category.html": """{% extends "base.html" %}
{% block content %}
<div class="pagehead"><h2>{{ cat.name }}</h2><a class="back" href="/">الرئيسية</a></div>
<main>
  <div class="grid">
    {% for p in products %}
    <article class="card">
      {% if p.images and p.images|length > 0 %}
      <div class="tile" style="padding:0; background: #f8f9fa; cursor:pointer; position:relative;" onclick="openModal('{{ url_for('static', filename='uploads/' + p.images[0]) }}', '{{ p.name }}')">
        <img src="{{ url_for('static', filename='uploads/' + p.images[0]) }}" alt="{{ p.name }}" style="width:100%; height:150px; object-fit:contain;" title="اضغط لتكبير الصورة">
        {% if p.images|length > 1 %}
        <span style="position:absolute; bottom:5px; right:5px; background:rgba(0,0,0,0.7); color:#fff; font-size:0.75rem; padding:2px 6px; border-radius:4px;">+{{ p.images|length - 1 }} صور</span>
        {% endif %}
      </div>
      {% else %}
      <div class="tile" style="background: {{ p.color }}"><span>{{ p.icon }}</span><b>موديل {{ p.model }}</b></div>
      {% endif %}
      <form class="bd" method="post" action="/add">
        <h3>{{ p.name }}</h3>
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <div class="pr">{{ p.price }} ج.م</div>
          <small style="color: var(--mut);">المخزون: {{ p.stock }}</small>
        </div>

        {% if p.images and p.images|length > 1 %}
        <div style="display: flex; gap: 5px; margin-top: 5px; overflow-x: auto;">
          {% for img in p.images %}
          <img src="{{ url_for('static', filename='uploads/' + img) }}" style="width: 35px; height: 35px; object-fit: cover; border-radius: 4px; cursor: pointer; border: 1px solid var(--ln);" onclick="event.stopPropagation(); openModal('{{ url_for('static', filename='uploads/' + img) }}', '{{ p.name }}')">
          {% endfor %}
        </div>
        {% endif %}

        <input type="hidden" name="product_id" value="{{ p.id }}">
        <div class="sz">
          {% for s in p.sizes %}
          <label class="chip"><input type="radio" name="size" value="{{ s }}" required><span>{{ s }}</span></label>
          {% endfor %}
        </div>
        <button class="add" type="submit">أضف للعربة</button>
      </form>
    </article>
    {% endfor %}
  </div>
</main>

<div id="imgModal" class="modal" onclick="closeModal()">
  <span class="close">&times;</span>
  <img class="modal-content" id="img01">
  <div id="caption"></div>
</div>

<script>
function openModal(src, name) {
  var modal = document.getElementById("imgModal");
  var modalImg = document.getElementById("img01");
  var captionText = document.getElementById("caption");
  modal.style.display = "block";
  modalImg.src = src;
  captionText.innerHTML = name;
}
function closeModal() {
  document.getElementById("imgModal").style.display = "none";
}
</script>
{% endblock %}""",
    "cart.html": """{% extends "base.html" %}
{% block content %}
<main class="cartpage">
  <h2>عربة الشراء</h2>
  {% if lines %}
    {% for l in lines %}
    <div class="ln" style="display: flex; align-items: center; gap: 12px; padding: 12px 0; border-bottom: 1px solid var(--ln);">
      {% if l.image %}
        <img src="{{ url_for('static', filename='uploads/' + l.image) }}" alt="{{ l.name }}" style="width: 55px; height: 55px; object-fit: contain; border-radius: 8px; background: #f8f9fa; border: 1px solid var(--ln);">
      {% else %}
        <div style="width: 55px; height: 55px; border-radius: 8px; background: {{ l.color }}; display: flex; align-items: center; justify-content: center; font-size: 1.5rem; color: #fff;">{{ l.icon }}</div>
      {% endif %}

      <div style="flex: 1;">
        <strong>{{ l.name }}</strong><br><small style="color: var(--mut);">مقاس {{ l.size }} · {{ l.price }} ج.م</small>
      </div>
      <form method="post" action="/remove" style="margin:0;"><input type="hidden" name="key" value="{{ l.key }}"><button class="x" aria-label="حذف">✕</button></form>
      <form class="qty" method="post" action="/change" style="margin:0;">
        <input type="hidden" name="key" value="{{ l.key }}">
        <button name="delta" value="-1" aria-label="أقل">−</button><span>{{ l.qty }}</span><button name="delta" value="1" aria-label="أكتر">+</button>
      </form>
      <div class="lt" style="min-width: 70px; text-align: end; font-weight: 600;">{{ l.line_total }} ج.م</div>
    </div>
    {% endfor %}

    <!-- 🤖 أداة الذكاء الاصطناعي لاقتراح تكملة الطقم -->
    {% if ai_suggestions %}
    <div style="background: var(--sf); border: 2px dashed var(--ac); padding: 15px; border-radius: 12px; margin: 20px 0;">
      <h3 style="font-size: 1.1rem; color: var(--ac); margin-bottom: 10px; display: flex; align-items: center; gap: 6px;">
        <span>✨</span> خبير الموضة (AI Stylist): اقترحنا ليك القطع دي عشان تكمل بيها طقمك!
      </h3>
      <div style="display: flex; flex-direction: column; gap: 10px;">
        {% for s in ai_suggestions %}
        <div style="display: flex; align-items: center; justify-content: space-between; background: var(--bg); padding: 10px; border-radius: 8px; border: 1px solid var(--ln);">
          <div style="display: flex; align-items: center; gap: 10px;">
            {% if s.images and s.images|length > 0 %}
              <img src="{{ url_for('static', filename='uploads/' + s.images[0]) }}" style="width: 45px; height: 45px; object-fit: contain; border-radius: 6px; background: #fff;">
            {% else %}
              <div style="width: 45px; height: 45px; border-radius: 6px; background: {{ s.color }}; display: flex; align-items: center; justify-content: center; color:#fff;">{{ s.icon }}</div>
            {% endif %}
            <div>
              <strong>{{ s.name }}</strong><br><span style="font-size: 0.9rem; color: var(--ac); font-weight: bold;">{{ s.price }} ج.م</span>
            </div>
          </div>
          <form method="post" action="/add" style="margin: 0;">
            <input type="hidden" name="product_id" value="{{ s.id }}">
            <button type="submit" style="background: var(--ac); color: var(--acx); border: 0; padding: 6px 12px; border-radius: 6px; font-weight: bold; font-size: 0.85rem;">إضافة للطقم +</button>
          </form>
        </div>
        {% endfor %}
      </div>
    </div>
    {% endif %}

    <div class="tot"><span>مجموع المنتجات</span><span>{{ total }} ج.م</span></div>
    <h2>بيانات الطلب</h2>
    {% if error %}<p class="err">{{ error }}</p>{% endif %}
    <form class="order" method="post" action="/order">
      <label>الاسم<input name="name" value="{{ form.get('name', '') }}" required></label>
      <label>رقم التليفون<input name="phone" inputmode="numeric" value="{{ form.get('phone', '') }}" required></label>
      <label>المحافظة
        <select name="gov" id="gov" required>
          <option value="" data-fee="">اختار المحافظة</option>
          {% for g in govs %}<option value="{{ g }}" data-fee="{{ fee_fast if g in fast else fee_other }}" {{ 'selected' if form.get('gov') == g }}>{{ g }}</option>{% endfor %}
        </select>
      </label>
      <label>العنوان بالتفصيل<textarea name="address" rows="3" required>{{ form.get('address', '') }}</textarea></label>
      <div class="tot"><span>سعر التوصيل</span><span id="fee">اختار المحافظة</span></div>
      <div class="tot"><span>الإجمالي</span><span id="grand">{{ total }} ج.م</span></div>
      <button class="go" type="submit">تأكيد الطلب</button>
    </form>
    <script>
      var SUB = {{ total }};
      var sel = document.getElementById("gov");
      function upd() {
        var f = sel.options[sel.selectedIndex].getAttribute("data-fee");
        document.getElementById("fee").textContent = f ? f + " ج.م" : "اختار المحافظة";
        document.getElementById("grand").textContent = (SUB + (f ? parseInt(f) : 0)) + " ج.م";
      }
      sel.addEventListener("change", upd);
      upd();
    </script>
  {% else %}
    <p class="empty">العربة فاضية. اختار مقاس وأضف منتج.</p>
  {% endif %}
  <p><a class="back" href="/">كمّل تسوق</a></p>
</main>
{% endblock %}""",
    "thanks.html": """{% extends "base.html" %}
{% block content %}
<main class="cartpage">
  <h2>تم تسجيل طلبك بنجاح!</h2>
  <p>رقم الطلب: {{ order_id }}</p>
  <pre class="sum">{{ text }}</pre>
  <p>جاري تحويل تفاصيل الطلب واتساب إلى هاتفك تلقائياً...</p>
  <a class="go" href="{{ wa_link }}" id="wa-btn">فتح واتساب يدوياً</a>
  <p><a class="back" href="/">الرئيسية</a></p>
  <script>
    setTimeout(function() {
      window.location.href = "{{ wa_link }}";
    }, 1000);
  </script>
</main>
{% endblock %}""",
    "admin_login.html": """{% extends "base.html" %}
{% block content %}
<main class="cartpage" style="max-width:400px; margin-top: 40px;">
  <h2>تسجيل دخول الأدمن</h2>
  {% if error %}<p class="err">{{ error }}</p>{% endif %}
  <form class="order" method="post">
    <label>كلمة السر
      <input type="password" name="password" required placeholder="أدخل كلمة السر">
    </label>
    <button class="go" type="submit" style="margin-top: 15px;">دخول</button>
  </form>
</main>
{% endblock %}""",
    "admin.html": """{% extends "base.html" %}
{% block content %}
<main class="cartpage" style="max-width: 850px;">
  <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
    <h2>لوحة تحكم الأدمن</h2>
    <a href="/admin/logout" style="color: #d33; text-decoration: none; font-weight: bold;">تسجيل الخروج 🚪</a>
  </div>

  {% if msg %}<p style="background: var(--ac); color: var(--acx); padding: 10px; border-radius: 8px;">{{ msg }}</p>{% endif %}

  <!-- إضافة منتج جديد -->
  <div style="background: var(--sf); border: 1px solid var(--ln); padding: 20px; border-radius: 12px; margin-bottom: 25px;">
    <h3>إضافة منتج جديد (مع الكمية وصور متعددة)</h3>
    <form class="order" method="post" enctype="multipart/form-data">
      <input type="hidden" name="action" value="add">
      <label>القسم
        <select name="cat_id" required>
          {% for cid, c in categories.items() %}
          <option value="{{ cid }}">{{ c.icon }} {{ c.name }}</option>
          {% endfor %}
        </select>
      </label>
      <label>اسم المنتج<input name="name" placeholder="مثال: جاكيت كلاسيك" required></label>
      <label>السعر (بالجنيه)<input name="price" type="number" placeholder="مثال: 1500" required></label>
      <label>الكمية في المخزن<input name="stock" type="number" placeholder="مثال: 10" value="10" required></label>
      <label>صور المنتج (اختر أكثر من صورة معاً)
        <input type="file" name="images" accept="image/*" multiple style="padding: 6px;">
      </label>
      <button class="go" type="submit" style="margin-top: 15px;">حفظ وإضافة المنتج</button>
    </form>
  </div>

  <!-- إدارة وتعديل المنتجات الحالية -->
  <div style="background: var(--sf); border: 1px solid var(--ln); padding: 20px; border-radius: 12px; margin-bottom: 25px;">
    <h3>إدارة وتعديل المنتجات الحالية</h3>
    <div style="display: flex; flex-direction: column; gap: 15px; margin-top: 15px; max-height: 400px; overflow-y: auto; padding-right: 5px;">
      {% for pid, p in products.items() %}
      <div style="background: var(--bg); padding: 15px; border-radius: 8px; border: 1px solid var(--ln);">
        <form method="post" enctype="multipart/form-data" style="display: flex; flex-direction: column; gap: 8px; margin: 0;">
          <input type="hidden" name="action" value="edit">
          <input type="hidden" name="cat_id" value="{{ p.cat }}">
          <input type="hidden" name="index" value="{{ p.model - 1 }}">

          <div style="display: flex; justify-content: space-between; align-items: center;">
            <strong>تعديل: {{ p.name }}</strong>
            <small style="color: var(--mut);">القسم: {{ categories[p.cat].name }}</small>
          </div>

          <div style="display: grid; grid-template-columns: 2fr 1fr 1fr; gap: 10px;">
            <label style="font-size: 0.85rem; margin:0;">الاسم: <input name="name" value="{{ p.name }}" required style="padding: 6px; font-size: 0.9rem;"></label>
            <label style="font-size: 0.85rem; margin:0;">السعر: <input name="price" type="number" value="{{ p.price }}" required style="padding: 6px; font-size: 0.9rem;"></label>
            <label style="font-size: 0.85rem; margin:0;">المخزون: <input name="stock" type="number" value="{{ p.stock }}" required style="padding: 6px; font-size: 0.9rem;"></label>
          </div>

          <label style="font-size: 0.85rem; margin:0;">إضافة صور جديدة للمنتج: 
            <input type="file" name="images" accept="image/*" multiple style="padding: 4px; font-size: 0.85rem;">
          </label>

          <div style="display: flex; justify-content: flex-end; gap: 10px; margin-top: 5px;">
            <button type="submit" style="background: var(--ac); color: var(--acx); border: 0; padding: 6px 14px; border-radius: 6px; font-weight: bold; font-size: 0.85rem;">حفظ التعديلات ✏️</button>
          </div>
        </form>

        <form method="post" style="margin-top: 5px; text-align: left;">
          <input type="hidden" name="action" value="delete">
          <input type="hidden" name="cat_id" value="{{ p.cat }}">
          <input type="hidden" name="index" value="{{ p.model - 1 }}">
          <button type="submit" style="background: #d33; color: #fff; border: 0; padding: 4px 10px; border-radius: 6px; font-size: 0.8rem; font-weight: bold;">حذف المنتج ❌</button>
        </form>
      </div>
      {% endfor %}
    </div>
  </div>

  <!-- سجل الطلبات الواردة -->
  <div style="background: var(--sf); border: 1px solid var(--ln); padding: 20px; border-radius: 12px;">
    <h3>الطلبات الواردة (سجل الطلبات)</h3>
    {% if orders %}
      <div style="display: flex; flex-direction: column; gap: 15px; margin-top: 15px; max-height: 500px; overflow-y: auto; padding-left: 5px;">
        {% for o in orders %}
        <div style="background: var(--bg); border: 1px solid var(--ln); border-radius: 10px; padding: 15px;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; border-bottom: 1px solid var(--ln); padding-bottom: 6px;">
            <span style="font-weight: bold;">🛒 طلب رقم: #{{ o.id }}</span>
            <div style="display: flex; align-items: center; gap: 10px;">
              <span style="color: var(--ac); font-weight: bold;">الإجمالي: {{ o.grand }} ج.م</span>
              <form method="post" style="margin: 0;">
                <input type="hidden" name="action" value="delete_order">
                <input type="hidden" name="order_id" value="{{ o.id }}">
                <button type="submit" style="background: #d33; color: #fff; border: 0; padding: 4px 10px; border-radius: 6px; font-size: 0.85rem; font-weight: bold;">حذف الطلب ❌</button>
              </form>
            </div>
          </div>
          <p style="margin: 4px 0;"><strong>الاسم:</strong> {{ o.name }}</p>
          <p style="margin: 4px 0;"><strong>التليفون:</strong> {{ o.phone }}</p>
          <p style="margin: 4px 0;"><strong>المحافظة:</strong> {{ o.gov }}</p>
          <p style="margin: 4px 0;"><strong>العنوان:</strong> {{ o.address }}</p>
          <div style="margin-top: 8px; background: var(--sf); padding: 8px; border-radius: 6px; border: 1px solid var(--ln);">
            <strong>المنتجات المطلوبة:</strong>
            <ul style="margin: 5px 0 0 20px; padding: 0;">
              {% for item in o.items_list %}
              <li>{{ item }}</li>
              {% endfor %}
            </ul>
          </div>
          <div style="display: flex; justify-content: space-between; font-size: 0.9rem; color: var(--mut); margin-top: 8px;">
            <span>مجموع المنتجات: {{ o.total }} ج.م</span>
            <span>التوصيل: {{ o.fee }} ج.م</span>
          </div>
        </div>
        {% endfor %}
      </div>
    {% else %}
      <p class="empty">لا توجد طلبات مسجلة حتى الآن.</p>
    {% endif %}
  </div>

  <p style="margin-top: 20px;"><a class="back" href="/">العودة للمتجر الرئيسي</a></p>
</main>
{% endblock %}
"""
})

# ================= الشكل (CSS) =================
CSS = """
:root{--bg:#eef0f2;--sf:#fff;--ink:#14171c;--mut:#5d6572;--ln:#d9dde2;--ac:#2b4bff;--acx:#fff;color-scheme:light}
@media (prefers-color-scheme:dark){:root{--bg:#101216;--sf:#181b21;--ink:#f1f2f4;--mut:#9aa3b0;--ln:#2a2f38;--ac:#7b8fff;--acx:#10131a;color-scheme:dark}}
*,*::before,*::after{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:Tahoma,"Segoe UI",Arial,sans-serif;line-height:1.6}
body::before{content:"";position:fixed;inset:0;background:url("/logo.png") center / min(560px,85vw) no-repeat;opacity:.1;pointer-events:none;z-index:-1}
button{font:inherit;color:inherit;cursor:pointer}
a{color:inherit}
:focus-visible{outline:3px solid var(--ac);outline-offset:2px}
header{position:sticky;top:0;z-index:20;background:var(--sf);border-bottom:1px solid var(--ln);display:grid;grid-template-columns:1fr auto 1fr;align-items:center;padding:12px 20px}
.brand{font-size:1.5rem;font-weight:700;text-decoration:none;letter-spacing:.02em;text-align:center}
.cartbtn{justify-self:end;background:var(--ink);color:var(--bg);border-radius:10px;padding:9px 16px;font-weight:600;text-decoration:none}
.cartbtn i{font-style:normal;background:var(--ac);color:var(--acx);border-radius:99px;padding:1px 8px;margin-inline-start:8px;font-size:.85rem}
main{max-width:1100px;margin:0 auto;padding:16px 20px 60px}
.hero{text-align:center;padding:36px 20px 8px}
.logo-img{width:150px;height:auto}
.boxes{max-width:900px;margin:0 auto;padding:20px 20px 60px;display:grid;grid-template-columns:repeat(3,1fr);gap:18px}
.box{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;min-height:190px;color:#fff;text-decoration:none;border-radius:40px 10px 10px 10px;font-size:1.5rem;font-weight:700}
.box span{font-size:3.2rem;line-height:1}
@media (max-width:620px){.boxes{grid-template-columns:repeat(2,1fr)}}
.pagehead{max-width:1100px;margin:0 auto;padding:22px 20px 0;display:flex;align-items:baseline;gap:16px}
.pagehead h2{margin:0;font-size:1.6rem}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:16px}
.card{background:var(--sf);border:1px solid var(--ln);border-radius:14px;overflow:hidden;display:flex;flex-direction:column}
.tile{height:150px;color:#fff;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px}
-tile span{font-size:3rem;line-height:1}
.tile b{font-weight:400;font-size:.85rem;opacity:.85}
.bd{padding:14px;display:flex;flex-direction:column;gap:10px;flex:1}
h3{margin:0;font-size:1rem;font-weight:600}
.pr{font-weight:700;font-size:1.1rem}
.sz{display:flex;flex-wrap:wrap;gap:6px}
.chip{position:relative}
.chip input{position:absolute;opacity:0;inset:0;margin:0;cursor:pointer}
.chip span{display:block;border:1px solid var(--ln);border-radius:8px;min-width:40px;padding:4px 8px;text-align:center;font-size:.9rem}
.chip input:checked + span{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.chip input:focus-visible + span{outline:3px solid var(--ac);outline-offset:2px}
.add{margin-top:auto;background:var(--ac);color:var(--acx);border:0;border-radius:10px;padding:10px;font-weight:600}
.cartpage{max-width:560px}
.ln{display:grid;grid-template-columns:1fr auto;gap:4px 10px;padding:12px 0;border-bottom:1px solid var(--ln)}
.ln small{color:var(--mut)}
.ln form{margin:0}
.qty{display:flex;align-items:center;gap:8px}
.qty button{width:32px;height:32px;border-radius:8px;border:1px solid var(--ln);background:none}
.lt{text-align:end;font-weight:600}
.x{background:none;border:0;font-size:1.3rem;color:var(--mut)}
.tot{display:flex;justify-content:space-between;font-weight:700;font-size:1.15rem;padding:14px 0}
.go{display:block;text-align:center;text-decoration:none;background:var(--ac);color:var(--acx);border-radius:10px;padding:12px;font-weight:600}
.empty{color:var(--mut);padding:30px 0;text-align:center}
.back{color:var(--mut)}
.cartpage h2{font-size:1.3rem}
.order label{display:block;margin:10px 0 4px;font-weight:600}
.order input,.order select,.order textarea{display:block;width:100%;margin-top:4px;padding:10px;border:1px solid var(--ln);border-radius:8px;background:var(--sf);color:var(--ink);font:inherit;font-weight:400}
.err{color:#d33;font-weight:600}
.sum{white-space:pre-wrap;background:var(--sf);border:1px solid var(--ln);border-radius:10px;padding:12px;font:inherit}
button.go{width:100%;border:0;margin-top:8px;cursor:pointer}

/* تصميم نافذة تكبير الصورة (Modal) */
.modal { display: none; position: fixed; z-index: 100; padding-top: 60px; left: 0; top: 0; width: 100%; height: 100%; overflow: auto; background-color: rgba(0,0,0,0.9); }
.modal-content { margin: auto; display: block; width: 80%; max-width: 700px; max-height: 80vh; object-fit: contain; border-radius: 10px; }
#caption { margin: auto; display: block; width: 80%; max-width: 700px; text-align: center; color: #ccc; padding: 10px 0; font-size: 1.2rem; }
.close { position: absolute; top: 20px; right: 35px; color: #f1f1f1; font-size: 40px; font-weight: bold; transition: 0.3s; cursor: pointer; }
.close:hover, .close:focus { color: #bbb; text-decoration: none; cursor: pointer; }
"""

if __name__ == "__main__":
    app.run(debug=True)