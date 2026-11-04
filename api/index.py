"""
Vercel serverless function entrypoint.
Imports and exposes the Flask WSGI application callable.
"""
from app import app

# Vercel looks for the WSGI application as `app`
if __name__ == "__main__":
    app.run()
