"""FastAPI middleware that lives next to `core/`.

Each module defines one middleware class plus any helpers it needs. The
`main.py` lifespan wires them into the FastAPI app in the right order
(request-ID outermost, CORS innermost).
"""
