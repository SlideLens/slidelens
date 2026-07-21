"""Review core: pure library for ingest, analyzers, aggregate, report.

Never imports ``app`` and never touches the database. Inputs are file paths
plus ``ReviewContext``; outputs are ``Finding`` lists and on-disk artifacts.
Bridged to the web layer only by ``worker.tasks``.
"""
