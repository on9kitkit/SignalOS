from fastapi import FastAPI
from fastapi.responses import HTMLResponse


app = FastAPI(title="SignalOS Dashboard")


@app.get("/", response_class=HTMLResponse)
def dashboard_home() -> str:
    return """
    <!doctype html>
    <html>
        <head>
            <title>SignalOS Dashboard</title>
        </head>
        <body>
            <h1>SignalOS Dashboard Online</h1>
            <p>The web UI layer is running.</p>
        </body>
    </html>
    """