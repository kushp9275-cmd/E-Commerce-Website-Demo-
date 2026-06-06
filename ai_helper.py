import os
import sqlite3
from flask import session, g, url_for
import google.generativeai as genai

# Database connection helper
def get_db_connection():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, 'mart.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

# Register actions helper
def add_ai_action(action_type, value):
    if not hasattr(g, 'ai_actions'):
        g.ai_actions = []
    g.ai_actions.append({'type': action_type, 'value': value})

# ─────────────────────────────────────────────────────────────────────────────
# AI CUSTOMER TOOLS (USER ACTIONS)
# ─────────────────────────────────────────────────────────────────────────────

def search_items(query: str, category: str = "All") -> str:
    """
    Search for items/products available in the store inventory.
    
    Args:
        query: The search term or keywords to look for.
        category: The category filter (e.g. 'Biscuits', 'Cold Drinks', 'Butter', 'All').
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    q_str = f"%{query.strip()}%"
    if category and category != 'All':
        cursor.execute("SELECT id, name, description, price, category, stock FROM items WHERE category = ? AND (name LIKE ? OR description LIKE ?)", (category, q_str, q_str))
    else:
        cursor.execute("SELECT id, name, description, price, category, stock FROM items WHERE name LIKE ? OR description LIKE ?", (q_str, q_str))
    
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    
    if not rows:
        return f"No items found matching '{query}' in category '{category}'."
    
    result = []
    for row in rows[:8]: # limit to 8 results for token safety
        status = "In Stock" if row['stock'] > 0 else "Out of Stock"
        result.append(f"- ID: {row['id']} | Name: {row['name']} | Price: Rs. {row['price']} | Category: {row['category']} | Status: {status} ({row['stock']} left)")
        
    return "Here are the matching items:\n" + "\n".join(result)


def add_item_to_cart(item_name_or_id: str, quantity: int = 1) -> str:
    """
    Add a specific quantity of an item/product to the user's shopping cart.
    
    Args:
        item_name_or_id: The name, partial name, or numerical ID of the item.
        quantity: The number of items to add (defaults to 1).
    """
    user_id = session.get('user_id')
    if not user_id:
        return "Error: You must be logged in to add items to the cart."
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Try parsing as ID first, if not search by name
    item = None
    if item_name_or_id.isdigit():
        cursor.execute("SELECT * FROM items WHERE id = ?", (int(item_name_or_id),))
        item = cursor.fetchone()
        
    if not item:
        cursor.execute("SELECT * FROM items WHERE name LIKE ? LIMIT 1", (f"%{item_name_or_id.strip()}%",))
        item = cursor.fetchone()
        
    if not item:
        cursor.close()
        conn.close()
        return f"Could not find any item matching '{item_name_or_id}'."
        
    item_id = item['id']
    stock = item['stock']
    
    if stock < 1:
        cursor.close()
        conn.close()
        return f"Sorry, '{item['name']}' is currently out of stock."
        
    # Check if already in cart
    cursor.execute("SELECT * FROM cart WHERE user_id = ? AND item_id = ?", (user_id, item_id))
    existing = cursor.fetchone()
    
    final_qty = quantity
    if existing:
        final_qty = existing['quantity'] + quantity
        if final_qty > stock:
            final_qty = stock
        cursor.execute("UPDATE cart SET quantity = ? WHERE id = ?", (final_qty, existing['id']))
    else:
        if final_qty > stock:
            final_qty = stock
        cursor.execute("INSERT INTO cart (user_id, item_id, quantity) VALUES (?, ?, ?)", (user_id, item_id, final_qty))
        
    conn.commit()
    cursor.close()
    conn.close()
    
    # Trigger a refresh on the frontend cart badge
    add_ai_action('refresh_cart', True)
    
    return f"Successfully added {final_qty} of '{item['name']}' to your cart."


def remove_item_from_cart(item_name_or_id: str) -> str:
    """
    Remove an item or decrease its quantity from the user's shopping cart.
    
    Args:
        item_name_or_id: The name or ID of the item in the cart.
    """
    user_id = session.get('user_id')
    if not user_id:
        return "Error: You must be logged in to modify your cart."
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    item = None
    if item_name_or_id.isdigit():
        cursor.execute("SELECT * FROM items WHERE id = ?", (int(item_name_or_id),))
        item = cursor.fetchone()
        
    if not item:
        cursor.execute("SELECT * FROM items WHERE name LIKE ? LIMIT 1", (f"%{item_name_or_id.strip()}%",))
        item = cursor.fetchone()
        
    if not item:
        cursor.close()
        conn.close()
        return f"Could not find any item matching '{item_name_or_id}'."
        
    cursor.execute("DELETE FROM cart WHERE user_id = ? AND item_id = ?", (user_id, item['id']))
    conn.commit()
    cursor.close()
    conn.close()
    
    add_ai_action('refresh_cart', True)
    return f"Removed '{item['name']}' from your cart."


def view_cart() -> str:
    """
    View the current items, pricing, and counts in the shopping cart and navigate to the cart page.
    """
    user_id = session.get('user_id')
    if not user_id:
        return "Error: You must be logged in to view your cart."
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.quantity, i.name, i.price, (c.quantity * i.price) as subtotal
        FROM cart c JOIN items i ON c.item_id = i.id
        WHERE c.user_id = ?
    """, (user_id,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    
    # Redirect user to the cart page
    add_ai_action('redirect', url_for('cart'))
    
    if not rows:
        return "Your cart is currently empty. I've opened the cart page for you."
        
    result = []
    total = 0.0
    for r in rows:
        result.append(f"- {r['name']} (Qty: {r['quantity']}) - Rs. {r['subtotal']}")
        total += r['subtotal']
        
    return f"Here is your cart (total Rs. {total}):\n" + "\n".join(result) + "\nI've navigated you to the cart page."


def navigate_to(page_name: str) -> str:
    """
    Redirect/navigate the user to different pages on the site.
    
    Args:
        page_name: The destination page. Allowed values: 'home', 'dashboard', 'cart', 'profile', 'admin_dashboard', 'orders'.
    """
    page_map = {
        'home': 'home',
        'dashboard': 'dashboard',
        'cart': 'cart',
        'profile': 'profile',
        'admin_dashboard': 'admin_dashboard',
    }
    
    target = page_name.lower().strip()
    if target in page_map:
        # Check permission for admin
        if target == 'admin_dashboard' and session.get('role') != 'Admin':
            return "Error: Access denied. Only admins can visit the Admin Dashboard."
        url = url_for(page_map[target])
        add_ai_action('redirect', url)
        return f"Redirecting you to the {page_name} page."
    else:
        return f"Unknown page '{page_name}'. You can navigate to: home, dashboard, cart, profile, admin_dashboard."


def checkout_cart(payment_method: str = "cod") -> str:
    """
    Process checkout and place the order for all items currently in the user's shopping cart.
    
    Args:
        payment_method: The payment method to use. Allowed values: 'cod' (Cash on Delivery), 'online' (Online Payment).
    """
    user_id = session.get('user_id')
    if not user_id:
        return "Error: You must be logged in to checkout."
        
    method = payment_method.lower().strip()
    if method not in ['cod', 'online']:
        return "Error: Invalid payment method. Must be 'cod' or 'online'."
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Get user profile details
    cursor.execute("SELECT address FROM users WHERE id = ?", (user_id,))
    user_row = cursor.fetchone()
    delivery_address = user_row['address'] if user_row else ''
    
    # 2. Fetch cart items
    query = """
    SELECT c.quantity, i.id as item_id, i.name, i.price, i.stock, i.image_url
    FROM cart c 
    JOIN items i ON c.item_id = i.id 
    WHERE c.user_id = ?
    """
    cursor.execute(query, (user_id,))
    cart_items = cursor.fetchall()
    
    if not cart_items:
        cursor.close()
        conn.close()
        return "Your cart is currently empty. Add items to your cart before checking out."
        
    # Check stock
    for item in cart_items:
        if item['quantity'] > item['stock']:
            cursor.close()
            conn.close()
            return f"Error: Insufficient stock for '{item['name']}'. Available: {item['stock']}."
            
    total_price = sum(item['quantity'] * item['price'] for item in cart_items)
    
    if method == 'online':
        cursor.close()
        conn.close()
        # Redirect the user to the cart page so they can trigger the Razorpay secure popup
        add_ai_action('redirect', url_for('cart'))
        return "To pay online, I have opened your cart page. Please click the 'Proceed to Checkout' button to open the secure Razorpay payment window."
        
    # 3. COD Order Placement
    try:
        # Create order record
        cursor.execute("""
            INSERT INTO orders (user_id, total_price, razorpay_order_id, status, payment_method, delivery_address)
            VALUES (?, ?, NULL, 'confirmed', 'cod', ?)
        """, (user_id, total_price, delivery_address))
        order_id = cursor.lastrowid
        
        # Save order items
        for item in cart_items:
            cursor.execute("""
                INSERT INTO order_items (order_id, item_id, item_name, quantity, price_at_time, image_url)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (order_id, item['item_id'], item['name'], item['quantity'], item['price'], item['image_url']))
            
        # Decrement stock
        for item in cart_items:
            cursor.execute("UPDATE items SET stock = stock - ? WHERE id = ?", (item['quantity'], item['item_id']))
            
        # Clear cart
        cursor.execute("DELETE FROM cart WHERE user_id = ?", (user_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        # Redirect user to the order details page
        add_ai_action('redirect', url_for('order_detail', order_id=order_id))
        return f"Successfully placed your Cash on Delivery order! Order ID: #ORD-{order_id:05d}. Total: Rs. {total_price}. Redirecting you to your order tracking page."
        
    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        return f"Error placing COD order: {str(e)}"


# ─────────────────────────────────────────────────────────────────────────────
# AI ADMIN TOOLS
# ─────────────────────────────────────────────────────────────────────────────

def get_admin_metrics() -> str:
    """
    Get current administrative store statistics (revenue, total orders, users, and out-of-stock or low-stock alerts).
    """
    if session.get('role') != 'Admin':
        return "Error: Access Denied. This tool is only available for Administrators."
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Stats
    cursor.execute("SELECT COUNT(*) as count FROM orders")
    total_orders = cursor.fetchone()['count']
    
    cursor.execute("SELECT COALESCE(SUM(total_price), 0) as revenue FROM orders WHERE status NOT IN ('pending', 'cancelled')")
    revenue = cursor.fetchone()['revenue']
    
    cursor.execute("SELECT COUNT(*) as count FROM users WHERE role = 'User'")
    total_users = cursor.fetchone()['count']
    
    # Low stock items
    cursor.execute("SELECT name, stock FROM items WHERE stock < 5 ORDER BY stock ASC LIMIT 5")
    low_stock = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    low_stock_list = []
    for item in low_stock:
        low_stock_list.append(f"- {item['name']} ({item['stock']} left)")
        
    low_stock_str = "\n".join(low_stock_list) if low_stock_list else "None (all items healthy)"
    
    return (
        f"--- Store Administrative Metrics ---\n"
        f"Total Revenue: Rs. {revenue:,.2f}\n"
        f"Total Orders: {total_orders}\n"
        f"Total Customers: {total_users}\n"
        f"\nLow/Out of Stock Alerts:\n{low_stock_str}"
    )


def update_item_stock(item_id_or_name: str, new_stock: int) -> str:
    """
    Update/modify the inventory stock levels for a specific product.
    
    Args:
        item_id_or_name: The item ID or the item name.
        new_stock: The new stock count to set (must be a positive number).
    """
    if session.get('role') != 'Admin':
        return "Error: Access Denied. Only administrators can update stock."
        
    if new_stock < 0:
        return "Error: Stock cannot be negative."
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    item = None
    if item_id_or_name.isdigit():
        cursor.execute("SELECT * FROM items WHERE id = ?", (int(item_id_or_name),))
        item = cursor.fetchone()
        
    if not item:
        cursor.execute("SELECT * FROM items WHERE name LIKE ? LIMIT 1", (f"%{item_id_or_name.strip()}%",))
        item = cursor.fetchone()
        
    if not item:
        cursor.close()
        conn.close()
        return f"Could not find item matching '{item_id_or_name}'."
        
    cursor.execute("UPDATE items SET stock = ? WHERE id = ?", (new_stock, item['id']))
    conn.commit()
    cursor.close()
    conn.close()
    
    # Trigger refresh to show updated stock lists on dashboard
    add_ai_action('refresh_page', True)
    return f"Successfully updated stock for '{item['name']}' to {new_stock}."


def update_order_status(order_id: int, new_status: str) -> str:
    """
    Update/modify the shipping status of an existing order.
    
    Args:
        order_id: The numeric ID of the order.
        new_status: The new status value (Allowed: 'confirmed', 'shipped', 'out_for_delivery', 'delivered', 'cancelled').
    """
    if session.get('role') != 'Admin':
        return "Error: Access Denied. Only administrators can update order status."
        
    allowed_statuses = ['confirmed', 'shipped', 'out_for_delivery', 'delivered', 'cancelled']
    status = new_status.lower().strip()
    if status not in allowed_statuses:
        return f"Error: Invalid status. Must be one of: {', '.join(allowed_statuses)}"
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, status FROM orders WHERE id = ?", (order_id,))
    order = cursor.fetchone()
    
    if not order:
        cursor.close()
        conn.close()
        return f"Order #{order_id} not found."
        
    old_status = order['status']
    
    # If transitioning to cancelled, restore stock
    if status == 'cancelled' and old_status != 'cancelled':
        cursor.execute("SELECT item_id, quantity FROM order_items WHERE order_id = ?", (order_id,))
        for item in cursor.fetchall():
            cursor.execute("UPDATE items SET stock = stock + ? WHERE id = ?", (item['quantity'], item['item_id']))
    # If transitioning from cancelled back to active, check and decrement stock
    elif status != 'cancelled' and old_status == 'cancelled':
        cursor.execute("SELECT item_id, quantity FROM order_items WHERE order_id = ?", (order_id,))
        items = cursor.fetchall()
        for item in items:
            cursor.execute("SELECT name, stock FROM items WHERE id = ?", (item['item_id'],))
            prod = cursor.fetchone()
            if prod and prod['stock'] < item['quantity']:
                cursor.close()
                conn.close()
                return f"Error: Cannot update status. Insufficient stock for '{prod['name']}' (Only {prod['stock']} available)."
        for item in items:
            cursor.execute("UPDATE items SET stock = stock - ? WHERE id = ?", (item['quantity'], item['item_id']))
            
    cursor.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
    conn.commit()
    cursor.close()
    conn.close()
    
    add_ai_action('refresh_page', True)
    return f"Successfully updated Order #{order_id} status to '{status}'."


def delete_order(order_id: int) -> str:
    """
    Delete a customer's order from the store database.
    
    Args:
        order_id: The numeric ID of the order to delete.
    """
    if session.get('role') != 'Admin':
        return "Error: Access Denied. Only administrators can delete orders."
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, status FROM orders WHERE id = ?", (order_id,))
    order = cursor.fetchone()
    
    if not order:
        cursor.close()
        conn.close()
        return f"Order #{order_id} not found."
        
    # Restore stock if the deleted order was not cancelled
    if order['status'] != 'cancelled':
        cursor.execute("SELECT item_id, quantity FROM order_items WHERE order_id = ?", (order_id,))
        for item in cursor.fetchall():
            cursor.execute("UPDATE items SET stock = stock + ? WHERE id = ?", (item['quantity'], item['item_id']))
        
    cursor.execute("DELETE FROM order_items WHERE order_id = ?", (order_id,))
    cursor.execute("DELETE FROM orders WHERE id = ?", (order_id,))
    conn.commit()
    cursor.close()
    conn.close()
    
    add_ai_action('refresh_page', True)
    return f"Successfully deleted Order #{order_id} from the database."


def delete_all_orders() -> str:
    """
    Delete all customer orders and their order items from the store database (Admin only).
    """
    if session.get('role') != 'Admin':
        return "Error: Access Denied. Only administrators can delete all orders."
        
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Restore stock for all non-cancelled orders
        cursor.execute("""
            SELECT oi.item_id, oi.quantity 
            FROM order_items oi 
            JOIN orders o ON oi.order_id = o.id 
            WHERE o.status != 'cancelled'
        """)
        for item in cursor.fetchall():
            cursor.execute("UPDATE items SET stock = stock + ? WHERE id = ?", (item['quantity'], item['item_id']))
            
        cursor.execute("DELETE FROM order_items")
        cursor.execute("DELETE FROM orders")
        cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('orders', 'order_items')")
        conn.commit()
        cursor.close()
        conn.close()
        
        add_ai_action('refresh_page', True)
        return "Successfully deleted all orders and their associated order items from the store database."
    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        return f"Error deleting all orders: {str(e)}"


def update_profile_details(username: str = None, mobile_no: str = None, address: str = None) -> str:
    """
    Update the logged-in user's profile details (username, mobile number, or delivery address).
    
    Args:
        username: The new username.
        mobile_no: The new mobile phone number.
        address: The new shipping/delivery address.
    """
    user_id = session.get('user_id')
    if not user_id:
        return "Error: You must be logged in to update profile details."
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    updates = []
    params = []
    
    if username:
        updates.append("username = ?")
        params.append(username)
        session['username'] = username  # Update session value
    if mobile_no:
        updates.append("mobile_no = ?")
        params.append(mobile_no)
    if address:
        updates.append("address = ?")
        params.append(address)
        
    if not updates:
        cursor.close()
        conn.close()
        return "No updates were specified. Please provide a username, mobile number, or address to update."
        
    params.append(user_id)
    query = f"UPDATE users SET {', '.join(updates)} WHERE id = ?"
    cursor.execute(query, params)
    conn.commit()
    cursor.close()
    conn.close()
    
    add_ai_action('refresh_page', True)
    return "Successfully updated your profile details!"


def update_cart_quantity(item_name_or_id: str, quantity: int) -> str:
    """
    Set/update the quantity of an item that is already inside the user's shopping cart.
    
    Args:
        item_name_or_id: The item name or ID.
        quantity: The new quantity to set (must be 1 or higher).
    """
    user_id = session.get('user_id')
    if not user_id:
        return "Error: You must be logged in to edit your cart."
        
    if quantity < 1:
        return remove_item_from_cart(item_name_or_id)
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Resolve item
    item = None
    if item_name_or_id.isdigit():
        cursor.execute("SELECT * FROM items WHERE id = ?", (int(item_name_or_id),))
        item = cursor.fetchone()
    if not item:
        cursor.execute("SELECT * FROM items WHERE name LIKE ? LIMIT 1", (f"%{item_name_or_id.strip()}%",))
        item = cursor.fetchone()
        
    if not item:
        cursor.close()
        conn.close()
        return f"Could not find item matching '{item_name_or_id}'."
        
    item_id = item['id']
    stock = item['stock']
    
    if quantity > stock:
        quantity = stock
        
    # Check if inside cart
    cursor.execute("SELECT * FROM cart WHERE user_id = ? AND item_id = ?", (user_id, item_id))
    cart_item = cursor.fetchone()
    
    if not cart_item:
        cursor.close()
        conn.close()
        return f"'{item['name']}' is not in your cart yet. Try adding it first."
        
    cursor.execute("UPDATE cart SET quantity = ? WHERE id = ?", (quantity, cart_item['id']))
    conn.commit()
    cursor.close()
    conn.close()
    
    add_ai_action('refresh_cart', True)
    return f"Successfully updated '{item['name']}' quantity to {quantity} in your cart."


def track_order(order_id: int) -> str:
    """
    Retrieve details and status tracking of a specific order (items, status, total price, delivery address).
    
    Args:
        order_id: The numeric ID of the order.
    """
    user_id = session.get('user_id')
    role = session.get('role', 'User')
    if not user_id:
        return "Error: You must be logged in."
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if role == 'Admin':
        cursor.execute("SELECT o.*, u.username FROM orders o JOIN users u ON o.user_id = u.id WHERE o.id = ?", (order_id,))
    else:
        cursor.execute("SELECT o.*, u.username FROM orders o JOIN users u ON o.user_id = u.id WHERE o.id = ? AND o.user_id = ?", (order_id, user_id))
        
    order = cursor.fetchone()
    if not order:
        cursor.close()
        conn.close()
        return f"Order #{order_id} not found."
        
    # Get items
    cursor.execute("SELECT item_name, quantity, price_at_time FROM order_items WHERE order_id = ?", (order_id,))
    items = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    # Redirect to details page
    add_ai_action('redirect', url_for('order_detail', order_id=order_id))
    
    items_list = [f"- {r['item_name']} (Qty: {r['quantity']}) @ Rs. {r['price_at_time']}" for r in items]
    items_str = "\n".join(items_list)
    
    return (
        f"--- Order #ORD-{order_id:05d} tracking details ---\n"
        f"Customer: {order['username']}\n"
        f"Status: {order['status'].upper()}\n"
        f"Total Price: Rs. {order['total_price']}\n"
        f"Payment Method: {order['payment_method'].upper()}\n"
        f"Delivery Address: {order['delivery_address']}\n"
        f"Items Ordered:\n{items_str}\n"
        f"I've opened the order tracking page for you."
    )


def logout_user() -> str:
    """
    Log out the current logged-in user and return to the login screen.
    """
    add_ai_action('redirect', url_for('logout'))
    return "Logging you out. Redirecting to home screen."


def add_new_product(name: str, description: str, price: float, category: str, stock: int = 10, image_url: str = "") -> str:
    """
    Add a new product item/product to the inventory catalog (Admin only).
    
    Args:
        name: The name of the product.
        description: The description of the product.
        price: The retail price of the product.
        category: The category division (e.g. 'Biscuits', 'Cold Drinks', 'Milk').
        stock: Initial stock level.
        image_url: Optional image filename or URL.
    """
    if session.get('role') != 'Admin':
        return "Error: Access Denied. Only administrators can add new products."
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO items (name, description, price, image_url, category, stock)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (name, description, price, image_url, category, stock))
    conn.commit()
    cursor.close()
    conn.close()
    
    add_ai_action('refresh_page', True)
    return f"Successfully added new product '{name}' to the store database under category '{category}'."


def edit_product_details(item_name_or_id: str, name: str = None, description: str = None, price: float = None, category: str = None, stock: int = None) -> str:
    """
    Edit/modify the details (name, price, stock, category, description) of an existing product in the catalog (Admin only).
    
    Args:
        item_name_or_id: The product name or numerical ID to edit.
        name: The new name of the product.
        description: The new description.
        price: The new price.
        category: The new category.
        stock: The new stock level.
    """
    if session.get('role') != 'Admin':
        return "Error: Access Denied. Only administrators can edit product details."
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    item = None
    if item_name_or_id.isdigit():
        cursor.execute("SELECT * FROM items WHERE id = ?", (int(item_name_or_id),))
        item = cursor.fetchone()
    if not item:
        cursor.execute("SELECT * FROM items WHERE name LIKE ? LIMIT 1", (f"%{item_name_or_id.strip()}%",))
        item = cursor.fetchone()
        
    if not item:
        cursor.close()
        conn.close()
        return f"Could not find any item matching '{item_name_or_id}'."
        
    item_id = item['id']
    updates = []
    params = []
    
    if name:
        updates.append("name = ?")
        params.append(name)
    if description:
        updates.append("description = ?")
        params.append(description)
    if price is not None:
        updates.append("price = ?")
        params.append(price)
    if category:
        updates.append("category = ?")
        params.append(category)
    if stock is not None:
        updates.append("stock = ?")
        params.append(stock)
        
    if not updates:
        cursor.close()
        conn.close()
        return "No updates were specified. Provide a name, price, stock, category, or description to edit."
        
    params.append(item_id)
    query = f"UPDATE items SET {', '.join(updates)} WHERE id = ?"
    cursor.execute(query, params)
    conn.commit()
    cursor.close()
    conn.close()
    
    add_ai_action('refresh_page', True)
    return f"Successfully updated product '{item['name']}' details in inventory!"


def delete_product(item_name_or_id: str) -> str:
    """
    Delete a product item entirely from the store inventory catalog (Admin only).
    
    Args:
        item_name_or_id: The name or numerical ID of the product.
    """
    if session.get('role') != 'Admin':
        return "Error: Access Denied. Only administrators can delete products."
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    item = None
    if item_name_or_id.isdigit():
        cursor.execute("SELECT * FROM items WHERE id = ?", (int(item_name_or_id),))
        item = cursor.fetchone()
    if not item:
        cursor.execute("SELECT * FROM items WHERE name LIKE ? LIMIT 1", (f"%{item_name_or_id.strip()}%",))
        item = cursor.fetchone()
        
    if not item:
        cursor.close()
        conn.close()
        return f"Could not find any item matching '{item_name_or_id}'."
        
    item_id = item['id']
    
    # Remove from cart (to protect foreign keys)
    cursor.execute("DELETE FROM cart WHERE item_id = ?", (item_id,))
    cursor.execute("DELETE FROM items WHERE id = ?", (item_id,))
    conn.commit()
    cursor.close()
    conn.close()
    
    add_ai_action('refresh_page', True)
    return f"Successfully deleted product '{item['name']}' from the inventory."


def list_all_orders(status_filter: str = "all") -> str:
    """
    List all store customer orders, optionally filtered by status (Admin only).
    
    Args:
        status_filter: Filter by status ('confirmed', 'shipped', 'out_for_delivery', 'delivered', 'cancelled', 'all').
    """
    if session.get('role') != 'Admin':
        return "Error: Access Denied. Only administrators can view all orders."
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    status = status_filter.lower().strip()
    if status and status != 'all':
        cursor.execute("SELECT o.id, o.total_price, o.status, u.username FROM orders o JOIN users u ON o.user_id = u.id WHERE o.status = ?", (status,))
    else:
        cursor.execute("SELECT o.id, o.total_price, o.status, u.username FROM orders o JOIN users u ON o.user_id = u.id")
        
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    
    add_ai_action('redirect', url_for('admin_orders', status=status))
    
    if not rows:
        return f"No orders found matching status '{status}'."
        
    result = []
    for r in rows[:15]: # Limit to 15 results for tokens safety
        result.append(f"- Order #ORD-{r['id']:05d} | Customer: {r['username']} | Total: Rs. {r['total_price']} | Status: {r['status']}")
        
    return f"Found {len(rows)} orders. Opening the order list for you:\n" + "\n".join(result)


# ─────────────────────────────────────────────────────────────────────────────
# CORE CHAT DISPATCHER
# ─────────────────────────────────────────────────────────────────────────────

def handle_ai_message(user_message: str) -> dict:
    """
    Sends the user message to Gemini, processes any tool calls,
    and returns a dict with the AI response text and any frontend actions.
    """
    # Define role context
    role = session.get('role', 'User')
    user_name = session.get('username', 'Guest')
    
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        # Simple offline regex/keyword routing for simulation
        msg_lower = user_message.lower()
        actions = []
        text = ""
        
        if "add" in msg_lower or "buy" in msg_lower or ("cart" in msg_lower and "view" not in msg_lower and "show" not in msg_lower):
            # Try to extract common product names
            found_item = "Butter"  # default fallback
            for item_kw in ["butter", "milk", "cheese", "lassi", "dahi", "ghee", "sprite", "coke", "fanta", "chips", "cookies"]:
                if item_kw in msg_lower:
                    found_item = item_kw.capitalize()
                    break
            text = add_item_to_cart(found_item, 1)
            text = f"*(Offline Simulation Mode)* {text}"
            actions = getattr(g, 'ai_actions', [])
        elif "cart" in msg_lower:
            text = view_cart()
            text = f"*(Offline Simulation Mode)* {text}"
            actions = getattr(g, 'ai_actions', [])
        elif "profile" in msg_lower:
            text = navigate_to("profile")
            text = f"*(Offline Simulation Mode)* {text}"
            actions = getattr(g, 'ai_actions', [])
        elif "dashboard" in msg_lower or "home" in msg_lower:
            text = navigate_to("dashboard")
            text = f"*(Offline Simulation Mode)* {text}"
            actions = getattr(g, 'ai_actions', [])
        elif "stats" in msg_lower or "metric" in msg_lower or "revenue" in msg_lower:
            if role == 'Admin':
                text = get_admin_metrics()
            else:
                text = "Error: Access Denied. Only admins can see stats."
            text = f"*(Offline Simulation Mode)*\n{text}"
        else:
            text = (
                f"Hello {user_name}! I am the Mart AI Assistant running in **Offline Simulation Mode**.\n\n"
                f"I can simulate database and interface control directly! Try typing:\n"
                f"- *'add butter to cart'*\n"
                f"- *'view my cart'*\n"
                f"- *'go to my profile'*\n"
                f"- *'get store metrics'* (Admin only)\n\n"
                f"To enable full semantic reasoning and product Q&A, please set `GEMINI_API_KEY` in your `.env` file."
            )
        return {
            'text': text,
            'actions': actions
        }
        
    # Compile the tools based on user permissions
    tool_list = [
        search_items, add_item_to_cart, remove_item_from_cart, view_cart, navigate_to, checkout_cart,
        update_profile_details, update_cart_quantity, track_order, logout_user
    ]
    
    role_instruction = "You are a customer assistant for the Mart e-commerce store."
    if role == 'Admin':
        tool_list.extend([
            get_admin_metrics, update_item_stock, update_order_status, delete_order, delete_all_orders,
            add_new_product, edit_product_details, delete_product, list_all_orders
        ])
        role_instruction = (
            "You are an administrative assistant for the Mart e-commerce store. "
            "You have access to privileged administrative tools to update stock levels, edit order statuses, "
            "delete orders, delete all orders, add new products, edit product details, delete products, "
            "list all orders, and fetch general site metrics."
        )
        
    system_instruction = (
        f"{role_instruction} "
        f"The current user's name is {user_name} and their role is {role}. "
        "Keep your responses friendly, concise, and helpful. "
        "When the user asks to add items, view the cart, navigate, checkout/place orders, delete orders, delete all orders, "
        "update profile details, change cart item quantities, track an order, log out, add products, edit products, delete products, "
        "or list orders, always use the appropriate tool function instead of just talking about it. "
        "Only call administrative tools if the user is verified as an Admin (which they are if role is Admin)."
    )
    
    try:
        model = genai.GenerativeModel(
            model_name='gemini-2.5-flash',
            tools=tool_list,
            system_instruction=system_instruction
        )
        
        # We start a chat session. For multi-turn conversations, we can load history from Flask session
        # For simplicity and robust stateless tool usage, we can pass the recent messages context.
        # Let's rebuild the chat history if stored in session, otherwise start a new one.
        chat_history = session.get('ai_chat_history', [])
        
        # Limit history size to prevent context bloat
        if len(chat_history) > 10:
            chat_history = chat_history[-10:]
            
        formatted_history = []
        for msg in chat_history:
            formatted_history.append({
                'role': msg['role'],
                'parts': [msg['text']]
            })
            
        chat = model.start_chat(history=formatted_history)
        response = chat.send_message(user_message)
        
        tool_map = {
            'search_items': search_items,
            'add_item_to_cart': add_item_to_cart,
            'remove_item_from_cart': remove_item_from_cart,
            'view_cart': view_cart,
            'navigate_to': navigate_to,
            'checkout_cart': checkout_cart,
            'update_profile_details': update_profile_details,
            'update_cart_quantity': update_cart_quantity,
            'track_order': track_order,
            'logout_user': logout_user,
            'get_admin_metrics': get_admin_metrics,
            'update_item_stock': update_item_stock,
            'update_order_status': update_order_status,
            'delete_order': delete_order,
            'delete_all_orders': delete_all_orders,
            'add_new_product': add_new_product,
            'edit_product_details': edit_product_details,
            'delete_product': delete_product,
            'list_all_orders': list_all_orders
        }
        
        # Helper to safely retrieve function calls from GenerateContentResponse
        def get_function_calls(resp):
            f_calls = []
            if resp.candidates and resp.candidates[0].content and resp.candidates[0].content.parts:
                for part in resp.candidates[0].content.parts:
                    if part.function_call:
                        f_calls.append(part.function_call)
            return f_calls

        # Resolve any tool requests made by the model
        function_calls = get_function_calls(response)
        while function_calls:
            for function_call in function_calls:
                name = function_call.name
                args = function_call.args
                print(f"AI requested tool execution: {name} with args {dict(args)}")
                
                if name in tool_map:
                    try:
                        kwargs = {k: v for k, v in args.items()}
                        tool_result = tool_map[name](**kwargs)
                    except Exception as fn_err:
                        tool_result = f"Error executing tool {name}: {str(fn_err)}"
                else:
                    tool_result = f"Error: Tool '{name}' is not registered."
                
                print(f"Tool execution result: {tool_result}")
                
                # Send tool execution result back to the model
                response = chat.send_message(
                    genai.protos.Part(
                        function_response=genai.protos.FunctionResponse(
                            name=name,
                            response={'result': str(tool_result)}
                        )
                    )
                )
            function_calls = get_function_calls(response)
        
        final_text = response.text
        
        # Save to chat history
        chat_history.append({'role': 'user', 'text': user_message})
        chat_history.append({'role': 'model', 'text': final_text})
        session['ai_chat_history'] = chat_history
        session.modified = True
        
        # Collect actions recorded during tool calls
        actions = getattr(g, 'ai_actions', [])
        
        return {
            'text': final_text,
            'actions': actions
        }
    except Exception as e:
        print(f"Gemini API Execution Error: {e}")
        return {
            'text': f"Sorry, I encountered an error while processing your request: {str(e)}",
            'actions': []
        }
