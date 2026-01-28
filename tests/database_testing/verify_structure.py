#!/usr/bin/env python3
"""
Code structure verification script.

Since SQLAlchemy is not available in this environment, this script
performs static checks on the code structure to verify the refactoring
is correct.
"""
import os
import sys
import ast
from pathlib import Path

def check_file_exists(filepath, description):
    """Check if a file exists."""
    if os.path.exists(filepath):
        print(f"✓ {description}: {filepath}")
        return True
    else:
        print(f"✗ {description} NOT FOUND: {filepath}")
        return False

def check_imports_in_file(filepath, expected_imports):
    """Check if file contains expected imports."""
    try:
        with open(filepath, 'r') as f:
            content = f.read()
            tree = ast.parse(content)
        
        imports_found = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module
                for alias in node.names:
                    imports_found.append(f"from {module} import {alias.name}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports_found.append(f"import {alias.name}")
        
        print(f"\n  Checking imports in {os.path.basename(filepath)}:")
        all_found = True
        for expected in expected_imports:
            if any(expected in imp for imp in imports_found):
                print(f"    ✓ Found: {expected}")
            else:
                print(f"    ✗ Missing: {expected}")
                all_found = False
        
        return all_found
    except Exception as e:
        print(f"    ✗ Error parsing file: {e}")
        return False

def check_class_has_attribute(filepath, classname, attribute):
    """Check if a class has a specific attribute."""
    try:
        with open(filepath, 'r') as f:
            content = f.read()
            tree = ast.parse(content)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == classname:
                for item in node.body:
                    if isinstance(item, ast.Assign):
                        for target in item.targets:
                            if isinstance(target, ast.Name) and target.id == attribute:
                                print(f"    ✓ Class {classname} has attribute: {attribute}")
                                return True
        
        print(f"    ✗ Class {classname} missing attribute: {attribute}")
        return False
    except Exception as e:
        print(f"    ✗ Error: {e}")
        return False

def main():
    project_root = Path(__file__).parent.parent.parent
    src_dir = project_root / "src" / "database"
    
    print("="*60)
    print("DATABASE LAYER STRUCTURE VERIFICATION")
    print("="*60)
    
    all_checks_passed = True
    
    # Check 1: Files exist
    print("\n1. Checking if all required files exist:")
    print("-" * 40)
    files_to_check = [
        (os.path.join(src_dir, "base.py"), "base.py (unified Base)"),
        (os.path.join(src_dir, "manager.py"), "manager.py (DatabaseManager)"),
        (os.path.join(src_dir, "database_device_tables.py"), "device tables"),
        (os.path.join(src_dir, "database_test_log_tables.py"), "test log tables"),
        (os.path.join(src_dir, "database_queries.py"), "queries"),
        (os.path.join(src_dir, "database_utils.py"), "utils"),
        (os.path.join(src_dir, "database_worker.py"), "worker"),
        (os.path.join(src_dir, "__init__.py"), "__init__.py"),
        (os.path.join(project_root, "data"), "data directory"),
    ]
    
    for filepath, desc in files_to_check:
        if not check_file_exists(filepath, desc):
            all_checks_passed = False
    
    # Check 2: base.py has unified Base
    print("\n2. Checking base.py structure:")
    print("-" * 40)
    base_file = os.path.join(src_dir, "base.py")
    if os.path.exists(base_file):
        with open(base_file, 'r') as f:
            content = f.read()
            if "Base = declarative_base()" in content:
                print("  ✓ base.py declares unified Base")
            else:
                print("  ✗ base.py does NOT declare unified Base")
                all_checks_passed = False
            
            if "def get_engine" in content:
                print("  ✓ base.py has get_engine function")
            else:
                print("  ✗ base.py missing get_engine")
                all_checks_passed = False
            
            if "def init_database" in content:
                print("  ✓ base.py has init_database function")
            else:
                print("  ✗ base.py missing init_database")
                all_checks_passed = False
    
    # Check 3: Models import from base.py
    print("\n3. Checking model files import from base.py:")
    print("-" * 40)
    
    device_tables = os.path.join(src_dir, "database_device_tables.py")
    if not check_imports_in_file(device_tables, ["from src.database.base import Base"]):
        all_checks_passed = False
    
    test_log_tables = os.path.join(src_dir, "database_test_log_tables.py")
    if not check_imports_in_file(test_log_tables, ["from src.database.base import Base"]):
        all_checks_passed = False
    
    # Check 4: Models have __tablename__ (not tablename)
    print("\n4. Checking models have __tablename__ attribute:")
    print("-" * 40)
    
    if not check_class_has_attribute(device_tables, "PMT", "__tablename__"):
        all_checks_passed = False
    if not check_class_has_attribute(device_tables, "PCBABoard", "__tablename__"):
        all_checks_passed = False
    if not check_class_has_attribute(test_log_tables, "TestLog", "__tablename__"):
        all_checks_passed = False
    if not check_class_has_attribute(test_log_tables, "SubTest", "__tablename__"):
        all_checks_passed = False
    if not check_class_has_attribute(test_log_tables, "Spec", "__tablename__"):
        all_checks_passed = False
    
    # Check 5: queries.py has correct imports
    print("\n5. Checking database_queries.py imports:")
    print("-" * 40)
    queries_file = os.path.join(src_dir, "database_queries.py")
    expected_queries_imports = [
        "from src.database.database_device_tables",
        "from src.database.database_test_log_tables",
    ]
    if not check_imports_in_file(queries_file, expected_queries_imports):
        all_checks_passed = False
    
    # Check that OLD imports are gone
    with open(queries_file, 'r') as f:
        content = f.read()
        if "src.appPackage" in content:
            print("  ✗ Still has old 'src.appPackage' imports!")
            all_checks_passed = False
        else:
            print("  ✓ No old 'src.appPackage' imports found")
    
    # Check 6: manager.py exists and has DatabaseManager class
    print("\n6. Checking manager.py structure:")
    print("-" * 40)
    manager_file = os.path.join(src_dir, "manager.py")
    if os.path.exists(manager_file):
        with open(manager_file, 'r') as f:
            content = f.read()
            
            checks = [
                ("class DatabaseManager:", "DatabaseManager class"),
                ("def session_scope(self):", "session_scope method"),
                ("def get_new_session(self):", "get_new_session method"),
                ("@property", "queries property"),
                ("def queries(self):", "queries getter"),
                ("from src.database.base import", "imports from base.py"),
                ("from src.database.database_queries import Queries", "imports Queries"),
            ]
            
            for check_str, desc in checks:
                if check_str in content:
                    print(f"  ✓ Has {desc}")
                else:
                    print(f"  ✗ Missing {desc}")
                    all_checks_passed = False
    
    # Check 7: __init__.py exports
    print("\n7. Checking __init__.py exports:")
    print("-" * 40)
    init_file = os.path.join(src_dir, "__init__.py")
    if os.path.exists(init_file):
        with open(init_file, 'r') as f:
            content = f.read()
            
            exports = [
                "DatabaseManager",
                "PMT",
                "PCBABoard",
                "TestLog",
                "SubTest",
                "Spec",
            ]
            
            for export in exports:
                if export in content:
                    print(f"  ✓ Exports {export}")
                else:
                    print(f"  ✗ Does not export {export}")
                    all_checks_passed = False
    
    # Check 8: database_utils.py updated
    print("\n8. Checking database_utils.py:")
    print("-" * 40)
    utils_file = os.path.join(src_dir, "database_utils.py")
    if os.path.exists(utils_file):
        with open(utils_file, 'r') as f:
            content = f.read()
            
            if "from src.database.base import" in content:
                print("  ✓ Imports from src.database.base")
            else:
                print("  ✗ Does not import from src.database.base")
                all_checks_passed = False
            
            if "src.appPackage" in content:
                print("  ✗ Still has old 'src.appPackage' imports!")
                all_checks_passed = False
            else:
                print("  ✓ No old 'src.appPackage' imports")
    
    # Check 9: database_worker.py updated
    print("\n9. Checking database_worker.py:")
    print("-" * 40)
    worker_file = os.path.join(src_dir, "database_worker.py")
    if os.path.exists(worker_file):
        with open(worker_file, 'r') as f:
            content = f.read()
            
            if "from src.database.base import get_session_factory" in content:
                print("  ✓ Imports get_session_factory from base")
            else:
                print("  ✗ Does not import get_session_factory from base")
                all_checks_passed = False
    
    # Summary
    print("\n" + "="*60)
    if all_checks_passed:
        print("✓ ALL STRUCTURE CHECKS PASSED!")
        print("="*60)
        print("\nThe database layer has been successfully refactored:")
        print("  • Unified Base class in base.py")
        print("  • Fixed __tablename__ attributes in all models")
        print("  • Fixed all import paths")
        print("  • Created DatabaseManager with Option C (all 3 patterns)")
        print("  • Updated all dependent files")
        print("\nNext steps:")
        print("  1. Install SQLAlchemy in your environment")
        print("  2. Run: python test_database.py")
        print("  3. Verify all tests pass")
        return 0
    else:
        print("✗ SOME CHECKS FAILED")
        print("="*60)
        print("\nPlease review the failed checks above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
