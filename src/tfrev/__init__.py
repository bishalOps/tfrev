"""tfrev — AI-powered Terraform plan reviewer."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("tfrev")
except PackageNotFoundError:
    __version__ = "0.0.0-dev"
