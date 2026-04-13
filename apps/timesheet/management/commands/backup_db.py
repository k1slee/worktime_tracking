import sqlite3
import zipfile
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


class Command(BaseCommand):
    help = "Back up the default database (SQLite supported) to a directory with rotation."

    def add_arguments(self, parser):
        parser.add_argument("--dest-dir", default=None)
        parser.add_argument("--prefix", default="db_backup")
        parser.add_argument("--keep", type=int, default=14)
        parser.add_argument("--compress", action="store_true", default=True)
        parser.add_argument("--no-compress", action="store_false", dest="compress")
        parser.add_argument("--dry-run", action="store_true", default=False)

    def handle(self, *args, **options):
        db = settings.DATABASES.get("default") or {}
        engine = (db.get("ENGINE") or "").strip()
        name = db.get("NAME")
        if not name:
            raise CommandError("DATABASES['default']['NAME'] is empty")

        if options["dest_dir"]:
            dest_dir = Path(options["dest_dir"])
        else:
            parent = Path(str(name)).resolve().parent
            dest_dir = parent / "backups"

        keep = int(options["keep"])
        if keep < 1:
            raise CommandError("--keep must be >= 1")

        prefix = (options["prefix"] or "db_backup").strip()
        if not prefix:
            raise CommandError("--prefix is empty")

        ts = timezone.localtime(timezone.now()).strftime("%Y%m%d_%H%M%S")
        ext = "zip" if options["compress"] else "sqlite3"
        out_path = dest_dir / f"{prefix}_{ts}.{ext}"

        if options["dry_run"]:
            self.stdout.write(f"Engine: {engine}")
            self.stdout.write(f"Source: {name}")
            self.stdout.write(f"Destination: {out_path}")
            return

        try:
            dest_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise CommandError(f"Cannot create destination directory: {dest_dir} ({e})")

        if engine.endswith("sqlite3"):
            src_path = Path(str(name)).resolve()
            if not src_path.exists():
                raise CommandError(f"SQLite file not found: {src_path}")

            tmp_path = dest_dir / f"{prefix}_{ts}.sqlite3"
            self._sqlite_backup(src_path, tmp_path)

            if options["compress"]:
                self._zip_one(tmp_path, out_path)
                try:
                    tmp_path.unlink(missing_ok=True)
                except Exception:
                    pass
            else:
                if out_path != tmp_path:
                    tmp_path.replace(out_path)
        else:
            raise CommandError(f"Unsupported DB engine for backup command: {engine}")

        removed = self._rotate(dest_dir, prefix, keep)
        self.stdout.write(self.style.SUCCESS(f"Backup created: {out_path}"))
        if removed:
            self.stdout.write(f"Old backups removed: {removed}")

    def _sqlite_backup(self, src_path: Path, dest_path: Path):
        try:
            if dest_path.exists():
                dest_path.unlink()
        except Exception:
            pass

        src = sqlite3.connect(str(src_path))
        try:
            dest = sqlite3.connect(str(dest_path))
            try:
                src.backup(dest)
            finally:
                dest.close()
        finally:
            src.close()

    def _zip_one(self, file_path: Path, zip_path: Path):
        with zipfile.ZipFile(str(zip_path), mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.write(str(file_path), arcname=file_path.name)

    def _rotate(self, dest_dir: Path, prefix: str, keep: int):
        items = []
        for p in dest_dir.iterdir():
            if not p.is_file():
                continue
            if not p.name.startswith(prefix + "_"):
                continue
            if not (p.name.endswith(".zip") or p.name.endswith(".sqlite3")):
                continue
            items.append(p)

        items.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        to_remove = items[keep:]
        removed = 0
        for p in to_remove:
            try:
                p.unlink()
                removed += 1
            except Exception:
                continue
        return removed
