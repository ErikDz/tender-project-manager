"""Run the Flask development server."""

import sys
from pathlib import Path

# Add project root so core/ and ai/ resolve from the single shared copy
sys.path.insert(0, str(Path(__file__).parent.parent))
# Add backend/ so app/ resolves
sys.path.insert(0, str(Path(__file__).parent))

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=app.config["DEBUG"])
