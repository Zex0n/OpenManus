import os
from flask import Flask, send_from_directory
from flask_cors import CORS
from webserver.backend.src.models.user import db
from webserver.backend.src.routes.chat import chat_bp
from webserver.backend.src.routes.user import user_bp
from app.config import config

app = Flask(__name__, static_folder=os.path.join("webserver", "frontend", "dist"))
app.config["SECRET_KEY"] = "asdf#FGSgvasgf$5$WGT"
CORS(app)

app.register_blueprint(user_bp, url_prefix="/api")
app.register_blueprint(chat_bp, url_prefix="/api")

db_path = os.path.join(config.root_path, "webserver", "backend", "src", "database", "app.db")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve(path):
    static_folder_path = app.static_folder
    if static_folder_path is None:
        return "Static folder not configured", 404

    if path != "" and os.path.exists(os.path.join(static_folder_path, path)):
        return send_from_directory(static_folder_path, path)
    else:
        index_path = os.path.join(static_folder_path, "index.html")
        if os.path.exists(index_path):
            return send_from_directory(static_folder_path, "index.html")
        else:
            return "index.html not found", 404

if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    backend_cfg = getattr(config, 'backend', None)
    if backend_cfg:
        host = getattr(backend_cfg, 'host', '0.0.0.0')
        port = getattr(backend_cfg, 'port', 5000)
    else:
        host = '0.0.0.0'
        port = 5000
    app.run(host=host, port=port, debug=True)
