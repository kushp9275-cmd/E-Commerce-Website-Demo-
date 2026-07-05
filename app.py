from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import os
from werkzeug.utils import secure_filename
import razorpay
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your_super_secret_key_here')

# Automatically initialize database and tables on startup
from setup_db import create_database_and_table
db_path = os.path.join(app.root_path, 'mart.db')
create_database_and_table(db_path)

# Razorpay Configuration
RAZORPAY_KEY_ID = os.getenv('RAZORPAY_KEY_ID')
RAZORPAY_KEY_SECRET = os.getenv('RAZORPAY_KEY_SECRET')

if RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET:
    try:
        razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
        print(f"Razorpay initialized with key: {RAZORPAY_KEY_ID[:12]}...")
    except Exception as e:
        razorpay_client = None
        print(f"WARNING: Razorpay client init failed: {e}. Online payments disabled.")
else:
    razorpay_client = None
    print("WARNING: RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET not set. Online payments disabled.")

# File upload setup
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024  # 2MB limit
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

def get_db_connection():
    db_path = os.path.join(app.root_path, 'mart.db')
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row  # This enables dictionary-like access
        return conn
    except sqlite3.Error as err:
        print(f"Error: {err}")
        return None

# ─────────────────────────────────────────────────────────────────────────────
# AUTH ROUTES
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['POST'])
def login():
    email = request.form.get('email')
    password = request.form.get('password')
    
    conn = get_db_connection()
    if not conn:
        flash("Database connection failed", "error")
        return redirect(url_for('home'))

    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    
    if user and check_password_hash(user['password_hash'], password):
        # Enforce selection check: if the user tries to login with a mismatched role option
        requested_role = request.form.get('role', 'User')
        if user['role'] != requested_role:
            cursor.close()
            conn.close()
            flash(f"Account exists, but not as an {requested_role}.", "error")
            return redirect(url_for('home'))

        session['user_id'] = user['id']
        session['username'] = user['username']
        session['role'] = user['role']
        cursor.close()
        conn.close()
        
        if user['role'] == 'Admin':
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('dashboard'))
    else:
        cursor.close()
        conn.close()
        flash("Invalid email or password.", "error")
        return redirect(url_for('home'))

@app.route('/register', methods=['POST'])
def register():
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')
    mobile_no = request.form.get('mobile_no')
    address = request.form.get('address')
    role = request.form.get('role', 'User')
    
    if not username or not email or not password or not mobile_no or not address:
        flash("All fields are required.", "error")
        return redirect(url_for('home'))

    hashed_password = generate_password_hash(password)

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (username, email, password_hash, mobile_no, address, role) VALUES (?, ?, ?, ?, ?, ?)",
            (username, email, hashed_password, mobile_no, address, role)
        )
        conn.commit()
        flash("Registration successful! Please log in.", "success")
    except sqlite3.IntegrityError:
        flash("Email already registered.", "error")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('home'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

# ─────────────────────────────────────────────────────────────────────────────
# DASHBOARD & SEARCH
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash("Please log in to access the dashboard.", "error")
        return redirect(url_for('home'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get user profile pic
    cursor.execute("SELECT profile_pic FROM users WHERE id = ?", (session['user_id'],))
    user_data = cursor.fetchone()
    profile_pic = user_data['profile_pic'] if user_data else 'default_dp.png'
    
    category = request.args.get('category')
    search_query = request.args.get('search', '').strip()
    
    if search_query:
        if category and category != 'All':
            cursor.execute("SELECT * FROM items WHERE category = ? AND (name LIKE ? OR description LIKE ?)", 
                         (category, f'%{search_query}%', f'%{search_query}%'))
        else:
            cursor.execute("SELECT * FROM items WHERE name LIKE ? OR description LIKE ?", 
                         (f'%{search_query}%', f'%{search_query}%'))
    elif category and category != 'All':
        cursor.execute("SELECT * FROM items WHERE category = ?", (category,))
    else:
        cursor.execute("SELECT * FROM items")
    items = cursor.fetchall()
    
    # Get Cart Count
    cursor.execute("SELECT SUM(quantity) as count FROM cart WHERE user_id = ?", (session['user_id'],))
    cart_count = cursor.fetchone()['count'] or 0
    
    # Get distinct categories for filter buttons
    cursor.execute("SELECT DISTINCT category FROM items ORDER BY category")
    categories = [row['category'] for row in cursor.fetchall()]
    
    cursor.close()
    conn.close()
    
    return render_template('dashboard.html', items=items, cart_count=cart_count, 
                         categories=categories, current_category=category or 'All', 
                         profile_pic=profile_pic, search_query=search_query)

# ─────────────────────────────────────────────────────────────────────────────
# PROFILE & USER SETTINGS
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('home'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT username, email, mobile_no, address, profile_pic, created_at FROM users WHERE id = ?", (session['user_id'],))
    user_info = cursor.fetchone()
    
    if not user_info:
        flash("User not found.", "error")
        cursor.close()
        conn.close()
        return redirect(url_for('dashboard'))

    # Convert row to a mutable dict so we can modify fields
    user_dict = dict(user_info)

    if not user_dict['profile_pic']:
        user_dict['profile_pic'] = 'default_dp.png'

    # SQLite returns TIMESTAMP as a plain string — parse it into a datetime object
    if user_dict.get('created_at'):
        try:
            user_dict['created_at'] = datetime.strptime(
                user_dict['created_at'], '%Y-%m-%d %H:%M:%S'
            )
        except (ValueError, TypeError):
            user_dict['created_at'] = None

    # Fetch order history with items
    cursor.execute("""
        SELECT id, total_price, status, order_date, razorpay_order_id, payment_method
        FROM orders
        WHERE user_id = ?
        ORDER BY order_date DESC
    """, (session['user_id'],))
    raw_orders = cursor.fetchall()

    orders = []
    for o in raw_orders:
        o_dict = dict(o)
        if o_dict.get('order_date'):
            try:
                o_dict['order_date'] = datetime.strptime(o_dict['order_date'], '%Y-%m-%d %H:%M:%S')
            except (ValueError, TypeError):
                pass
        
        # Fetch items for this order
        cursor.execute("""
            SELECT oi.item_name, oi.quantity, oi.price_at_time, oi.image_url,
                   (oi.quantity * oi.price_at_time) as subtotal
            FROM order_items oi
            WHERE oi.order_id = ?
        """, (o_dict['id'],))
        o_dict['items'] = [dict(item) for item in cursor.fetchall()]
        orders.append(o_dict)

    cursor.close()
    conn.close()

    total_orders = len(orders)
    total_spent  = sum(o['total_price'] for o in orders if o['status'] not in ('pending', 'cancelled'))
    paid_orders  = sum(1 for o in orders if o.get('payment_method') == 'online' and o['status'] != 'pending')
    cod_orders   = sum(1 for o in orders if o.get('payment_method') == 'cod')

    return render_template('profile.html',
                           user=user_dict,
                           orders=orders,
                           total_orders=total_orders,
                           total_spent=total_spent,
                           paid_orders=paid_orders,
                           cod_orders=cod_orders)

@app.route('/update_profile', methods=['POST'])
def update_profile():
    if 'user_id' not in session:
        return redirect(url_for('home'))
        
    username = request.form.get('username')
    mobile_no = request.form.get('mobile_no')
    address = request.form.get('address')
    
    if not username or not mobile_no or not address:
        flash("All fields are required.", "error")
        return redirect(url_for('profile'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE users 
        SET username = ?, mobile_no = ?, address = ?
        WHERE id = ?
    """, (username, mobile_no, address, session['user_id']))
    conn.commit()
    cursor.close()
    conn.close()
    
    session['username'] = username
    flash("Profile updated successfully!", "success")
    return redirect(url_for('profile'))

@app.route('/upload_dp', methods=['POST'])
def upload_dp():
    if 'user_id' not in session:
        return redirect(url_for('home'))
        
    redirect_target = url_for('admin_dashboard') if session.get('role') == 'Admin' else url_for('dashboard')
        
    if 'dp' not in request.files:
        flash("No file selected.", "error")
        return redirect(redirect_target)
        
    file = request.files['dp']
    if file.filename == '':
        flash("No file selected.", "error")
        return redirect(redirect_target)
        
    if file:
        filename = secure_filename(file.filename)
        ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else 'jpg'
        new_filename = f"user_{session['user_id']}_dp.{ext}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], new_filename))
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET profile_pic = ? WHERE id = ?", (new_filename, session['user_id']))
        conn.commit()
        cursor.close()
        conn.close()
        
        flash("Profile picture updated successfully!", "success")
        
    return redirect(redirect_target)

# ─────────────────────────────────────────────────────────────────────────────
# CART MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/add_to_cart/<int:item_id>', methods=['POST'])
def add_to_cart(item_id):
    if 'user_id' not in session:
        return redirect(url_for('home'))

    quantity = int(request.form.get('quantity', 1))
    if quantity < 1:
        quantity = 1
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check stock
    cursor.execute("SELECT stock FROM items WHERE id = ?", (item_id,))
    item = cursor.fetchone()
    if not item or item['stock'] < 1:
        flash("Item is out of stock!", "error")
        cursor.close()
        conn.close()
        return redirect(url_for('dashboard'))
    
    # Check if item exists in cart already
    cursor.execute("SELECT * FROM cart WHERE user_id = ? AND item_id = ?", (session['user_id'], item_id))
    existing_entry = cursor.fetchone()
    
    if existing_entry:
        new_qty = existing_entry['quantity'] + quantity
        if new_qty > item['stock']:
            new_qty = item['stock']
            flash(f"Quantity adjusted to available stock ({item['stock']}).", "error")
        cursor.execute("UPDATE cart SET quantity = ? WHERE id = ?", (new_qty, existing_entry['id']))
    else:
        if quantity > item['stock']:
            quantity = item['stock']
            flash(f"Quantity adjusted to available stock ({item['stock']}).", "error")
        cursor.execute("INSERT INTO cart (user_id, item_id, quantity) VALUES (?, ?, ?)", (session['user_id'], item_id, quantity))
        
    conn.commit()
    cursor.close()
    conn.close()
    
    flash("Item added to cart!", "success")
    return redirect(url_for('dashboard'))

@app.route('/update_cart/<int:cart_id>', methods=['POST'])
def update_cart(cart_id):
    if 'user_id' not in session:
        return redirect(url_for('home'))
    
    action = request.form.get('action')  # 'increase' or 'decrease'
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Verify this cart item belongs to the user and get stock info
    cursor.execute("""
        SELECT c.*, i.stock FROM cart c 
        JOIN items i ON c.item_id = i.id 
        WHERE c.id = ? AND c.user_id = ?
    """, (cart_id, session['user_id']))
    cart_item = cursor.fetchone()
    
    if not cart_item:
        flash("Cart item not found.", "error")
    else:
        if action == 'increase':
            if cart_item['quantity'] < cart_item['stock']:
                cursor.execute("UPDATE cart SET quantity = quantity + 1 WHERE id = ?", (cart_id,))
            else:
                flash("Cannot exceed available stock.", "error")
        elif action == 'decrease':
            if cart_item['quantity'] > 1:
                cursor.execute("UPDATE cart SET quantity = quantity - 1 WHERE id = ?", (cart_id,))
            else:
                cursor.execute("DELETE FROM cart WHERE id = ?", (cart_id,))
                flash("Item removed from cart.", "success")
    
    conn.commit()
    cursor.close()
    conn.close()
    
    return redirect(url_for('cart'))

@app.route('/remove_from_cart/<int:cart_id>', methods=['POST'])
def remove_from_cart(cart_id):
    if 'user_id' not in session:
        return redirect(url_for('home'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM cart WHERE id = ? AND user_id = ?", (cart_id, session['user_id']))
    conn.commit()
    cursor.close()
    conn.close()
    
    flash("Item removed from cart.", "success")
    return redirect(url_for('cart'))

@app.route('/cart')
def cart():
    if 'user_id' not in session:
        return redirect(url_for('home'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = """
    SELECT c.id as cart_id, c.quantity, i.id as item_id, i.name, i.price, 
           i.image_url, i.stock, (c.quantity * i.price) as subtotal
    FROM cart c 
    JOIN items i ON c.item_id = i.id 
    WHERE c.user_id = ?
    """
    cursor.execute(query, (session['user_id'],))
    cart_items = cursor.fetchall()
    
    total_price = sum(item['subtotal'] for item in cart_items)
    item_count = sum(item['quantity'] for item in cart_items)
    
    cursor.close()
    conn.close()
    
    return render_template('cart.html', cart_items=cart_items, total_price=total_price, item_count=item_count)

# ─────────────────────────────────────────────────────────────────────────────
# CHECKOUT & PAYMENT
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/checkout', methods=['POST'])
def checkout():
    if 'user_id' not in session:
        return redirect(url_for('home'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get user address for delivery
    cursor.execute("SELECT address FROM users WHERE id = ?", (session['user_id'],))
    user_row = cursor.fetchone()
    delivery_address = user_row['address'] if user_row else ''
    
    # Calculate Total & Check Stock
    query = """
    SELECT c.quantity, i.id as item_id, i.name, i.price, i.stock, i.image_url
    FROM cart c 
    JOIN items i ON c.item_id = i.id 
    WHERE c.user_id = ?
    """
    cursor.execute(query, (session['user_id'],))
    cart_items = cursor.fetchall()

    if not cart_items:
        flash("Your cart is empty.", "error")
        cursor.close()
        conn.close()
        return redirect(url_for('dashboard'))

    total_price = sum(item['quantity'] * item['price'] for item in cart_items)

    # Check sufficient stock
    for item in cart_items:
        if item['quantity'] > item['stock']:
            flash(f"Insufficient stock for {item['name']}. Available: {item['stock']}", "error")
            cursor.close()
            conn.close()
            return redirect(url_for('cart'))

    payment_method = request.form.get('payment_method', 'online')

    # ── Cash on Delivery flow ────────────────────────────────────────────
    if payment_method == 'cod':
        try:
            # 1. Record COD order
            cursor.execute("""
                INSERT INTO orders (user_id, total_price, razorpay_order_id, status, payment_method, delivery_address)
                VALUES (?, ?, NULL, 'confirmed', 'cod', ?)
            """, (session['user_id'], total_price, delivery_address))
            order_id = cursor.lastrowid

            # 2. Save order items
            for item in cart_items:
                cursor.execute("""
                    INSERT INTO order_items (order_id, item_id, item_name, quantity, price_at_time, image_url)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (order_id, item['item_id'], item['name'], item['quantity'], item['price'], item['image_url']))

            # 3. Decrement stock
            for item in cart_items:
                cursor.execute(
                    "UPDATE items SET stock = stock - ? WHERE id = ?",
                    (item['quantity'], item['item_id'])
                )

            # 4. Clear cart
            cursor.execute("DELETE FROM cart WHERE user_id = ?", (session['user_id'],))

            conn.commit()
            cursor.close()
            conn.close()

            flash("Order placed successfully! Pay with cash on delivery. 🎉", "success")
            return redirect(url_for('order_detail', order_id=order_id))

        except Exception as e:
            conn.rollback()
            cursor.close()
            conn.close()
            flash(f"Could not place COD order: {str(e)}", "error")
            return redirect(url_for('cart'))

    # ── Online (Razorpay) flow ───────────────────────────────────────────
    # Ensure Razorpay client and credentials are available
    if not razorpay_client or not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
        flash("Online payment is currently unavailable. Please use Cash on Delivery.", "error")
        cursor.close()
        conn.close()
        # Render the payment page with fallback visible
        return render_template('checkout_payment.html',
                               order_id=None,
                               amount=int(total_price * 100),
                               key_id=RAZORPAY_KEY_ID,
                               total_price=total_price,
                               internal_order_id=None,
                               payment_unavailable=True)

    amount_paise = int(total_price * 100)
    data = {
        "amount": amount_paise,
        "currency": "INR",
        "receipt": f"receipt_{session['user_id']}_{int(datetime.now().timestamp())}",
        "payment_capture": 1
    }
    
    try:
        razorpay_order = razorpay_client.order.create(data=data)
        razorpay_order_id = razorpay_order['id']
        
        # Create order record
        cursor.execute("""
            INSERT INTO orders (user_id, total_price, razorpay_order_id, status, payment_method, delivery_address) 
            VALUES (?, ?, ?, 'pending', 'online', ?)
        """, (session['user_id'], total_price, razorpay_order_id, delivery_address))
        order_id = cursor.lastrowid

        # Save order items
        for item in cart_items:
            cursor.execute("""
                INSERT INTO order_items (order_id, item_id, item_name, quantity, price_at_time, image_url)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (order_id, item['item_id'], item['name'], item['quantity'], item['price'], item['image_url']))

        conn.commit()
        cursor.close()
        conn.close()
        
        return render_template('checkout_payment.html', 
                             order_id=razorpay_order_id, 
                             amount=amount_paise, 
                             key_id=RAZORPAY_KEY_ID,
                             total_price=total_price,
                             internal_order_id=order_id,
                             payment_unavailable=False)
                             
    except razorpay.errors.BadRequestError as e:
        print(f"Razorpay BadRequestError: {e}")
        flash("Payment gateway error. Please try again or use Cash on Delivery.", "error")
        cursor.close()
        conn.close()
        return redirect(url_for('cart'))
    except (razorpay.errors.ServerError, razorpay.errors.GatewayError) as e:
        print(f"Razorpay server/gateway error: {e}")
        flash("Payment service is temporarily down. Please try again later or use Cash on Delivery.", "error")
        cursor.close()
        conn.close()
        return redirect(url_for('cart'))
    except Exception as e:
        error_msg = str(e).lower()
        print(f"Razorpay order creation failed: {e}")
        if 'authentication' in error_msg or 'unauthorized' in error_msg or 'auth' in error_msg:
            flash("Online payment is temporarily unavailable due to a configuration issue. Please use Cash on Delivery.", "error")
        else:
            flash(f"Payment gateway error. Please use Cash on Delivery.", "error")
        cursor.close()
        conn.close()
        return redirect(url_for('cart'))

@app.route('/verify_payment', methods=['POST'])
def verify_payment():
    if 'user_id' not in session:
        return redirect(url_for('home'))
        
    payment_id = request.form.get('razorpay_payment_id')
    order_id = request.form.get('razorpay_order_id')
    signature = request.form.get('razorpay_signature')
    
    # Verify the signature
    params_dict = {
        'razorpay_order_id': order_id,
        'razorpay_payment_id': payment_id,
        'razorpay_signature': signature
    }
    
    try:
        razorpay_client.utility.verify_payment_signature(params_dict)
        
        # Payment Successful!
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. Update Order Status to confirmed
        cursor.execute("""
            UPDATE orders 
            SET status = 'confirmed', razorpay_payment_id = ? 
            WHERE razorpay_order_id = ?
        """, (payment_id, order_id))
        
        # 2. Get the internal order id
        cursor.execute("SELECT id FROM orders WHERE razorpay_order_id = ?", (order_id,))
        order_row = cursor.fetchone()
        internal_order_id = order_row['id'] if order_row else None
        
        # 3. Decrease Stock
        cursor.execute("""
            SELECT c.quantity, i.id as item_id 
            FROM cart c 
            JOIN items i ON c.item_id = i.id 
            WHERE c.user_id = ?
        """, (session['user_id'],))
        cart_items = cursor.fetchall()
        
        for item in cart_items:
            cursor.execute("UPDATE items SET stock = stock - ? WHERE id = ?", (item['quantity'], item['item_id']))
            
        # 4. Clear Cart
        cursor.execute("DELETE FROM cart WHERE user_id = ?", (session['user_id'],))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        flash("Payment successful! Your order has been placed. 🎉", "success")
        if internal_order_id:
            return redirect(url_for('order_detail', order_id=internal_order_id))
        return redirect(url_for('dashboard'))
        
    except Exception as e:
        # Verification failed
        flash("Payment verification failed. Please contact support.", "error")
        return redirect(url_for('cart'))

# ─────────────────────────────────────────────────────────────────────────────
# ORDER TRACKING
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/order/<int:order_id>')
def order_detail(order_id):
    if 'user_id' not in session:
        return redirect(url_for('home'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get order — verify it belongs to the user, or user is admin
    if session.get('role') == 'Admin':
        cursor.execute("""
            SELECT o.*, u.username, u.address as user_address, u.mobile_no, u.email 
            FROM orders o 
            JOIN users u ON o.user_id = u.id 
            WHERE o.id = ?
        """, (order_id,))
    else:
        cursor.execute("""
            SELECT o.*, u.username, u.address as user_address, u.mobile_no, u.email 
            FROM orders o 
            JOIN users u ON o.user_id = u.id 
            WHERE o.id = ? AND o.user_id = ?
        """, (order_id, session['user_id']))
    
    order = cursor.fetchone()
    if not order:
        flash("Order not found.", "error")
        cursor.close()
        conn.close()
        return redirect(url_for('profile'))
    
    # Get order items
    cursor.execute("""
        SELECT oi.item_name, oi.quantity, oi.price_at_time, oi.image_url,
               (oi.quantity * oi.price_at_time) as subtotal
        FROM order_items oi 
        WHERE oi.order_id = ?
    """, (order_id,))
    items = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    order_dict = dict(order)
    items_list = [dict(i) for i in items]
    
    # Parse order date
    if order_dict.get('order_date'):
        try:
            order_dict['order_date'] = datetime.strptime(order_dict['order_date'], '%Y-%m-%d %H:%M:%S')
        except (ValueError, TypeError):
            pass
    
    # Define tracking steps
    all_steps = ['confirmed', 'shipped', 'out_for_delivery', 'delivered']
    current_status = order_dict['status']
    
    if current_status == 'pending':
        completed_steps = []
    elif current_status == 'cancelled':
        completed_steps = []
    elif current_status in all_steps:
        idx = all_steps.index(current_status)
        completed_steps = all_steps[:idx + 1]
    else:
        completed_steps = []
    
    return render_template('order_detail.html', 
                         order=order_dict, 
                         order_items=items_list,
                         all_steps=all_steps,
                         completed_steps=completed_steps)

# ─────────────────────────────────────────────────────────────────────────────
# ADMIN ROUTES
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/admin_dashboard')
def admin_dashboard():
    if 'user_id' not in session or session.get('role') != 'Admin':
        flash("Access Denied. Admins only.", "error")
        return redirect(url_for('home'))
        
    category = request.args.get('category', 'All')
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get user profile pic
    cursor.execute("SELECT profile_pic FROM users WHERE id = ?", (session['user_id'],))
    user_data = cursor.fetchone()
    profile_pic = user_data['profile_pic'] if user_data and user_data['profile_pic'] else 'default_dp.png'
    
    if category == 'All':
        cursor.execute("SELECT * FROM items")
        items = cursor.fetchall()
    else:
        cursor.execute("SELECT * FROM items WHERE category = ?", (category,))
        items = cursor.fetchall()
    
    # Get distinct categories for filter if needed
    cursor.execute("SELECT DISTINCT category FROM items ORDER BY category")
    categories = [row['category'] for row in cursor.fetchall()]
    
    # ── Admin Stats ──
    cursor.execute("SELECT COUNT(*) as count FROM orders")
    total_orders_count = cursor.fetchone()['count']

    cursor.execute("SELECT COALESCE(SUM(total_price), 0) as revenue FROM orders WHERE status NOT IN ('pending', 'cancelled')")
    total_revenue = cursor.fetchone()['revenue']

    cursor.execute("SELECT COUNT(*) as count FROM orders WHERE status IN ('confirmed', 'pending')")
    pending_orders_count = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) as count FROM users WHERE role = 'User'")
    total_users = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) as count FROM items")
    total_products = cursor.fetchone()['count']

    # Low stock items count
    cursor.execute("SELECT COUNT(*) as count FROM items WHERE stock < 5")
    low_stock_count = cursor.fetchone()['count']
    
    cursor.close()
    conn.close()
    
    return render_template('admin_dashboard.html', items=items, categories=categories, 
                         profile_pic=profile_pic, current_category=category,
                         total_orders_count=total_orders_count,
                         total_revenue=total_revenue,
                         pending_orders_count=pending_orders_count,
                         total_users=total_users,
                         total_products=total_products,
                         low_stock_count=low_stock_count)

@app.route('/admin/orders')
def admin_orders():
    if 'user_id' not in session or session.get('role') != 'Admin':
        flash("Access Denied.", "error")
        return redirect(url_for('home'))
    
    status_filter = request.args.get('status', 'all')
    
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get profile pic for navbar
    cursor.execute("SELECT profile_pic FROM users WHERE id = ?", (session['user_id'],))
    user_data = cursor.fetchone()
    profile_pic = user_data['profile_pic'] if user_data and user_data['profile_pic'] else 'default_dp.png'
    
    if status_filter == 'all':
        cursor.execute("""
            SELECT o.*, u.username,
                   (SELECT COUNT(*) FROM order_items WHERE order_id = o.id) as item_count
            FROM orders o
            JOIN users u ON o.user_id = u.id
            ORDER BY o.order_date DESC
        """)
    else:
        cursor.execute("""
            SELECT o.*, u.username,
                   (SELECT COUNT(*) FROM order_items WHERE order_id = o.id) as item_count
            FROM orders o
            JOIN users u ON o.user_id = u.id
            WHERE o.status = ?
            ORDER BY o.order_date DESC
        """, (status_filter,))
    
    orders = cursor.fetchall()
    
    # Get counts for filter tabs
    cursor.execute("SELECT COUNT(*) as count FROM orders")
    total_count = cursor.fetchone()['count']
    
    cursor.execute("SELECT status, COUNT(*) as count FROM orders GROUP BY status")
    status_counts = {row['status']: row['count'] for row in cursor.fetchall()}
    status_counts['all'] = total_count
    
    cursor.close()
    conn.close()
    
    orders_list = []
    for o in orders:
        o_dict = dict(o)
        if o_dict.get('order_date'):
            try:
                o_dict['order_date'] = datetime.strptime(o_dict['order_date'], '%Y-%m-%d %H:%M:%S')
            except (ValueError, TypeError):
                pass
        orders_list.append(o_dict)
    
    return render_template('admin_orders.html', orders=orders_list, 
                         status_filter=status_filter, status_counts=status_counts,
                         profile_pic=profile_pic)

@app.route('/admin/order/update_status/<int:order_id>', methods=['POST'])
def admin_update_order_status(order_id):
    if 'user_id' not in session or session.get('role') != 'Admin':
        return redirect(url_for('home'))
    
    new_status = request.form.get('status')
    valid_statuses = ['confirmed', 'shipped', 'out_for_delivery', 'delivered', 'cancelled']
    
    if new_status not in valid_statuses:
        flash("Invalid status.", "error")
        return redirect(url_for('admin_orders'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM orders WHERE id = ?", (order_id,))
    order_row = cursor.fetchone()
    if not order_row:
        cursor.close()
        conn.close()
        flash("Order not found.", "error")
        return redirect(url_for('admin_orders'))
        
    old_status = order_row['status']
    
    # If transitioning to cancelled, restore stock
    if new_status == 'cancelled' and old_status != 'cancelled':
        cursor.execute("SELECT item_id, quantity FROM order_items WHERE order_id = ?", (order_id,))
        for item in cursor.fetchall():
            cursor.execute("UPDATE items SET stock = stock + ? WHERE id = ?", (item['quantity'], item['item_id']))
    # If transitioning from cancelled back to active, decrement stock
    elif new_status != 'cancelled' and old_status == 'cancelled':
        cursor.execute("SELECT item_id, quantity FROM order_items WHERE order_id = ?", (order_id,))
        items = cursor.fetchall()
        for item in items:
            cursor.execute("SELECT name, stock FROM items WHERE id = ?", (item['item_id'],))
            prod = cursor.fetchone()
            if prod and prod['stock'] < item['quantity']:
                cursor.close()
                conn.close()
                flash(f"Cannot update status. Insufficient stock for '{prod['name']}' (Only {prod['stock']} available).", "error")
                return redirect(url_for('admin_orders'))
        for item in items:
            cursor.execute("UPDATE items SET stock = stock - ? WHERE id = ?", (item['quantity'], item['item_id']))
            
    cursor.execute("UPDATE orders SET status = ? WHERE id = ?", (new_status, order_id))
    conn.commit()
    cursor.close()
    conn.close()
    
    flash(f"Order #{order_id} status updated to {new_status.replace('_', ' ').title()}.", "success")
    return redirect(url_for('admin_orders'))

@app.route('/admin/order/delete/<int:order_id>', methods=['POST'])
def admin_delete_order(order_id):
    if 'user_id' not in session or session.get('role') != 'Admin':
        return redirect(url_for('home'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT status FROM orders WHERE id = ?", (order_id,))
    order_row = cursor.fetchone()
    if order_row and order_row['status'] != 'cancelled':
        cursor.execute("SELECT item_id, quantity FROM order_items WHERE order_id = ?", (order_id,))
        for item in cursor.fetchall():
            cursor.execute("UPDATE items SET stock = stock + ? WHERE id = ?", (item['quantity'], item['item_id']))
            
    cursor.execute("DELETE FROM order_items WHERE order_id = ?", (order_id,))
    cursor.execute("DELETE FROM orders WHERE id = ?", (order_id,))
    conn.commit()
    cursor.close()
    conn.close()
    
    flash(f"Order #{order_id} deleted successfully.", "success")
    return redirect(url_for('admin_orders'))

@app.route('/admin/item/add', methods=['POST'])
def add_item():
    if 'user_id' not in session or session.get('role') != 'Admin':
        return redirect(url_for('home'))
        
    name = request.form.get('name')
    description = request.form.get('description')
    price = request.form.get('price')
    image_url = request.form.get('image_url')
    category = request.form.get('category')
    stock = request.form.get('stock')

    # Handle file upload
    if 'item_image' in request.files:
        file = request.files['item_image']
        if file and file.filename != '':
            import time
            filename = secure_filename(file.filename)
            ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else 'jpg'
            new_filename = f"item_{int(time.time())}_{filename}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], new_filename))
            image_url = new_filename # Store local filename
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO items (name, description, price, image_url, category, stock) VALUES (?, ?, ?, ?, ?, ?)",
        (name, description, price, image_url, category, stock)
    )
    conn.commit()
    cursor.close()
    conn.close()
    
    # Sync database to CSV
    from setup_db import sync_db_to_csv
    sync_db_to_csv()
    
    flash("Item added successfully!", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/item/edit/<int:item_id>', methods=['POST'])
def edit_item(item_id):
    if 'user_id' not in session or session.get('role') != 'Admin':
        return redirect(url_for('home'))

    name = request.form.get('name')
    description = request.form.get('description')
    price = request.form.get('price')
    image_url = request.form.get('image_url')
    category = request.form.get('category')
    stock = request.form.get('stock')

    # Handle file upload
    if 'item_image' in request.files:
        file = request.files['item_image']
        if file and file.filename != '':
            import time
            filename = secure_filename(file.filename)
            ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else 'jpg'
            new_filename = f"item_{int(time.time())}_{filename}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], new_filename))
            image_url = new_filename # Override with local filename

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE items SET name=?, description=?, price=?, image_url=?, category=?, stock=? WHERE id=?",
        (name, description, price, image_url, category, stock, item_id)
    )
    conn.commit()
    cursor.close()
    conn.close()

    # Sync database to CSV
    from setup_db import sync_db_to_csv
    sync_db_to_csv()

    flash("Item updated successfully!", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/item/delete/<int:item_id>', methods=['POST'])
def delete_item(item_id):
    if 'user_id' not in session or session.get('role') != 'Admin':
        return redirect(url_for('home'))

    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if item is in cart and remove it first (foreign key constraint)
    cursor.execute("DELETE FROM cart WHERE item_id=?", (item_id,))
    cursor.execute("DELETE FROM items WHERE id=?", (item_id,))
    conn.commit()
    cursor.close()
    conn.close()

    # Sync database to CSV
    from setup_db import sync_db_to_csv
    sync_db_to_csv()

    flash("Item deleted successfully!", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/divisions')
def admin_divisions():
    if 'user_id' not in session or session.get('role') != 'Admin':
        flash("Access Denied. Admins only.", "error")
        return redirect(url_for('home'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get user profile pic
    cursor.execute("SELECT profile_pic FROM users WHERE id = ?", (session['user_id'],))
    user_data = cursor.fetchone()
    profile_pic = user_data['profile_pic'] if user_data and user_data['profile_pic'] else 'default_dp.png'
    
    # Get divisions (categories) and associated item counts
    cursor.execute("SELECT category, COUNT(*) as product_count FROM items GROUP BY category ORDER BY category")
    divisions = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('admin_divisions.html', divisions=divisions, profile_pic=profile_pic)

@app.route('/admin/category/rename', methods=['POST'])
def rename_category():
    if 'user_id' not in session or session.get('role') != 'Admin':
        return redirect(url_for('home'))

    old_category = request.form.get('old_category', '').strip()
    new_category = request.form.get('new_category', '').strip()

    if not old_category or not new_category:
        flash("Category names cannot be empty.", "error")
        return redirect(url_for('admin_divisions'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE items SET category = ? WHERE category = ?", (new_category, old_category))
    conn.commit()
    cursor.close()
    conn.close()

    # Sync database to CSV
    from setup_db import sync_db_to_csv
    sync_db_to_csv()

    flash(f"Category '{old_category}' successfully renamed to '{new_category}'!", "success")
    return redirect(url_for('admin_divisions'))

@app.route('/api/chat', methods=['POST'])
def api_chat():
    from flask import jsonify
    if 'user_id' not in session:
        return jsonify({'text': 'Please log in to chat with the assistant.', 'actions': []}), 401
    
    data = request.get_json() or {}
    message = data.get('message', '').strip()
    if not message:
        return jsonify({'text': 'Please enter a message.', 'actions': []}), 400
        
    from ai_helper import handle_ai_message
    res = handle_ai_message(message)
    return jsonify(res)

if __name__ == '__main__':
    app.run(debug=True, port=5000)

