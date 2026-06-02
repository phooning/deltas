"""Panel entrypoint for the Deltas trading desk."""

from __future__ import annotations

import panel as pn

from pages.fundamentals import build_page


pn.extension("tabulator", "plotly", sizing_mode="stretch_width")


def app() -> pn.template.FastListTemplate:
    fundamentals = build_page()

    template = pn.template.FastListTemplate(
        title="Deltas",
        accent_base_color="#175cd3",
        header_background="#101828",
        sidebar=[
            pn.pane.Markdown("## Desk"),
            pn.pane.Markdown(
                "Medium-term context for ETF shares and long calls."
            ),
        ],
        main=[
            pn.Tabs(
                ("Fundamentals", fundamentals),
                dynamic=True,
                sizing_mode="stretch_width",
            )
        ],
    )
    return template


dashboard = app()
dashboard.servable()
