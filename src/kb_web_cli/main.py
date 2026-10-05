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


@app.command("restart")
def client_restart(
    wait: bool = typer.Option(True, "--wait/--no-wait", help="Wait and poll until the server comes back online."),
    timeout: int = typer.Option(60, "--timeout", "-t", help="Max seconds to wait for server reboot."),
):
    """Sends a remote restart command to the live kb-web server and verifies health."""
    import time

    cfg = load_client_config()
    server_url = cfg["server_url"].rstrip("/")

    typer.secho(f"Sending restart command to '{server_url}'...", bold=True)
    try:
        with httpx.Client(timeout=15.0) as client:
            res = client.post(
                f"{server_url}/api/cli/system/restart",
                headers={"X-API-Key": cfg["api_key"]},
            )
        if res.status_code == 200:
            data = res.json()
            typer.secho(
                f"Server acknowledged restart: {data.get('message', 'Restart scheduled.')}",
                fg=typer.colors.YELLOW,
                bold=True,
            )
        else:
            typer.secho(
                f"Restart request failed (HTTP {res.status_code}): {res.text}",
                fg=typer.colors.RED,
                bold=True,
                err=True,
            )
            raise typer.Exit(code=1)
    except Exception as e:
        typer.secho(
            f"Network error sending restart command: {str(e)}",
            fg=typer.colors.RED,
            bold=True,
            err=True,
        )
        raise typer.Exit(code=1)

    if not wait:
        typer.echo("Restart signal dispatched. (--no-wait requested, exiting).")
        return

    typer.echo("Waiting for server to reboot and resume service...")
    start_wait = time.time()
    time.sleep(2.0)

    reboot_success = False
    while time.time() - start_wait < timeout:
        try:
            with httpx.Client(timeout=3.0) as check_client:
                r = check_client.get(f"{server_url}/api/health")
                if r.status_code == 200:
                    reboot_success = True
                    break
        except Exception:
            pass
        time.sleep(1.0)

    if reboot_success:
        elapsed = round(time.time() - start_wait, 1)
        typer.secho(
            f"\nSuccess! kb-web is online and healthy (responded in {elapsed}s).",
            fg=typer.colors.GREEN,
            bold=True,
        )
    else:
        typer.secho(
            f"\nWarning: Server did not respond within {timeout}s. Check service status or server logs.",
            fg=typer.colors.RED,
            bold=True,
        )


workspace_app = typer.Typer(
    help="Manage workspaces, versioned snapshots, and run interactive coding agent pairings.",
    no_args_is_help=True,
)
app.add_typer(workspace_app, name="workspace")


@workspace_app.command("snapshots")
def workspace_list_snapshots(
    workspace_id: int = typer.Argument(..., help="Workspace ID to view snapshots for"),
):
    """Lists all tagged snapshots for a workspace."""
    cfg = load_client_config()
    server_url = cfg["server_url"].rstrip("/")

    try:
        with httpx.Client(timeout=15.0) as client:
            res = client.get(
                f"{server_url}/api/workspaces/{workspace_id}/snapshots",
                headers={"X-API-Key": cfg["api_key"]},
            )
        if res.status_code == 200:
            snapshots = res.json()
            if not snapshots:
                typer.echo(f"No snapshots found for workspace {workspace_id}.")
                return
            typer.secho(f"\n--- Snapshots for Workspace {workspace_id} ---", bold=True)
            for s in snapshots:
                tag = s.get("version_tag", "")
                created = s.get("created_at", "")
                files = s.get("file_count", 0)
                desc = s.get("description", "")
                typer.echo(f"  🏷️  {tag} ({files} files) - Created: {created}")
                if desc:
                    typer.echo(f"      {desc}")
        else:
            typer.secho(f"Error {res.status_code}: {res.text}", fg=typer.colors.RED, bold=True, err=True)
    except Exception as e:
        typer.secho(f"Network error: {str(e)}", fg=typer.colors.RED, bold=True, err=True)


@workspace_app.command("snapshot")
def workspace_create_snapshot(
    workspace_id: int = typer.Argument(..., help="Workspace ID to snapshot"),
    tag: str = typer.Option(..., "--tag", "-t", prompt="Snapshot version tag (e.g. v1.0.0)"),
    description: str = typer.Option("", "--desc", "-d", help="Optional description of snapshot"),
):
    """Creates a tagged snapshot of the workspace."""
    cfg = load_client_config()
    server_url = cfg["server_url"].rstrip("/")

    try:
        with httpx.Client(timeout=15.0) as client:
            res = client.post(
                f"{server_url}/api/workspaces/{workspace_id}/snapshots",
                headers={"X-API-Key": cfg["api_key"]},
                json={"version_tag": tag, "description": description},
            )
        if res.status_code == 200:
            data = res.json()
            typer.secho(f"✅ Snapshot '{tag}' created successfully with {data.get('file_count', 0)} files!", fg=typer.colors.GREEN, bold=True)
        else:
            typer.secho(f"Error {res.status_code}: {res.text}", fg=typer.colors.RED, bold=True, err=True)
    except Exception as e:
        typer.secho(f"Network error: {str(e)}", fg=typer.colors.RED, bold=True, err=True)


@workspace_app.command("freeze")
def workspace_freeze_article(
    workspace_id: int = typer.Argument(..., help="Workspace ID"),
    snapshot_id: int = typer.Argument(..., help="Snapshot ID to freeze to an article"),
):
    """Freezes a workspace snapshot and publishes it as a Knowledge Base article."""
    cfg = load_client_config()
    server_url = cfg["server_url"].rstrip("/")

    try:
        with httpx.Client(timeout=30.0) as client:
            res = client.post(
                f"{server_url}/api/workspaces/{workspace_id}/snapshots/{snapshot_id}/freeze-article",
                headers={"X-API-Key": cfg["api_key"]},
            )
        if res.status_code == 200:
            data = res.json()
            typer.secho(f"✅ Published: {data.get('title')}", fg=typer.colors.GREEN, bold=True)
            typer.echo(f"Article URL: {data.get('article_url')}")
        else:
            typer.secho(f"Error {res.status_code}: {res.text}", fg=typer.colors.RED, bold=True, err=True)
    except Exception as e:
        typer.secho(f"Network error: {str(e)}", fg=typer.colors.RED, bold=True, err=True)


@workspace_app.command("agent")
@app.command("agent")
def workspace_terminal_agent(
    workspace_id: int = typer.Argument(..., help="Workspace ID to connect the terminal agent harness to"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Coding model to pair with tev1 decisions"),
):
    """Interactive terminal agent harness pairing tev1 structured decisions with tool execution in a workspace."""
    cfg = load_client_config()
    server_url = cfg["server_url"].rstrip("/")

    try:
        with httpx.Client(timeout=15.0) as client:
            res = client.get(
                f"{server_url}/api/workspaces/{workspace_id}",
                headers={"X-API-Key": cfg["api_key"]},
            )
        if res.status_code != 200:
            typer.secho(f"Failed to access workspace {workspace_id}: {res.text}", fg=typer.colors.RED, bold=True, err=True)
            raise typer.Exit(code=1)
        ws_info = res.json()
    except Exception as e:
        typer.secho(f"Network error connecting to workspace: {str(e)}", fg=typer.colors.RED, bold=True, err=True)
        raise typer.Exit(code=1)

    typer.secho("=" * 60, fg=typer.colors.CYAN)
    typer.secho(f"🤖 kb-web Autonomous Workspace Agent Harness", fg=typer.colors.CYAN, bold=True)
    typer.secho(f"Connected to Workspace: {ws_info.get('name')} (ID: {workspace_id})", bold=True)
    files = list(ws_info.get("files", {}).keys())
    typer.echo(f"Files ({len(files)}): {', '.join(files) if files else 'None (Empty)'}")
    typer.echo("Type your prompt or instructions. Type 'exit' or 'quit' to end session.")
    typer.secho("=" * 60, fg=typer.colors.CYAN)

    active_file = files[0] if files else None

    while True:
        try:
            prompt = typer.prompt("\nagent> ").strip()
        except (KeyboardInterrupt, EOFError):
            typer.echo("\nSession ended.")
            break

        if not prompt:
            continue
        if prompt.lower() in ("exit", "quit", "q"):
            typer.secho("Exiting workspace agent session.", fg=typer.colors.YELLOW)
            break

        typer.secho("Thinking & deciding...", fg=typer.colors.MAGENTA)
        try:
            with httpx.Client(timeout=180.0) as client:
                res = client.post(
                    f"{server_url}/api/workspaces/{workspace_id}/agent/chat",
                    headers={"X-API-Key": cfg["api_key"]},
                    json={
                        "message": prompt,
                        "active_file": active_file,
                        "model": model,
                    },
                )
            if res.status_code == 200:
                data = res.json()
                decision = data.get("decision", {})
                if decision:
                    typer.secho(
                        f"⚙️  [tev1 Decision] Intent: {decision.get('intent')} | Target: {decision.get('target_file') or 'none'} | ReadNeeded: {decision.get('needs_reading')}",
                        fg=typer.colors.BLUE,
                    )

                executed = data.get("executed_tools", [])
                for t in executed:
                    action = t.get("action", "executed")
                    fpath = t.get("file_path", "")
                    ann = f" - {t['annotation']}" if t.get("annotation") else ""
                    typer.secho(f"🛠️  Tool Action: {action.upper()} '{fpath}'{ann}", fg=typer.colors.GREEN, bold=True)

                reply = data.get("reply", "")
                typer.echo(f"\n{reply}\n")
            else:
                typer.secho(f"Agent error (HTTP {res.status_code}): {res.text}", fg=typer.colors.RED, bold=True)
        except Exception as e:
            typer.secho(f"Network error during agent execution: {str(e)}", fg=typer.colors.RED, bold=True)


rag_app = typer.Typer(
    help="Autonomous Agentic RAG multi-sub-agent report generator with tev1 decision gating.",
    no_args_is_help=True,
)
app.add_typer(rag_app, name="rag")


@rag_app.command("report")
def generate_rag_report(
    query: str = typer.Argument(..., help="Research question or topic to synthesize"),
    purpose: str = typer.Option("", "--purpose", "-p", help="Optional research goal or technical focus"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Optional path to save generated markdown report"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Synthesis model override"),
    save_to_notes: bool = typer.Option(False, "--save-notes", "-s", help="Automatically save synthesized report to Knowledge Base notes"),
):
    """Executes multi-sub-agent retrieval (tag, vector, text) and tev1 decision scoring to synthesize a publication-grade Markdown research report."""
    cfg = load_client_config()
    server_url = cfg["server_url"].rstrip("/")

    typer.secho("=" * 60, fg=typer.colors.CYAN)
    typer.secho("🔬 kb-web Agentic RAG Report Generator", fg=typer.colors.CYAN, bold=True)
    typer.echo(f"Query: {query}")
    if purpose:
        typer.echo(f"Purpose: {purpose}")
    typer.secho("=" * 60, fg=typer.colors.CYAN)

    typer.secho("Deploying retrieval sub-agents & evaluating candidates with tev1...", fg=typer.colors.MAGENTA)

    try:
        with httpx.Client(timeout=300.0) as client:
            res = client.post(
                f"{server_url}/api/reports/rag/generate",
                headers={"X-API-Key": cfg["api_key"]},
                json={
                    "query": query,
                    "purpose": purpose,
                    "synthesis_model": model,
                },
            )
        if res.status_code != 200:
            typer.secho(f"RAG Generation Error (HTTP {res.status_code}): {res.text}", fg=typer.colors.RED, bold=True, err=True)
            raise typer.Exit(code=1)

        data = res.json()
        metrics = data.get("subagent_metrics", {})
        typer.secho(
            f"✅ Sub-Agent Retrieval: Tag: {metrics.get('tag_hits', 0)} | Vector: {metrics.get('vector_hits', 0)} | Text: {metrics.get('text_hits', 0)} | Total Candidates: {metrics.get('total_candidates', 0)}",
            fg=typer.colors.GREEN,
        )
        sources = data.get("sources", [])
        typer.secho(f"⚡ tev1 Decision Gating: Selected {len(sources)} vetted primary evidence sources.", fg=typer.colors.BLUE)

        for s in sources:
            typer.echo(f"  - [{s.get('tev1_score', 'N/A')}%] {s.get('title')} ({', '.join(s.get('match_types', []))})")

        report_md = data.get("report_markdown", "")
        typer.echo("\n" + "=" * 60)
        typer.echo(report_md)
        typer.echo("=" * 60 + "\n")

        if output:
            output.write_text(report_md, encoding="utf-8")
            typer.secho(f"📁 Report saved to: {output.resolve()}", fg=typer.colors.GREEN, bold=True)

        if save_to_notes and data.get("id"):
            with httpx.Client(timeout=15.0) as client:
                save_res = client.post(
                    f"{server_url}/api/reports/rag/{data['id']}/save-to-notes",
                    headers={"X-API-Key": cfg["api_key"]},
                )
            if save_res.status_code == 200:
                note_info = save_res.json()
                typer.secho(f"💾 Saved to Knowledge Base Notes: {note_info.get('note_url')}", fg=typer.colors.GREEN)

    except Exception as e:
        typer.secho(f"Network error during RAG report generation: {str(e)}", fg=typer.colors.RED, bold=True, err=True)
        raise typer.Exit(code=1)



error_app = typer.Typer(
    help="Inspect, search, and diagnose server error incidents and review Maintenance Agent feedback.",
    no_args_is_help=True,
)
app.add_typer(error_app, name="error")


@error_app.command("list")
def list_errors_cli(
    limit: int = typer.Option(25, "--limit", "-n", help="Maximum number of errors to return"),
    status: Optional[str] = typer.Option(None, "--status", "-s", help="Filter by status (open, analyzed)"),
):
    """Lists recent server error incidents recorded in the server database."""
    cfg = load_client_config()
    server_url = cfg["server_url"].rstrip("/")

    params = {"limit": limit}
    if status:
        params["status"] = status

    try:
        with httpx.Client(timeout=15.0) as client:
            res = client.get(
                f"{server_url}/api/errors",
                headers={"X-API-Key": cfg["api_key"]},
                params=params,
            )
        if res.status_code == 200:
            data = res.json()
            items = data.get("items", [])
            total = data.get("total", 0)
            typer.secho(f"\n--- Server Error Incidents (Total: {total}) ---", bold=True)
            if not items:
                typer.secho("✅ No error incidents found.", fg=typer.colors.GREEN)
                return

            header = f"{'ID':<6} {'Timestamp':<20} {'Status':<10} {'Error Type':<25} {'Endpoint'}"
            typer.echo(header)
            typer.echo("-" * 80)
            for it in items:
                eid = it.get("id")
                ts = it.get("timestamp", "")[:19].replace("T", " ")
                st = it.get("status", "open")
                etype = it.get("error_type", "Unknown")[:24]
                req = f"{it.get('request_method', '')} {it.get('request_url', '')}"[:35]
                st_color = typer.colors.GREEN if st == "analyzed" else typer.colors.YELLOW
                typer.echo(f"{eid:<6} {ts:<20} ", nl=False)
                typer.secho(f"{st:<10}", fg=st_color, nl=False)
                typer.echo(f" {etype:<25} {req}")
            typer.echo("")
        else:
            typer.secho(f"Error {res.status_code}: {res.text}", fg=typer.colors.RED, bold=True, err=True)
    except Exception as e:
        typer.secho(f"Network error: {str(e)}", fg=typer.colors.RED, bold=True, err=True)


@error_app.command("view")
def view_error_cli(
    error_id: int = typer.Argument(..., help="Server Error Incident ID to inspect"),
):
    """Views full stack trace and Maintenance Agent diagnostic feedback for an error incident."""
    cfg = load_client_config()
    server_url = cfg["server_url"].rstrip("/")

    try:
        with httpx.Client(timeout=15.0) as client:
            res = client.get(
                f"{server_url}/api/errors/{error_id}",
                headers={"X-API-Key": cfg["api_key"]},
            )
        if res.status_code == 200:
            err = res.json()
            typer.secho("\n" + "=" * 70, fg=typer.colors.RED)
            typer.secho(f"🚨 Server Error Incident #{err.get('id')} - {err.get('error_type')}", fg=typer.colors.RED, bold=True)
            typer.secho("=" * 70, fg=typer.colors.RED)
            typer.echo(f"Timestamp:      {err.get('timestamp')}")
            typer.echo(f"Request:        {err.get('request_method')} {err.get('request_url')}")
            typer.echo(f"Client IP:      {err.get('client_ip')}")
            typer.echo(f"Status:         {err.get('status')}")
            typer.echo(f"Error Message:  {err.get('error_message')}")
            typer.echo("\n--- Stack Trace ---")
            typer.secho(err.get("stack_trace", "No stack trace recorded."), fg=typer.colors.YELLOW)

            feedback = err.get("agent_feedback")
            if feedback:
                typer.secho("\n--- 🤖 Maintenance Agent Diagnostic Feedback ---", fg=typer.colors.CYAN, bold=True)
                typer.echo(feedback)
            else:
                typer.secho("\n[INFO] No agent diagnosis generated yet. Run 'kb-web-cli error analyze <id>' to trigger analysis.", fg=typer.colors.YELLOW)
            typer.echo("")
        else:
            typer.secho(f"Error {res.status_code}: {res.text}", fg=typer.colors.RED, bold=True, err=True)
    except Exception as e:
        typer.secho(f"Network error: {str(e)}", fg=typer.colors.RED, bold=True, err=True)


@error_app.command("search")
def search_errors_cli(
    query: str = typer.Argument(..., help="Search query string"),
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum results to return"),
):
    """Searches historical server error incidents by error message, type, or stack trace keywords."""
    cfg = load_client_config()
    server_url = cfg["server_url"].rstrip("/")

    try:
        with httpx.Client(timeout=15.0) as client:
            res = client.get(
                f"{server_url}/api/errors/search",
                headers={"X-API-Key": cfg["api_key"]},
                params={"q": query, "limit": limit},
            )
        if res.status_code == 200:
            data = res.json()
            items = data.get("items", [])
            typer.secho(f"\n--- Error Search Results for '{query}' ({data.get('count', 0)} matches) ---", bold=True)
            if not items:
                typer.echo("No matching errors found.")
                return

            for it in items:
                fb_icon = "🤖" if it.get("has_feedback") else " "
                typer.echo(f"  [#{it.get('id')}] {it.get('timestamp', '')[:19]} | {it.get('error_type')} | {it.get('error_message', '')[:70]} {fb_icon}")
            typer.echo("")
        else:
            typer.secho(f"Error {res.status_code}: {res.text}", fg=typer.colors.RED, bold=True, err=True)
    except Exception as e:
        typer.secho(f"Network error: {str(e)}", fg=typer.colors.RED, bold=True, err=True)


@error_app.command("analyze")
def analyze_error_cli(
    error_id: int = typer.Argument(..., help="Incident ID to trigger Maintenance Agent analysis for"),
):
    """Manually triggers the Maintenance Agent sidecar to inspect source code and diagnose an error."""
    cfg = load_client_config()
    server_url = cfg["server_url"].rstrip("/")

    typer.echo(f"Dispatching error #{error_id} to Maintenance Agent...")
    try:
        with httpx.Client(timeout=30.0) as client:
            res = client.post(
                f"{server_url}/api/errors/{error_id}/analyze",
                headers={"X-API-Key": cfg["api_key"]},
            )
        if res.status_code == 200:
            data = res.json()
            typer.secho(f"\n--- 🤖 Maintenance Agent Diagnosis for #{error_id} ---", fg=typer.colors.CYAN, bold=True)
            typer.echo(data.get("agent_feedback", "No feedback produced."))
            typer.echo("")
        else:
            typer.secho(f"Error {res.status_code}: {res.text}", fg=typer.colors.RED, bold=True, err=True)
    except Exception as e:
        typer.secho(f"Network error: {str(e)}", fg=typer.colors.RED, bold=True, err=True)


@app.command("maintenance-daemon")
def run_maintenance_daemon_cli(
    interval: int = typer.Option(5, "--interval", "-i", help="Polling interval in seconds"),
    run_once: bool = typer.Option(False, "--once", help="Process pending errors once and exit"),
):
    """Runs the background sidecar Maintenance Agent daemon monitoring for uncaught errors."""
    try:
        from kb_web.maintenance_agent import run_maintenance_daemon
        run_maintenance_daemon(poll_interval=interval, run_once=run_once)
    except ImportError:
        typer.secho("Error: kb_web core package not found in Python path.", fg=typer.colors.RED, bold=True, err=True)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()




