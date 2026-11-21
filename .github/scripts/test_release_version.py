"""The version of a release follows the API: `python3 -m unittest discover -s .github/scripts`."""

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from release_version import LEKTO, api_version, fits, main, next_version

# The releases on PyPI on 21.11.2026: 0.3.0 speaks the API 0.2, 0.4.0 the API 0.3.
PUBLISHED = ["v0.1.0", "v0.2.0", "v0.2.1", "v0.3.0", "v0.4.0"]


class ReleaseVersionTest(unittest.TestCase):
    def test_reads_the_api_of_this_pylekto(self) -> None:
        self.assertRegex(api_version(LEKTO.read_text(encoding="utf-8")), r"^[0-9]+\.[0-9]+$")

    def test_reads_only_the_assignment(self) -> None:
        source = '"""API_VERSION = "9.9" in a docstring."""\nAPI_VERSION = "0.3"\n'
        self.assertEqual(api_version(source), "0.3")

    def test_fails_without_an_api(self) -> None:
        with self.assertRaises(ValueError):
            api_version('LEKTO_VERSION = "0.17.0"\n')

    def test_counts_on_from_the_highest_release_of_the_api(self) -> None:
        cases = [
            ("0.3", PUBLISHED, "0.3.1"),
            ("0.4", PUBLISHED, "0.4.1"),
            ("0.5", PUBLISHED, "0.5.0"),
            ("0.3", [*PUBLISHED, "v0.3.1"], "0.3.2"),
            ("0.3", ["v0.3.1", "v0.3.10", "v0.3.9"], "0.3.11"),
            ("0.3", ["v0.3.5"], "0.3.6"),
            ("1.0", PUBLISHED, "1.0.0"),
            ("0.3", [], "0.3.0"),
        ]
        for api, tags, expected in cases:
            with self.subTest(api=api, tags=tags):
                self.assertEqual(next_version(api, tags), expected)

    def test_skips_tags_of_no_release(self) -> None:
        tags = ["v0.3.1rc1", "0.3.4", "v0.3", "v0.30.2", "v10.3.7", "v0.3.٣", "latest"]
        self.assertEqual(next_version("0.3", tags), "0.3.0")

    def test_skips_a_tag_in_capitals(self) -> None:
        self.assertEqual(next_version("0.3", ["V0.3.1"]), "0.3.0")

    def test_a_tag_fits_only_its_api(self) -> None:
        cases = [
            ("v0.3.1", True),
            ("V0.3.1", False),
            ("v0.3.0", True),
            ("v0.4.0", False),
            ("v0.30.1", False),
            ("v10.3.1", False),
            ("v0.3", False),
            ("0.3.1", False),
            ("v0.3.1rc1", False),
        ]
        for tag, expected in cases:
            with self.subTest(tag=tag):
                self.assertEqual(fits("0.3", tag), expected)


class MainTest(unittest.TestCase):
    def run_main(self, arguments: list[str], stdin: str = "") -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with (
            mock.patch("sys.stdin", io.StringIO(stdin)),
            redirect_stdout(out),
            redirect_stderr(err),
            mock.patch("release_version.LEKTO") as lekto,
        ):
            lekto.read_text.return_value = 'API_VERSION = "0.3"'
            code = main(arguments)
        return code, out.getvalue(), err.getvalue()

    def test_prints_the_next_version_from_the_tags_on_stdin(self) -> None:
        self.assertEqual(self.run_main([], "\n".join(PUBLISHED) + "\n"), (0, "0.3.1\n", ""))

    def test_passes_a_tag_of_the_api(self) -> None:
        self.assertEqual(self.run_main(["--check", "v0.3.1"]), (0, "", ""))

    def test_stops_a_tag_of_another_api(self) -> None:
        code, out, err = self.run_main(["--check", "v0.4.1"])
        self.assertEqual((code, out), (1, ""))
        self.assertIn("v0.3.<release>", err)

    def test_explains_itself_on_other_arguments(self) -> None:
        for arguments in (["--check"], ["--check", "v0.3.1", "v0.3.2"], ["v0.3.1"]):
            with self.subTest(arguments=arguments):
                code, out, err = self.run_main(arguments)
                self.assertEqual((code, out), (2, ""))
                self.assertIn("--check", err)


if __name__ == "__main__":
    unittest.main()
