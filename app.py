from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import os
from werkzeug.utils import secure_filename
import razorpay
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = 'your_super_secret_key_here'

# Razorpay Configuration
RAZORPAY_KEY_ID = os.getenv('RAZORPAY_KEY_ID')
RAZORPAY_KEY_SECRET = os.getenv('RAZORPAY_KEY_SECRET')
razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

# File upload setup
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024 # 2MB limit
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
    
    if category and category != 'All':
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
    
    return render_template('dashboard.html', items=items, cart_count=cart_count, categories=categories, current_category=category or 'All', profile_pic=profile_pic)

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('home'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT username, email, mobile_no, address, profile_pic, created_at FROM users WHERE id = ?", (session['user_id'],))
    user_info = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if not user_info:
        flash("User not found.", "error")
        return redirect(url_for('dashboard'))
        
    if not user_info['profile_pic']:
        user_info['profile_pic'] = 'default_dp.png'
        
    return render_template('profile.html', user=user_info)

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

@app.route('/add_to_cart/<int:item_id>', methods=['POST'])
def add_to_cart(item_id):
    if 'user_id' not in session:
        return redirect(url_for('home'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if item exists in cart already
    cursor.execute("SELECT * FROM cart WHERE user_id = ? AND item_id = ?", (session['user_id'], item_id))
    existing_entry = cursor.fetchone()
    
    if existing_entry:
        cursor.execute("UPDATE cart SET quantity = quantity + 1 WHERE id = ?", (existing_entry['id'],))
    else:
        cursor.execute("INSERT INTO cart (user_id, item_id, quantity) VALUES (?, ?, 1)", (session['user_id'], item_id))
        
    conn.commit()
    cursor.close()
    conn.close()
    
    flash("Item added to cart!", "success")
    return redirect(url_for('dashboard'))

@app.route('/cart')
def cart():
    if 'user_id' not in session:
        return redirect(url_for('home'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = """
    SELECT c.id as cart_id, c.quantity, i.id as item_id, i.name, i.price, i.image_url, (c.quantity * i.price) as subtotal
    FROM cart c 
    JOIN items i ON c.item_id = i.id 
    WHERE c.user_id = ?
    """
    cursor.execute(query, (session['user_id'],))
    cart_items = cursor.fetchall()
    
    total_price = sum(item['subtotal'] for item in cart_items)
    
    cursor.close()
    conn.close()
    
    return render_template('cart.html', cart_items=cart_items, total_price=total_price)

@app.route('/checkout', methods=['POST'])
def checkout():
    if 'user_id' not in session:
        return redirect(url_for('home'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Calculate Total & Check Stock
    query = """
    SELECT c.quantity, i.id as item_id, i.price, i.stock 
    FROM cart c 
    JOIN items i ON c.item_id = i.id 
    WHERE c.user_id = ?
    """
    cursor.execute(query, (session['user_id'],))
    cart_items = cursor.fetchall()

    total_price = sum(item['quantity'] * item['price'] for item in cart_items)

    if total_price > 0:
        # Check sufficient stock
        for item in cart_items:
            if item['quantity'] > item['stock']:
                flash("Insufficient stock for one or more items.", "error")
                cursor.close()
                conn.close()
                return redirect(url_for('cart'))

        # 1. Create Razorpay Order (Amount in paise: multiply by 100)
        amount_paise = int(total_price * 100)
        data = {
            "amount": amount_paise,
            "currency": "INR",
            "receipt": f"receipt_{session['user_id']}",
            "payment_capture": 1 # Auto-capture payment
        }
        
        try:
            razorpay_order = razorpay_client.order.create(data=data)
            razorpay_order_id = razorpay_order['id']
            
            # 2. Record Pending Order in our DB
            cursor.execute("""
                INSERT INTO orders (user_id, total_price, razorpay_order_id, status) 
                VALUES (?, ?, ?, 'pending')
            """, (session['user_id'], total_price, razorpay_order_id))
            conn.commit()
            
            # 3. Clean up before sending to frontend
            cursor.close()
            conn.close()
            
            # Pass data to verify on frontend via Razorpay modal
            return render_template('checkout_payment.html', 
                                 order_id=razorpay_order_id, 
                                 amount=amount_paise, 
                                 key_id=RAZORPAY_KEY_ID,
                                 total_price=total_price)
                                 
        except Exception as e:
            flash(f"Payment gateway error: {str(e)}", "error")
            cursor.close()
            conn.close()
            return redirect(url_for('cart'))
    else:
        flash("Your cart is empty.", "error")
        cursor.close()
        conn.close()
        return redirect(url_for('dashboard'))

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
        
        # 1. Update Order Status
        cursor.execute("""
            UPDATE orders 
            SET status = 'paid', razorpay_payment_id = ? 
            WHERE razorpay_order_id = ?
        """, (payment_id, order_id))
        
        # 2. Decrease Stock
        # First, find what was in the cart for this user
        cursor.execute("""
            SELECT c.quantity, i.id as item_id 
            FROM cart c 
            JOIN items i ON c.item_id = i.id 
            WHERE c.user_id = ?
        """, (session['user_id'],))
        cart_items = cursor.fetchall()
        
        for item in cart_items:
            cursor.execute("UPDATE items SET stock = stock - ? WHERE id = ?", (item['quantity'], item['item_id']))
            
        # 3. Clear Cart
        cursor.execute("DELETE FROM cart WHERE user_id = ?", (session['user_id'],))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        flash("Payment successful! Your order has been placed.", "success")
        return redirect(url_for('dashboard'))
        
    except Exception as e:
        # Verification failed
        flash("Payment verification failed. Please contact support.", "error")
        return redirect(url_for('cart'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

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
    
    cursor.close()
    conn.close()
    
    return render_template('admin_dashboard.html', items=items, categories=categories, profile_pic=profile_pic, current_category=category)

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

    flash("Item deleted successfully!", "success")
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)
