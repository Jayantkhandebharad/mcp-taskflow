"""One router per resource. ``main.py`` mounts them all.

A FastAPI ``APIRouter`` is a group of routes sharing a URL prefix and tags.
Splitting by resource keeps each file about one thing, which matters more
than usual here because each file is also a teaching example.
"""
