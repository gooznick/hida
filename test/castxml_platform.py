import platform
is_native_windows = platform.system() == "Windows"


windows = False
directory = "castxml_linux"

windows = True
directory = "castxml_windows"
native = windows == is_native_windows