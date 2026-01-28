"""
GUI Pages package.

Contains page handlers for each section of the application.
"""
# Use lazy imports to avoid import failures
# Import these directly in your code:
#   from src.gui.pages.graph_page import GraphPage
#   from src.gui.pages.database_page import DatabasePage
#   from src.gui.pages.reports_page import ReportsPage
#   from src.gui.pages.search_page import SearchPage

__all__ = ["GraphPage", "DatabasePage", "ReportsPage", "SearchPage"]

def __getattr__(name):
    """Lazy import to avoid circular imports and missing dependency issues."""
    if name == "GraphPage":
        from src.gui.pages.graph_page import GraphPage
        return GraphPage
    elif name == "DatabasePage":
        from src.gui.pages.database_page import DatabasePage
        return DatabasePage
    elif name == "ReportsPage":
        from src.gui.pages.reports_page import ReportsPage
        return ReportsPage
    elif name == "SearchPage":
        from src.gui.pages.search_page import SearchPage
        return SearchPage
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


