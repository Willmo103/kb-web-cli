import json
import socket
from pathlib import Path
from typing import Optional

import typer
import httpx

app = typer.Typer(
    help="Standalone CLI Command Station to interact with a LIVE kb-web server.",
    no_args_is_help=True,
)


def load_client_config() -> dict:
    config_file = Path.home() / ".kb" / "cli-config.json"
    if not config_file.exists():
        typer.secho(
            "Error: CLI is not installed/configured. Please run 'kb-cli install' first.",
            fg=typer.colors.RED,
            bold=True,
            err=True
        )
        raise typer.Exit(code=1)

    try:
        with open(config_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        typer.secho(
            f"Error reading configuration: {str(e)}",
            fg=typer.colors.RED,
            bold=True,
            err=True
        )
        raise typer.Exit(code=1)


@app.command("install")
def client_install(
    server_url: str = typer.Option("http://localhost:8050", prompt="Enter the LIVE server URL"),
    api_key: str = typer.Option(..., prompt="Enter your generated CLI API Key"),
):
    """Registers this client computer with the LIVE server and saves credentials locally."""
    server_url = server_url.rstrip("/")
    computer_name = socket.gethostname()

    typer.echo(f"Attempting to register client '{computer_name}' with server '{server_url}'...")

    try:
        with httpx.Client(timeout=15.0) as client:
            res = client.post(
                f"{server_url}/api/cli/register",
                headers={"X-API-Key": api_key},
                json={"computer_name": computer_name},
            )

        if res.status_code == 200:
            data = res.json()
            if data.get("status") == "success":
                config_dir = Path.home() / ".kb"
                config_dir.mkdir(parents=True, exist_ok=True)
                config_file = config_dir / "cli-config.json"

                with open(config_file, "w", encoding="utf-8") as f:
                    json.dump({
                        "server_url": server_url,
                        "api_key": api_key,
                        "computer_name": computer_name
                    }, f, indent=4)

                typer.secho("Success: Client registered and CLI configuration saved!", fg=typer.colors.GREEN, bold=True)
            else:
                typer.secho(f"Registration failed: {data.get('message')}", fg=typer.colors.RED, bold=True, err=True)
        else:
            typer.secho(f"Error {res.status_code}: {res.text}", fg=typer.colors.RED, bold=True, err=True)
    except Exception as e:
        typer.secho(f"Network error: {str(e)}", fg=typer.colors.RED, bold=True, err=True)


@app.command("import")
def client_import(
    url: str = typer.Argument(..., help="The URL to process and import on the server."),
    collection_id: Optional[str] = typer.Option(None, help="Optional target collection ID."),
    new_collection_title: Optional[str] = typer.Option(None, help="Optional new collection title to create.")
):
    """Submits a URL to the server for fetch, rewrite, and indexing."""
    cfg = load_client_config()

    typer.echo(f"Submitting URL '{url}' for processing...")
    try:
        with httpx.Client(timeout=300.0) as client:
            res = client.post(
                f"{cfg['server_url']}/api/cli/import/url",
                headers={"X-API-Key": cfg["api_key"]},
                data={
                    "url": url,
                    "collection_id": collection_id,
                    "new_collection_title": new_collection_title
                },
            )
        if res.status_code == 200:
            data = res.json()
            if data.get("status") == "success":
                typer.secho(f"Success: {data.get('message')}", fg=typer.colors.GREEN, bold=True)
                typer.echo(f"Title: {data.get('title')}")
                typer.echo(f"Tags: {', '.join(data.get('tags', []))}")
            else:
                typer.secho(f"Error: {data.get('message')}", fg=typer.colors.RED, bold=True, err=True)
        else:
            typer.secho(f"Error {res.status_code}: {res.text}", fg=typer.colors.RED, bold=True, err=True)
    except Exception as e:
        typer.secho(f"Network/Server timeout error: {str(e)}", fg=typer.colors.RED, bold=True, err=True)


@app.command("list")
def client_list(
    limit: int = typer.Option(10, "--limit", "-n", help="Number of items to retrieve."),
    type: Optional[str] = typer.Option(None, help="Filter by type ('videos' or 'articles').")
):
    """Lists recent articles and videos ingested in the Knowledge Base."""
    cfg = load_client_config()

    params = {"limit": limit}
    if type:
        params["type"] = type

    try:
        with httpx.Client(timeout=15.0) as client:
            res = client.get(
                f"{cfg['server_url']}/api/cli/pages",
                headers={"X-API-Key": cfg["api_key"]},
                params=params,
            )
        if res.status_code == 200:
            items = res.json()
            if not items:
                typer.echo("No items found.")
                return

            typer.secho(f"\n--- Recent {len(items)} Items ---", bold=True)
            for i, item in enumerate(items):
                typer.secho(f"{i+1}. {item['title']}", fg=typer.colors.CYAN, bold=True)
                typer.echo(f"   URL: {item['url']}")
                typer.echo(f"   Fetched: {item['fetched_at']}")
                if item.get("tags"):
                    typer.echo(f"   Tags: {', '.join(item['tags'])}")
                typer.echo("")
        else:
            typer.secho(f"Error {res.status_code}: {res.text}", fg=typer.colors.RED, bold=True, err=True)
    except Exception as e:
        typer.secho(f"Network error: {str(e)}", fg=typer.colors.RED, bold=True, err=True)


@app.command("action")
def client_action(
    action: str = typer.Argument(..., help="The action: 'regenerate-wiki', 'download-video', or 'regenerate-tags'"),
    url: str = typer.Argument(..., help="The URL of the target article/video.")
):
    """Triggers a privileged processing function on the server."""
    cfg = load_client_config()

    typer.echo(f"Triggering action '{action}' for URL '{url}'...")
    try:
        with httpx.Client(timeout=300.0) as client:
            res = client.post(
                f"{cfg['server_url']}/api/cli/pages/action",
                headers={"X-API-Key": cfg["api_key"]},
                data={"url": url, "action": action},
            )
        if res.status_code == 200:
            data = res.json()
            if data.get("status") == "success":
                typer.secho(f"Success: {data.get('message')}", fg=typer.colors.GREEN, bold=True)
                if "wiki" in data:
                    typer.echo(f"Wiki summary:\n{data['wiki']}")
                if "tags" in data:
                    typer.echo(f"Tags: {', '.join(data['tags'])}")
                if "local_path" in data:
                    typer.echo(f"Local Path: {data['local_path']}")
            else:
                typer.secho(f"Error: {data.get('message')}", fg=typer.colors.RED, bold=True, err=True)
        else:
            typer.secho(f"Error {res.status_code}: {res.text}", fg=typer.colors.RED, bold=True, err=True)
    except Exception as e:
        typer.secho(f"Network error: {str(e)}", fg=typer.colors.RED, bold=True, err=True)


@app.command("collections")
def client_collections(
    list_all: bool = typer.Option(False, "--list", "-l", help="List available collections and item counts."),
    add: bool = typer.Option(False, "--add", help="Add an item to a collection."),
    remove: bool = typer.Option(False, "--remove", help="Remove an item from a collection."),
    collection_id: Optional[int] = typer.Option(None, "--id", help="The target collection ID."),
    url: Optional[str] = typer.Option(None, "--url", help="The item URL.")
):
    """Manages or views collections on the LIVE server."""
    cfg = load_client_config()

    if list_all:
        try:
            with httpx.Client(timeout=15.0) as client:
                res = client.get(
                    f"{cfg['server_url']}/api/cli/collections",
                    headers={"X-API-Key": cfg["api_key"]},
                )
            if res.status_code == 200:
                cols = res.json()
                if not cols:
                    typer.echo("No collections found.")
                    return
                typer.secho("\n--- Collections List ---", bold=True)
                for c in cols:
                    typer.echo(f"ID {c['id']}: {c['title']} ({c['visibility']}) - {c['item_count']} items")
            else:
                typer.secho(f"Error {res.status_code}: {res.text}", fg=typer.colors.RED, bold=True, err=True)
        except Exception as e:
            typer.secho(f"Network error: {str(e)}", fg=typer.colors.RED, bold=True, err=True)

    elif add or remove:
        if not collection_id or not url:
            typer.secho("Error: --id and --url are required when performing add or remove operations.", fg=typer.colors.RED, bold=True, err=True)
            raise typer.Exit(code=1)
        action = "add" if add else "remove"
        try:
            with httpx.Client(timeout=15.0) as client:
                res = client.post(
                    f"{cfg['server_url']}/api/cli/collections/item",
                    headers={"X-API-Key": cfg["api_key"]},
                    data={
                        "action": action,
                        "collection_id": collection_id,
                        "url": url
                    },
                )
            if res.status_code == 200:
                data = res.json()
                if data.get("status") == "success":
                    typer.secho(f"Success: {data.get('message')}", fg=typer.colors.GREEN, bold=True)
                else:
                    typer.secho(f"Error: {data.get('message')}", fg=typer.colors.RED, bold=True, err=True)
            else:
                typer.secho(f"Error {res.status_code}: {res.text}", fg=typer.colors.RED, bold=True, err=True)
        except Exception as e:
            typer.secho(f"Network error: {str(e)}", fg=typer.colors.RED, bold=True, err=True)
    else:
        typer.echo("Please specify an action (e.g. --list, --add, or --remove). Run --help for details.")


@app.command("tags")
def client_tags(
    list_all: bool = typer.Option(False, "--list", "-l", help="List all tags in the system."),
    add: bool = typer.Option(False, "--add", help="Add a tag to a page."),
    remove: bool = typer.Option(False, "--remove", help="Remove a tag from a page."),
    tag: Optional[str] = typer.Option(None, "--tag", help="The tag string."),
    url: Optional[str] = typer.Option(None, "--url", help="The page URL.")
):
    """Manages or views tags on the LIVE server."""
    cfg = load_client_config()

    if list_all:
        try:
            with httpx.Client(timeout=15.0) as client:
                res = client.get(
                    f"{cfg['server_url']}/api/cli/tags",
                    headers={"X-API-Key": cfg["api_key"]},
                )
            if res.status_code == 200:
                tags = res.json()
                if not tags:
                    typer.echo("No tags found.")
                    return
                typer.secho("\n--- System Tags ---", bold=True)
                typer.echo(", ".join(tags))
            else:
                typer.secho(f"Error {res.status_code}: {res.text}", fg=typer.colors.RED, bold=True, err=True)
        except Exception as e:
            typer.secho(f"Network error: {str(e)}", fg=typer.colors.RED, bold=True, err=True)
    elif add or remove:
        if not tag or not url:
            typer.secho("Error: --tag and --url are required when performing add or remove operations.", fg=typer.colors.RED, bold=True, err=True)
            raise typer.Exit(code=1)
        action = "add" if add else "remove"
        try:
            with httpx.Client(timeout=15.0) as client:
                res = client.post(
                    f"{cfg['server_url']}/api/cli/tags/operation",
                    headers={"X-API-Key": cfg["api_key"]},
                    data={
                        "action": action,
                        "tag": tag,
                        "url": url
                    },
                )
            if res.status_code == 200:
                data = res.json()
                if data.get("status") == "success":
                    typer.secho(f"Success: {data.get('message')}", fg=typer.colors.GREEN, bold=True)
                    typer.echo(f"Updated Tags: {', '.join(data.get('tags', []))}")
                else:
                    typer.secho(f"Error: {data.get('message')}", fg=typer.colors.RED, bold=True, err=True)
            else:
                typer.secho(f"Error {res.status_code}: {res.text}", fg=typer.colors.RED, bold=True, err=True)
        except Exception as e:
            typer.secho(f"Network error: {str(e)}", fg=typer.colors.RED, bold=True, err=True)
    else:
        typer.echo("Please specify an action (e.g. --list, --add, or --remove). Run --help for details.")


@app.command("query")
def client_query(
    prompt: str = typer.Argument(..., help="The query/prompt to ask the RAG agent.")
):
    """Queries the RAG agent on the server for knowledge search and context retrieval."""
    cfg = load_client_config()

    typer.echo("Querying Knowledge Base RAG agent...")
    try:
        with httpx.Client(timeout=180.0) as client:
            res = client.post(
                f"{cfg['server_url']}/api/cli/agent/query",
                headers={"X-API-Key": cfg["api_key"]},
                data={"query": prompt},
            )
        if res.status_code == 200:
            data = res.json()
            if data.get("status") == "success":
                typer.secho("\n=== Agent Reply ===", fg=typer.colors.CYAN, bold=True)
                typer.echo(data.get("reply"))

                refs = data.get("references", [])
                if refs:
                    typer.secho("\n=== Referenced Documents ===", fg=typer.colors.CYAN, bold=True)
                    for r in refs:
                        typer.echo(f"- {r['title']} ({r['url']})")
                typer.echo("")
            else:
                typer.secho(f"Error: {data.get('message')}", fg=typer.colors.RED, bold=True, err=True)
        else:
            typer.secho(f"Error {res.status_code}: {res.text}", fg=typer.colors.RED, bold=True, err=True)
    except Exception as e:
        typer.secho(f"Network error: {str(e)}", fg=typer.colors.RED, bold=True, err=True)


@app.command("logs")
def client_logs(
    limit: Optional[int] = typer.Option(None, "--limit", "-n", help="Number of log lines to retrieve.")
):
    """Displays server system logs (most recent first)."""
    cfg = load_client_config()

    if limit is None:
        limit = cfg.get("log_limit", 100)
    else:
        cfg["log_limit"] = limit
        config_file = Path.home() / ".kb" / "cli-config.json"
        try:
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=4)
        except Exception:
            pass

    try:
        with httpx.Client(timeout=30.0) as client:
            res = client.get(
                f"{cfg['server_url']}/api/cli/logs",
                headers={"X-API-Key": cfg["api_key"]},
                params={"limit": limit},
            )
        if res.status_code == 200:
            logs = res.json()
            if not logs:
                typer.echo("No logs found.")
                return

            typer.secho(f"\n--- Server Logs (Last {len(logs)} lines) ---", bold=True)
            for log in logs:
                ts = log.get("timestamp", "")
                lvl = log.get("level", "INFO")
                mod = log.get("module", "root")
                msg = log.get("message", "")
                tb = log.get("traceback", "")

                line = f"[{ts}] {lvl} in {mod}: {msg}"
                if lvl == "ERROR":
                    typer.secho(line, fg=typer.colors.RED, bold=True)
                elif lvl == "WARNING":
                    typer.secho(line, fg=typer.colors.YELLOW)
                else:
                    typer.echo(line)
                if tb:
                    typer.echo(tb)
        else:
            typer.secho(f"Error {res.status_code}: {res.text}", fg=typer.colors.RED, bold=True, err=True)
    except Exception as e:
        typer.secho(f"Network error: {str(e)}", fg=typer.colors.RED, bold=True, err=True)


if __name__ == "__main__":
    app()

