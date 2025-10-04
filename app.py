from flask import Flask, request, jsonify, redirect, render_template
import sqlite3
import string
import random
import os

app = Flask(__name__)

# ---------------------- SIMPLE IN-MEMORY CACHE (No Redis Needed) ----------------------
class SimpleCache:
    def __init__(self):
        self.store = {}

    def get(self, key):
        return self.store.get(key)

    def set(self, key, value):
        self.store[key] = value

cache = SimpleCache()

# ---------------------- SQLITE DATABASE SETUP ----------------------
def init_db():
    conn = sqlite3.connect('shortly.db')
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS urls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            short_code TEXT UNIQUE,
            long_url TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# ---------------------- HELPER FUNCTION ----------------------
def generate_short_code(length=6):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

# ---------------------- ROUTES ----------------------

# Home Page
@app.route('/')
def home():
    return render_template('index.html')

# API: Create Short URL
@app.route('/shorten', methods=['POST'])
def shorten_url():
    long_url = request.form.get('url')

    if not long_url:
        return jsonify({'error': 'URL is required'}), 400

    # Check if cached
    cached_short = cache.get(long_url)
    if cached_short:
        return jsonify({
            'short_url': f"http://localhost:5000/{cached_short}",
            'cached': True
        }), 200

    # Generate short code
    short_code = generate_short_code()

    # Store in SQLite
    conn = sqlite3.connect('shortly.db')
    cur = conn.cursor()
    cur.execute('INSERT INTO urls (short_code, long_url) VALUES (?, ?)', (short_code, long_url))
    conn.commit()
    conn.close()

    # Cache both directions
    cache.set(short_code, long_url)
    cache.set(long_url, short_code)

    return jsonify({
        'short_url': f"http://localhost:5000/{short_code}",
        'cached': False
    }), 201

# Redirect Short URL → Original
@app.route('/<short_code>')
def redirect_url(short_code):
    # Try cache first
    long_url = cache.get(short_code)
    if long_url:
        return redirect(long_url)

    # Fallback to DB
    conn = sqlite3.connect('shortly.db')
    cur = conn.cursor()
    cur.execute('SELECT long_url FROM urls WHERE short_code = ?', (short_code,))
    result = cur.fetchone()
    conn.close()

    if result:
        long_url = result[0]
        cache.set(short_code, long_url)
        return redirect(long_url)
    else:
        return "⚠️ URL not found or expired.", 404

# Admin: List all stored URLs
@app.route('/urls')
def view_urls():
    conn = sqlite3.connect('shortly.db')
    cur = conn.cursor()
    cur.execute('SELECT short_code, long_url FROM urls ORDER BY id DESC')
    data = cur.fetchall()
    conn.close()

    return jsonify([{'short_code': s, 'long_url': l} for s, l in data])

# ---------------------- RUN APP ----------------------
if __name__ == '__main__':
    app.run(debug=True)
