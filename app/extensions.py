from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

db: SQLAlchemy = SQLAlchemy()
migrate: Migrate = Migrate()
jwt: JWTManager = JWTManager()
cors: CORS = CORS()

limiter: Limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["2000 per day", "500 per hour"],
    storage_uri="memory://",
)
