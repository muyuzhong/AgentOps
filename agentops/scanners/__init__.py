"""只读仓库扫描器。"""

from agentops.scanners.ci import CIDetector, CIScanError
from agentops.scanners.repo import RepoScanner

__all__ = ["CIDetector", "CIScanError", "RepoScanner"]
