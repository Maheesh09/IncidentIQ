# tools/log_parser.py
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import TypedDict

# Regex patterns for common log formats
TIMESTAMP_PATTERNS = [
    r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}",   # ISO 8601: 2026-07-03T14:33:12
    r"\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}",        # US format: 07/03/2026 14:33:12
    r"\w{3}\s+\d{1,2} \d{2}:\d{2}:\d{2}",           # Syslog: Jul  3 14:33:12
]

ERROR_LEVEL_PATTERN = re.compile(
    r"\b(ERROR|FATAL|CRITICAL|WARN|WARNING|EXCEPTION|SEVERE)\b",
    re.IGNORECASE,
)

STACK_TRACE_PATTERN = re.compile(
    r"(Traceback \(most recent call last\)|"
    r"at \w+\.\w+\([\w.]+:\d+\)|"
    r"\w+Exception:|"
    r"\w+Error:)",
)

LOG_LEVEL_SEVERITY = {
    "FATAL": 5,
    "CRITICAL": 5,
    "SEVERE": 4,
    "ERROR": 3,
    "EXCEPTION": 3,
    "WARNING": 2,
    "WARN": 2,
}

class ParsedLogLine(TypedDict):
    """Represents a single parsed log line with extracted fields."""
    raw: str
    timestamp: str | None
    level: str | None
    severity: int
    has_stack_trace: bool
    line_number: int


def parse_log_line(line: str, line_number: int) -> ParsedLogLine:
    """Extract structured fields from a single raw log line.

    Args:
        line: Raw log line string.
        line_number: The line's position in the file (1-indexed).

    Returns:
        A ParsedLogLine with extracted timestamp, level, and flags.
    """
    # Extract timestamp
    timestamp = None
    for pattern in TIMESTAMP_PATTERNS:
        match = re.search(pattern, line)
        if match:
            timestamp = match.group(0)
            break

    # Extract error level
    level = None
    level_match = ERROR_LEVEL_PATTERN.search(line)
    if level_match:
        level = level_match.group(0).upper()

    # Check for stack trace indicators
    has_stack_trace = bool(STACK_TRACE_PATTERN.search(line))

    return ParsedLogLine(
        raw=line,
        timestamp=timestamp,
        level=level,
        severity=LOG_LEVEL_SEVERITY.get(level, 0) if level else 0,
        has_stack_trace=has_stack_trace,
        line_number=line_number,
    )

class ErrorFrequency(TypedDict):
    """Error counts before and after the investigation window start."""
    before_window: int
    after_window: int
    spike_ratio: float


def calculate_error_frequency(
    parsed_lines: list[ParsedLogLine],
    window_start: str,
) -> ErrorFrequency:
    """Calculate error frequency before and after the investigation window.

    Compares error rate before and after window_start to detect spikes.

    Args:
        parsed_lines: List of parsed log lines with timestamps and levels.
        window_start: ISO format string marking the start of the window.

    Returns:
        ErrorFrequency with counts and spike ratio.
    """
    before_count = 0
    after_count = 0

    for line in parsed_lines:
        if line["severity"] < 3:
            continue  # Only count ERROR and above

        if line["timestamp"] is None:
            continue  # Skip lines with no timestamp

        # Compare line timestamp against window start
        try:
            line_time = datetime.fromisoformat(line["timestamp"])
            window_time = datetime.fromisoformat(window_start)

            # Make both timezone-aware for comparison
            if line_time.tzinfo is None:
                line_time = line_time.replace(tzinfo=timezone.utc)
            if window_time.tzinfo is None:
                window_time = window_time.replace(tzinfo=timezone.utc)

            if line_time < window_time:
                before_count += 1
            else:
                after_count += 1

        except ValueError:
            continue  # Skip unparseable timestamps

    # Calculate spike ratio — how many times worse after vs before
    spike_ratio = (
        after_count / before_count
        if before_count > 0
        else float(after_count)
    )

    return ErrorFrequency(
        before_window=before_count,
        after_window=after_count,
        spike_ratio=round(spike_ratio, 2),
    )

class LogParserResult(TypedDict):
    """Complete result from parsing a raw log file."""
    total_lines: int
    error_lines: list[ParsedLogLine]
    first_error_timestamp: str | None
    error_frequency: ErrorFrequency | None
    stack_traces: list[str]
    error_patterns: list[str]


def parse_logs(
    raw_logs: str,
    window_start: str | None = None,
) -> LogParserResult:
    """Parse a raw log string and extract all structured signals.

    Runs all deterministic extraction in one pass. The result is
    passed directly to the Log Analysis Agent for LLM reasoning.

    Args:
        raw_logs: Raw log file content as a string.
        window_start: ISO format window start for frequency analysis.
                      If None, frequency analysis is skipped.

    Returns:
        LogParserResult containing all extracted signals.
    """
    lines = raw_logs.splitlines()
    parsed_lines = [
        parse_log_line(line, i + 1)
        for i, line in enumerate(lines)
    ]

    # Filter to error-level lines only
    error_lines = [
        line for line in parsed_lines
        if line["severity"] >= 3
    ]

    # Find the first error timestamp
    first_error_timestamp = None
    for line in error_lines:
        if line["timestamp"] is not None:
            first_error_timestamp = line["timestamp"]
            break

    # Extract unique error patterns (deduplicated)
    seen_patterns: set[str] = set()
    error_patterns: list[str] = []
    for line in error_lines:
        # Use first 120 chars as the pattern signature
        pattern = line["raw"][:120].strip()
        if pattern not in seen_patterns:
            seen_patterns.add(pattern)
            error_patterns.append(pattern)

    # Extract stack trace lines
    stack_traces = [
        line["raw"]
        for line in parsed_lines
        if line["has_stack_trace"]
    ]

    # Calculate frequency if window provided
    error_frequency = None
    if window_start is not None:
        error_frequency = calculate_error_frequency(parsed_lines, window_start)

    return LogParserResult(
        total_lines=len(lines),
        error_lines=error_lines,
        first_error_timestamp=first_error_timestamp,
        error_frequency=error_frequency,
        stack_traces=stack_traces[:20],
        error_patterns=error_patterns[:50],
    )