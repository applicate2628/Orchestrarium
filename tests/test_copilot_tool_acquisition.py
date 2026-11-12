"""Typed file-target acquisition, not native tool or policy admission."""
from pathlib import Path
import copy
import pytest
from _module_loading_support import load_module

ROOT = Path(__file__).resolve().parents[1]
WIRE = load_module(ROOT / "scripts/installation/copilot_transport.py", "copilot_acquisition_wire")
COMMON = load_module(ROOT / "scripts/universal-hooks/scripts/hook_common.py", "copilot_acquisition_common")


def acquire(name, args, shape="camel"):
    payload = {"cwd":"/fixture","toolName":name,"toolArgs":args} if shape=="camel" else {
        "cwd":"/fixture","hook_event_name":"PreToolUse","tool_name":name,"tool_input":args}
    call = WIRE.read_pre_tool_use(payload, registration_event="preToolUse")
    before = copy.deepcopy(call.arguments)
    result = WIRE.acquire_pre_tool_input(call, acquire=COMMON.acquire_tool_input)
    assert call.arguments == before and call.tool_name == name
    assert result.raw_name == name
    return result


@pytest.mark.parametrize("name,args,operation", [
    ("create", {"path":"/fixture/\u4e2d\u6587.txt","file_text":"data"}, "write"),
    ("edit", {"path":"/fixture/\u4e2d\u6587.txt","old_str":"a","new_str":"b"}, "edit"),
    ("create_file", {"filePath":"/fixture/\u4e2d\u6587.txt","content":"data"}, "write"),
    ("replace_string_in_file", {"filePath":"/fixture/\u4e2d\u6587.txt","oldString":"a","newString":"b"}, "edit"),
    ("insert_edit_into_file", {"filePath":"/fixture/\u4e2d\u6587.txt","code":"data","explanation":"fixture"}, "edit"),
    ("edit_notebook_file", {"filePath":"/fixture/\u4e2d\u6587.txt","editType":"edit","cellId":"cell"}, "notebookedit"),
])
def test_native_file_carriers_retain_raw_identity(name, args, operation):
    result = acquire(name,args)
    assert result.operation == operation and result.resolved
    assert result.targets == ("/fixture/\u4e2d\u6587.txt",) and result.command is None


@pytest.mark.parametrize("command,operation", [("create","write"),("str_replace","edit"),("insert","edit")])
def test_native_command_selected_editor_mutations(command, operation):
    result = acquire("str_replace_editor", {"command":command,"path":"/fixture/file.txt"})
    assert result.operation == operation and result.resolved and result.targets == ("/fixture/file.txt",)


@pytest.mark.parametrize("command", ["view","unknown",None,[],{},True,3])
def test_editor_read_or_unknown_command_is_not_invented_as_a_mutation(command):
    result = acquire("str_replace_editor", {"command":command,"path":"/fixture/file.txt"})
    assert not result.resolved and result.targets == ()


def test_multi_replace_acquires_every_target_through_existing_owner():
    result = acquire("multi_replace_string_in_file", {"explanation":"fixture","replacements":[
        {"filePath":"/fixture/a.txt","oldString":"a","newString":"b"},
        {"filePath":"/fixture/\u4e2d\u6587.txt","oldString":"c","newString":"d"}]}, "snake")
    assert result.operation == "edit" and result.resolved
    assert result.targets == ("/fixture/a.txt","/fixture/\u4e2d\u6587.txt")


@pytest.mark.parametrize("rows", [[],None,[{"filePath":"/fixture/a"},{}],[{"filePath":"/fixture/a"},"bad"]])
def test_multi_replace_never_returns_partial_target_credit(rows):
    result = acquire("multi_replace_string_in_file", {"replacements":rows})
    assert not result.resolved and result.targets == ()


@pytest.mark.parametrize("path", [None,[],"", " /fixture/file", "/fixture/file ", "bad\x00path", "untitled:Untitled-1", "file:///fixture/file"])
def test_unqualified_path_carriers_are_not_trimmed_or_guessed(path):
    result = acquire("create_file", {"filePath":path,"content":"data"})
    assert not result.resolved and result.targets == ()


def test_native_path_field_wins_over_unrelated_foreign_field_without_rewrite():
    result = acquire("create_file", {"filePath":"/fixture/actual","file_path":"/fixture/foreign","content":"data"})
    assert result.resolved and result.targets == ("/fixture/actual",)


def test_generic_local_terminal_keeps_unqualified_dialect():
    result = acquire("run_in_terminal", {"command":"git status"}, "snake")
    assert not result.resolved and result.command is None and result.operation is None


def test_explicit_shell_and_patch_reuse_existing_acquisition():
    shell = acquire("powershell", {"command":"Write-Output fixture"})
    assert shell.resolved and shell.operation == "powershell" and shell.command == "Write-Output fixture"
    patch = acquire("apply_patch", "*** Begin Patch\n*** Delete File: /fixture/a.txt\n*** End Patch\n")
    assert patch.resolved and patch.operation == "apply_patch" and patch.targets == ("/fixture/a.txt",)


@pytest.mark.parametrize("path", [r"C:\fixture\file.txt", "D:/fixture/file.txt", r"\\server\share\file.txt", "relative/file.txt"])
def test_literal_native_paths_are_preserved(path):
    result = acquire("create_file", {"filePath":path,"content":"data"})
    assert result.resolved and result.targets == (path,)
