"""
One-command local setup for MediFind (Windows, Linux and Mac; standard library only).

    python scripts/setup.py            # Linux / Mac
    py scripts\\setup.py                # Windows
    python scripts/setup.py --reset    # fresh demo database (keeps a backup of the old one)

What it does:
  1. checks that Python is 3.11 or newer;
  2. creates the virtual environment .venv (if missing) and installs requirements.txt into it;
  3. copies .env.example to .env (if .env is missing);
  4. runs migrate, and seed_data only when db.sqlite3 did not exist before;
     with --reset it first moves db.sqlite3 to ../medifind_db_backup_<time>.sqlite3 and always seeds;
  5. prints the command that starts the server.
"""
import argparse
import os
import shutil
import subprocess
import sys
import venv
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV = ROOT / ".venv"
DB = ROOT / "db.sqlite3"
WINDOWS = os.name == "nt"
VENV_PYTHON = VENV / ("Scripts/python.exe" if WINDOWS else "bin/python")


def step(text):
    print(f"==> {text}", flush=True)


def fail(text):
    print(f"\nERROR: {text}", file=sys.stderr)
    sys.exit(1)


def run(*args):
    """Runs a command in the project folder with the venv's Python; stops on the first error."""
    result = subprocess.run([str(VENV_PYTHON), *args], cwd=ROOT)
    if result.returncode != 0:
        fail(f"This command failed: python {' '.join(args)}")


def check_python():
    if sys.version_info < (3, 11):
        found = ".".join(map(str, sys.version_info[:3]))
        fail(f"MediFind needs Python 3.11 or newer, but this is Python {found}.\n"
             "Install Python 3.11 from https://www.python.org/downloads/ and run this script with it "
             "(Windows: py -3.11 scripts\\setup.py).")


def create_venv():
    if VENV_PYTHON.exists():
        step("Virtual environment .venv already exists")
        return
    step("Creating virtual environment .venv ...")
    try:
        venv.EnvBuilder(with_pip=True).create(VENV)
    except Exception as exc:  # for example Debian/Ubuntu without the python3-venv package
        shutil.rmtree(VENV, ignore_errors=True)
        fail(f"Could not create .venv ({exc}).\n"
             "On Debian/Ubuntu install the venv package first, for example: sudo apt install python3.11-venv")


def install_requirements():
    step("Installing packages from requirements.txt ...")
    run("-m", "pip", "install", "--disable-pip-version-check", "-r", "requirements.txt")


def create_env_file():
    env_file = ROOT / ".env"
    if env_file.exists():
        step(".env already exists (not changed)")
        return
    shutil.copyfile(ROOT / ".env.example", env_file)
    step("Created .env from .env.example (DEBUG=True, SQLite)")


def backup_database():
    if not DB.exists():
        return
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = ROOT.parent / f"medifind_db_backup_{stamp}.sqlite3"
    shutil.move(str(DB), str(backup))
    step(f"Old database moved to {backup}")


def main():
    parser = argparse.ArgumentParser(description="Set up MediFind for local use.")
    parser.add_argument("--reset", action="store_true",
                        help="back up db.sqlite3 to ../medifind_db_backup_<time>.sqlite3, then migrate and seed again")
    args = parser.parse_args()

    check_python()
    if os.environ.get("DATABASE_URL"):
        fail("DATABASE_URL is set, so this is not the local SQLite database. "
             "This script is only for local use; unset DATABASE_URL first.")

    create_venv()
    install_requirements()
    create_env_file()

    if args.reset:
        backup_database()
    seed = args.reset or not DB.exists()

    step("Creating or updating the database tables (migrate) ...")
    run("manage.py", "migrate", "--no-input")
    if seed:
        step("Adding demo data (seed_data) ...")
        run("manage.py", "seed_data")
    else:
        step("db.sqlite3 already existed, so demo data was not added again (use --reset for a fresh demo)")

    start = r".venv\Scripts\python.exe manage.py runserver" if WINDOWS else ".venv/bin/python manage.py runserver"
    print("\nSetup finished. Start the server with:\n")
    print(f"    {start}\n")
    print("Then open http://127.0.0.1:8000  (demo login: admin / admin123)")


if __name__ == "__main__":
    main()
