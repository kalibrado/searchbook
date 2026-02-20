from flask import Flask, request, jsonify, send_from_directory
from search_book import search_annas_archive
import json
import os
from datetime import datetime

app = Flask(__name__)

FAVORITES_FILE = "favorites.json"

def load_favorites():
    """Charge les favoris depuis le fichier JSON"""
    if os.path.exists(FAVORITES_FILE):
        try:
            with open(FAVORITES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_favorites(favorites):
    """Sauvegarde les favoris dans le fichier JSON"""
    with open(FAVORITES_FILE, 'w', encoding='utf-8') as f:
        json.dump(favorites, f, ensure_ascii=False, indent=2)

@app.route("/")
def home():
    return send_from_directory("static", "index.html")

@app.route("/search")
def search():
    query = request.args.get("q")
    if not query:
        return jsonify({"error": "Missing q parameter"}), 400
    
    results = search_annas_archive(query, max_workers=15)
    return jsonify({
        "success": True,
        "total": len(results),
        "data": results
    })

@app.route("/favorites", methods=["GET"])
def get_favorites():
    """Récupère les favoris d'un utilisateur"""
    username = request.args.get("username")
    if not username:
        return jsonify({"error": "Missing username parameter"}), 400
    
    favorites = load_favorites()
    user_favorites = favorites.get(username, [])
    
    return jsonify({
        "success": True,
        "username": username,
        "total": len(user_favorites),
        "data": user_favorites
    })

@app.route("/favorites", methods=["POST"])
def add_favorite():
    """Ajoute un livre aux favoris"""
    data = request.json
    username = data.get("username")
    book = data.get("book")
    
    if not username or not book:
        return jsonify({"error": "Missing username or book data"}), 400
    
    favorites = load_favorites()
    
    if username not in favorites:
        favorites[username] = []
    
    # Vérifier si le livre n'est pas déjà dans les favoris
    book_exists = any(fav.get("url") == book.get("url") for fav in favorites[username])
    
    if book_exists:
        return jsonify({
            "success": False,
            "message": "Ce livre est déjà dans vos favoris"
        }), 400
    
    # Ajouter la date d'ajout
    book["added_at"] = datetime.now().isoformat()
    
    favorites[username].append(book)
    save_favorites(favorites)
    
    return jsonify({
        "success": True,
        "message": "Livre ajouté aux favoris",
        "total": len(favorites[username])
    })

@app.route("/favorites", methods=["DELETE"])
def remove_favorite():
    """Supprime un livre des favoris"""
    data = request.json
    username = data.get("username")
    book_url = data.get("url")
    
    if not username or not book_url:
        return jsonify({"error": "Missing username or url"}), 400
    
    favorites = load_favorites()
    
    if username not in favorites:
        return jsonify({"error": "User not found"}), 404
    
    # Filtrer pour retirer le livre
    initial_count = len(favorites[username])
    favorites[username] = [fav for fav in favorites[username] if fav.get("url") != book_url]
    
    if len(favorites[username]) == initial_count:
        return jsonify({
            "success": False,
            "message": "Livre non trouvé dans les favoris"
        }), 404
    
    save_favorites(favorites)
    
    return jsonify({
        "success": True,
        "message": "Livre retiré des favoris",
        "total": len(favorites[username])
    })

@app.route("/users", methods=["GET"])
def get_users():
    """Liste tous les utilisateurs ayant des favoris"""
    favorites = load_favorites()
    users = [
        {
            "username": username,
            "favorites_count": len(favs)
        }
        for username, favs in favorites.items()
    ]
    
    return jsonify({
        "success": True,
        "total": len(users),
        "data": users
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)