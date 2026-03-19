"""
WSGI entry point for HelioHost (Apache + Passenger/mod_wsgi).
Wraps the FastAPI ASGI app into a WSGI-compatible application.
"""
import sys
import os

# Ensure the project root is on sys.path
sys.path.insert(0, os.path.dirname(__file__))

from a2wsgi import ASGIMiddleware
from api.main import app

# Passenger expects an `application` callable
application = ASGIMiddleware(app)
