import os
import sys
from flask import Flask, render_template, request, jsonify

# Asosiy loyiha yo'lini qo'shish (modules ni topish uchun)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from modules.database import db

app = Flask(__name__)

@app.route('/')
def index():
    chats = db.get_all_chats()
    return render_template('index.html', chats=chats)

@app.route('/api/stats/<chat_id>')
def get_stats(chat_id):
    stats = db.get_stats(int(chat_id))
    return jsonify(stats)

@app.route('/api/members/<chat_id>')
def get_members(chat_id):
    search = request.args.get('search', '')
    gender = request.args.get('gender', 'All')
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 50))
    offset = (page - 1) * limit
    
    cid = int(chat_id)
    members = db.get_members_paginated(cid, search, gender, offset, limit)
    total = db.get_total_count(cid, search, gender)
    
    return jsonify({
        "members": members,
        "total": total,
        "page": page,
        "pages": (total + limit - 1) // limit
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)
