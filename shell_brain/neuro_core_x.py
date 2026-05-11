"""
SHELL BRAIN - NEURO CORE X
Backend architecture templates for generated applications.
"""

from __future__ import annotations

import logging
from copy import deepcopy
from typing import Dict

logger = logging.getLogger("neuro_core_x")


class NeuroCoreX:
    """
    Logic and backend architect.
    Returns routes/models/extension templates by detected app archetype.
    """

    def __init__(self) -> None:
        self._blueprints: Dict[str, Dict[str, object]] = {
            "ecommerce": {
                "routes": [
                    """
@app.route('/api/products', methods=['GET'])
def get_products():
    try:
        sample_products = [
            {'id': 1, 'name': 'Neural Chip X1', 'price': 999.0, 'currency': 'USD', 'stock': 45},
            {'id': 2, 'name': 'Cyber Deck Pro', 'price': 2499.0, 'currency': 'USD', 'stock': 12},
        ]
        return jsonify({'status': 'success', 'data': sample_products}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
                    """.strip(),
                    """
@app.route('/api/cart', methods=['POST'])
def add_to_cart():
    try:
        payload = request.get_json(silent=True) or {}
        product_id = payload.get('product_id')
        quantity = int(payload.get('quantity', 1))

        if not product_id:
            return jsonify({'status': 'error', 'message': 'product_id is required'}), 400

        # MOCK DB INSERTION LOGIC HERE
        return jsonify({'status': 'success', 'data': {'product_id': product_id, 'quantity': quantity}}), 201
    except ValueError:
        return jsonify({'status': 'error', 'message': 'Invalid quantity format'}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
                    """.strip(),
                ],
                "models": [
                    """
class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, index=True)
    price = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
                    """.strip(),
                    """
class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    total = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(32), default='pending', index=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
                    """.strip(),
                ],
                "extensions": ["Flask", "SQLAlchemy", "CORS"],
            },
            "admin": {
                "routes": [
                    """
@app.route('/api/stats', methods=['GET'])
def get_stats():
    try:
        data = {
            'users_total': 10540,
            'active_sessions': 3215,
            'revenue_usd': 540000.50,
            'uptime_percent': 99.99,
        }
        return jsonify({'status': 'success', 'data': data}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
                    """.strip(),
                    """
@app.route('/api/audit', methods=['GET'])
def audit_logs():
    try:
        entries = [
            {'id': 1, 'action': 'login', 'user': 'admin', 'ip': '192.168.1.1'},
            {'id': 2, 'action': 'security_patch_deployed', 'user': 'system', 'ip': 'localhost'},
        ]
        return jsonify({'status': 'success', 'data': entries}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
                    """.strip(),
                ],
                "models": [
                    """
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    role = db.Column(db.String(32), default='viewer')
    last_login = db.Column(db.DateTime)
                    """.strip(),
                    """
class ActivityLog(db.Model):
    __tablename__ = 'activity_logs'
    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(200), nullable=False)
    actor = db.Column(db.String(64), nullable=False, index=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
                    """.strip(),
                ],
                "extensions": ["Flask", "SQLAlchemy", "CORS"],
            },
            "blog": {
                "routes": [
                    """
@app.route('/api/posts', methods=['GET'])
def get_posts():
    try:
        posts = [
            {'id': 1, 'title': 'The Singularity is Near', 'excerpt': 'What happens when AI codes itself?', 'author': 'Shell AI'},
            {'id': 2, 'title': 'Reliable AI Architectures', 'excerpt': 'Building maintainable systems', 'author': 'mdshoebking'},
        ]
        return jsonify({'status': 'success', 'data': posts}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
                    """.strip(),
                    """
@app.route('/api/post/<int:post_id>', methods=['GET'])
def get_post(post_id):
    try:
        if post_id <= 0:
            return jsonify({'status': 'error', 'message': 'Invalid Post ID'}), 400
            
        data = {
            'id': post_id,
            'title': 'Sample Architecture Post',
            'content': 'This is full markdown content generated dynamically...',
            'comments_count': 420,
        }
        return jsonify({'status': 'success', 'data': data}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
                    """.strip(),
                ],
                "models": [
                    """
class Post(db.Model):
    __tablename__ = 'posts'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    author = db.Column(db.String(100), nullable=False, index=True)
    published_at = db.Column(db.DateTime, server_default=db.func.now())
                    """.strip(),
                    """
class Comment(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, nullable=False, index=True)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
                    """.strip(),
                ],
                "extensions": ["Flask", "SQLAlchemy", "CORS"],
            },
            "landing": {
                "routes": [
                    """
@app.route('/api/signup', methods=['POST'])
def signup():
    payload = request.get_json(silent=True) or {}
    email = payload.get('email')
    if not email:
        return jsonify({'error': 'email is required'}), 400
    return jsonify({'status': 'subscribed', 'email': email}), 201
                    """.strip(),
                    """
@app.route('/api/features', methods=['GET'])
def get_features():
    return jsonify([
        {'icon': 'rocket', 'title': 'Lightning Fast', 'desc': '10x performance'},
        {'icon': 'shield', 'title': 'Secure', 'desc': 'Bank-grade encryption'},
    ]), 200
                    """.strip(),
                ],
                "models": [
                    """
class Subscriber(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    subscribed_at = db.Column(db.DateTime, server_default=db.func.now())
                    """.strip(),
                ],
                "extensions": ["Flask", "SQLAlchemy", "CORS"],
            },
            "portfolio": {
                "routes": [
                    """
@app.route('/api/contact', methods=['POST'])
def contact_form():
    payload = request.get_json(silent=True) or {}
    name = payload.get('name', 'anonymous')
    message = payload.get('message', '')
    if not message:
        return jsonify({'error': 'message is required'}), 400
    return jsonify({'status': 'message_received', 'from': name}), 200
                    """.strip(),
                ],
                "models": [],
                "extensions": ["Flask", "CORS"],
            },
        }

    def _detect_archetype(self, app_type: str) -> str:
        app = (app_type or "").lower()
        if any(token in app for token in ("shop", "commerce", "store", "market", "product")):
            return "ecommerce"
        if any(token in app for token in ("admin", "dashboard", "panel", "analytics")):
            return "admin"
        if any(token in app for token in ("blog", "article", "news", "content")):
            return "blog"
        if any(token in app for token in ("landing", "marketing", "promo", "campaign")):
            return "landing"
        return "portfolio"

    def get_backend_structure(self, app_type: str) -> dict:
        """Returns backend DNA for requested app type."""
        archetype = self._detect_archetype(app_type)
        structure = deepcopy(self._blueprints[archetype])
        structure["archetype"] = archetype
        logger.info("NeuroCoreX selected '%s' archetype for app_type='%s'", archetype, app_type)
        return structure


neuro_core = NeuroCoreX()
