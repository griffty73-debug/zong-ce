from app import create_app

app = create_app()

if __name__ == "__main__":
    debug = app.config.get("FLASK_ENV") == "development"
    app.run(host="127.0.0.1", port=5003, debug=debug, use_reloader=False)
