import os


def get_includes():
    import dmf_control
    r"""
    Return the directory that contains the dmf_control Cython *.hpp and
    *.pxd header files.

    Extension modules that need to compile against dmf_control should use this
    function to locate the appropriate include directory.

    Notes
    -----
    When using ``distutils``, for example in ``setup.py``.
    ::

        import dmf_control
        ...
        Extension('extension_name', ...
                  include_dirs=[...] + dmf_control.get_includes())
        ...

    """
    return [os.path.join(os.path.dirname(dmf_control.__file__), 'src')]


def get_sources():
    import dmf_control
    r"""
    Return a list of the additional *.cpp files that must be compiled along
    with the dmf_control Cython extension definitions.

    Extension modules that need to compile against dmf_control should use this
    function to locate the appropriate source files.

    Notes
    -----
    When using ``distutils``, for example in ``setup.py``.
    ::

        import dmf_control
        ...
        Extension('extension_name', ...
                  sources + dmf_control.get_sources())
        ...

    """
    source_dir = get_includes()[0]
    return [os.path.join(source_dir, f) for f in ('dmf_control_board.cpp',
                                                  'logging.cpp',
                                                  'RemoteObject.cpp',
                                                  'SimpleSerial.cpp')]
