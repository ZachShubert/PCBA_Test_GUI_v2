#!/usr/bin/env python3
"""
QSS Theme Generator
Reads theme TOML files and generates complete QSS stylesheets by replacing placeholders
in template files with theme colors.

Usage:
    python generate_qss.py --theme ocean --mode dark
    python generate_qss.py --theme sunset --mode light
    python generate_qss.py --list  # List available themes
"""

import argparse
from pathlib import Path
try:
    import tomllib  # Python 3.11+
except ImportError:
    import tomli as tomllib  # Fallback for older Python


class QSSGenerator:
    """Generates QSS stylesheets from TOML theme files."""
    
    def __init__(self, base_dir: Path = None):
        """
        Initialize the generator.
        
        Args:
            base_dir: Base directory containing themes and styling folders.
                     Defaults to parent directory of this script.
        """
        if base_dir is None:
            base_dir = Path(__file__).parent.parent
        
        self.base_dir = base_dir
        self.themes_dir = base_dir / "styling" / "themes"
        self.templates_dir = base_dir / "styling" / "templates"
        self.output_dir = base_dir / "styling" / "generated"
        
        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def list_themes(self) -> list[str]:
        """
        List all available themes.
        
        Returns:
            List of theme names (without 'theme_' prefix and '.toml' suffix)
        """
        if not self.themes_dir.exists():
            return []
        
        themes = []
        for theme_file in self.themes_dir.glob("theme_*.toml"):
            theme_name = theme_file.stem.replace("theme_", "")
            themes.append(theme_name)
        
        return sorted(themes)
    
    def load_theme(self, theme_name: str, mode: str = "dark") -> dict:
        """
        Load a theme configuration.
        
        Args:
            theme_name: Name of the theme (e.g., 'ocean', 'sunset')
            mode: Either 'light' or 'dark'
        
        Returns:
            Dictionary of color values
        
        Raises:
            FileNotFoundError: If theme file doesn't exist
            KeyError: If mode doesn't exist in theme
        """
        theme_file = self.themes_dir / f"theme_{theme_name}.toml"
        
        if not theme_file.exists():
            raise FileNotFoundError(f"Theme file not found: {theme_file}")
        
        with open(theme_file, "rb") as f:
            theme_data = tomllib.load(f)
        
        if mode not in theme_data:
            raise KeyError(f"Mode '{mode}' not found in theme '{theme_name}'")
        
        return theme_data[mode]
    
    def load_template(self, template_name: str) -> str:
        """
        Load a QSS template file.
        
        Args:
            template_name: Name of template file (e.g., 'base.qss')
        
        Returns:
            Template content as string
        
        Raises:
            FileNotFoundError: If template doesn't exist
        """
        template_file = self.templates_dir / template_name
        
        if not template_file.exists():
            raise FileNotFoundError(f"Template file not found: {template_file}")
        
        with open(template_file, "r", encoding="utf-8") as f:
            return f.read()
    
    def replace_placeholders(self, template: str, colors: dict) -> str:
        """
        Replace color placeholders in template with actual values.
        
        Args:
            template: Template string with {color_name} placeholders
            colors: Dictionary mapping color names to hex values
        
        Returns:
            Template with placeholders replaced
        """
        result = template
        for key, value in colors.items():
            placeholder = "{" + key + "}"
            result = result.replace(placeholder, value)
        
        return result
    
    def generate_qss(self, theme_name: str, mode: str = "dark", output_file: str = "styles.qss") -> Path:
        """
        Generate complete QSS stylesheet from theme and templates.
        
        Args:
            theme_name: Name of theme to use
            mode: 'light' or 'dark'
            output_file: Name of output file (default: styles.qss)
        
        Returns:
            Path to generated QSS file
        """
        # Load theme colors
        colors = self.load_theme(theme_name, mode)
        
        # Template files in order
        template_files = [
            "base.qss",
            "buttons.qss",
            "inputs.qss",
            "tables.qss",
            "labels.qss"
        ]
        
        # Generate QSS content
        qss_parts = []
        qss_parts.append(f"/* Generated from theme: {theme_name} ({mode} mode) */\n")
        qss_parts.append(f"/* DO NOT EDIT - This file is auto-generated */\n\n")
        
        for template_name in template_files:
            try:
                template = self.load_template(template_name)
                processed = self.replace_placeholders(template, colors)
                qss_parts.append(processed)
                qss_parts.append("\n\n")
            except FileNotFoundError as e:
                print(f"Warning: {e}")
                continue
        
        # Write to output file
        output_path = self.output_dir / output_file
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("".join(qss_parts))
        
        return output_path
    
    def generate_all_themes(self):
        """Generate QSS files for all themes in both light and dark modes."""
        themes = self.list_themes()
        
        if not themes:
            print("No themes found!")
            return
        
        for theme_name in themes:
            for mode in ["light", "dark"]:
                try:
                    output_file = f"styles_{theme_name}_{mode}.qss"
                    output_path = self.generate_qss(theme_name, mode, output_file)
                    print(f"✓ Generated: {output_path.name}")
                except Exception as e:
                    print(f"✗ Error generating {theme_name} ({mode}): {e}")


def main():
    """Main entry point for the script."""

    # Initialize generator
    generator = QSSGenerator()
    
    # List themes
    themes = generator.list_themes()
    if themes:
        print("Available themes:")
        for theme in themes:
            print(f"  - {theme}")
    else:
        print("No themes found!")
    
    # Generate all themes
    print("\n\nGenerating all themes...")
    generator.generate_all_themes()


if __name__ == "__main__":
    main()
