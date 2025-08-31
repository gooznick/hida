import platform
is_native_windows = platform.system() == "Windows"


windows = False
directory = "castxml_linux2"

windows = True
directory = "castxml_windows2"
native = windows == is_native_windows