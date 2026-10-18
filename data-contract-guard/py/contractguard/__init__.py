"""contract-guard: data contracts as YAML, enforced in CI before bad data reaches anyone downstream."""

from __future__ import annotations

__version__ = "1.0.0"

from .checks import CheckResult, ValidationReport, validate
from .contract import Column, Contract, ContractError, Rule, load_contract, parse_contract
from .diff import Change, DiffReport, diff_contracts
from .infer import infer_contract

__all__ = [
    "CheckResult",
    "Change",
    "Column",
    "Contract",
    "ContractError",
    "DiffReport",
    "Rule",
    "ValidationReport",
    "__version__",
    "diff_contracts",
    "infer_contract",
    "load_contract",
    "parse_contract",
    "validate",
]
