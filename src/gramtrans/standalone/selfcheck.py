"""Render `PrerequisiteReport` as one copyable block (FR-036, FR-037).

`contracts/cli-and-selfcheck.md` §2. Deliberately plain: `[PASS]` / `[FAIL]` /
`[UNKNOWN]` prefixes, ASCII only, no colour, no box drawing. It has to survive
being pasted into an email, a chat window, a bug tracker and a Word document
without turning into mojibake — which rules out the pretty version.

One block, not a table of expandable rows, because FR-037 is about the whole
thing being copyable **as a unit**: a user asked for "the self-check" should be
able to select all, copy, and paste something complete. Anything that requires
them to expand three sections first will arrive missing the section that
mattered.

Every `[FAIL]` is followed by a `remedy:` line. That is guaranteed upstream —
`PrerequisiteCheck.__post_init__` refuses to construct a failing check without
one — so this renderer never has to decide what to do about a failure with no
next step.
"""
from __future__ import annotations

from typing import List, Optional

from gramtrans.standalone.prereq import PrerequisiteReport, Verdict, run_checks

__all__ = ["render", "produce", "run_cli"]

_INDENT = "         "


def _wrap(label: str, text: str, width: int = 66) -> List[str]:
    """`label: text`, wrapped and hanging-indented under the label.

    Hand-rolled rather than `textwrap` because the continuation has to align
    under the *value*, not the label, so a multi-line "detected" reads as one
    field rather than as several.
    """
    prefix = f"{_INDENT}{label}: "
    pad = " " * len(prefix)
    words = str(text).split()
    if not words:
        return [prefix.rstrip()]
    lines, current = [], prefix
    for word in words:
        if len(current) + len(word) + 1 > width + len(pad) and current.strip() != prefix.strip():
            lines.append(current.rstrip())
            current = pad + word
        else:
            current += ("" if current.endswith(" ") else " ") + word
    lines.append(current.rstrip())
    return lines


def render(report: PrerequisiteReport) -> str:
    """The block itself."""
    out: List[str] = []
    out.append("GramTrans self-check")
    out.append(f"  Application version : {report.app_version}")
    out.append(f"  Generated           : {report.generated_at}")
    out.append("")

    for check in report.checks:
        out.append(f"[{check.verdict.value}] {check.name}")
        out.extend(_wrap("detected", check.detected))
        out.extend(_wrap("expected", check.expected))
        if check.verdict is Verdict.FAIL:
            out.extend(_wrap("remedy", check.remedy))

    out.append("")
    out.append(f"VERDICT: {report.overall.value} "
               f"({report.passed} of {report.total})")
    if report.log_path:
        out.append(f"Log file: {report.log_path}")
    return "\n".join(out)


def produce(log_path: str = "",
            log_error: Optional[str] = None) -> "tuple[str, PrerequisiteReport]":
    """Run the checks and render them. Returns `(text, report)`.

    Both, because the two routes need different things: the CLI prints the text
    and exits on the verdict, while the Help-menu window shows the text and
    keeps the report for its Copy button.
    """
    report = run_checks(log_path=log_path, log_error=log_error)
    return render(report), report


def run_cli(log_path: str = "", log_error: Optional[str] = None) -> int:
    """`--self-check`: print the block, return `0` on PASS and `1` on FAIL."""
    text, report = produce(log_path=log_path, log_error=log_error)
    print(text)
    return 0 if report.overall is Verdict.PASS else 1
