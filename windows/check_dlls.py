#!/usr/bin/env python3
"""Static check that every DLL imported by the bundled binaries will be found.

    python check_dlls.py <python dir> [<other dir> ...]

A DLL import counts as satisfied when the DLL is part of Windows itself, or
is shipped in the bundle next to the importing file, in one of the given
application directories (where python.exe / tectonic.exe live), or in the
importing package's own vendored-library folder (``<pkg>.libs`` or
``<pkg>/.libs``). A copy vendored by one package does not count for another
package, because Windows only finds it there if that package loaded first.

Microsoft's C++ runtime (msvcp140, vcruntime140, ...) is deliberately NOT
treated as part of Windows: a fresh PC may not have the Visual C++
redistributable, so the bundle must carry its own copy. On Windows, other
system DLLs are looked up in System32; elsewhere a built-in list is used.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pefile

VC_RUNTIME = ("msvcp140", "vcruntime140", "vcomp140", "concrt140",
              "vccorlib140", "mfc140")
# Core Windows DLLs (used when this check runs on a non-Windows machine).
CORE = {f"{name}.dll" for name in """
    advapi32 bcrypt cfgmgr32 comctl32 comdlg32 crypt32 d2d1 d3d11 dbghelp
    dnsapi dwmapi dwrite dxgi gdi32 gdiplus glu32 hid imagehlp imm32 iphlpapi
    kernel32 kernelbase mpr msimg32 msvcrt mswsock ncrypt netapi32 normaliz
    ntdll ole32 oleaut32 opengl32 powrprof propsys psapi rpcrt4 secur32
    setupapi shcore shell32 shlwapi ucrtbase urlmon user32 userenv uxtheme
    version winhttp wininet winmm wintrust wldap32 ws2_32 wtsapi32
    windowscodecs credui synchronization combase bcryptprimitives
    msvcp_win""".split()}
BINARY = {".dll", ".pyd", ".exe"}


def imported_dlls(path: Path) -> set[str]:
    pe = pefile.PE(str(path), fast_load=True)
    pe.parse_data_directories(directories=[
        pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"],
        pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_DELAY_IMPORT"]])
    names = {entry.dll.decode("ascii", "replace").lower()
             for attr in ("DIRECTORY_ENTRY_IMPORT", "DIRECTORY_ENTRY_DELAY_IMPORT")
             for entry in getattr(pe, attr, [])}
    pe.close()
    return names


def main(roots: list[Path]) -> int:
    binaries = [p for root in roots for p in root.rglob("*")
                if p.suffix.lower() in BINARY and p.is_file()]
    where: dict[str, set[Path]] = {}
    for b in binaries:
        where.setdefault(b.name.lower(), set()).add(b.parent)
    # vendored-library folder -> the package folder it serves
    vendored = {}
    for b in binaries:
        lib = b.parent
        if lib.name == ".libs":
            vendored[lib] = lib.parent
        elif lib.name.endswith(".libs"):
            vendored[lib] = lib.parent / lib.name[:-len(".libs")]
    system32 = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32"
    on_windows = sys.platform == "win32"

    def satisfied(dll: str, importer: Path) -> bool:
        if dll.startswith(("api-ms-win-", "ext-ms-")):
            return True
        dirs = where.get(dll, set())
        if importer.parent in dirs or dirs & set(roots):
            return True
        for lib in dirs & vendored.keys():
            if importer.is_relative_to(vendored[lib]) or importer.is_relative_to(lib):
                return True
        if dll.startswith(VC_RUNTIME):
            return False
        return (system32 / dll).is_file() if on_windows else dll in CORE

    missing: dict[str, list[Path]] = {}
    checked = 0
    for b in binaries:
        try:
            deps = imported_dlls(b)
        except pefile.PEFormatError:
            continue
        checked += 1
        for dll in deps:
            if not satisfied(dll, b):
                missing.setdefault(dll, []).append(b)

    vc = sorted(n for n in where if n.startswith(VC_RUNTIME))
    print(f"checked {checked} binaries under {', '.join(map(str, roots))}")
    print(f"C++ runtime shipped: {', '.join(vc) or 'none'}")
    if not missing:
        print("PASS: every imported DLL is shipped or part of Windows")
        return 0
    print(f"FAIL: {len(missing)} DLL(s) would not be found:")
    for dll, users in sorted(missing.items()):
        shown = ", ".join(str(u.relative_to(u.anchor)) for u in users[:3])
        print(f"  {dll}  <- {shown}{' ...' if len(users) > 3 else ''}")
    return 1


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    sys.exit(main([Path(a).resolve() for a in sys.argv[1:]]))
