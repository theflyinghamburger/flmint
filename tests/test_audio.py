from __future__ import annotations

import unittest

import helpers

from flmint.audio import (
    PIPEWIRE_PIPEASIO_MIN,
    parse_docker_version,
    parse_flatpak_version,
    parse_nvcc_version,
    parse_pipewire_version,
    parse_wine_version,
    parse_wpctl_audio_devices,
)


class AudioTest(unittest.TestCase):
    def test_pipeasio_minimum_gate(self) -> None:
        self.assertEqual(PIPEWIRE_PIPEASIO_MIN, (1, 4, 2))

    def test_parse_pipewire_version(self) -> None:
        self.assertEqual(parse_pipewire_version(helpers.fixture_text("pipewire-168.txt")), (1, 6, 8))
        self.assertEqual(parse_pipewire_version("Compiled with libpipewire 1.4.2-1ubuntu2"), (1, 4, 2))
        self.assertEqual(parse_pipewire_version("pw 1.0.0"), (1, 0, 0))
        self.assertEqual(parse_pipewire_version("pw 1.2"), (1, 2, 0))
        self.assertIsNone(parse_pipewire_version(""))
        self.assertIsNone(parse_pipewire_version("no version"))

    def test_parse_other_versions(self) -> None:
        self.assertEqual(parse_wine_version("wine-9.0\n"), "9.0")
        self.assertEqual(parse_wine_version("wine-10.0-rc1"), "10.0")
        self.assertEqual(parse_nvcc_version(helpers.fixture_text("nvcc.txt")), "12.4")
        self.assertEqual(parse_flatpak_version("Flatpak 1.18.4"), "1.18.4")
        self.assertEqual(parse_docker_version("Docker version 27.3.1, build x"), "27.3.1")

    def test_parse_wpctl_audio_devices(self) -> None:
        devices = parse_wpctl_audio_devices(helpers.fixture_text("wpctl-status.txt"))
        names = [d["name"] for d in devices]
        self.assertEqual(
            names,
            [
                "Brio 100",
                "Scarlett Solo USB",
                "GA102 High Definition Audio Controller",
                "Starship/Matisse HD Audio Controller",
            ],
        )
        self.assertTrue(all(d["api"] == "alsa" for d in devices))


if __name__ == "__main__":
    unittest.main()
