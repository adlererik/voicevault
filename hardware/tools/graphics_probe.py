#!/usr/bin/env python3
"""Create a real OpenGL context and verify a rendered pixel inside KiCad's runtime."""
import ctypes as C
import json


def binding(library, name, result, arguments):
    function = getattr(library, name)
    function.restype = result
    function.argtypes = arguments
    return function


def run():
    import wx
    import wx.glcanvas
    app = wx.App(False)
    glx_version = wx.glcanvas.GLCanvas.GetGLXVersion()
    if glx_version < 13:
        raise RuntimeError('KiCad GLX backend is unavailable. Check its per-application graphics setting.')
    egl = C.CDLL('libEGL.so.1')
    gl = C.CDLL('libOpenGL.so.0')
    pointer = C.c_void_p
    integer = C.c_int
    int_pointer = C.POINTER(integer)
    display = binding(egl, 'eglGetDisplay', pointer, [pointer])(None)
    major, minor = integer(), integer()
    initialize = binding(egl, 'eglInitialize', C.c_uint, [pointer, int_pointer, int_pointer])
    if not initialize(display, C.byref(major), C.byref(minor)):
        raise RuntimeError('EGL initialization failed')
    attributes = (integer * 13)(0x3033, 1, 0x3040, 8, 0x3024, 8, 0x3023, 8, 0x3022, 8, 0x3021, 8, 0x3038)
    config, count = pointer(), integer()
    choose = binding(egl, 'eglChooseConfig', C.c_uint, [pointer, int_pointer, C.POINTER(pointer), integer, int_pointer])
    if not choose(display, attributes, C.byref(config), 1, C.byref(count)) or count.value < 1:
        raise RuntimeError('No suitable OpenGL framebuffer configuration')
    if not binding(egl, 'eglBindAPI', C.c_uint, [C.c_uint])(0x30A2):
        raise RuntimeError('OpenGL API binding failed')
    context_attributes = (integer * 7)(0x3098, 3, 0x30FB, 3, 0x30FD, 1, 0x3038)
    context = binding(egl, 'eglCreateContext', pointer, [pointer, pointer, pointer, int_pointer])(display, config, None, context_attributes)
    surface_attributes = (integer * 5)(0x3057, 2, 0x3056, 2, 0x3038)
    surface = binding(egl, 'eglCreatePbufferSurface', pointer, [pointer, pointer, int_pointer])(display, config, surface_attributes)
    make_current = binding(egl, 'eglMakeCurrent', C.c_uint, [pointer, pointer, pointer, pointer])
    if not context or not surface or not make_current(display, surface, surface, context):
        raise RuntimeError('OpenGL 3.3 core context creation failed')
    get_string = binding(gl, 'glGetString', C.c_char_p, [C.c_uint])
    renderer = get_string(0x1F01).decode()
    vendor = get_string(0x1F00).decode()
    version = get_string(0x1F02).decode()
    binding(gl, 'glClearColor', None, [C.c_float] * 4)(.125, .25, .5, 1)
    binding(gl, 'glClear', None, [C.c_uint])(0x4000)
    binding(gl, 'glFinish', None, [])()
    pixel = (C.c_ubyte * 4)()
    binding(gl, 'glReadPixels', None, [integer, integer, integer, integer, C.c_uint, C.c_uint, pointer])(0, 0, 1, 1, 0x1908, 0x1401, pixel)
    error = binding(gl, 'glGetError', C.c_uint, [])()
    if error or any(abs(actual - expected) > 1 for actual, expected in zip(pixel, (32, 64, 128, 255))):
        raise RuntimeError('OpenGL render/readback check failed')
    make_current(display, None, None, None)
    binding(egl, 'eglDestroySurface', C.c_uint, [pointer, pointer])(display, surface)
    binding(egl, 'eglDestroyContext', C.c_uint, [pointer, pointer])(display, context)
    binding(egl, 'eglTerminate', C.c_uint, [pointer])(display)
    software = any(name in renderer.lower() for name in ('llvmpipe', 'softpipe', 'software rasterizer'))
    report = dict(status='pass', wx_glx_version=glx_version, egl_version=f'{major.value}.{minor.value}', opengl_version=version,
                  vendor=vendor, renderer=renderer, hardware_accelerated=not software,
                  rendered_rgba=list(pixel), gl_error=error)
    if software:
        raise RuntimeError('Context used software rendering ' + renderer)
    return report


if __name__ == '__main__':
    try:
        print(json.dumps(run(), indent=2))
    except (OSError, RuntimeError, AttributeError) as error:
        raise SystemExit('Graphics verification failed ' + str(error))
