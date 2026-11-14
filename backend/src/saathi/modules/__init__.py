"""Business modules (bounded contexts). Each could become its own service later.

Rule: a module never imports another module's internals. Cross-module needs go through the
other module's public facade (its __init__.py) or, later, domain events.
"""
