#!/usr/bin/env python3
"""
Set default language model in Kyma deployment.

This script sets the default language model for chat sessions.
Run this inside the Kyma backend pod.
"""

import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, '/app')

from api.services.settings import set_model_defaults


async def main():
    """Set default language model to first SAP AI Core model."""
    # Use the first SAP AI Core gpt-4o model
    model_id = "3ab4bef8-f62c-4421-8030-b040538b1563"  # SAP AI Core - gpt-5.4

    print(f"Setting default language model to: {model_id}")
    await set_model_defaults(language_model_id=model_id)
    print("Default language model set successfully!")


if __name__ == "__main__":
    asyncio.run(main())
