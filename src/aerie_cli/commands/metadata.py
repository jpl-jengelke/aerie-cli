import json

import arrow
import typer
from rich.console import Console
from rich.table import Table

from aerie_cli.utils.sessions import get_active_session_client

app = typer.Typer()


# placeholder for now
@app.command()
def upload(
    schema_path: str = typer.Option(
        ..., help="path to JSON file defining the schema to be created", prompt=True
    ),
):
    """Add to the metadata schema from a .json file."""
    client = get_active_session_client()

    with open(schema_path) as in_file:
        contents = in_file.read()
    schema_data = json.loads(contents)
    result = client.add_metadata_schemas(schema_data["schemas"])
    print(result)


# placeholder for now
@app.command()
def delete(
    schema_name: str = typer.Option(
        ..., help="Name of schema to be deleted", prompt=True
    ),
):
    """Delete a metadata schema by its name."""
    resp = get_active_session_client().delete_metadata_schema(schema_name)
    typer.echo(f"Schema `{resp}` has been removed.")


@app.command()
def list():
    """List uploaded mission models."""

    resp = get_active_session_client().get_metadata()

    table = Table(title="Metadata Schemas")
    table.add_column("Key", style="magenta")
    table.add_column("Schema", no_wrap=True)
    for schema in resp:
        table.add_row(
            str(schema["key"]),
            str(schema["schema"]["type"]),
        )

    console = Console()
    console.print(table)
