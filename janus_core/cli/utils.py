"""Utility functions for CLI."""

from __future__ import annotations

from collections.abc import Sequence
import datetime
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from typer_config import conf_callback_factory, yaml_loader
import yaml

if TYPE_CHECKING:
    from ase import Atoms
    from typer import Context

    from janus_core.cli.types import TyperDict
    from janus_core.helpers.janus_types import (
        MaybeSequence,
    )


def dict_paths_to_strs(dictionary: dict) -> None:
    """
    Recursively iterate over dictionary, converting Path values to strings.

    Parameters
    ----------
    dictionary
        Dictionary to be converted.
    """
    for key, value in dictionary.items():
        if isinstance(value, dict):
            dict_paths_to_strs(value)
        elif isinstance(value, Path):
            dictionary[key] = str(value)


def dict_tuples_to_lists(dictionary: dict) -> None:
    """
    Recursively iterate over dictionary, converting tuple values to lists.

    Parameters
    ----------
    dictionary
        Dictionary to be converted.
    """
    for key, value in dictionary.items():
        if isinstance(value, dict):
            dict_tuples_to_lists(value)
        elif isinstance(value, tuple):
            dictionary[key] = list(value)


def dict_remove_hyphens(dictionary: dict) -> dict:
    """
    Recursively iterate over dictionary, replacing hyphens with underscores in keys.

    Parameters
    ----------
    dictionary
        Dictionary to be converted.

    Returns
    -------
    dict
        Dictionary with hyphens in keys replaced with underscores.
    """
    for key, value in dictionary.items():
        if isinstance(value, dict):
            dictionary[key] = dict_remove_hyphens(value)
    return {k.replace("-", "_"): v for k, v in dictionary.items()}


def set_read_kwargs_index(read_kwargs: dict[str, Any]) -> None:
    """
    Set default read_kwargs["index"] to final image and check its value is an integer.

    To ensure only a single Atoms object is read, slices such as ":" are forbidden.

    Parameters
    ----------
    read_kwargs
        Keyword arguments to be passed to ase.io.read. If specified,
        read_kwargs["index"] must be an integer, and if not, a default value
        of -1 is set.
    """
    read_kwargs.setdefault("index", -1)
    try:
        int(read_kwargs["index"])
    except ValueError as e:
        raise ValueError("`read_kwargs['index']` must be an integer") from e


def parse_typer_dicts(typer_dicts: list[TyperDict]) -> list[dict]:
    """
    Convert list of TyperDict objects to list of dictionaries.

    Parameters
    ----------
    typer_dicts
        List of TyperDict objects to convert.

    Returns
    -------
    list[dict]
        List of converted dictionaries.

    Raises
    ------
    ValueError
        If items in list are not converted to dicts.
    """
    for i, typer_dict in enumerate(typer_dicts):
        typer_dicts[i] = typer_dict.value if typer_dict else {}
        if not isinstance(typer_dicts[i], dict):
            raise ValueError(
                f"""{typer_dicts[i]} must be passed as a dictionary wrapped in quotes.\
 For example, "{{'key': value}}" """
            )
    return typer_dicts


def yaml_converter_loader(config_file: str) -> dict[str, Any]:
    """
    Load yaml configuration and replace hyphens with underscores.

    Parameters
    ----------
    config_file
        Yaml configuration file to read.

    Returns
    -------
    dict[str, Any]
        Dictionary with loaded configuration.
    """
    if not config_file:
        return {}

    config = yaml_loader(config_file)
    # Replace all "-"" with "_" in conf
    return dict_remove_hyphens(config)


yaml_converter_callback = conf_callback_factory(yaml_converter_loader)


def start_summary(
    *, command: str, summary: Path, config: dict[str, Any], info: dict[str, Any]
) -> None:
    """
    Write initial summary contents.

    Parameters
    ----------
    command
        Name of CLI command being used.
    summary
        Path to summary file being saved.
    config
        Inputs to CLI command to save.
    info
        Extra information to save.
    """
    config.pop("config", None)

    summary_contents = {
        "command": f"janus {command}",
        "start_time": datetime.datetime.now().strftime("%d/%m/%Y, %H:%M:%S"),
        "config": config,
        "info": info,
    }

    # Convert all paths to strings in inputs nested dictionary
    dict_paths_to_strs(summary_contents)
    dict_tuples_to_lists(summary_contents)

    with open(summary, "w", encoding="utf8") as outfile:
        yaml.dump(summary_contents, outfile, default_flow_style=False)


def carbon_summary(*, summary: Path, log: Path) -> None:
    """
    Calculate and write carbon tracking summary.

    Parameters
    ----------
    summary
        Path to summary file being saved.
    log
        Path to log file with carbon emissions saved.
    """
    with open(log, encoding="utf8") as file:
        logs = yaml.safe_load(file)

    emissions = sum(
        lg["message"]["emissions"]
        for lg in logs
        if isinstance(lg["message"], dict) and "emissions" in lg["message"]
    )

    with open(summary, "a", encoding="utf8") as outfile:
        yaml.dump({"emissions": emissions}, outfile, default_flow_style=False)


def end_summary(summary: Path) -> None:
    """
    Write final time to summary and close.

    Parameters
    ----------
    summary
        Path to summary file being saved.
    """
    with open(summary, "a", encoding="utf8") as outfile:
        yaml.dump(
            {"end_time": datetime.datetime.now().strftime("%d/%m/%Y, %H:%M:%S")},
            outfile,
            default_flow_style=False,
        )
    logging.shutdown()


def get_struct_info(
    *,
    struct: MaybeSequence[Atoms],
    struct_path: Path,
) -> dict[str, Any]:
    """
    Add structure information to a dictionary.

    Parameters
    ----------
    struct
        Structure to be simulated.
    struct_path
        Path of structure file.

    Returns
    -------
    dict[str, Any]
        Dictionary with structure information.
    """
    from ase import Atoms

    info = {}

    if isinstance(struct, Atoms):
        info["struct"] = {
            "n_atoms": len(struct),
            "struct_path": struct_path,
            "formula": struct.get_chemical_formula(),
        }
    elif isinstance(struct, Sequence):
        info["traj"] = {
            "length": len(struct),
            "struct_path": struct_path,
            "struct": {
                "n_atoms": len(struct[0]),
                "formula": struct[0].get_chemical_formula(),
            },
        }

    return info


def get_config(*, params: dict[str, Any], all_kwargs: dict[str, Any]) -> dict[str, Any]:
    """
    Get configuration and set kwargs dictionaries.

    Parameters
    ----------
    params
        CLI input parameters from ctx.
    all_kwargs
        Name and contents of all kwargs dictionaries.

    Returns
    -------
    dict[str, Any]
        Input parameters with parsed kwargs dictionaries substituted in.
    """
    for param in params:
        if param in all_kwargs:
            params[param] = all_kwargs[param]

    return params


def check_config(ctx: Context) -> None:
    """
    Check options in configuration file are valid options for CLI command.

    Parameters
    ----------
    ctx
        Typer (Click) Context within command.
    """
    # Compare options from config file (default_map) to function definition (params)
    for option in ctx.default_map:
        # Check options individually so can inform user of specific issue
        if option not in ctx.params:
            raise ValueError(f"'{option}' in configuration file is not a valid option")
