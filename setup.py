#!/usr/bin/env python
import sys
from distutils.core import setup, Extension
from Cython.Build import cythonize

import dmf_control

include_dirs = dmf_control.get_includes()
sys.path += include_dirs

cy_config = dict(include_dirs=include_dirs, language='c++',
                 libraries=['boost_iostreams', 'boost_system', 'boost_thread'],
                 extra_compile_args=['-O3', '-Wfatal-errors'])

cy_exts = [Extension('dmf_control.%s' % v, dmf_control.get_sources()
                     + ['dmf_control/src/%s.pyx' % v], **cy_config)
           for v in ('cDmfControlBoard', 'cRemoteObject')]

utility_exts = [Extension('dmf_control.%s' % v,
                          ['dmf_control/src/%s.pyx' % v], language='c++')
                for v in ('ArduinoConstants', )]


setup(name = "dmf_control",
    version = "0.0.1",
    description = "Proxy for Digital Micro-Fluidics Control Board",
    keywords = "dmf microfluidics python c++ cython bindings",
    author = "Christian Fobel",
    url = "http://microfluidics.utoronto.ca/dropbot",
    license = "GPL",
    long_description = """""",
    packages = ['dmf_control', ],
    #package_data = {'dmf_control': 'src/*.pyx'},
    ext_modules=cythonize(utility_exts + cy_exts)
)
