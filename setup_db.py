import sqlite3
import os
import csv
import shutil


def create_database_and_table(db_path='mart.db'):
    
    # Connect to SQLite (creates the file if it doesn't exist)
    connection = sqlite3.connect(db_path)
    cursor = connection.cursor()

    # Create users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username VARCHAR(50) NOT NULL,
        email VARCHAR(100) NOT NULL UNIQUE,
        password_hash VARCHAR(255) NOT NULL,
        mobile_no VARCHAR(20),
        address TEXT,
        profile_pic VARCHAR(255) DEFAULT 'default_dp.png',
        role VARCHAR(20) DEFAULT 'User',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Create items table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name VARCHAR(100) NOT NULL,
        description TEXT,
        price DECIMAL(10, 2) NOT NULL,
        image_url VARCHAR(255),
        category VARCHAR(50) NOT NULL DEFAULT 'General',
        stock INT DEFAULT 10
    )
    """)

    # Create cart table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cart (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INT NOT NULL,
        item_id INT NOT NULL,
        quantity INT DEFAULT 1,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (item_id) REFERENCES items(id)
    )
    """)

    # Create orders table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INT NOT NULL,
        total_price DECIMAL(10, 2) NOT NULL,
        razorpay_order_id VARCHAR(255),
        razorpay_payment_id VARCHAR(255),
        payment_method VARCHAR(20) DEFAULT 'online',
        status VARCHAR(30) DEFAULT 'pending',
        delivery_address TEXT,
        order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """)

    # Create order_items table — tracks individual items per order
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INT NOT NULL,
        item_id INT NOT NULL,
        item_name VARCHAR(100) NOT NULL,
        quantity INT NOT NULL,
        price_at_time DECIMAL(10, 2) NOT NULL,
        image_url VARCHAR(255),
        FOREIGN KEY (order_id) REFERENCES orders(id),
        FOREIGN KEY (item_id) REFERENCES items(id)
    )
    """)

    # --- Migrations for existing databases ---
    # Add payment_method column if it doesn't exist
    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN payment_method VARCHAR(20) DEFAULT 'online'")
    except sqlite3.OperationalError:
        pass  # Column already exists

    # Add delivery_address column if it doesn't exist
    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN delivery_address TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists

    # Check for items count to trigger sync from CSV
    cursor.execute("SELECT COUNT(*) FROM items")
    current_count = cursor.fetchone()[0]
    
    # We want exactly the items from items_neocart.csv
    base_dir = os.path.dirname(os.path.abspath(__file__))
    items_csv_path = os.path.join(base_dir, 'items_neocart.csv')
    
    if not os.path.exists(items_csv_path):
        print("Product CSV file not found. Skipping synchronization.")
        csv_count = current_count
    else:
        csv_count = 0
        try:
            with open(items_csv_path, mode='r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                csv_count = sum(1 for _ in reader)
        except Exception as e:
            print(f"Error reading CSV for counting: {e}")
            csv_count = 514
            
    if current_count != csv_count:

        print(f"Syncing database: current items count ({current_count}) differs from CSV count ({csv_count}).")
        # Clear existing items, cart, orders, order_items to avoid invalid foreign key associations
        cursor.execute("DELETE FROM items")
        cursor.execute("DELETE FROM cart")
        cursor.execute("DELETE FROM orders")
        cursor.execute("DELETE FROM order_items")
        cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('items', 'cart', 'orders', 'order_items')")
        
        # Load categories from item-categories_neocart.csv for reference
        categories = set()
        categories_csv_path = os.path.join(base_dir, 'item-categories_neocart.csv')
        if os.path.exists(categories_csv_path):
            try:
                with open(categories_csv_path, mode='r', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        categories.add(row['Name'].strip())
            except Exception as e:
                print(f"Error reading categories CSV: {e}")
                
        # Mapping name keywords to local images under static/images
        local_images_dir = os.path.join(base_dir, 'static', 'images')
        uploads_dir = os.path.join(base_dir, 'static', 'uploads')
        if not os.path.exists(uploads_dir):
            os.makedirs(uploads_dir)
            
        local_image_mappings = {
            "butter": "amul_butter.jpg",
            "chaas": "amul_chaas.webp",
            "buttermilk": "amul_chaas.webp",
            "butter milk": "amul_chaas.webp",
            "cheese": "amul_cheese.jpg",
            "dark chocolate": "amul_dark_chocolate.jpg",
            "dark chocolat": "amul_dark_chocolate.jpg",
            "amul gold": "amul_gold.jpg",
            "lassi": "amul_lassi.jpg",
            "dahi": "amul_masti_dahi.jpg",
            "curd": "amul_masti_dahi.jpg",
            "yogurt": "amul_masti_dahi.jpg",
            "paneer": "amul_paneer.jpg",
            "ghee": "amul_pure_ghee.jpg",
            "shrikhand": "amul_shrikhand.jpg",
            "taza": "amul_taza.jpg",
            "taaza": "amul_taza.jpg",
            "appy fizz": "appy_fizz.jpg",
            "appy": "appy_fizz.jpg",
            "balaji": "balaji_chips.webp",
            "bikaji": "bikaji_namkeen.png",
            "bingo": "bingo_mad_angels.jpg",
            "mad angels": "bingo_mad_angels.jpg",
            "chocobakes": "cadbury_chocobakes.jpg",
            "cookie": "cadbury_chocobakes.jpg",
            "cookies": "cadbury_chocobakes.jpg",
            "coke": "coke.jpg",
            "coca-cola": "coke.jpg",
            "coca cola": "coke.jpg",
            "doritos": "doritos_nachos.jpg",
            "fanta": "fanta.jpg",
            "frooti": "frooti.jpg",
            "haldiram": "haldiram_bhujia.jpg",
            "bhujia": "haldiram_bhujia.jpg",
            "hell energy": "hell_energy_drink.jpg",
            "hide & seek": "hide_and_seek.jpg",
            "hide and seek": "hide_and_seek.jpg",
            "popcorn": "instant_popcorn_pouch.jpg",
            "jagdish": "jagdish_namkeen.jpg",
            "lotus biscoff": "lotus_biscoff.jpg",
            "biscoff": "lotus_biscoff.jpg",
            "monster": "monster_energy.jpg",
            "pav bhaji": "pav_bhaji_buns.jpg",
            "bun": "pav_bhaji_buns.jpg",
            "buns": "pav_bhaji_buns.jpg",
            "bread": "pav_bhaji_buns.jpg",
            "pepsi": "pepsi.jpg",
            "red bull": "red_bull.jpg",
            "redbull": "red_bull.jpg",
            "sprite": "sprite.jpg",
            "dark fantasy": "sunfeast_dark_fantasy.jpg",
            "too yum": "too_yum_chips.jpg",
            "tooyum": "too_yum_chips.jpg",
            "biscuit": "toss_biscuit.jpg",
            "unibic": "unibic_cookies.jpg"
        }
        
        category_image_fallbacks = {
            "Oil": "https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400",
            "Biscuits": "https://images.unsplash.com/photo-1558961363-fa8fdf82db35?w=400",
            "Body Spray": "https://images.unsplash.com/photo-1596462502278-27bfdc403348?w=400",
            "Cosmetics": "https://images.unsplash.com/photo-1596462502278-27bfdc403348?w=400",
            "Face Wash": "https://images.unsplash.com/photo-1596462502278-27bfdc403348?w=400",
            "Hair Serum": "https://images.unsplash.com/photo-1596462502278-27bfdc403348?w=400",
            "Hair Oil": "https://images.unsplash.com/photo-1596462502278-27bfdc403348?w=400",
            "Chocolates": "https://images.unsplash.com/photo-1511381939415-e44015466834?w=400",
            "Cold Drinks": "https://images.unsplash.com/photo-1622483767028-3f66f32aef97?w=400",
            "Detergent": "https://images.unsplash.com/photo-1607006342411-92fc2a4d3600?w=400",
            "Soap": "https://images.unsplash.com/photo-1607006342411-92fc2a4d3600?w=400",
            "Hand Wash": "https://images.unsplash.com/photo-1607006342411-92fc2a4d3600?w=400",
            "Diaper": "https://images.unsplash.com/photo-1522850959516-58f958d6212e?w=400",
            "Santry Pad": "https://images.unsplash.com/photo-1522850959516-58f958d6212e?w=400",
            "Honey": "https://images.unsplash.com/photo-1587049352846-4a222e784d38?w=400",
            "Ketchup": "https://images.unsplash.com/photo-1607305387299-a3d9611cd46f?w=400",
            "souses": "https://images.unsplash.com/photo-1607305387299-a3d9611cd46f?w=400",
            "Tea": "https://images.unsplash.com/photo-1576092768241-dec231879fc3?w=400",
            "Tooth Brush": "https://images.unsplash.com/photo-1559591937-e6b359f4f134?w=400",
            "Toothpaste": "https://images.unsplash.com/photo-1559591937-e6b359f4f134?w=400",
            "Groceries": "https://images.unsplash.com/photo-1542838132-92c53300491e?w=400",
            "Other": "https://images.unsplash.com/photo-1542838132-92c53300491e?w=400",
            "MASALA": "https://images.unsplash.com/photo-1596790011460-155c89654714?w=400",
            "VICHARE MASALA": "https://images.unsplash.com/photo-1596790011460-155c89654714?w=400",
            "Milk drinks": "https://images.unsplash.com/photo-1563636619-e9143da7973b?w=400",
            "Butter": "https://images.unsplash.com/photo-1563636619-e9143da7973b?w=400",
            "Cheese": "https://images.unsplash.com/photo-1563636619-e9143da7973b?w=400",
            "Dahi": "https://images.unsplash.com/photo-1563636619-e9143da7973b?w=400",
            "Ghee": "https://images.unsplash.com/photo-1563636619-e9143da7973b?w=400",
            "Lassi": "https://images.unsplash.com/photo-1563636619-e9143da7973b?w=400",
            "Shrikhand": "https://images.unsplash.com/photo-1563636619-e9143da7973b?w=400",
            "Amul": "https://images.unsplash.com/photo-1563636619-e9143da7973b?w=400"
        }
        
        items_data = []
        if os.path.exists(items_csv_path):
            try:
                with open(items_csv_path, mode='r', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        # Extract only Name, Category, and Price
                        name = row.get('Item Name', '').strip()
                        cat = row.get('Category Name', '').strip()
                        if not cat:
                            cat = 'Other'
                        
                        price_str = row.get('Sales Rate', '0').strip()
                        try:
                            price = float(price_str)
                        except ValueError:
                            price = 0.0
                            
                        # Default stock
                        stock = 15
                        
                        # Default description
                        desc = f"Fresh quality product from {cat} category."
                        
                        # Image URL mapping
                        image_url = None
                        name_lower = name.lower()
                        
                        # Check local images first
                        for keyword, img_file in local_image_mappings.items():
                            if keyword in name_lower:
                                src_path = os.path.join(local_images_dir, img_file)
                                if os.path.exists(src_path):
                                    dst_path = os.path.join(uploads_dir, img_file)
                                    if not os.path.exists(dst_path):
                                        try:
                                            shutil.copy(src_path, dst_path)
                                        except Exception as copy_err:
                                            print(f"Error copying local image {img_file}: {copy_err}")
                                    image_url = img_file
                                    break
                                    
                        # No fallback image - keep it empty if not found locally
                        if not image_url:
                            image_url = ""

                            
                        items_data.append((name, desc, price, image_url, cat, stock))
            except Exception as e:
                print(f"Error parsing items CSV: {e}")
                
        if items_data:
            cursor.executemany("INSERT INTO items (name, description, price, image_url, category, stock) VALUES (?, ?, ?, ?, ?, ?)", items_data)
            print(f"Seeded database with {len(items_data)} items from CSV.")
        else:
            print("WARNING: No items parsed from CSV.")


    # Check for users
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        from werkzeug.security import generate_password_hash
        user_hash = generate_password_hash("password123")
        admin_hash = generate_password_hash("admin123")
        
        users_data = [
            ('testuser', 'test@example.com', user_hash, '1234567890', '123 Test St', 'User'),
            ('adminuser', 'patelkartavya79@gmail.com', admin_hash, '0987654321', '456 Admin St', 'Admin')
        ]
        cursor.executemany(
            "INSERT INTO users (username, email, password_hash, mobile_no, address, role) VALUES (?, ?, ?, ?, ?, ?)",
            users_data
        )
        print("Seeded database with default users.")

    connection.commit()
    connection.close()
    print(f"Database '{db_path}' and all required tables ensured.")

if __name__ == '__main__':
    create_database_and_table()


def sync_db_to_csv(db_path=None):
    """
    Exports the current items in the SQLite database back to the items_neocart.csv
    and item-categories_neocart.csv files. This keeps the CSV source files
    synchronized with any edits, additions, or deletions made through the website.
    """
    import csv
    if not db_path:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(base_dir, 'mart.db')
        
    items_csv_path = os.path.join(os.path.dirname(db_path), 'items_neocart.csv')
    categories_csv_path = os.path.join(os.path.dirname(db_path), 'item-categories_neocart.csv')
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 1. Export items
    cursor.execute("SELECT id, name, description, price, category, image_url, stock FROM items ORDER BY id")
    items = cursor.fetchall()
    
    try:
        with open(items_csv_path, mode='w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            # Match the exact headers of items_neocart.csv
            writer.writerow(['Item ID', 'Item Name', 'Description', 'Sales Rate', 'Category Name', 'image_url', 'Available Stock'])
            for item in items:
                price_val = item['price']
                # Format price safely
                if isinstance(price_val, float) and price_val.is_integer():
                    price_val = int(price_val)
                writer.writerow([
                    item['id'],
                    item['name'],
                    item['description'],
                    price_val,
                    item['category'],
                    item['image_url'] or '',
                    item['stock']
                ])
        print(f"Successfully synced database items to CSV: {len(items)} items written.")
    except Exception as e:
        print(f"Error syncing items to CSV: {e}")
        
    # 2. Export categories
    cursor.execute("SELECT DISTINCT category FROM items ORDER BY category")
    categories = cursor.fetchall()
    
    try:
        with open(categories_csv_path, mode='w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Name'])
            for cat in categories:
                if cat['category']:
                    writer.writerow([cat['category']])
        print(f"Successfully synced categories to CSV: {len(categories)} categories written.")
    except Exception as e:
        print(f"Error syncing categories to CSV: {e}")
        
    cursor.close()
    conn.close()

