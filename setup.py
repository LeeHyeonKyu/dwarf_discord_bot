#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
dwarf_discord_bot 설정 스크립트.
"""

from setuptools import setup, find_packages

if __name__ == "__main__":
    setup(
        name="dwarf_discord_bot",
        packages=find_packages(include=["cogs", "services", "utils", "cogs.*", "services.*", "utils.*"]),
    ) 