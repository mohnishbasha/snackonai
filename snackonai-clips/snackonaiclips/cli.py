"""
CLI entry point for SnackOnAIClips.

Usage:
    python snackonaiclips.py --url <blog_url> [options]
    snackonaiclips --url <blog_url> [options]   # after pip install
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.text import Text

from . import __version__
from .config import LLMProvider, TTSProvider, VideoStyle, get_config
from .extractor import ArticleContent, ExtractionError, URLValidationError, extract_content
from .summarizer import Summary, SummarizationError, summarize
from .tts import TTSError, generate_voiceover
from .utils import setup_logging
from .video_generator import generate_thumbnail, generate_video

console = Console()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="snackonaiclips",
        description=(
            "SnackOnAIClips — Turn any blog post into a LinkedIn-ready short video."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python snackonaiclips.py --url https://example.com/blog/post --output output.mp4
  python snackonaiclips.py --url https://example.com/post --style cinematic --no-tts
  python snackonaiclips.py --url https://example.com/post --llm ollama --watermark ""
        """,
    )

    # Core
    parser.add_argument("--url", required=True, help="Blog or article URL to summarize")
    parser.add_argument(
        "--output", default="output.mp4", metavar="PATH",
        help="Output video file path (default: output.mp4)",
    )

    # Style
    parser.add_argument(
        "--style",
        choices=[s.value for s in VideoStyle],
        default=VideoStyle.MODERN.value,
        help="Visual style preset (default: modern)",
    )
    parser.add_argument(
        "--watermark",
        default=None,
        metavar="TEXT",
        help='Watermark text (default: "SnackOnAI", pass "" to disable)',
    )

    # LLM
    parser.add_argument(
        "--llm",
        choices=[p.value for p in LLMProvider],
        default=None,
        metavar="PROVIDER",
        help="LLM provider: openai or ollama (overrides SNACKONAI_LLM_PROVIDER env var)",
    )
    parser.add_argument(
        "--ollama-model",
        default=None,
        metavar="MODEL",
        help="Ollama model name (e.g. llama3.2)",
    )
    parser.add_argument(
        "--openai-model",
        default=None,
        metavar="MODEL",
        help="OpenAI model name (e.g. gpt-4o-mini)",
    )

    # TTS
    parser.add_argument(
        "--no-tts", action="store_true",
        help="Disable text-to-speech voiceover generation",
    )
    parser.add_argument(
        "--tts-provider",
        choices=[p.value for p in TTSProvider],
        default=None,
        metavar="PROVIDER",
        help="TTS provider: gtts or elevenlabs",
    )

    # Output extras
    parser.add_argument(
        "--thumbnail", action="store_true",
        help="Also generate a thumbnail PNG alongside the video",
    )
    parser.add_argument(
        "--json-output", default=None, metavar="PATH",
        help="Save the summary JSON to a file",
    )
    parser.add_argument(
        "--summary-only", action="store_true",
        help="Print summary JSON and exit without generating video",
    )

    # Misc
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default=None,
        metavar="LEVEL",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    return parser


# ---------------------------------------------------------------------------
# Rich helpers
# ---------------------------------------------------------------------------

def _print_summary(summary: Summary) -> None:
    console.print()
    console.print(Panel(
        f"[bold cyan]{summary.headline}[/]\n\n"
        f"[white]{summary.summary}[/]",
        title="[bold]Summary[/]",
        border_style="blue",
        padding=(1, 2),
    ))
    bullets_text = "\n".join(f"  [cyan]•[/] {b}" for b in summary.bullets)
    console.print(Panel(bullets_text, title="[bold]Key Points[/]", border_style="green", padding=(1, 2)))
    console.print()


def _print_banner() -> None:
    banner = Text()
    banner.append("  SnackOnAI", style="bold magenta")
    banner.append("Clips", style="bold cyan")
    banner.append(f"  v{__version__}", style="dim")
    console.print(Panel(banner, border_style="magenta", padding=(0, 2)))


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run(args: argparse.Namespace) -> int:
    """Execute the full pipeline. Returns 0 on success, non-zero on error."""
    # Logging
    log_level = args.log_level or get_config().log_level
    setup_logging(log_level)

    # Apply CLI overrides to config
    cfg = get_config()
    if args.llm:
        cfg.llm.provider = LLMProvider(args.llm)
    if args.ollama_model:
        cfg.llm.ollama_model = args.ollama_model
    if args.openai_model:
        cfg.llm.openai_model = args.openai_model
    if args.watermark is not None:
        cfg.watermark = args.watermark
    if args.no_tts:
        cfg.tts.provider = TTSProvider.DISABLED
    if args.tts_provider:
        cfg.tts.provider = TTSProvider(args.tts_provider)

    style = VideoStyle(args.style)
    watermark = cfg.watermark

    _print_banner()
    console.print(f"[dim]URL:[/] {args.url}")
    console.print()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=False,
    ) as progress:

        # Step 1: Extract content
        task = progress.add_task("[cyan]Extracting content…", total=None)
        try:
            content: ArticleContent = extract_content(args.url)
            progress.update(task, description=f"[green]✓ Extracted {len(content.text):,} chars", completed=1, total=1)
        except URLValidationError as exc:
            console.print(f"[red]URL Error:[/] {exc}")
            return 1
        except ExtractionError as exc:
            console.print(f"[red]Extraction Error:[/] {exc}")
            return 1

        # Step 2: Summarize
        task2 = progress.add_task("[cyan]Summarizing with LLM…", total=None)
        try:
            summary: Summary = summarize(content)
            progress.update(task2, description="[green]✓ Summary ready", completed=1, total=1)
        except SummarizationError as exc:
            console.print(f"[red]Summarization Error:[/] {exc}")
            return 1

    _print_summary(summary)

    # Save JSON output
    if args.json_output:
        json_path = Path(args.json_output)
        json_path.write_text(json.dumps(summary.to_dict(), indent=2, ensure_ascii=False))
        console.print(f"[dim]Summary JSON saved to:[/] {json_path}")

    if args.summary_only:
        console.print(json.dumps(summary.to_dict(), indent=2))
        return 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=False,
    ) as progress:

        # Step 3: TTS
        audio_path: str | None = None
        if cfg.tts.provider != TTSProvider.DISABLED:
            task3 = progress.add_task("[cyan]Generating voiceover…", total=None)
            try:
                audio_path = generate_voiceover(summary)
                progress.update(task3, description="[green]✓ Voiceover ready", completed=1, total=1)
            except TTSError as exc:
                console.print(f"[yellow]TTS Warning:[/] {exc} — continuing without audio")
                progress.update(task3, description="[yellow]⚠ TTS skipped", completed=1, total=1)
        else:
            console.print("[dim]TTS disabled[/]")

        # Step 4: Video generation
        total_slides = 3 + len(summary.bullets)
        task4 = progress.add_task("[cyan]Rendering video…", total=total_slides)

        def on_progress(current: int, total: int) -> None:
            progress.update(task4, completed=current)

        try:
            output = generate_video(
                summary=summary,
                output_path=args.output,
                audio_path=audio_path,
                style=style,
                watermark=watermark,
                progress_callback=on_progress,
            )
            progress.update(task4, description="[green]✓ Video rendered", completed=total_slides)
        except ImportError as exc:
            console.print(f"[red]Dependency Error:[/] {exc}")
            return 2
        except Exception as exc:
            logger.exception("Video generation failed")
            console.print(f"[red]Video Error:[/] {exc}")
            return 3

        # Step 5: Optional thumbnail
        if args.thumbnail:
            thumb_path = str(Path(args.output).with_suffix(".png"))
            task5 = progress.add_task("[cyan]Generating thumbnail…", total=None)
            try:
                generate_thumbnail(summary, thumb_path, style=style, watermark=watermark)
                progress.update(task5, description=f"[green]✓ Thumbnail: {thumb_path}", completed=1, total=1)
            except Exception as exc:
                console.print(f"[yellow]Thumbnail Warning:[/] {exc}")

    console.print()
    console.print(Panel(
        f"[bold green]Done![/] Video saved to: [bold]{output}[/]",
        border_style="green",
        padding=(0, 2),
    ))
    return 0


def main() -> None:
    """CLI entry point registered in setup.py / pyproject.toml."""
    parser = build_parser()
    args = parser.parse_args()
    sys.exit(run(args))


if __name__ == "__main__":
    main()
