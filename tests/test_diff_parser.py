from agentops.core import ChangeKind
from agentops.parsers.diff import DiffParser


def test_diff_parser_counts_modified_file_lines() -> None:
    summary = DiffParser().parse(
        "\n".join(
            [
                "diff --git a/src/app.py b/src/app.py",
                "--- a/src/app.py",
                "+++ b/src/app.py",
                "@@ -1,2 +1,3 @@",
                " old",
                "-before",
                "+after",
                "+extra",
            ]
        )
    )

    assert summary.additions == 2
    assert summary.deletions == 1
    assert len(summary.files) == 1
    assert summary.files[0].path == "src/app.py"
    assert summary.files[0].change_kind is ChangeKind.MODIFIED
    assert summary.files[0].additions == 2
    assert summary.files[0].deletions == 1
    assert summary.files[0].previous_path is None


def test_diff_parser_marks_new_file_as_added() -> None:
    summary = DiffParser().parse(
        "\n".join(
            [
                "diff --git a/src/new.py b/src/new.py",
                "new file mode 100644",
                "--- /dev/null",
                "+++ b/src/new.py",
                "@@ -0,0 +1 @@",
                "+created",
            ]
        )
    )

    assert summary.files[0].path == "src/new.py"
    assert summary.files[0].change_kind is ChangeKind.ADDED
    assert summary.files[0].additions == 1
    assert summary.files[0].deletions == 0


def test_diff_parser_marks_deleted_file_as_deleted() -> None:
    summary = DiffParser().parse(
        "\n".join(
            [
                "diff --git a/src/old.py b/src/old.py",
                "deleted file mode 100644",
                "--- a/src/old.py",
                "+++ /dev/null",
                "@@ -1 +0,0 @@",
                "-removed",
            ]
        )
    )

    assert summary.files[0].path == "src/old.py"
    assert summary.files[0].change_kind is ChangeKind.DELETED
    assert summary.files[0].additions == 0
    assert summary.files[0].deletions == 1


def test_diff_parser_marks_renamed_file_and_previous_path() -> None:
    summary = DiffParser().parse(
        "\n".join(
            [
                "diff --git a/src/before.py b/src/after.py",
                "similarity index 100%",
                "rename from src/before.py",
                "rename to src/after.py",
            ]
        )
    )

    assert summary.files[0].path == "src/after.py"
    assert summary.files[0].previous_path == "src/before.py"
    assert summary.files[0].change_kind is ChangeKind.RENAMED
    assert summary.files[0].additions == 0
    assert summary.files[0].deletions == 0


def test_diff_parser_keeps_binary_metadata_without_line_counts() -> None:
    summary = DiffParser().parse(
        "\n".join(
            [
                "diff --git a/assets/logo.png b/assets/logo.png",
                "index 1234567..89abcde 100644",
                "Binary files a/assets/logo.png and b/assets/logo.png differ",
            ]
        )
    )

    assert summary.additions == 0
    assert summary.deletions == 0
    assert summary.files[0].path == "assets/logo.png"
    assert summary.files[0].change_kind is ChangeKind.MODIFIED


def test_diff_parser_returns_empty_summary_for_empty_diff() -> None:
    summary = DiffParser().parse("")

    assert summary.files == ()
    assert summary.additions == 0
    assert summary.deletions == 0


def test_diff_parser_ignores_headers_context_and_no_newline_marker() -> None:
    summary = DiffParser().parse(
        "\n".join(
            [
                "diff --git a/src/app.py b/src/app.py",
                "--- a/src/app.py",
                "+++ b/src/app.py",
                "@@ -1,2 +1,2 @@",
                " context",
                "-before",
                r"\ No newline at end of file",
                "+after",
                r"\ No newline at end of file",
            ]
        )
    )

    assert summary.additions == 1
    assert summary.deletions == 1


def test_diff_parser_preserves_file_source_order() -> None:
    summary = DiffParser().parse(
        "\n".join(
            [
                "diff --git a/src/z.py b/src/z.py",
                "--- a/src/z.py",
                "+++ b/src/z.py",
                "@@ -1 +1 @@",
                "-old",
                "+new",
                "diff --git a/src/a.py b/src/a.py",
                "new file mode 100644",
                "--- /dev/null",
                "+++ b/src/a.py",
                "@@ -0,0 +1 @@",
                "+created",
            ]
        )
    )

    assert [file.path for file in summary.files] == ["src/z.py", "src/a.py"]


def test_diff_parser_preserves_spaces_in_binary_file_path() -> None:
    summary = DiffParser().parse(
        "\n".join(
            [
                "diff --git a/assets/product logo.png b/assets/product logo.png",
                "index 1234567..89abcde 100644",
                "Binary files a/assets/product logo.png and b/assets/product logo.png differ",
            ]
        )
    )

    assert summary.files[0].path == "assets/product logo.png"


def test_diff_parser_decodes_quoted_utf8_octal_file_path() -> None:
    summary = DiffParser().parse(
        "\n".join(
            [
                r'diff --git "a/\346\265\213\350\257\225.png" "b/\346\265\213\350\257\225.png"',
                r'Binary files "a/\346\265\213\350\257\225.png" and "b/\346\265\213\350\257\225.png" differ',
            ]
        )
    )

    assert summary.files[0].path == "测试.png"


def test_diff_parser_preserves_nested_b_directory_in_binary_file_path() -> None:
    summary = DiffParser().parse(
        "\n".join(
            [
                "diff --git a/foo b/product logo.png b/foo b/product logo.png",
                "index 1234567..89abcde 100644",
                "Binary files a/foo b/product logo.png and b/foo b/product logo.png differ",
            ]
        )
    )

    assert summary.files[0].path == "foo b/product logo.png"
