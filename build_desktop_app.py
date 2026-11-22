#!/usr/bin/env python3
"""One-click script to package AgentBar into a Desktop App and install Desktop shortcuts."""

import sys
from agentbar.cli import main

if __name__ == "__main__":
    sys.exit(main(["install-desktop"] + sys.argv[1:]))
