import typer
from typing import List
app = typer.Typer()
@app.command()
def test(arg1: List[str] = typer.Argument(...)):
    print(arg1)
app()
