from pathlib import Path

# ===== 설정 =====
ROOT = Path(__file__).resolve().parent
OUTDIR = ROOT / "_project_sources"
EXCLUDE_INIT = True
EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "_project_sources",
    ".idea",
    ".pytest_cache",
}
# ================


def is_excluded_dir(path: Path) -> bool:
    return any(part in EXCLUDE_DIRS for part in path.parts)


def get_py_files_in_folder(folder: Path):
    files = []
    for p in sorted(folder.iterdir(), key=lambda x: x.name.lower()):
        if not p.is_file():
            continue
        if p.suffix.lower() != ".py":
            continue
        if EXCLUDE_INIT and p.name == "__init__.py":
            continue
        files.append(p)
    return files


# 🔹 prefix 추가
def folder_to_output_name(folder: Path, root: Path, prefix: str) -> str:
    rel = folder.relative_to(root)
    if not rel.parts:
        return f"{prefix}_root.txt"
    return f"{prefix}_{'_'.join(rel.parts)}.txt"


def build_folder_header(folder: Path, root: Path, py_files: list[Path]) -> str:
    rel = folder.relative_to(root)
    rel_str = "." if str(rel) == "." else rel.as_posix()

    lines = [
        "=" * 80,
        f"FOLDER: {rel_str}",
        f"PYTHON FILE COUNT: {len(py_files)}",
        "=" * 80,
        "",
        "FILES:",
    ]

    for f in py_files:
        lines.append(f"- {f.name}")

    lines.extend(["", ""])
    return "\n".join(lines)


def build_file_block(py_file: Path, root: Path) -> str:
    rel_path = py_file.relative_to(root).as_posix()

    try:
        code = py_file.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        code = py_file.read_text(encoding="utf-8", errors="replace")

    lines = [
        "#" * 80,
        f"FILE: {py_file.name}",
        f"PATH: {rel_path}",
        "#" * 80,
        "",
        code.rstrip(),
        "",
        "",
    ]
    return "\n".join(lines)


def export_sources(prefix: str):
    OUTDIR.mkdir(exist_ok=True)

    exported_count = 0

    for folder in sorted(ROOT.rglob("*")):
        if not folder.is_dir():
            continue
        if folder == OUTDIR:
            continue
        if is_excluded_dir(folder):
            continue

        py_files = get_py_files_in_folder(folder)
        if not py_files:
            continue

        # 🔹 prefix 전달
        out_name = folder_to_output_name(folder, ROOT, prefix)
        out_path = OUTDIR / out_name

        content_parts = [
            build_folder_header(folder, ROOT, py_files)
        ]

        for py_file in py_files:
            content_parts.append(build_file_block(py_file, ROOT))

        out_text = "".join(content_parts)

        out_path.write_text(out_text, encoding="utf-8", newline="\n")
        exported_count += 1
        print(f"[OK] {out_path.relative_to(ROOT)}")

    print()
    print(f"완료: {exported_count}개 txt 생성")
    print(f"출력 폴더: {OUTDIR}")


if __name__ == "__main__":
    # 🔹 실행 시 입력 받기
    prefix = input("프로젝트명을 입력하시오: ").strip()

    if not prefix:
        print("프로젝트명이 비어있습니다. 종료합니다.")
    else:
        export_sources(prefix)