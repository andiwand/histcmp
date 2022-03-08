from pathlib import Path
from typing import Optional

import typer
from rich.panel import Panel
from rich.console import Group
from rich.text import Text
from rich.pretty import Pretty
from rich.emoji import Emoji
import jinja2
import yaml

from histcmp.console import fail, info, console
from histcmp.report import make_report
from histcmp.checks import Status
from histcmp.config import Config
from histcmp.github import is_github_actions, github_actions_marker

#  install(show_locals=True)

app = typer.Typer()


@app.command()
def main(
    config_path: Path = typer.Option(
        None, "--config", "-c", dir_okay=False, exists=True
    ),
    monitored: Path = typer.Argument(..., exists=True, dir_okay=False),
    reference: Path = typer.Argument(..., exists=True, dir_okay=False),
    output: Optional[Path] = typer.Option(None, "-o", "--output", dir_okay=False),
):
    try:
        import ROOT
    except ImportError:
        fail("ROOT could not be imported")
        return
    ROOT.gROOT.SetBatch(ROOT.kTRUE)

    from histcmp.compare import compare

    console.print(
        Panel(
            Group(f"Monitored: {monitored}", f"Reference: {reference}"),
            title="Comparing files:",
        )
    )

    if config_path is None:
        config = Config(
            checks={
                "*": {
                    k: None
                    for k in [
                        "Chi2Test",
                        "KolmogorovTest",
                        "RatioCheck",
                        "ResidualCheck",
                        "IntegralCheck",
                    ]
                }
            }
        )
    else:
        with config_path.open() as fh:
            config = Config(**yaml.safe_load(fh))

    console.print(Panel(Pretty(config), title="Configuration"))

    try:
        comparison, removed, new = compare(config, monitored, reference)

        status = Status.SUCCESS
        style = "bold green"

        if (
            any(c.status == Status.FAILURE for c in comparison.common)
            and len(removed) == 0
            and len(new) == 0
        ):
            status = Status.FAILURE
            style = "bold red"
            if is_github_actions:
                print(
                    github_actions_marker(
                        "error",
                        f"Comparison between {monitored} and {reference} failed!",
                    )
                )
        elif all(c.status == Status.INCONCLUSIVE for c in comparison.common):
            status = Status.INCONCLUSIVE
            style = "bold yellow"
            if is_github_actions:
                print(
                    github_actions_marker(
                        "error",
                        f"Comparison between {monitored} and {reference} was inconclusive!",
                    )
                )

        console.print(
            Panel(
                Text(f"{Emoji.replace(status.icon)} {status.name}", justify="center"),
                style=style,
            )
        )

        if output is not None:
            make_report(comparison, output)

        if status != Status.SUCCESS:
            raise typer.Exit(1)

    except Exception as e:
        if isinstance(e, jinja2.exceptions.TemplateRuntimeError):
            raise e
        raise
        #  console.print_exception(show_locals=True)
