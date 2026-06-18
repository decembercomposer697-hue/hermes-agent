"""Test that setup.py has shutil available for Matrix E2EE auto-install."""
import ast
import pathlib


def _parse_setup_imports():
    """Parse setup.py and return top-level import names."""
    with pathlib.Path("hermes_cli/setup.py").open() as f:
        tree = ast.parse(f.read())
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) or isinstance(node, ast.ImportFrom):
            names.update(alias.name for alias in node.names)
    return names


class TestSetupShutilImport:
    def test_shutil_imported_at_module_level(self):
        """Shutil must be imported at module level so setup_gateway can use it
        for the mautrix auto-install path.
        """
        names = _parse_setup_imports()
        assert "shutil" in names, (
            "shutil is not imported at the top of hermes_cli/setup.py. "
            "This causes a NameError when the Matrix E2EE auto-install "
            "tries to call shutil.which('uv')."
        )
