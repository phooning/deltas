"""Panel server entrypoint for the local Deltas trading desk MVP shell."""

import panel as pn

from trading_desk.app import create_app


pn.extension(
    "plotly",
    "tabulator",
    "vega",
    sizing_mode="stretch_width",
    notifications=True,
)

app = create_app()
app.servable()


if __name__ == "__main__":
    pn.serve(
        app,
        address="localhost",
        port=5006,
        show=False,
        title="Deltas Trading Desk",
        websocket_origin=["localhost:5006", "127.0.0.1:5006"],
    )
