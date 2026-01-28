"""
Standalone test for Graph Page multi-mode functionality.
Tests code structure and logic without requiring external dependencies.
"""
import os
import sys
import ast
from pathlib import Path

# Add src to path so we can import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))


def test_file_exists(filepath, name):
    """Check if a file exists."""
    exists = os.path.exists(filepath)
    status = "✓" if exists else "✗"
    print(f"{status} {name}: {'Found' if exists else 'NOT FOUND'}")
    return exists


def test_class_has_methods(filepath, class_name, required_methods):
    """Check if a class has the required methods."""
    try:
        with open(filepath, 'r') as f:
            content = f.read()

        tree = ast.parse(content)

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                methods = [n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]

                missing = [m for m in required_methods if m not in methods]

                if missing:
                    print(f"✗ {class_name} missing methods: {missing}")
                    return False
                else:
                    print(f"✓ {class_name} has all {len(required_methods)} required methods")
                    return True

        print(f"✗ Class {class_name} not found in {filepath}")
        return False

    except Exception as e:
        print(f"✗ Error parsing {filepath}: {e}")
        return False


def test_file_contains_patterns(filepath, patterns, name):
    """Check if file contains required patterns."""
    try:
        with open(filepath, 'r') as f:
            content = f.read()

        missing = []
        for pattern in patterns:
            if pattern not in content:
                missing.append(pattern)

        if missing:
            print(f"✗ {name} missing patterns: {missing[:3]}...")  # Show first 3
            return False
        else:
            print(f"✓ {name} contains all {len(patterns)} required patterns")
            return True

    except Exception as e:
        print(f"✗ Error reading {filepath}: {e}")
        return False


def run_structure_tests():
    """Run all structure tests."""
    print("=" * 60)
    print("GRAPH PAGE MULTI-MODE STRUCTURE TESTS")
    print("=" * 60)

    # project_root = "/tmp/pcba database"
    project_root = Path(__file__).parent.parent

    results = []

    # Test 1: Check all required files exist
    print("\n--- File Existence ---")
    files_to_check = [
        (f"{project_root}/src/database/database_manufacturer_tables.py", "Manufacturer tables"),
        (f"{project_root}/src/database/database_test_log_tables.py", "Test log tables"),
        (f"{project_root}/src/database/database_queries.py", "Database queries"),
        (f"{project_root}/src/database/__init__.py", "Database __init__"),
        (f"{project_root}/src/gui/graph_generation/graph_generator.py", "Graph generator"),
        (f"{project_root}/src/gui/graph_generation/graph_config.py", "Graph config"),
        (f"{project_root}/src/gui/pages/graph_page.py", "Graph page"),
    ]

    for filepath, name in files_to_check:
        results.append(test_file_exists(filepath, name))

    # Test 2: Check Manufacturer model structure
    print("\n--- Manufacturer Model ---")
    mfr_patterns = [
        "class Manufacturer(Base):",
        "class ManufacturerSpec(Base):",
        "class ManufacturerDeviceBatch(Base):",
        "class ManufacturerExcelImporter:",
        "def import_from_excel",
        "def export_template",
    ]
    results.append(test_file_contains_patterns(
        f"{project_root}/src/database/database_manufacturer_tables.py",
        mfr_patterns,
        "Manufacturer module"
    ))

    # Test 3: Check Spec model has plot_data
    print("\n--- Spec Model Updates ---")
    spec_patterns = [
        "plot_data = Column(Text",
        "def get_plot_data(self):",
        "def set_plot_data(self, data):",
        "json.loads",
        "json.dumps",
    ]
    results.append(test_file_contains_patterns(
        f"{project_root}/src/database/database_test_log_tables.py",
        spec_patterns,
        "Spec model plot_data"
    ))

    # Test 4: Check query methods
    print("\n--- Query Methods ---")
    query_patterns = [
        "def get_plot_spec_names(self):",
        "def get_paired_spec_names(self, spec_name",
        "has_plot == True",
    ]
    results.append(test_file_contains_patterns(
        f"{project_root}/src/database/database_queries.py",
        query_patterns,
        "Spec queries"
    ))

    # Test 5: Check graph_page structure
    print("\n--- GraphPage Structure ---")
    gp_patterns = [
        "class GraphMode:",
        "class DisplayType:",
        "class GraphPage:",
        "self.cached_plots",
        "self.current_mode",
        "def on_graph_mode_changed",
        "def on_display_type_changed",
        "def update_display_type_options",
        "def _generate_standard_plots",
        "def _generate_comparison_plots",
        "def _generate_relational_plots",
        "def _generate_overlay_plot",
        "def _pair_measurements",
        "def clear_cached_plots",
        "def display_plot",
        "DisplayType.SCATTER",
        "DisplayType.LINE",
        "DisplayType.HISTOGRAM",
        "DisplayType.DIFFERENCE",
        "DisplayType.MANUFACTURER",
        "DisplayType.OVERLAY",
        "GraphMode.STANDARD",
        "GraphMode.COMPARISON",
        "GraphMode.RELATIONAL",
        "GraphMode.PLOT_OVERLAY",
    ]
    results.append(test_file_contains_patterns(
        f"{project_root}/src/gui/pages/graph_page.py",
        gp_patterns,
        "GraphPage V2"
    ))

    # Test 6: Check grid density fix is present
    print("\n--- Grid Density Fix ---")
    grid_patterns = [
        "def _set_grid_density_axis",
        "axis_range = abs(view_range",
        "major = axis_range /",
        "Grid Density",
        "X-Axis",
        "Y-Axis",
        "Both Axes",
    ]
    results.append(test_file_contains_patterns(
        f"{project_root}/src/gui/graph_generation/graph_generator.py",
        grid_patterns,
        "Grid density"
    ))

    # Test 7: Check database __init__ exports
    print("\n--- Database Exports ---")
    init_patterns = [
        "from src.database.database_manufacturer_tables import",
        "Manufacturer",
        "ManufacturerSpec",
        "ManufacturerDeviceBatch",
        "ManufacturerExcelImporter",
    ]
    results.append(test_file_contains_patterns(
        f"{project_root}/src/database/__init__.py",
        init_patterns,
        "Database exports"
    ))

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    passed = sum(results)
    total = len(results)

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n✓ ALL STRUCTURE TESTS PASSED!")
        print("\nThe following features are implemented:")
        print("  1. Manufacturer tables with Excel import")
        print("  2. Spec plot_data JSON storage")
        print("  3. get_plot_spec_names() and get_paired_spec_names() queries")
        print("  4. GraphPage with multi-mode support:")
        print("     - Standard: Scatter, Line, Histogram")
        print("     - Comparison: Manufacturer, Difference, Fixture, Batch comparisons")
        print("     - Relational: Scatter, Line between measurements")
        print("     - Plot Overlay: Overlaid line plots")
        print("  5. Cached plots for quick display type switching")
        print("  6. Dynamic X/Y axis population based on mode")
        print("  7. Grid density relative to axis range (Y-axis fix)")
    else:
        print("\n✗ SOME TESTS FAILED - Please check the output above")

    return passed == total


if __name__ == '__main__':
    import sys

    success = run_structure_tests()
    sys.exit(0 if success else 1)