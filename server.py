from app import create_app

app = create_app()

# ------ Ruta necesaria para Railway (health check) ------
@app.route("/")
def health_check():
    return "OK", 200
# --------------------------------------------------------

if __name__ == "__main__":
    app.run()