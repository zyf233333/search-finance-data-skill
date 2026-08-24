"""Connector interfaces and provider implementations."""

from .base import DatasetConnector
from .fred import FredConnector
from .institutional import CsmarConnector, RessetConnector, WrdsConnector
from .kenneth_french import KennethFrenchConnector
from .sec_edgar import SecEdgarConnector

__all__ = ["DatasetConnector", "FredConnector", "KennethFrenchConnector", "SecEdgarConnector", "WrdsConnector", "CsmarConnector", "RessetConnector"]
