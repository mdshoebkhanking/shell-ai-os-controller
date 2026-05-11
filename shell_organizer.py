#!/usr/bin/env python3
import os
import shutil
import logging
import datetime
import hashlib
import json
from pathlib import Path
from shell_safe_executor import god_tier_tool as function_tool

logger = logging.getLogger("shell_organizer")

# Category Definitions
FILE_CATEGORIES = {
    "Images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".tiff", ".ico"],
    "Videos": [".mp4", ".mkv", ".avi", ".mov", ".flv", ".wmv", ".webm", ".m4v"],
    "Documents": [".pdf", ".docx", ".doc", ".txt", ".xlsx", ".xls", ".pptx", ".ppt", ".csv", ".rtf"],
    "Audio": [".mp3", ".wav", ".aac", ".flac", ".ogg", ".m4a"],
    "Archives": [".zip", ".rar", ".7z", ".tar", ".gz"],
    "Code": [".py", ".js", ".html", ".css", ".java", ".cpp", ".c", ".json", ".xml", ".bat", ".sh"],
    "Executables": [".exe", ".msi", ".apk"],
    "Fonts": [".ttf", ".otf", ".woff", ".woff2"],
    "Database": [".db", ".sqlite", ".sql", ".mdb"],
    "3D Models": [".obj", ".stl", ".fbx", ".blend"],
}

UNDO_LOG_FILENAME = "shell_organize_undo.json"


def _format_size(size_bytes: int) -> str:
    """Human-readable file size."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def _md5_hash(filepath: str, chunk_size: int = 8192) -> str:
    """Calculate MD5 hash of a file."""
    h = hashlib.md5()
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


@function_tool
async def organize_folder_tool(directory_path: str = None, by_date: bool = False, dry_run: bool = False) -> str:
    """
    Organizes files in a folder into categories like Images, Videos, Fonts, Database, 3D Models, etc.

    Args:
        directory_path: Absolute path (e.g., 'C:\\Users\\Downloads').
        by_date: If True, creates Year/Month subfolders inside categories (e.g., Images/2024/Jan).
        dry_run: If True, shows what would be moved without actually moving anything.
    """
    if not directory_path:
        return "❌ boss, path specify kijiye (e.g., 'Downloads')."

    # Validate path
    target_dir = os.path.abspath(directory_path)
    if not os.path.exists(target_dir):
        return f"❌ Path nahi mila: {target_dir}"

    try:
        mode_label = "DRY RUN" if dry_run else "LIVE"
        logger.info(f"📂 Organizing ({mode_label}): {target_dir} (Date Mode: {by_date})")

        stats = {cat: 0 for cat in FILE_CATEGORIES}
        stats["Others"] = 0
        category_sizes = {cat: 0 for cat in FILE_CATEGORIES}
        category_sizes["Others"] = 0
        moved_count = 0
        move_log = []  # For undo capability

        # Scan and Move
        for filename in os.listdir(target_dir):
            file_path = os.path.join(target_dir, filename)

            # Skip directories and the undo log itself
            if os.path.isdir(file_path):
                continue
            if filename == UNDO_LOG_FILENAME:
                continue

            # Identify Category
            _, ext = os.path.splitext(filename)
            ext = ext.lower()

            target_category = "Others"
            for category, extensions in FILE_CATEGORIES.items():
                if ext in extensions:
                    target_category = category
                    break

            # Prepare destination
            dest_folder = os.path.join(target_dir, target_category)

            # Date-based subfolder logic
            if by_date and target_category != "Others":
                try:
                    mtime = os.path.getmtime(file_path)
                    dt = datetime.datetime.fromtimestamp(mtime)
                    year_folder = dt.strftime("%Y")
                    month_folder = dt.strftime("%m-%b")
                    dest_folder = os.path.join(dest_folder, year_folder, month_folder)
                except (OSError, ValueError, OverflowError) as _date_err:
                    # Log the root cause so "organized 400 files but 12 skipped
                    # date bucketing" is actually visible to the user.
                    logger.warning(
                        "date-bucket skipped for %r: %s — falling back to category root",
                        file_path, _date_err,
                    )

            # Determine final destination path
            dest_path = os.path.join(dest_folder, filename)
            final_filename = filename
            if os.path.exists(dest_path) or (not dry_run and os.path.exists(dest_path)):
                base, extension = os.path.splitext(filename)
                counter = 1
                while os.path.exists(os.path.join(dest_folder, f"{base}_{counter}{extension}")):
                    counter += 1
                final_filename = f"{base}_{counter}{extension}"
                dest_path = os.path.join(dest_folder, final_filename)

            # Get file size
            try:
                file_size = os.path.getsize(file_path)
            except OSError:
                file_size = 0

            if not dry_run:
                os.makedirs(dest_folder, exist_ok=True)
                shutil.move(file_path, dest_path)
                # Log for undo
                move_log.append({
                    "original": file_path,
                    "moved_to": dest_path,
                    "category": target_category,
                    "size": file_size
                })

            stats[target_category] += 1
            category_sizes[target_category] += file_size
            moved_count += 1

        # Save undo log (only in live mode)
        if not dry_run and move_log:
            undo_path = os.path.join(target_dir, UNDO_LOG_FILENAME)
            undo_data = {
                "timestamp": datetime.datetime.now().isoformat(),
                "directory": target_dir,
                "by_date": by_date,
                "moves": move_log
            }
            with open(undo_path, "w", encoding="utf-8") as f:
                json.dump(undo_data, f, indent=2, ensure_ascii=False)

        # Generate Report
        if moved_count == 0:
            return f"📂 Folder '{os.path.basename(target_dir)}' already clean hai, boss."

        report_lines = []
        for cat in list(FILE_CATEGORIES.keys()) + ["Others"]:
            count = stats.get(cat, 0)
            if count > 0:
                size_str = _format_size(category_sizes.get(cat, 0))
                report_lines.append(f"  • {cat}: {count} files ({size_str})")

        report_str = "\n".join(report_lines)
        total_size_str = _format_size(sum(category_sizes.values()))

        if dry_run:
            return (
                f"🔍 DRY RUN Complete, boss! {moved_count} files move hongi:\n"
                f"{report_str}\n"
                f"  📊 Total size: {total_size_str}\n\n"
                f"⚠️ Koi file actually move nahi hui. dry_run=False karke run karo to move hogi.\n"
                f"📍 Location: {target_dir}"
            )

        return (
            f"✅ Done boss! {moved_count} files organize ho gayi:\n"
            f"{report_str}\n"
            f"  📊 Total size moved: {total_size_str}\n\n"
            f"📍 Location: {target_dir}\n"
            f"↩️ Undo log saved: {UNDO_LOG_FILENAME} (reversal ke liye)"
        )

    except Exception as e:
        logger.error(f"Organization error: {e}")
        return f"❌ Organizing mein error: {str(e)}"


@function_tool
async def find_duplicate_files_tool(directory_path: str = None) -> str:
    """
    Finds duplicate files in a directory by comparing file sizes and then MD5 hashes.
    Returns list of duplicate groups with paths and sizes. Suggests which to keep (oldest).

    Args:
        directory_path: Absolute path to the directory to scan for duplicates.
    """
    if not directory_path:
        return "❌ boss, directory path dena zaroori hai (e.g., 'C:\\\\Users\\\\Downloads')."

    target_dir = os.path.abspath(directory_path)
    if not os.path.exists(target_dir):
        return f"❌ Path nahi mila: {target_dir}"
    if not os.path.isdir(target_dir):
        return f"❌ Ye directory nahi hai: {target_dir}"

    try:
        logger.info(f"🔍 Scanning for duplicates: {target_dir}")

        # Step 1: Group files by size
        size_map = {}
        file_count = 0
        for root, dirs, files in os.walk(target_dir):
            for fname in files:
                fpath = os.path.join(root, fname)
                try:
                    fsize = os.path.getsize(fpath)
                    file_count += 1
                    if fsize > 0:  # Ignore empty files
                        size_map.setdefault(fsize, []).append(fpath)
                except OSError:
                    continue

        # Step 2: For groups with same size, compare MD5 hashes
        hash_map = {}
        files_hashed = 0
        for size, paths in size_map.items():
            if len(paths) < 2:
                continue
            for fpath in paths:
                try:
                    fhash = _md5_hash(fpath)
                    files_hashed += 1
                    key = (size, fhash)
                    hash_map.setdefault(key, []).append(fpath)
                except (OSError, PermissionError):
                    continue

        # Step 3: Filter actual duplicates
        duplicate_groups = []
        for (size, fhash), paths in hash_map.items():
            if len(paths) >= 2:
                duplicate_groups.append({
                    "hash": fhash,
                    "size": size,
                    "files": paths
                })

        if not duplicate_groups:
            return (
                f"✅ boss, koi duplicate nahi mila!\n"
                f"  📁 Scanned: {file_count} files\n"
                f"  🔐 Hashed: {files_hashed} files\n"
                f"📍 Directory: {target_dir}"
            )

        # Step 4: Build report
        total_wasted = 0
        report_lines = []
        for i, group in enumerate(duplicate_groups, 1):
            size_str = _format_size(group["size"])
            wasted = group["size"] * (len(group["files"]) - 1)
            total_wasted += wasted

            report_lines.append(f"\n🔁 Group {i} — Size: {size_str} | Hash: {group['hash'][:12]}...")

            # Find oldest file (to suggest keeping)
            oldest_path = None
            oldest_time = float("inf")
            for fpath in group["files"]:
                try:
                    ctime = os.path.getctime(fpath)
                    if ctime < oldest_time:
                        oldest_time = ctime
                        oldest_path = fpath
                except Exception as _e:
                    logger.debug("ignored Exception: %s", _e)

            for fpath in group["files"]:
                marker = " ⬅️ KEEP (sabse purani)" if fpath == oldest_path else " 🗑️ duplicate"
                report_lines.append(f"    • {fpath}{marker}")

        report_str = "\n".join(report_lines)
        total_wasted_str = _format_size(total_wasted)

        return (
            f"🔍 Duplicate Scan Complete, boss!\n"
            f"  📁 Total files scanned: {file_count}\n"
            f"  🔐 Files hashed: {files_hashed}\n"
            f"  🔁 Duplicate groups: {len(duplicate_groups)}\n"
            f"  💾 Wasted space: {total_wasted_str}\n"
            f"{report_str}\n\n"
            f"💡 Suggestion: Sabse purani file rakhein (KEEP), baaki delete kar sakte hain.\n"
            f"📍 Directory: {target_dir}"
        )

    except Exception as e:
        logger.error(f"Duplicate scan error: {e}")
        return f"❌ Duplicate scan mein error: {str(e)}"


@function_tool
async def find_large_files_tool(directory_path: str = "", min_size_mb: int = 100) -> str:
    """
    Scans directory for files larger than min_size_mb. Shows filename, path, size, and last modified date.
    Sorted by size descending. Default scans user home directory.

    Args:
        directory_path: Absolute path to scan. Defaults to user home directory if empty.
        min_size_mb: Minimum file size in MB to include (default 100).
    """
    if not directory_path or directory_path.strip() == "":
        directory_path = str(Path.home())

    target_dir = os.path.abspath(directory_path)
    if not os.path.exists(target_dir):
        return f"❌ Path nahi mila: {target_dir}"
    if not os.path.isdir(target_dir):
        return f"❌ Ye directory nahi hai: {target_dir}"

    try:
        min_size_bytes = min_size_mb * 1024 * 1024
        logger.info(f"📏 Scanning for large files (>= {min_size_mb} MB): {target_dir}")

        large_files = []
        scanned = 0
        errors = 0

        for root, dirs, files in os.walk(target_dir):
            for fname in files:
                fpath = os.path.join(root, fname)
                scanned += 1
                try:
                    fsize = os.path.getsize(fpath)
                    if fsize >= min_size_bytes:
                        mtime = os.path.getmtime(fpath)
                        mdate = datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
                        large_files.append({
                            "name": fname,
                            "path": fpath,
                            "size": fsize,
                            "modified": mdate
                        })
                except (OSError, PermissionError):
                    errors += 1
                    continue

        if not large_files:
            return (
                f"✅ boss, koi file {min_size_mb} MB se badi nahi mili!\n"
                f"  📁 Scanned: {scanned} files\n"
                f"📍 Directory: {target_dir}"
            )

        # Sort by size descending
        large_files.sort(key=lambda x: x["size"], reverse=True)

        total_size = sum(f["size"] for f in large_files)
        report_lines = []
        for idx, f in enumerate(large_files, 1):
            size_str = _format_size(f["size"])
            report_lines.append(
                f"  {idx}. 📄 {f['name']}\n"
                f"      📍 {f['path']}\n"
                f"      📏 Size: {size_str} | 📅 Modified: {f['modified']}"
            )

        report_str = "\n".join(report_lines)
        total_str = _format_size(total_size)

        return (
            f"📏 Large File Scan Complete, boss!\n"
            f"  📁 Total scanned: {scanned} files\n"
            f"  🐘 Large files found: {len(large_files)} (>= {min_size_mb} MB)\n"
            f"  💾 Total size: {total_str}\n"
            f"{'  ⚠️ ' + str(errors) + ' files access nahi ho payi' if errors else ''}\n\n"
            f"{report_str}\n\n"
            f"💡 Tip: In files ko delete ya move karke space free kar sakte hain.\n"
            f"📍 Directory: {target_dir}"
        )

    except Exception as e:
        logger.error(f"Large file scan error: {e}")
        return f"❌ Large file scan mein error: {str(e)}"


@function_tool
async def batch_rename_files_tool(directory_path: str = None, pattern: str = "file", start_number: int = 1) -> str:
    """
    Batch renames files in a folder. Renames to pattern_001, pattern_002, etc.
    Preserves file extensions. Shows before/after list. Only renames files, not folders.

    Args:
        directory_path: Absolute path to the folder containing files to rename.
        pattern: Naming pattern prefix (default 'file'). Files become pattern_001, pattern_002, etc.
        start_number: Starting number for sequential naming (default 1).
    """
    if not directory_path:
        return "❌ boss, directory path dena zaroori hai (e.g., 'C:\\\\Users\\\\Photos')."

    target_dir = os.path.abspath(directory_path)
    if not os.path.exists(target_dir):
        return f"❌ Path nahi mila: {target_dir}"
    if not os.path.isdir(target_dir):
        return f"❌ Ye directory nahi hai: {target_dir}"

    try:
        logger.info(f"✏️ Batch rename: {target_dir} (pattern: {pattern}, start: {start_number})")

        # Collect files only (not directories), sorted by name for consistent ordering
        files = []
        for fname in sorted(os.listdir(target_dir)):
            fpath = os.path.join(target_dir, fname)
            if os.path.isfile(fpath):
                files.append(fname)

        if not files:
            return f"📂 boss, is folder mein koi file nahi hai: {target_dir}"

        # Determine padding width based on total count
        total = len(files)
        pad_width = max(3, len(str(total + start_number - 1)))

        # Build rename plan
        rename_plan = []
        current_number = start_number
        for fname in files:
            _, ext = os.path.splitext(fname)
            new_name = f"{pattern}_{str(current_number).zfill(pad_width)}{ext}"
            rename_plan.append({
                "old_name": fname,
                "new_name": new_name,
                "old_path": os.path.join(target_dir, fname),
                "new_path": os.path.join(target_dir, new_name)
            })
            current_number += 1

        # Execute renames using temp names first to avoid conflicts
        temp_map = []
        for item in rename_plan:
            temp_name = f"__shell_temp_rename_{os.urandom(8).hex()}_{item['new_name']}"
            temp_path = os.path.join(target_dir, temp_name)
            os.rename(item["old_path"], temp_path)
            temp_map.append((temp_path, item["new_path"]))

        for temp_path, final_path in temp_map:
            os.rename(temp_path, final_path)

        # Build report
        report_lines = []
        for item in rename_plan:
            report_lines.append(f"  📄 {item['old_name']}  ➡️  {item['new_name']}")

        report_str = "\n".join(report_lines)

        return (
            f"✅ Batch Rename Complete, boss!\n"
            f"  📁 Folder: {target_dir}\n"
            f"  ✏️ Pattern: {pattern}_XXX\n"
            f"  🔢 Range: {start_number} → {start_number + total - 1}\n"
            f"  📄 Files renamed: {total}\n\n"
            f"{report_str}\n\n"
            f"💡 Sab files successfully rename ho gayi hain!"
        )

    except Exception as e:
        logger.error(f"Batch rename error: {e}")
        return f"❌ Batch rename mein error: {str(e)}"


__all__ = [
    'organize_folder_tool',
    'find_duplicate_files_tool',
    'find_large_files_tool',
    'batch_rename_files_tool',
]
