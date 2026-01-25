"""Main entry point for the voice chatbot."""

import argparse
import sys


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Local Voice Chatbot - A fully local voice assistant for Mac",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  voice-chat              Start voice chat (requires microphone)
  voice-chat --text       Start text-only chat
  voice-chat --web        Start web interface
  voice-chat --text --no-tts  Text chat without speech output
        """,
    )

    parser.add_argument(
        "--text",
        "-t",
        action="store_true",
        help="Use text input instead of voice",
    )
    parser.add_argument(
        "--no-tts",
        action="store_true",
        help="Disable text-to-speech output",
    )
    parser.add_argument(
        "--web",
        "-w",
        action="store_true",
        help="Start web interface instead of CLI",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Web server host (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=8000,
        help="Web server port (default: 8000)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check system requirements and exit",
    )
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="List audio devices and exit",
    )
    parser.add_argument(
        "--list-voices",
        action="store_true",
        help="List available TTS voices and exit",
    )

    args = parser.parse_args()

    # Handle info commands
    if args.check:
        check_requirements()
        return

    if args.list_devices:
        list_audio_devices()
        return

    if args.list_voices:
        list_tts_voices()
        return

    # Start appropriate interface
    if args.web:
        from .interfaces.web import run_server

        print(f"Starting web server at http://{args.host}:{args.port}")
        run_server(host=args.host, port=args.port, reload=args.reload)
    else:
        from .interfaces.cli import run_cli

        run_cli(text_mode=args.text, no_tts=args.no_tts)


def check_requirements():
    """Check system requirements."""
    from rich.console import Console
    from rich.table import Table

    console = Console()
    console.print("\n[bold]System Requirements Check[/bold]\n")

    table = Table(show_header=True)
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Notes")

    # Check Python
    import platform

    py_version = platform.python_version()
    py_ok = tuple(map(int, py_version.split(".")[:2])) >= (3, 10)
    table.add_row(
        "Python",
        "✓" if py_ok else "✗",
        f"v{py_version}" + ("" if py_ok else " (need 3.10+)"),
    )

    # Check Apple Silicon
    is_arm = platform.machine() == "arm64"
    table.add_row(
        "Apple Silicon",
        "✓" if is_arm else "⚠",
        "Detected" if is_arm else "Intel Mac (slower)",
    )

    # Check sounddevice
    try:
        import sounddevice as sd

        devices = sd.query_devices()
        input_count = sum(1 for d in devices if d["max_input_channels"] > 0)
        table.add_row("Audio (sounddevice)", "✓", f"{input_count} input devices")
    except Exception as e:
        table.add_row("Audio (sounddevice)", "✗", str(e))

    # Check MLX
    try:
        import mlx

        table.add_row("MLX", "✓", "Installed")
    except ImportError:
        table.add_row("MLX", "✗", "pip install mlx")

    # Check Ollama
    try:
        import httpx

        response = httpx.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get("models", [])
            model_names = [m.get("name", "") for m in models[:3]]
            table.add_row("Ollama", "✓", f"Running ({len(models)} models)")
        else:
            table.add_row("Ollama", "⚠", "Running but no models")
    except Exception:
        table.add_row("Ollama", "✗", "Not running - start with: ollama serve")

    # Check Kokoro
    try:
        import kokoro

        table.add_row("Kokoro TTS", "✓", "Installed")
    except ImportError:
        table.add_row("Kokoro TTS", "✗", "pip install kokoro")

    console.print(table)
    console.print()


def list_audio_devices():
    """List available audio devices."""
    from rich.console import Console
    from rich.table import Table

    from .audio.capture import list_input_devices
    from .audio.playback import list_output_devices

    console = Console()

    console.print("\n[bold]Input Devices (Microphones)[/bold]")
    input_table = Table(show_header=True)
    input_table.add_column("Index")
    input_table.add_column("Name")
    input_table.add_column("Channels")
    input_table.add_column("Sample Rate")

    for device in list_input_devices():
        input_table.add_row(
            str(device["index"]),
            device["name"],
            str(device["channels"]),
            f"{device['sample_rate']:.0f}",
        )
    console.print(input_table)

    console.print("\n[bold]Output Devices (Speakers)[/bold]")
    output_table = Table(show_header=True)
    output_table.add_column("Index")
    output_table.add_column("Name")
    output_table.add_column("Channels")
    output_table.add_column("Sample Rate")

    for device in list_output_devices():
        output_table.add_row(
            str(device["index"]),
            device["name"],
            str(device["channels"]),
            f"{device['sample_rate']:.0f}",
        )
    console.print(output_table)
    console.print()


def list_tts_voices():
    """List available TTS voices."""
    from rich.console import Console
    from rich.table import Table

    from .pipeline.tts import TextToSpeech

    console = Console()
    console.print("\n[bold]Available TTS Voices[/bold]")

    table = Table(show_header=True)
    table.add_column("Voice ID", style="cyan")
    table.add_column("Description")

    for voice_id, description in TextToSpeech.list_voices().items():
        table.add_row(voice_id, description)

    console.print(table)
    console.print()


if __name__ == "__main__":
    main()
