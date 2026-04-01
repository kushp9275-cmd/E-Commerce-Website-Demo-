# E-Commerce Website - Final Project

A sophisticated, full-stack digital storefront featuring a modern glassmorphic design and secure payment integrations.

## 🚀 Features
- **Modern UI:** Responsive, premium design with subtle micro-animations.
- **Secure Payments:** Full integration with the **Razorpay** payment gateway for safe transactions.
- **Dynamic Catalog:** Automated product categorization with professional item identification.
- **Admin Dashboard:** Powerful management tools for inventory, stock levels, and item modifications.
- **Portable Database:** Uses **SQLite** for zero-configuration setup, making the project easy to move and deploy.
- **Persistent Cart:** Real-time shopping cart that keeps track of your items across sessions.

## 🛠️ Technology Stack
- **Backend:** Flask (Python)
- **Frontend:** HTML5, CSS3 (Vanilla), JavaScript
- **Database:** SQLite
- **Payment Gateway:** Razorpay SDK
- **Environment Management:** python-dotenv

## 📦 Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
   cd E-Commerce-Website
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables:**
   Create a `.env` file in the root directory and add your Razorpay keys:
   ```env
   RAZORPAY_KEY_ID=your_key_id
   RAZORPAY_KEY_SECRET=your_key_secret
   ```

4. **Initialize the Database:**
   ```bash
   python setup_db.py
   ```

5. **Run the Application:**
   ```bash
   python app.py
   ```
   The website will be available at `http://127.0.0.1:5000`.

## 📜 Description
This project is a state-of-the-art E-Commerce platform designed to provide a secure and aesthetically pleasing user experience. From the automated stock tracking to the seamless payment flow, every component is refined for reliability and speed.
