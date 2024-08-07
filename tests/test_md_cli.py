"""Test md commandline interface."""

from pathlib import Path

from ase import Atoms
from ase.io import read
import numpy as np
import pytest
from typer.testing import CliRunner
import yaml

from janus_core.cli.janus import app
from tests.utils import assert_log_contains

DATA_PATH = Path(__file__).parent / "data"

runner = CliRunner()

# Many pylint now warnings raised due to similar log/summary flags
# These depend on tmp_path, so not easily refactorisable
# pylint: disable=duplicate-code


def test_md_help():
    """Test calling `janus md --help`."""
    result = runner.invoke(app, ["md", "--help"])
    assert result.exit_code == 0
    assert "Usage: janus md [OPTIONS]" in result.stdout


test_data = [
    ("nvt"),
    ("nve"),
    ("npt"),
    ("nvt-nh"),
    ("nph"),
]


@pytest.mark.parametrize("ensemble", test_data)
def test_md(ensemble, tmp_path):
    """Test all MD simulations are able to run."""
    file_prefix = tmp_path / f"{ensemble}-T300"
    traj_path = tmp_path / f"{ensemble}-T300-traj.extxyz"
    log_path = tmp_path / "test.log"
    summary_path = tmp_path / "summary.yml"

    result = runner.invoke(
        app,
        [
            "md",
            "--ensemble",
            ensemble,
            "--struct",
            DATA_PATH / "NaCl.cif",
            "--file-prefix",
            file_prefix,
            "--steps",
            2,
            "--traj-every",
            1,
            "--log",
            log_path,
            "--summary",
            summary_path,
        ],
    )

    assert result.exit_code == 0

    # Check at least one image has been saved in trajectory
    atoms = read(traj_path)
    assert isinstance(atoms, Atoms)


def test_log(tmp_path):
    """Test log correctly written for MD."""
    file_prefix = tmp_path / "nvt-T300"
    log_path = tmp_path / "test.log"
    summary_path = tmp_path / "summary.yml"

    result = runner.invoke(
        app,
        [
            "md",
            "--ensemble",
            "nvt",
            "--struct",
            DATA_PATH / "NaCl.cif",
            "--file-prefix",
            file_prefix,
            "--steps",
            20,
            "--stats-every",
            1,
            "--log",
            log_path,
            "--summary",
            summary_path,
        ],
    )
    assert result.exit_code == 0

    assert_log_contains(log_path, includes=["Starting molecular dynamics simulation"])

    with open(tmp_path / "nvt-T300-stats.dat", encoding="utf8") as stats_file:
        lines = stats_file.readlines()
        # Includes step 0
        assert len(lines) == 22

        # Test constant volume
        assert lines[0].split(" | ")[8] == "Volume [A^3]"
        init_volume = float(lines[1].split()[8])
        final_volume = float(lines[-1].split()[8])
        assert init_volume == 179.406144
        assert init_volume == pytest.approx(final_volume)

        # Test constant temperature
        assert lines[0].split(" | ")[16] == "Target T [K]\n"
        init_temp = float(lines[1].split()[16])
        final_temp = float(lines[-1].split()[16])
        assert init_temp == 300.0
        assert final_temp == pytest.approx(final_temp)


def test_seed(tmp_path):
    """Test seed enables reproducable results for NVT."""
    file_prefix = tmp_path / "nvt-T300"
    stats_path = tmp_path / "nvt-T300-stats.dat"
    log_path = tmp_path / "test.log"
    summary_path = tmp_path / "summary.yml"

    result_1 = runner.invoke(
        app,
        [
            "md",
            "--ensemble",
            "nvt",
            "--struct",
            DATA_PATH / "NaCl.cif",
            "--file-prefix",
            file_prefix,
            "--steps",
            20,
            "--stats-every",
            20,
            "--seed",
            42,
            "--log",
            log_path,
            "--summary",
            summary_path,
        ],
    )
    assert result_1.exit_code == 0

    with open(stats_path, encoding="utf8") as stats_file:
        lines = stats_file.readlines()
        # Includes step 0
        assert len(lines) == 3

        final_stats_1 = lines[2].split()

    stats_path.unlink()

    result_2 = runner.invoke(
        app,
        [
            "md",
            "--ensemble",
            "nvt",
            "--struct",
            DATA_PATH / "NaCl.cif",
            "--file-prefix",
            file_prefix,
            "--steps",
            20,
            "--stats-every",
            20,
            "--seed",
            42,
            "--log",
            log_path,
            "--summary",
            summary_path,
        ],
    )
    assert result_2.exit_code == 0

    with open(stats_path, encoding="utf8") as stats_file:
        lines = stats_file.readlines()
        # Includes step 0
        assert len(lines) == 3

        final_stats_2 = lines[2].split()

    for i, (stats_1, stats_2) in enumerate(zip(final_stats_1, final_stats_2)):
        if i != 1:
            assert stats_1 == stats_2


def test_summary(tmp_path):
    """Test summary file can be read correctly."""
    file_prefix = tmp_path / "nvt-T300"
    log_path = tmp_path / "test.log"
    summary_path = tmp_path / "summary.yml"

    result = runner.invoke(
        app,
        [
            "md",
            "--ensemble",
            "nve",
            "--struct",
            DATA_PATH / "NaCl.cif",
            "--file-prefix",
            file_prefix,
            "--steps",
            2,
            "--traj-every",
            1,
            "--log",
            log_path,
            "--summary",
            summary_path,
        ],
    )

    assert result.exit_code == 0

    # Read summary
    with open(summary_path, encoding="utf8") as file:
        summary = yaml.safe_load(file)

    assert "command" in summary
    assert "janus md" in summary["command"]
    assert "start_time" in summary
    assert "inputs" in summary
    assert "end_time" in summary

    assert "ensemble" in summary["inputs"]
    assert "struct" in summary["inputs"]
    assert "n_atoms" in summary["inputs"]["struct"]


def test_config(tmp_path):
    """Test passing a config file with ."""
    file_prefix = tmp_path / "nvt-T300"
    log_path = tmp_path / "test.log"
    summary_path = tmp_path / "summary.yml"

    result = runner.invoke(
        app,
        [
            "md",
            "--ensemble",
            "nve",
            "--struct",
            DATA_PATH / "NaCl.cif",
            "--file-prefix",
            file_prefix,
            "--steps",
            2,
            "--minimize",
            "--log",
            log_path,
            "--summary",
            summary_path,
            "--config",
            DATA_PATH / "md_config.yml",
        ],
    )
    assert result.exit_code == 0

    # Read md summary file
    with open(summary_path, encoding="utf8") as file:
        md_summary = yaml.safe_load(file)

    # Check temperature is passed correctly
    assert md_summary["inputs"]["temp"] == 200
    # Check explicit option overwrites config
    assert md_summary["inputs"]["ensemble"] == "nve"
    # Check nested dictionary
    assert (
        md_summary["inputs"]["minimize_kwargs"]["filter_kwargs"]["hydrostatic_strain"]
        is True
    )

    # Check hydrostatic strain passed correctly
    assert_log_contains(log_path, includes=["hydrostatic_strain: True"])


def test_heating(tmp_path):
    """Test heating before MD."""
    file_prefix = tmp_path / "nvt-T300"
    log_path = tmp_path / "test.log"
    summary_path = tmp_path / "summary.yml"

    result = runner.invoke(
        app,
        [
            "md",
            "--ensemble",
            "nvt",
            "--struct",
            DATA_PATH / "NaCl.cif",
            "--file-prefix",
            file_prefix,
            "--stats-every",
            1,
            "--steps",
            5,
            "--temp-start",
            10,
            "--temp-end",
            20,
            "--temp-step",
            50,
            "--temp-time",
            0.05,
            "--log",
            log_path,
            "--summary",
            summary_path,
        ],
    )
    assert result.exit_code == 0


def test_invalid_config():
    """Test passing a config file with an invalid option name."""
    result = runner.invoke(
        app,
        [
            "md",
            "--struct",
            DATA_PATH / "NaCl.cif",
            "--ensemble",
            "nvt",
            "--config",
            DATA_PATH / "invalid.yml",
        ],
    )
    assert result.exit_code == 1
    assert isinstance(result.exception, ValueError)


def test_struct_name(tmp_path):
    """Test specifying the structure name."""
    struct_name = "EXAMPLE"
    struct_path = tmp_path / struct_name
    stats_path = tmp_path / f"{struct_name}-nvt-T10.0-stats.dat"
    traj_path = tmp_path / f"{struct_name}-nvt-T10.0-traj.extxyz"
    final_path = tmp_path / f"{struct_name}-nvt-T10.0-final.extxyz"
    log_path = tmp_path / "test.log"
    summary_path = tmp_path / "summary.yml"
    result = runner.invoke(
        app,
        [
            "md",
            "--struct",
            DATA_PATH / "NaCl.cif",
            "--ensemble",
            "nvt",
            "--steps",
            "2",
            "--temp",
            "10",
            "--struct-name",
            str(struct_path),
            "--log",
            log_path,
            "--summary",
            summary_path,
        ],
    )
    assert result.exit_code == 0
    assert stats_path.exists()
    assert traj_path.exists()
    assert final_path.exists()


def test_ensemble_kwargs(tmp_path):
    """Test passing ensemble-kwargs to NPT."""
    struct_path = DATA_PATH / "NaCl.cif"
    file_prefix = tmp_path / "md"
    log_path = tmp_path / "md.log"
    summary_path = tmp_path / "summary.yml"
    final_path = tmp_path / "md-final.extxyz"
    stats_path = tmp_path / "md-stats.dat"

    ensemble_kwargs = "{'mask' : (0, 1, 0)}"

    result = runner.invoke(
        app,
        [
            "md",
            "--ensemble",
            "npt",
            "--struct",
            struct_path,
            "--file-prefix",
            file_prefix,
            "--steps",
            2,
            "--ensemble-kwargs",
            ensemble_kwargs,
            "--stats-every",
            1,
            "--log",
            log_path,
            "--summary",
            summary_path,
        ],
    )

    assert result.exit_code == 0
    assert final_path.exists()
    assert stats_path.exists()

    with open(stats_path, encoding="utf8") as stats_file:
        lines = stats_file.readlines()
        # Includes step 0
        assert len(lines) == 3

    init_atoms = read(struct_path)
    final_atoms = read(final_path)

    assert np.array_equal(init_atoms.cell[0], final_atoms.cell[0])
    assert not np.array_equal(init_atoms.cell[1], final_atoms.cell[1])
    assert np.array_equal(init_atoms.cell[2], final_atoms.cell[2])


def test_invalid_ensemble_kwargs(tmp_path):
    """Test passing invalid key to ensemble-kwargs."""
    file_prefix = tmp_path / "npt-T300"
    log_path = tmp_path / "md.log"
    summary_path = tmp_path / "summary.yml"

    # Not an option for NVT
    ensemble_kwargs = "{'mask': (0, 1, 0)}"

    result = runner.invoke(
        app,
        [
            "md",
            "--ensemble",
            "nvt",
            "--struct",
            DATA_PATH / "NaCl.cif",
            "--file-prefix",
            file_prefix,
            "--steps",
            2,
            "--ensemble-kwargs",
            ensemble_kwargs,
            "--traj-every",
            1,
            "--log",
            log_path,
            "--summary",
            summary_path,
        ],
    )

    assert result.exit_code == 1
    assert isinstance(result.exception, TypeError)


def test_final_name(tmp_path):
    """Test specifying the final file name."""
    file_prefix = tmp_path / "npt"
    stats_path = tmp_path / "npt-stats.dat"
    traj_path = tmp_path / "npt-traj.extxyz"
    final_path = tmp_path / "example.extxyz"
    log_path = tmp_path / "test.log"
    summary_path = tmp_path / "summary.yml"
    result = runner.invoke(
        app,
        [
            "md",
            "--struct",
            DATA_PATH / "NaCl.cif",
            "--ensemble",
            "nvt",
            "--steps",
            "2",
            "--stats-every",
            1,
            "--traj-every",
            1,
            "--file-prefix",
            file_prefix,
            "--final-file",
            final_path,
            "--log",
            log_path,
            "--summary",
            summary_path,
        ],
    )
    assert result.exit_code == 0
    assert traj_path.exists()
    assert stats_path.exists()
    assert final_path.exists()


def test_write_kwargs(tmp_path):
    """Test passing write-kwargs."""
    struct_path = DATA_PATH / "NaCl.cif"
    file_prefix = tmp_path / "md"
    log_path = tmp_path / "md.log"
    summary_path = tmp_path / "summary.yml"
    final_path = tmp_path / "md-final.extxyz"
    traj_path = tmp_path / "md-traj.extxyz"
    write_kwargs = (
        "{'invalidate_calc': False, 'columns': ['symbols', 'positions', 'masses']}"
    )

    result = runner.invoke(
        app,
        [
            "md",
            "--ensemble",
            "npt",
            "--struct",
            struct_path,
            "--file-prefix",
            file_prefix,
            "--steps",
            2,
            "--write-kwargs",
            write_kwargs,
            "--traj-every",
            1,
            "--log",
            log_path,
            "--summary",
            summary_path,
        ],
    )

    assert result.exit_code == 0
    assert final_path.exists()
    assert traj_path.exists()
    final_atoms = read(final_path)
    traj = read(traj_path, index=":")

    # Check columns has been set
    assert not final_atoms.has("momenta")
    assert not traj[0].has("momenta")

    # Check calculated results have been saved
    assert "energy" in final_atoms.calc.results
    assert "energy" in traj[0].calc.results

    # Check labelled info has been set
    assert "mace_mp_energy" in final_atoms.info
    assert "mace_mp_energy" in traj[0].info


@pytest.mark.parametrize("read_kwargs", ["{'index': 1}", "{}"])
def test_valid_traj_input(read_kwargs, tmp_path):
    """Test valid trajectory input structure handled."""
    file_prefix = tmp_path / "traj"
    final_path = tmp_path / "traj-final.extxyz"
    log_path = tmp_path / "test.log"
    summary_path = tmp_path / "summary.yml"

    result = runner.invoke(
        app,
        [
            "md",
            "--ensemble",
            "nvt",
            "--struct",
            DATA_PATH / "benzene-traj.xyz",
            "--file-prefix",
            file_prefix,
            "--steps",
            2,
            "--read-kwargs",
            read_kwargs,
            "--log",
            log_path,
            "--summary",
            summary_path,
        ],
    )
    assert result.exit_code == 0
    atoms = read(final_path)
    assert isinstance(atoms, Atoms)


def test_invalid_traj_input(tmp_path):
    """Test invalid trajectory input structure handled."""
    file_prefix = tmp_path / "traj"
    log_path = tmp_path / "test.log"
    summary_path = tmp_path / "summary.yml"

    result = runner.invoke(
        app,
        [
            "md",
            "--ensemble",
            "nvt",
            "--struct",
            DATA_PATH / "benzene-traj.xyz",
            "--file-prefix",
            file_prefix,
            "--steps",
            2,
            "--read-kwargs",
            "{'index': ':'}",
            "--log",
            log_path,
            "--summary",
            summary_path,
        ],
    )
    assert result.exit_code == 1
    assert isinstance(result.exception, ValueError)
