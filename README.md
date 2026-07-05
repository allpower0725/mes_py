# MES Py

Python desktop MES MVP. The first implementation uses a local SQLite database
through SQLAlchemy and keeps the same service boundaries needed to move to a
PostgreSQL backend later.

## Run

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m mes_py
```

The default database URL is:

```text
sqlite:///data/mes.db
```

Override it with:

```powershell
$env:MES_DATABASE_URL = "postgresql+psycopg://user:password@host:5432/mes"
```

## First Login

On the first run, the app creates a local bootstrap account:

```text
Email: admin@local
Password: admin123
```

Change this before using real production data.

## Packaging Direction

Development builds can use PyInstaller, but the formal Windows delivery target
is Nuitka standalone mode with the PySide6 plugin, then an installer such as
Inno Setup or NSIS.

```powershell
python -m nuitka --mode=standalone --enable-plugin=pyside6 --include-package-data=mes_py --windows-console-mode=disable src\mes_py\__main__.py
```

