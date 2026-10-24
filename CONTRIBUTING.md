# Contribuer

## Règle bilingue

Le projet est volontairement bilingue ; c'est une décision, pas une dérive :

- **Identifiants de code en anglais** : noms de variables, fonctions, classes, modules, options CLI, clés JSON — convention Python du projet.
- **Interfaces visibles et documents en français** : libellés des interfaces, README, `docs/`, docstrings, messages d'erreur destinés à l'utilisateur — selon le vocabulaire de [GLOSSARY.md](GLOSSARY.md).
- Utiliser les termes consacrés du glossaire (sujet, transition, parcours, Approfondir, Découvrir, baseline, corpus, chemin de sujets, sujet mort, rétention applicative) et éviter les formulations listées en *Avoid*.

## Tests

```bash
python3 -m pytest tests/ -q
```

Aucun test réseau, Gemini ni framework d'UI ; les corpus de test sont des fixtures JSON figées dans `tests/conftest.py`.

## Commits

Conventionnels, sujet en français, ex. `docs(adr): ...`, `fix(engine): ...`.
