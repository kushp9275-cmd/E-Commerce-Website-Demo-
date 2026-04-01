import sqlite3
import os

def create_database_and_table():
    db_path = 'mart.db'
    
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
        status VARCHAR(20) DEFAULT 'pending',
        order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """)

    # Check for items
    cursor.execute("SELECT COUNT(*) FROM items")
    if cursor.fetchone()[0] == 0:
        items_data = [
            ('Fresh Apple', 'Crisp and sweet red apples.', 1.99, 'https://images.unsplash.com/photo-1560806887-1e4cd0b6bcd6?w=400', 'Produce', 10),
            ('Whole Milk', '1 Gallon of fresh whole milk.', 3.49, 'https://images.unsplash.com/photo-1550583724-b2692b85b150?w=400', 'Dairy', 10),
            ('Sourdough Bread', 'Freshly baked artisan sourdough bread.', 4.50, 'https://images.unsplash.com/photo-1585478259715-876acc5be8eb?w=400', 'Bakery', 10),
            ('Organic Coffee', 'Dark roast organic coffee beans.', 12.99, 'https://images.unsplash.com/photo-1559056199-641a0ac8b55e?w=400', 'Drinks', 10),
            ('Free Range Eggs', 'Dozen large free range brown eggs.', 5.20, 'https://images.unsplash.com/photo-1518562180175-34a163b1a9a6?w=400', 'Dairy', 10),
            ('Avocado', 'Ripe Hass avocado, perfect for toast.', 2.10, 'https://images.unsplash.com/photo-1523049673857-eb18f1d7b578?w=400', 'Produce', 10),
            ('Orange Juice', 'Freshly squeezed 100% orange juice.', 4.99, 'https://images.unsplash.com/photo-1613478223719-2ab802602423?w=400', 'Drinks', 10),
            ('Potato Chips', 'Crispy, lightly salted potato chips.', 2.50, 'https://images.unsplash.com/photo-1566478438185-95a3136d493a?w=400', 'Snacks', 10),
            ('Dark Chocolate', '70% cocoa organic dark chocolate bar.', 3.50, 'https://images.unsplash.com/photo-1511381939415-e44015466834?w=400', 'Snacks', 10),
            ('Green Tea', 'Premium organic matcha green tea.', 6.99, 'https://images.unsplash.com/photo-1544787210-2211d7c9ad0b?w=400', 'Drinks', 10),
            ('Cheddar Cheese', 'Aged sharp cheddar cheese block.', 5.50, 'https://images.unsplash.com/photo-1618161595703-3e9d28211fc1?w=400', 'Dairy', 10),
            ('Croissant', 'Flaky, buttery French-style croissant.', 2.99, 'https://images.unsplash.com/photo-1555507036-ab1f4038808a?w=400', 'Bakery', 10)
        ]
        cursor.executemany("INSERT INTO items (name, description, price, image_url, category, stock) VALUES (?, ?, ?, ?, ?, ?)", items_data)
        print("Seeded database with items.")

    connection.commit()
    connection.close()
    print(f"Database '{db_path}' and all required tables ensured.")

if __name__ == '__main__':
    create_database_and_table()
