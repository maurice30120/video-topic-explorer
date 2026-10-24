# Contribuer

## Règle bilingue

Le projet est volontairement bilingue ; c'est une décision, pas une dérive :

- **Identifiants de code en anglais** : noms de variables, fonctions, classes, modules, options CLI — convention Python du projet.
- **Clés JSON selon la destination** : les artefacts machines consommés par le code (`run.json`, corpus, modules Python) gardent des clés anglaises ; les rapports évalués à destination humaine (`eval/decision.json` : `moyennes`, `seuil`, `comparaisons`, `origine`…) suivent la langue des documents, donc le français. C'est une décision délibérée (dont le renommage `kind`→`origine`) : ne pas renommer ces clés existantes.
- **Interfaces visibles et documents en français** : libellés des interfaces, README, `docs/`, docstrings, messages d'erreur destinés à l'utilisateur — selon le vocabulaire de [GLOSSARY.md](GLOSSARY.md).
- Utiliser les termes consacrés du glossaire (sujet, transition, parcours, Approfondir, Découvrir, baseline, corpus, chemin de sujets, sujet mort, rétention applicative) et éviter les formulations listées en *Avoid*.

## Tests

```bash
python3 -m pytest tests/ -q
```

Aucun test réseau, Gemini ni framework d'UI ; les corpus de test sont des fixtures JSON figées dans `tests/conftest.py`.

## Commits

Conventionnels, sujet en français, ex. `docs(adr): ...`, `fix(engine): ...`.
