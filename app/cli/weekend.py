"""
``scout weekend`` commands: local family outings for the coming weekend.
"""

import asyncio
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from sqlalchemy import select

from app.config import settings
from app.database import get_async_session_context, get_sync_session

console = Console()

weekend_app = typer.Typer(
    help="Plan this weekend near home (indoor and outdoor ideas for the kids)",
    invoke_without_command=True,
)


def _parse_date(value: Optional[str]) -> Optional[date]:
    if value is None:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise typer.BadParameter(f"'{value}' is not a date in YYYY-MM-DD format") from None


def _fail(message: str) -> None:
    console.print(f"[bold red]✗[/bold red] {message}")
    raise typer.Exit(code=1)


@weekend_app.callback()
def weekend_main(ctx: typer.Context):
    """Show the plan for the coming weekend when no subcommand is given."""
    if ctx.invoked_subcommand is None:
        _run_plan(send=False, use_ai=True, on_date=None, html=None, only_if_changed=False)


@weekend_app.command("plan")
def weekend_plan(
    send: bool = typer.Option(False, "--send", help="Email the plan and record it as sent"),
    no_ai: bool = typer.Option(False, "--no-ai", help="Skip Claude; use the automatic ranking"),
    on_date: Optional[str] = typer.Option(
        None, "--date", help="Plan as if today were this date (YYYY-MM-DD)"
    ),
    html: Optional[Path] = typer.Option(
        None, "--html", help="Also write the email HTML to this file"
    ),
    only_if_changed: bool = typer.Option(
        False,
        "--only-if-changed",
        help="With --send: only email if the forecast changed since the last sent plan",
    ),
):
    """
    Build the weekend plan: one outdoor idea, one indoor idea, picked by forecast.

    Examples:
        scout weekend                      # preview in the terminal
        scout weekend plan --no-ai         # preview without calling Claude
        scout weekend plan --html plan.html
        scout weekend plan --send          # email it now
    """
    _run_plan(
        send=send,
        use_ai=not no_ai,
        on_date=_parse_date(on_date),
        html=html,
        only_if_changed=only_if_changed,
    )


def _run_plan(
    *,
    send: bool,
    use_ai: bool,
    on_date: Optional[date],
    html: Optional[Path],
    only_if_changed: bool,
) -> None:
    from app.notifications.email_sender import create_email_notifier
    from app.weekend import service

    try:
        run = asyncio.run(
            service.run_weekend_planner(
                send=send,
                use_ai=use_ai,
                only_if_forecast_changed=only_if_changed,
                today=on_date,
            )
        )
    except Exception as exc:  # noqa: BLE001 - CLI boundary
        _fail(f"Weekend planning failed: {exc}")
        return

    notifier = create_email_notifier()
    console.print(
        Panel(
            notifier.render_weekend_plan_text(run.plan, is_update=run.is_update),
            title="Weekend plan" + ("" if run.plan.ai_used else " (automatic ranking)"),
            border_style="green",
        )
    )

    if html is not None:
        html.write_text(
            notifier.render_weekend_plan(run.plan, is_update=run.is_update), encoding="utf-8"
        )
        console.print(f"[blue]ℹ[/blue] Email HTML written to {html}")

    if run.status == service.STATUS_SENT:
        console.print(f"[bold green]✓[/bold green] Sent to {', '.join(run.sent_to)}")
    elif run.status == service.STATUS_UNCHANGED:
        console.print("[blue]ℹ[/blue] Forecast unchanged since the last plan; nothing sent")
    elif run.status == service.STATUS_NO_RECIPIENTS:
        _fail("No recipient: set WEEKEND_PLAN_EMAIL or add an email to your preferences")
    elif run.status == service.STATUS_SEND_FAILED:
        _fail("Email could not be sent; check the SMTP settings (see the log for details)")
    elif run.status == service.STATUS_EMPTY:
        _fail("No places matched, so nothing was sent. Try 'scout weekend seed'")


@weekend_app.command("places")
def weekend_places(
    show_all: bool = typer.Option(
        False, "--all", help="Include places filtered out for the kids' ages or the drive limit"
    ),
):
    """List the known places and whether they are currently eligible."""
    asyncio.run(_show_places(show_all))


async def _show_places(show_all: bool) -> None:
    from app.models.place import Place, PlaceVisit

    kid_ages = settings.get_weekend_kid_ages()
    month = date.today().month

    async with get_async_session_context() as db:
        places = list((await db.execute(select(Place).order_by(Place.drive_minutes))).scalars())
        visits = list((await db.execute(select(PlaceVisit))).scalars())

    if not places:
        console.print("[yellow]⚠[/yellow] No places yet. Run 'scout weekend seed' first.")
        return

    last_visit = {}
    for visit in visits:
        if visit.place_id not in last_visit or visit.visited_on > last_visit[visit.place_id]:
            last_visit[visit.place_id] = visit.visited_on

    table = Table(show_header=True, header_style="bold green")
    for column in ("Place", "Type", "Setting", "Drive", "Transit", "Cost", "Last visit", "Status"):
        table.add_column(column)

    shown = 0
    for place in places:
        reasons = []
        if not place.is_active:
            reasons.append("inactive")
        if not place.suits_ages(kid_ages):
            reasons.append("age range")
        if place.drive_minutes > settings.weekend_max_drive_minutes:
            reasons.append("too far")
        if not place.is_open_in(month):
            reasons.append("out of season")
        hidden = any(r in ("inactive", "age range", "too far") for r in reasons)
        if hidden and not show_all:
            continue
        shown += 1
        table.add_row(
            place.name,
            place.category,
            place.setting,
            f"{place.drive_minutes} min",
            f"{place.transit_minutes} min" if place.transit_minutes is not None else "car only",
            "?" if place.cost_family_eur is None else f"€{place.cost_family_eur}",
            str(last_visit.get(place.id, "-")),
            "[green]ok[/green]" if not reasons else f"[yellow]{', '.join(reasons)}[/yellow]",
        )

    console.print(table)
    console.print(
        f"{shown} of {len(places)} places shown "
        f"(kids aged {', '.join(map(str, kid_ages))}, "
        f"max drive {settings.weekend_max_drive_minutes} min)"
    )


@weekend_app.command("done")
def weekend_done(
    place: str = typer.Argument(..., help="Place name (or part of it) or slug"),
    rating: Optional[int] = typer.Option(None, "--rating", min=1, max=5, help="1-5 stars"),
    on_date: Optional[str] = typer.Option(
        None, "--date", help="Day of the visit (YYYY-MM-DD). Default: today"
    ),
    comment: Optional[str] = typer.Option(None, "--comment", help="A note for next time"),
):
    """
    Log a visit so the place is not suggested again too soon.

    A rating of 1 or 2 stops the place from being suggested at all.

    Examples:
        scout weekend done "Wildpark Poing" --rating 4
        scout weekend done hellabrunn --date 2026-11-08 --comment "petting zoo was closed"
    """
    visited_on = _parse_date(on_date) or date.today()
    asyncio.run(_log_visit(place, visited_on, rating, comment))


async def _log_visit(
    place: str, visited_on: date, rating: Optional[int], comment: Optional[str]
) -> None:
    from app.weekend.planner import PlaceNotFound, log_visit

    try:
        async with get_async_session_context() as db:
            visit = await log_visit(
                db, place, visited_on=visited_on, rating=rating, comment=comment
            )
            name = visit.place.name
    except PlaceNotFound as exc:
        _fail(str(exc))
        return

    stars = f", rated {rating}/5" if rating is not None else ""
    console.print(f"[bold green]✓[/bold green] Logged {name} on {visited_on}{stars}")


@weekend_app.command("seed")
def weekend_seed(
    update: bool = typer.Option(
        False, "--update", help="Overwrite existing places with the starter data"
    ),
):
    """Load the starter list of places in and around Munich."""
    from app.weekend.seed_places import seed_places

    db = get_sync_session()
    try:
        counts = seed_places(db, update=update)
    finally:
        db.close()

    console.print(
        f"[bold green]✓[/bold green] Places: {counts['created']} created, "
        f"{counts['updated']} updated, {counts['skipped']} already present"
    )
    console.print(
        "[blue]ℹ[/blue] Travel times and costs are rough estimates from Marienplatz; "
        "edit them in the 'places' table as you learn better."
    )
