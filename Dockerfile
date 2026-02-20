# Étape 1 : image Python légère
FROM python:3.12-slim

# Définir le répertoire de travail
WORKDIR /app

# Copier les fichiers Python et HTML/JS
COPY . /app

# Installer Flask et requests (nécessaires pour ton script)
RUN pip install --no-cache-dir flask requests beautifulsoup4 lxml

# Exposer le port
EXPOSE 5000

# Commande de démarrage
CMD ["python", "server.py"]
