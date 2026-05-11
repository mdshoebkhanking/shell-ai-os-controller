import traceback
import runpy

try:
    print("Starting wrapper...")
    runpy.run_path('shell_ui/shell_cinematic_full.py')
except BaseException as e:
    print("Caught exception:")
    traceback.print_exc()
