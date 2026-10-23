"""Patch only the optical stdin reader, preserving all other camera code/settings.

Run once after extracting this package into iteration_3.
"""
from pathlib import Path

OLD = '''                if mode == 'serve':
                    while not stop.is_set():
                        if not select.select([sys.stdin], [], [], 0.2)[0]:
                            continue
                        line = sys.stdin.readline()
                        if not line:
                            break
'''
NEW = '''                if mode == 'serve':
                    # WINDOWS_PIPE_READER: select() on Windows accepts sockets, not stdin pipes.
                    import queue
                    commands = queue.Queue()
                    input_stream = sys.stdin
                    def read_commands():
                        try:
                            for command_line in input_stream:
                                commands.put(command_line)
                        except Exception as error:
                            commands.put(error)
                        finally:
                            commands.put(None)
                    threading.Thread(target=read_commands, daemon=True).start()
                    while not stop.is_set():
                        try:
                            line = commands.get(timeout=0.2)
                        except queue.Empty:
                            continue
                        if isinstance(line, Exception):
                            raise line
                        if line is None:
                            break
'''


def patch(path):
    original = path.read_bytes()
    text = original.decode('utf-8-sig').replace('\r\n', '\n')
    if 'WINDOWS_PIPE_READER' in text:
        print(f'Already patched: {path}')
        return False
    if text.count(OLD) != 1:
        raise RuntimeError(f'Expected optical serve block not found in {path}; file unchanged. Share this capture.py to adapt the patch.')
    updated = text.replace(OLD, NEW)
    compile(updated, str(path), 'exec')
    backup = path.with_name(path.name + '.before-windows-pipes.bak')
    if not backup.exists():
        backup.write_bytes(original)
    path.write_text(updated, encoding='utf-8', newline='\n')
    print(f'Patched: {path}\nOriginal backup: {backup}')
    return True


if __name__ == '__main__':
    patch(Path(__file__).resolve().parents[1] / 'optical_camera' / 'capture.py')
