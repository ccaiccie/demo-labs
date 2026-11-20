#!/usr/bin/env python3
"""Generate a self-contained HTML5 video player page with playback speed controls."""

from __future__ import annotations

import argparse
import html
from pathlib import Path
import sys
from typing import Sequence

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{title}</title>
  <style>
    :root {{
      --bg: #0b1120;
      --surface: #111827;
      --surface-elevated: #1e293b;
      --border: #263244;
      --text: #f1f5f9;
      --text-muted: #94a3b8;
      --accent: #38bdf8;
      --accent-strong: #0284c7;
      --accent-glow: rgba(56, 189, 248, 0.25);
      --warn-bg: rgba(245, 158, 11, 0.12);
      --warn-border: rgba(245, 158, 11, 0.35);
      --warn-text: #fcd34d;
    }}

    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}

    body {{
      min-height: 100vh;
      background: radial-gradient(circle at top, #13203b 0%, var(--bg) 55%);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Inter, sans-serif;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 24px 16px;
      line-height: 1.5;
    }}

    .player-shell {{
      width: 100%;
      max-width: 1120px;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 16px;
      box-shadow: 0 24px 60px rgba(0, 0, 0, 0.55);
      overflow: hidden;
    }}

    .player-header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 16px 22px;
      border-bottom: 1px solid var(--border);
      background: rgba(15, 23, 42, 0.7);
    }}

    .player-title {{
      font-size: 1.125rem;
      font-weight: 600;
      letter-spacing: -0.01em;
      color: var(--text);
    }}

    .speed-badge {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: 0.8125rem;
      font-weight: 600;
      color: var(--accent);
      background: rgba(56, 189, 248, 0.1);
      border: 1px solid rgba(56, 189, 248, 0.25);
      border-radius: 999px;
      padding: 4px 12px;
      white-space: nowrap;
    }}

    .video-stage {{
      position: relative;
      background: #000;
      aspect-ratio: 16 / 9;
      width: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
    }}

    video {{
      width: 100%;
      height: 100%;
      display: block;
      background: #000;
      outline: none;
    }}

    .error-banner {{
      display: none;
      margin: 14px 22px 0;
      padding: 12px 16px;
      border-radius: 10px;
      background: var(--warn-bg);
      border: 1px solid var(--warn-border);
      color: var(--warn-text);
      font-size: 0.875rem;
    }}

    .error-banner.visible {{
      display: block;
    }}

    .error-banner code {{
      color: #fef3c7;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 0.85em;
    }}

    .controls-bar {{
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 14px;
      padding: 16px 22px;
      border-top: 1px solid var(--border);
      background: rgba(15, 23, 42, 0.5);
    }}

    .speed-controls {{
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
    }}

    .control-label {{
      font-size: 0.85rem;
      color: var(--text-muted);
      font-weight: 500;
    }}

    .speed-buttons {{
      display: inline-flex;
      gap: 6px;
      background: var(--bg);
      padding: 4px;
      border-radius: 10px;
      border: 1px solid var(--border);
    }}

    .speed-btn {{
      appearance: none;
      border: 1px solid transparent;
      background: transparent;
      color: var(--text-muted);
      font-size: 0.875rem;
      font-weight: 600;
      padding: 6px 14px;
      border-radius: 7px;
      cursor: pointer;
      transition: background-color 0.15s ease, color 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease;
    }}

    .speed-btn:hover {{
      color: var(--text);
      background: var(--surface-elevated);
    }}

    .speed-btn:focus-visible {{
      outline: 2px solid var(--accent);
      outline-offset: 2px;
    }}

    .speed-btn.active {{
      background: var(--accent-strong);
      color: #ffffff;
      border-color: var(--accent);
      box-shadow: 0 0 0 3px var(--accent-glow);
    }}

    .shortcuts-hint {{
      display: flex;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;
      font-size: 0.8rem;
      color: var(--text-muted);
    }}

    kbd {{
      display: inline-block;
      padding: 2px 6px;
      font-size: 0.75rem;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      color: var(--text);
      background: var(--surface-elevated);
      border: 1px solid var(--border);
      border-radius: 5px;
      box-shadow: inset 0 -1px 0 rgba(0, 0, 0, 0.35);
    }}

    @media (max-width: 640px) {{
      .player-header,
      .controls-bar {{
        padding: 14px 16px;
      }}

      .shortcuts-hint {{
        width: 100%;
      }}
    }}
  </style>
</head>
<body>
  <main class="player-shell">
    <header class="player-header">
      <h1 class="player-title">{title}</h1>
      <span class="speed-badge" aria-live="polite">Speed: <span id="current-speed">1x</span></span>
    </header>

    <section class="video-stage">
      <video id="demo-video" src="{video_src}" controls preload="metadata" playsinline>
        Your browser does not support HTML5 video playback.
      </video>
    </section>

    <div id="video-error" class="error-banner" role="alert">
      Unable to load video <code>{video_src}</code>. Ensure the MP4 file exists at this path relative to the HTML file and try reloading.
    </div>

    <footer class="controls-bar">
      <div class="speed-controls">
        <span class="control-label">Playback speed</span>
        <div class="speed-buttons" role="group" aria-label="Playback speed">
          <button type="button" class="speed-btn active" data-speed="1" aria-pressed="true">1x</button>
          <button type="button" class="speed-btn" data-speed="1.5" aria-pressed="false">1.5x</button>
          <button type="button" class="speed-btn" data-speed="2" aria-pressed="false">2x</button>
        </div>
      </div>

      <div class="shortcuts-hint" aria-label="Keyboard shortcuts">
        <span><kbd>1</kbd> <kbd>2</kbd> <kbd>3</kbd> Speed</span>
        <span><kbd>Space</kbd> Play / Pause</span>
      </div>
    </footer>
  </main>

  <script>
    (function () {{
      const video = document.getElementById("demo-video");
      const speedButtons = Array.from(document.querySelectorAll(".speed-btn[data-speed]"));
      const speedDisplay = document.getElementById("current-speed");
      const errorBanner = document.getElementById("video-error");

      function formatSpeed(rate) {{
        return Number(rate).toString() + "x";
      }}

      function updateSpeedUI(rate) {{
        speedDisplay.textContent = formatSpeed(rate);
        speedButtons.forEach((btn) => {{
          const btnRate = parseFloat(btn.dataset.speed);
          const isActive = Math.abs(btnRate - rate) < 0.001;
          btn.classList.toggle("active", isActive);
          btn.setAttribute("aria-pressed", isActive ? "true" : "false");
        }});
      }}

      function setSpeed(rate) {{
        const parsed = parseFloat(rate);
        if (!Number.isFinite(parsed) || parsed <= 0) {{
          return;
        }}
        video.playbackRate = parsed;
        updateSpeedUI(parsed);
      }}

      speedButtons.forEach((btn) => {{
        btn.addEventListener("click", () => {{
          setSpeed(btn.dataset.speed);
        }});
      }});

      video.addEventListener("ratechange", () => {{
        updateSpeedUI(video.playbackRate);
      }});

      video.addEventListener("error", () => {{
        errorBanner.classList.add("visible");
      }});

      video.addEventListener("loadeddata", () => {{
        errorBanner.classList.remove("visible");
      }});

      document.addEventListener("keydown", (event) => {{
        if (event.ctrlKey || event.metaKey || event.altKey) {{
          return;
        }}
        const tag = event.target && event.target.tagName ? event.target.tagName.toUpperCase() : "";
        if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") {{
          return;
        }}

        if (event.key === "1") {{
          setSpeed(1);
        }} else if (event.key === "2") {{
          setSpeed(1.5);
        }} else if (event.key === "3") {{
          setSpeed(2);
        }} else if (event.code === "Space" || event.key === " ") {{
          if (tag === "BUTTON" || event.target === video) {{
            return;
          }}
          event.preventDefault();
          if (video.paused) {{
            video.play().catch(() => {{}});
          }} else {{
            video.pause();
          }}
        }}
      }});

      setSpeed(1);
    }})();
  </script>
</body>
</html>
"""


def build_html(video_src: str = "demo.mp4", title: str = "NetOps Status Demo") -> str:
    """Return the self-contained HTML5 player document as a string."""
    return HTML_TEMPLATE.format(
        title=html.escape(title, quote=True),
        video_src=html.escape(video_src, quote=True),
    )


def write_player_html(
    video_src: str = "demo.mp4",
    out_path: str | Path = "out/player.html",
    title: str = "NetOps Status Demo",
) -> Path:
    """Generate and write the HTML player file to out_path."""
    target = Path(out_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(build_html(video_src=video_src, title=title), encoding="utf-8")
    return target


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a self-contained HTML5 video player with 1x, 1.5x, and 2x speed controls."
    )
    parser.add_argument(
        "--video",
        default="demo.mp4",
        help="Path or src URL used in the <video> element (default: demo.mp4)",
    )
    parser.add_argument(
        "--out",
        default="out/player.html",
        help="Output HTML file path (default: out/player.html)",
    )
    parser.add_argument(
        "--title",
        default="NetOps Status Demo",
        help="HTML page and header title (default: NetOps Status Demo)",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    written = write_player_html(video_src=args.video, out_path=args.out, title=args.title)
    print(f"Wrote player HTML to {written}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
