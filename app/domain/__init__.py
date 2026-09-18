"""
Domain value types shared across scrapers, orchestration, AI and the API.

Deliberately free of imports from those layers: ``app/orchestration/__init__``
eagerly imports the orchestrators, so anything importing a value type from
there would drag in the whole orchestration layer and create import cycles.
"""
