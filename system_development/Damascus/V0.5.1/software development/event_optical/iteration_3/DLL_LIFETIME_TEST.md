# SDK DLL search-path lifetime test

Extract into iteration_3 and replace coordinator/windows_runtime.py. The existing camera recorder, SDK settings, output paths, and coordinator success checks are preserved. This patch keeps DLL search-directory handles registered through interpreter shutdown instead of explicitly closing them immediately after recorder.main returns. Python's normal exit still runs; this does not use os._exit or convert native crashes into success.

The markers showed recorder main returned 0 before process exit crashed. That narrows the failure to late shutdown, not a native stack frame. Removing a DLL search directory does not unload existing DLLs, so the link between that removal and the crash is still a hypothesis. This test checks it without masking a failure.

Repeat the direct two-second windows_runtime.py capture and check LASTEXITCODE. Only after it returns 0 should the paired run be retested. If the same crash persists, capture Windows Application Error event 1000 to identify the faulting module before further changes.

Three hardware-free tests confirm that paths are retained and errors/nonzero recorder results still propagate. They do not reproduce the vendor SDK's native finalization.
