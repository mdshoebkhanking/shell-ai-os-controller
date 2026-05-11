
import os
import json

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Shell AI Thinking Visualizer</title>
    <style>
        body { background: #1a1a1a; color: #0f0; font-family: monospace; padding: 20px; }
        .node { border: 1px solid #444; padding: 10px; margin: 10px; border-radius: 5px; background: #222; }
        .timestamp { color: #888; font-size: 0.8em; }
        .success { border-color: #0f0; }
        .error { border-color: #f00; color: #f88; }
    </style>
</head>
<body>
    <h1>🧠 Shell AI Thinking Stream</h1>
    <div id="log-container">
        <!-- LOGS -->
    </div>
    <script>
        // Simple script to polling could be added, but static for now.
    </script>
</body>
</html>
"""

class VisualizerLite:
    """
    Zero-Dependency Visualizer.
    Writes logs to an HTML file that user can open.
    """
    def __init__(self):
        self.log_path = "brain/visualization/thought_stream.html"
        self._init_html()

    def _init_html(self):
        if not os.path.exists(self.log_path):
            self._write_html(HTML_TEMPLATE.replace("<!-- LOGS -->", ""))

    def _write_html(self, content):
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
        with open(self.log_path, "w", encoding="utf-8") as f:
            f.write(content)

    def log_thought(self, agent: str, thought: str, status: str = "success"):
        """Appends a thought node to the HTML."""
        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                current_html = f.read()
            
            node_html = f"""
            <div class="node {status}">
                <span class="timestamp">{agent}</span><br>
                {thought}
            </div>
            <!-- LOGS -->
            """
            
            new_html = current_html.replace("<!-- LOGS -->", node_html)
            self._write_html(new_html)
        except Exception:
            pass  # Visualization is non-critical, don't crash agent

visualizer_lite = VisualizerLite()
