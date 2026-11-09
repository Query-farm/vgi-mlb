# /// script
# requires-python = ">=3.13"
# dependencies = ["vgi-python[http]>=0.50.0,<0.51", "httpx>=0.27,<1", "pyarrow>=18,<26"]
# ///
"""Stdio entry point for attaching the MLB VGI catalog."""

from vgi_mlb.worker import main

if __name__ == "__main__":
    main()
