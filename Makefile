PY ?= python3
CORPUS ?= data/corpus_real.json
START ?= ghnY4S8unMM
RUN ?= data/runs/demo.json
PORT ?= 8000
ELARGI ?= data/corpus_elargi.json
ELARGI_START ?= xuCn8ux2gbs

.PHONY: serve run feed preview graph render stats test real demo arbre panneau elargi elargi-site help

help: ## Liste les cibles disponibles
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "} {printf "  make %-10s %s\n", $$1, $$2}'

serve: ## Serveur local : sélection, parcours, graphe (127.0.0.1, PORT 8000)
	$(PY) -m vte.cli serve $(CORPUS) --port $(PORT)

run: ## Calcule un parcours au rayon 3 depuis START
	$(PY) -m vte.cli run $(CORPUS) --start $(START) --rayon 3 --out $(RUN)

feed: ## Génère le feed statique out/site/index.html
	$(PY) -m vte.cli feed $(CORPUS) --out out/site/index.html

preview: ## Sert out/site en local (http://127.0.0.1:8377) et ouvre le navigateur
	$(PY) -m http.server 8377 --directory out/site

graph: ## Génère le graphe out/graphe.png (run surligné si présent)
	$(PY) -m vte.cli graph $(CORPUS) --run $(RUN) --out out/graphe.png

render: ## Génère la page parcours out/parcours.html
	$(PY) -m vte.cli render $(CORPUS) --run $(RUN) --out out/parcours.html

stats: ## Stats du graphe : composantes, sujets morts, densité
	$(PY) -m vte.cli stats $(CORPUS)

test: ## Lance la suite de tests
	$(PY) -m pytest

real: ## Régénère le corpus réel data/corpus_real.json
	$(PY) scripts/make_real_corpus.py

demo: ## Génère le corpus de démo fictif data/corpus_demo.json
	$(PY) scripts/make_demo_corpus.py

arbre: ## Régénère le corpus arbre étoffé data/corpus_arbre.json (69 vidéos, 14 branches)
	$(PY) scripts/make_arbre_corpus.py

panneau: ## Panneau à rétention sur le corpus arbre (http://127.0.0.1:8200)
	$(PY) -m vte.cli serve data/corpus_arbre.json --port 8200

elargi: ## Régénère le corpus élargi data/corpus_elargi.json (corpus réel + 22 vidéos : musique, fun, science, économie, jeux)
	$(PY) scripts/make_elargi_corpus.py

elargi-site: ## Site local depuis le corpus élargi : out/site (feed + parcours + graphe surligné, départ bill wurtz)
	$(PY) -m vte.cli run $(ELARGI) --start $(ELARGI_START) --rayon 3 --out out/run/elargi.json
	$(PY) -m vte.cli feed $(ELARGI) --start $(ELARGI_START) --out out/site/index.html
	$(PY) -m vte.cli graph $(ELARGI) --run out/run/elargi.json --out out/site/graphe.png
	$(PY) -m vte.cli render $(ELARGI) --run out/run/elargi.json --out out/site/parcours.html
