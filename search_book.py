#!/usr/bin/env python3
"""
Script pour analyser Anna's Archive et extraire les livres avec leurs liens de téléchargement
Usage: python script.py "terme de recherche" [--workers 10] [--output json|web]
"""

import sys
import json
import requests
from bs4 import BeautifulSoup
from lxml import html, etree
from urllib.parse import urljoin, quote
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
from time import perf_counter

# Session réutilisable avec pool de connexions optimisé
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(
    pool_connections=20,
    pool_maxsize=20,
    max_retries=2
)
session.mount('http://', adapter)
session.mount('https://', adapter)
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept-Encoding': 'gzip, deflate'
})

def get_book_details(book_url):
    """
    Récupère les détails d'un livre depuis sa page
    """
    try:
        response = session.get(book_url, timeout=8)
        response.raise_for_status()
        
        # Parse une seule fois avec lxml (plus rapide que BeautifulSoup)
        tree = html.fromstring(response.content)
        
        # Extraire l'image (première img avec src)
        image = tree.xpath('//img/@src')
        image = image[0] if image else ""
        
        # Extraire le titre (plusieurs fallbacks)
        title = (
            tree.xpath("/html/body/main/div/div[1]/div[2]/text()") or
            tree.xpath("/html/body/main/div/div[1]/div[3]/text()") or
            tree.xpath("//a[contains(@class, 'custom-a')]//text()")
        )
        main_title = title[0].strip() if title else ""
        
  # Extraire tous les liens de téléchargement
        download_links = tree.xpath("//a[contains(@class, 'js-download-link')]/@href")
        # Convertir les liens relatifs en URLs absolues
        download_links = [urljoin(book_url, link) if not link.startswith('http') else link for link in download_links]
        
        return {
            "main_title": main_title,
            "download_links": download_links,
            "image": image
        }
    
    except requests.Timeout:
        print(f"⏱️  Timeout pour {book_url}", file=sys.stderr)
        return {"main_title": "", "download_links": [], "image": ""}
    except Exception as e:
        print(f"❌ Erreur pour {book_url}: {e}", file=sys.stderr)
        return {"main_title": "", "download_links": [], "image": ""}


def process_book(args):
    """
    Traite un seul livre (pour le multi-threading)
    """
    i, elem, tree, base_url = args
    
    try:
        # Chercher le lien <a> dans l'élément
        link = elem.find('a') if elem.name != 'a' else elem
        
        if not link or not link.get('href'):
            return None
        
        url = urljoin(base_url, link.get('href'))
        
        # Extraire les informations via XPath (optimisé)
        base_xpath = f"/html/body/main/div/form/div/div[2]/div[3]/div[2]/div/div[{i}]/div"
        
        edition = tree.xpath(f"{base_xpath}/div[1]/a[3]/text()")
        author = tree.xpath(f"{base_xpath}/div[1]/a[2]/text()")
        description = tree.xpath(f"{base_xpath}/div[2]/div[2]/div/text()")
        
        # Récupérer les détails de la page du livre
        details = get_book_details(url)
        
        # Construire le résultat de manière plus propre
        result = {
            "title": details["main_title"] or "Titre non disponible",
            "author": author[0].strip() if author else "Auteur inconnu",
            "edition": edition[0].strip() if edition else "",
            "description": " ".join(d.strip() for d in description).strip() or "Pas de description",
            "image": details["image"] or "/placeholder.jpg",
            "url": url,
            "download_links": details["download_links"],
            "download_count": len(details["download_links"])
        }
        
        return result
    
    except Exception as e:
        print(f"❌ Erreur traitement livre {i}: {e}", file=sys.stderr)
        return None


def search_annas_archive(query, max_workers=10):
    """
    Recherche sur Anna's Archive et retourne les résultats au format JSON
    """
    base_url = "https://fr.annas-archive.li/"
    search_url = f"{base_url}/search?index=&page=1&sort=newest_added&lang=fr&display=&q={quote(query)}"
    try:
        print(f"🔍 Recherche en cours...", file=sys.stderr)
        response = session.get(search_url, timeout=10)
        response.raise_for_status()
        
        # Parser avec lxml (plus rapide)
        tree = html.fromstring(response.content)
        
        # Récupérer tous les éléments avec la classe 'js-vim-focus'
        soup = BeautifulSoup(response.content, 'lxml')  # lxml parser plus rapide
        elements = soup.find_all(class_='js-vim-focus')
        
        total = len(elements)
        print(f"📚 {total} résultats trouvés", file=sys.stderr)
        print(f"⚡ Utilisation de {max_workers} threads parallèles", file=sys.stderr)
        print("-" * 50, file=sys.stderr)
        
        results = []
        
        # Préparer les arguments pour chaque livre
        tasks = [(i+1, elem, tree, base_url) for i, elem in enumerate(elements)]
        
        # Traitement parallèle
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(process_book, task): task[0] for task in tasks}
            
            completed = 0
            for future in as_completed(futures):
                completed += 1
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                        progress = (completed / total) * 100
                        print(f"✓ [{completed}/{total}] {progress:.1f}% - {result['title'][:50]}", file=sys.stderr)
                except Exception as e:
                    print(f"❌ Erreur: {e}", file=sys.stderr)
        
        return results
    
    except requests.RequestException as e:
        print(f"❌ Erreur de connexion: {e}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"❌ Erreur inattendue: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return []


def format_for_web(results):
    """
    Formate les résultats pour une utilisation web (structure optimisée)
    """
    return {
        "success": True,
        "total": len(results),
        "query_time": None,  # sera rempli dans main()
        "data": results
    }


def main():
    t1_start = perf_counter()
    
    parser = argparse.ArgumentParser(
        description='🔍 Recherche de livres sur Anna\'s Archive',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  python script.py "python programming"
  python script.py "machine learning" --workers 15
  python script.py "data science" --output web > results.json
        """
    )
    parser.add_argument('query', help='Terme de recherche')
    parser.add_argument('--workers', type=int, default=10, 
                       help='Nombre de threads parallèles (défaut: 10, recommandé: 10-15)')
    parser.add_argument('--output', choices=['json', 'web'], default='json',
                       help='Format de sortie (json=simple, web=optimisé pour API)')
    
    args = parser.parse_args()
    
    print(f"🚀 Recherche de: '{args.query}'", file=sys.stderr)
    print("=" * 50, file=sys.stderr)
    
    results = search_annas_archive(args.query, max_workers=args.workers)
    
    t1_stop = perf_counter()
    elapsed = t1_stop - t1_start
    
    print("=" * 50, file=sys.stderr)
    print(f"✅ Terminé! {len(results)} livres trouvés en {elapsed:.2f}s", file=sys.stderr)
    print(f"⚡ Vitesse: {len(results)/elapsed:.1f} livres/seconde", file=sys.stderr)
    
    # Formater la sortie selon le format demandé
    if args.output == 'web':
        output = format_for_web(results)
        output['query_time'] = round(elapsed, 2)
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()