import marimo

__generated_with = "0.15.5"
app = marimo.App(width="full")


@app.cell
def _():
    HEPTABASE_BACKUP="./data/heptabase"
    return (HEPTABASE_BACKUP,)


@app.cell
def _(HEPTABASE_BACKUP):
    from notes.heptabase import loader
    kg = loader.load_graph_from_backup(HEPTABASE_BACKUP)
    import polars
    df = polars.DataFrame(kg.cards)
    df
    return (kg,)


@app.cell
def _(kg):
    kg.cards
    return


@app.cell
def _(kg):
    import marimo as mo
    mo.ui.table(kg.cards)

    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r""" """)
    return


if __name__ == "__main__":
    app.run()
