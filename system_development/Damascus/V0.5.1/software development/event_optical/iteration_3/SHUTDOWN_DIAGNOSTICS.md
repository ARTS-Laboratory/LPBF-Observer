# Windows event shutdown diagnostics

Extract into iteration_3, replacing the two included Python files. Back up the current files first if desired. This recorder is based on the uploaded recorder(8).py and preserves the timestamp format and acquisition/cleanup behavior. It adds flushed messages before and after stream/device release, recorder return, DLL directory removal, and Python exit.

This is a diagnostic patch, not a confirmed native crash fix. No exit checks are bypassed. No SDK rebuild or optical patch is needed.

Run the same two-second windows_runtime.py command with PYTHONFAULTHANDLER=1. Report all [shutdown] messages and the direct process exit code. If device reference release completes but record() does not return, remaining local object teardown may be involved. If Python exit is requested before the crash, interpreter/native module finalization needs investigation. The last printed marker narrows the region, but is not a native call stack.

All 11 existing recorder tests pass using fake camera/stream facilities. These tests do not reproduce the Windows vendor SDK crash.
