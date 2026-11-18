"""The public source boundary shared by validation and release packaging."""
from pathlib import Path

DIRECTORIES = ('.github', 'LICENSES', 'branding', 'config', 'docs', 'helpers', 'scripts', 'vendor')
FILES = ('.editorconfig', '.gitattributes', '.gitignore', 'CHANGELOG.md', 'CONTRIBUTING.md',
         'LICENSE', 'README.md', 'SECURITY.md', 'THIRD_PARTY.md', 'build.sh')


def public_files(root: Path):
    """Yield source files only; never traverse build state or local VM fixtures."""
    for name in FILES:
        path = root / name
        if not path.is_file() or path.is_symlink():
            raise ValueError(f'Missing or symlinked public file: {name}')
        yield path
    for name in DIRECTORIES:
        directory = root / name
        if not directory.is_dir():
            raise ValueError(f'Missing public directory: {name}')
        for path in sorted(directory.rglob('*')):
            relative = path.relative_to(root)
            if any(part in {'.git', '__pycache__', 'node_modules', '.venv'} for part in relative.parts):
                continue
            if path.is_symlink():
                raise ValueError(f'Public source must not contain symlinks: {relative}')
            if path.is_file():
                yield path
