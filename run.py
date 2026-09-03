import os
from app import create_app
from app.extensions import db

app = create_app(os.getenv("FLASK_ENV", "development"))

# Ensure database tables exist whether started via Gunicorn or direct python execution
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print(f"  MSME360 running on http://127.0.0.1:{port}")
    app.run(host="0.0.0.0", port=port, debug=True)
