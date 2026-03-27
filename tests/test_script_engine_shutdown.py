from __future__ import annotations

import ast
from pathlib import Path


def _parse_script(path: str) -> ast.Module:
    source = Path(path).read_text(encoding="utf-8")
    return ast.parse(source, filename=path)


def _collect_asyncio_run_calls(tree: ast.AST) -> list[ast.Call]:
    calls: list[ast.Call] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Name)
            and func.value.id == "asyncio"
            and func.attr == "run"
        ):
            calls.append(node)
    return calls


def _has_awaited_close_engine(tree: ast.AST, function_name: str) -> bool:
    for node in ast.walk(tree):
        if not isinstance(node, ast.AsyncFunctionDef) or node.name != function_name:
            continue
        for child in ast.walk(node):
            if not isinstance(child, ast.Await):
                continue
            call = child.value
            if isinstance(call, ast.Call) and isinstance(call.func, ast.Name):
                if call.func.id == "close_engine":
                    return True
    return False


def _call_targets_function(call: ast.Call, function_name: str) -> bool:
    if not call.args:
        return False
    first_arg = call.args[0]
    return (
        isinstance(first_arg, ast.Call)
        and isinstance(first_arg.func, ast.Name)
        and first_arg.func.id == function_name
    )


def test_synthetic_retention_closes_engine_in_same_async_entrypoint() -> None:
    tree = _parse_script("scripts/synthetic_ops_retention.py")
    run_calls = _collect_asyncio_run_calls(tree)

    assert len(run_calls) == 1
    assert _call_targets_function(run_calls[0], "_run_main")
    assert _has_awaited_close_engine(tree, "_run_main")


def test_demo_seed_closes_engine_in_same_async_entrypoint() -> None:
    tree = _parse_script("scripts/seed_demo_data.py")
    run_calls = _collect_asyncio_run_calls(tree)

    assert len(run_calls) == 1
    assert _call_targets_function(run_calls[0], "_run_main")
    assert _has_awaited_close_engine(tree, "_run_main")
