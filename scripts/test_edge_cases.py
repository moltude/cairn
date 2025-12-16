#!/usr/bin/env python3
"""Test edge case conversions and document results.

This script systematically tests all edge case fixtures by:
1. Attempting to convert them
2. Validating the output
3. Recording pass/fail status
4. Generating a comprehensive report
"""

import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import time


# Paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures" / "edge_cases"
OUTPUT_DIR = PROJECT_ROOT / "tests" / "output" / "edge_cases"
VALIDATOR_SCRIPT = SCRIPT_DIR / "validate_output_integrity.py"

# Ensure output directory exists
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class TestCase:
    """Represents a test case."""

    def __init__(self, name: str, input_file: Path, description: str):
        self.name = name
        self.input_file = input_file
        self.description = description
        self.status = "PENDING"
        self.error_message: Optional[str] = None
        self.output_file: Optional[Path] = None
        self.conversion_time: Optional[float] = None

    def __str__(self):
        status_emoji = {
            "PASSED": "✅",
            "FAILED": "❌",
            "WARNING": "⚠️ ",
            "SKIPPED": "⏭️ ",
            "PENDING": "⏳"
        }
        emoji = status_emoji.get(self.status, "•")
        result = f"{emoji} {self.name}: {self.status}"
        if self.error_message:
            result += f"\n   └─ {self.error_message}"
        if self.conversion_time:
            result += f"\n   └─ Time: {self.conversion_time:.3f}s"
        return result


def run_conversion(input_file: Path, output_file: Path,
                   from_format: str, to_format: str) -> Tuple[bool, str, float]:
    """
    Run a conversion using Cairn CLI.

    Returns:
        (success, error_message, execution_time)
    """
    # Use uv run to ensure dependencies are available
    cmd = [
        "uv", "run", "cairn",
        "convert",
        str(input_file),
        "--from", from_format,
        "--to", to_format,
        "--output", str(output_file),
        "--yes"  # Skip interactive prompts
    ]

    start_time = time.time()

    try:
        result = subprocess.run(
            cmd,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=60  # 60 second timeout
        )

        elapsed = time.time() - start_time

        if result.returncode == 0:
            return True, "", elapsed
        else:
            error = result.stderr or result.stdout or "Unknown error"
            return False, error.strip()[:200], elapsed  # Limit error message length

    except subprocess.TimeoutExpired:
        elapsed = time.time() - start_time
        return False, "Conversion timed out (>60s)", elapsed
    except Exception as e:
        elapsed = time.time() - start_time
        return False, str(e), elapsed


def validate_output(output_file: Path) -> Tuple[bool, str]:
    """
    Validate an output file using the validation script.

    Returns:
        (success, error_message)
    """
    if not output_file.exists():
        return False, "Output file/directory was not created"

    # If it's a directory (OnX output), check if it has files
    if output_file.is_dir():
        files = list(output_file.glob("*.gpx")) + list(output_file.glob("*.kml"))
        if not files:
            return False, "Output directory is empty"
        # Validate the first GPX file found
        for f in files:
            if f.suffix.lower() == ".gpx":
                output_file = f
                break
        else:
            return True, ""  # No GPX to validate, assume success

    cmd = [sys.executable, str(VALIDATOR_SCRIPT), str(output_file)]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )

        # Exit code 0 means validation passed
        if result.returncode == 0:
            return True, ""
        else:
            # Extract first error from output
            lines = result.stdout.split('\n')
            for line in lines:
                if '❌' in line or 'ERROR' in line:
                    return False, line.strip()[:200]
            return False, "Validation failed"

    except subprocess.TimeoutExpired:
        return False, "Validation timed out"
    except Exception as e:
        return False, str(e)


def run_test(test: TestCase, from_format: str, to_format: str) -> None:
    """Run a single test case."""

    # Determine output filename
    # For OnX output, it creates a directory, so we'll check for the directory
    if to_format == "OnX":
        output_file = OUTPUT_DIR / f"{test.input_file.stem}_onx_output"
    else:
        output_ext = ".json" if to_format == "caltopo_geojson" else ".out"
        output_file = OUTPUT_DIR / f"{test.input_file.stem}_to_{to_format}{output_ext}"

    test.output_file = output_file

    # Run conversion
    success, error, elapsed = run_conversion(
        test.input_file,
        output_file,
        from_format,
        to_format
    )

    test.conversion_time = elapsed

    if not success:
        test.status = "FAILED"
        test.error_message = f"Conversion failed: {error}"
        return

    # Validate output
    valid, error = validate_output(output_file)

    if not valid:
        test.status = "WARNING"
        test.error_message = f"Output validation issues: {error}"
    else:
        test.status = "PASSED"


def generate_test_cases() -> List[Tuple[TestCase, str, str]]:
    """
    Generate list of test cases.

    Returns:
        List of (test_case, from_format, to_format) tuples
    """
    tests = []

    # GPX to CalTopo conversions
    gpx_files = [
        ("poles", "poles.gpx", "Waypoints at North and South Poles"),
        ("dateline", "dateline.gpx", "Waypoints at International Date Line"),
        ("prime_meridian", "prime_meridian.gpx", "Waypoint at Prime Meridian"),
        ("equator", "equator.gpx", "Waypoint at Equator"),
        ("elevations", "elevations.gpx", "Extreme elevation values"),
        ("unicode", "unicode.gpx", "Unicode characters and emoji"),
        ("xml_chars", "xml_chars.gpx", "XML special characters"),
        ("quotes", "quotes.gpx", "Various quote types"),
        ("long_name", "long_name.gpx", "Very long name (1000+ chars)"),
        ("empty_names", "empty_names.gpx", "Empty/missing names"),
        ("empty", "empty.gpx", "Empty GPX file"),
        ("single_waypoint", "single_waypoint.gpx", "Single waypoint"),
        ("single_point_track", "single_point_track.gpx", "Track with 1 point"),
        ("colors", "colors.gpx", "Various color specifications"),
        ("duplicates", "duplicates.gpx", "Duplicate waypoints"),
    ]

    for name, filename, desc in gpx_files:
        filepath = FIXTURES_DIR / filename
        if filepath.exists():
            test = TestCase(f"GPX→CalTopo: {name}", filepath, desc)
            tests.append((test, "OnX_gpx", "caltopo_geojson"))

    # GeoJSON to OnX conversions
    json_files = [
        ("empty", "empty.json", "Empty GeoJSON"),
        ("single_marker", "single_marker.json", "Single marker"),
        ("mixed_features", "mixed_features.json", "All feature types"),
    ]

    for name, filename, desc in json_files:
        filepath = FIXTURES_DIR / filename
        if filepath.exists():
            test = TestCase(f"CalTopo→OnX: {name}", filepath, desc)
            tests.append((test, "caltopo_geojson", "OnX"))

    # Stress tests - GPX files
    stress_gpx = [
        ("many_waypoints_1000", "many_waypoints_1000.gpx", "1000 waypoints"),
        ("many_waypoints_10000", "many_waypoints_10000.gpx", "10,000 waypoints"),
        ("long_track_1000", "long_track_1000.gpx", "Track with 1000 points"),
        ("long_track_10000", "long_track_10000.gpx", "Track with 10,000 points"),
    ]

    for name, filename, desc in stress_gpx:
        filepath = FIXTURES_DIR / filename
        if filepath.exists():
            test = TestCase(f"Stress: {name}", filepath, desc)
            tests.append((test, "OnX_gpx", "caltopo_geojson"))

    # Malformed files (expect these to fail gracefully)
    malformed = [
        ("malformed_gpx", "malformed.gpx", "Malformed XML"),
        ("malformed_json", "malformed.json", "Malformed JSON"),
    ]

    for name, filename, desc in malformed:
        filepath = FIXTURES_DIR / filename
        if filepath.exists():
            test = TestCase(f"Malformed: {name}", filepath, desc)
            # Try to convert, expect graceful failure
            tests.append((test, "OnX_gpx" if filename.endswith('.gpx') else "caltopo_geojson",
                         "caltopo_geojson" if filename.endswith('.gpx') else "OnX"))

    return tests


def print_summary(test_results: List[TestCase]) -> None:
    """Print test summary."""

    passed = sum(1 for t in test_results if t.status == "PASSED")
    failed = sum(1 for t in test_results if t.status == "FAILED")
    warnings = sum(1 for t in test_results if t.status == "WARNING")
    skipped = sum(1 for t in test_results if t.status == "SKIPPED")
    total = len(test_results)

    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"\nTotal Tests: {total}")
    print(f"  ✅ Passed:   {passed}")
    print(f"  ❌ Failed:   {failed}")
    print(f"  ⚠️  Warnings: {warnings}")
    print(f"  ⏭️  Skipped:  {skipped}")

    # Calculate success rate
    success_rate = (passed / total * 100) if total > 0 else 0
    print(f"\nSuccess Rate: {success_rate:.1f}%")

    # Show timing stats
    times = [t.conversion_time for t in test_results if t.conversion_time is not None]
    if times:
        print(f"\nConversion Times:")
        print(f"  Average: {sum(times)/len(times):.3f}s")
        print(f"  Min:     {min(times):.3f}s")
        print(f"  Max:     {max(times):.3f}s")
        print(f"  Total:   {sum(times):.3f}s")

    print("\n" + "="*80)

    # Overall status
    if failed == 0:
        if warnings > 0:
            print("⚠️  PASSED WITH WARNINGS")
        else:
            print("✅ ALL TESTS PASSED!")
    else:
        print("❌ SOME TESTS FAILED")

    print("="*80)


def save_report(test_results: List[TestCase], output_path: Path) -> None:
    """Save detailed test report to file."""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("# Edge Case Test Results\n\n")
        f.write(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        # Summary
        passed = sum(1 for t in test_results if t.status == "PASSED")
        failed = sum(1 for t in test_results if t.status == "FAILED")
        warnings = sum(1 for t in test_results if t.status == "WARNING")

        f.write("## Summary\n\n")
        f.write(f"- Total Tests: {len(test_results)}\n")
        f.write(f"- Passed: {passed}\n")
        f.write(f"- Failed: {failed}\n")
        f.write(f"- Warnings: {warnings}\n\n")

        # Group by status
        for status in ["FAILED", "WARNING", "PASSED"]:
            tests = [t for t in test_results if t.status == status]
            if tests:
                f.write(f"## {status} ({len(tests)})\n\n")
                for test in tests:
                    f.write(f"### {test.name}\n\n")
                    f.write(f"- **Description:** {test.description}\n")
                    f.write(f"- **Input:** `{test.input_file.name}`\n")
                    if test.output_file:
                        f.write(f"- **Output:** `{test.output_file.name}`\n")
                    if test.conversion_time:
                        f.write(f"- **Time:** {test.conversion_time:.3f}s\n")
                    if test.error_message:
                        f.write(f"- **Error:** {test.error_message}\n")
                    f.write("\n")

    print(f"\n📄 Detailed report saved to: {output_path}")


def main():
    """Main test runner."""

    print("="*80)
    print("CAIRN EDGE CASE TESTING")
    print("="*80)
    print(f"\nFixtures directory: {FIXTURES_DIR}")
    print(f"Output directory:   {OUTPUT_DIR}")
    print(f"Validator script:   {VALIDATOR_SCRIPT}")

    # Generate test cases
    test_specs = generate_test_cases()
    print(f"\nGenerated {len(test_specs)} test case(s)\n")

    if not test_specs:
        print("❌ No test cases found!")
        sys.exit(1)

    # Run tests
    print("Running tests...")
    print("-"*80)

    test_results = []

    for i, (test, from_fmt, to_fmt) in enumerate(test_specs, 1):
        print(f"\n[{i}/{len(test_specs)}] {test.name}")
        print(f"  {test.description}")
        print(f"  {from_fmt} → {to_fmt}")
        print(f"  Input: {test.input_file.name}")

        run_test(test, from_fmt, to_fmt)
        test_results.append(test)

        # Print immediate result
        status_emoji = {"PASSED": "✅", "FAILED": "❌", "WARNING": "⚠️ "}.get(test.status, "•")
        print(f"  {status_emoji} {test.status}", end="")
        if test.conversion_time:
            print(f" ({test.conversion_time:.3f}s)", end="")
        print()

        if test.error_message:
            # Print first line of error
            first_line = test.error_message.split('\n')[0]
            print(f"     └─ {first_line}")

    print("\n" + "-"*80)

    # Print summary
    print_summary(test_results)

    # Save detailed report
    report_path = PROJECT_ROOT / "tests" / "edge_case_test_report.md"
    save_report(test_results, report_path)

    # Exit with appropriate code
    failed = sum(1 for t in test_results if t.status == "FAILED")
    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
