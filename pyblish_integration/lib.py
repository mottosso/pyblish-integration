"""Internal library for Pyblish Maya

Attributes:
    CREATE_NO_WINDOW: Flag from MSDN;
        https://msdn.microsoft.com/en-us/library/ms684863(v=VS.85).aspx
    PYBLISH_QML_CONSOLE: Environment variable for displaying
        the console upon launching Pyblish QML

"""

# Standard library
import os
import sys
import time
import socket
import logging
import threading
import traceback
import subprocess

import pyblish_rpc
import pyblish_rpc.server
import pyblish_qml.client
import pyblish_qml.server
import pyblish_integration

CREATE_NO_WINDOW = 0x08000000
PYBLISH_QML_CONSOLE = "PYBLISH_QML_CONSOLE"
PYBLISH_CLIENT_PORT = "PYBLISH_CLIENT_PORT"

log = logging.getLogger("pyblish-integration")

self = sys.modules[__name__]
self.proxy = None
self.port = None
self.executable = None


def show():
    """Show the Pyblish graphical user interface

    An interface may already have been loaded; if that's the
    case, we favour it to launching a new unless `prefer_cached`
    is False.

    """

    if self.port is None:
        raise TypeError("Integration not initialised correctly")

    if self.proxy is None:
        self.proxy = pyblish_qml.client.proxy()

    try:
        self.proxy.show(self.port)

    except (socket.error, socket.timeout):
        preload()

    finally:
        self.proxy.show(self.port)


def setup(console=False):
    """Setup integration

    Find or launch Pyblish QML and setup endpoint in host
    for it to communicate with. Once setup is complete,
    call :func:`show` to display the GUI.

    Attributes:
        console (bool): Display console with GUI

    """

    if console:
        os.environ[PYBLISH_QML_CONSOLE] = "1"

    try:
        # In case QML is live and well, ask it
        # for the next available port number.
        self.proxy = pyblish_qml.client.proxy()
        self.port = self.proxy.find_available_port()

    except (socket.timeout, socket.error):
        # Otherwise, we can assume that this is
        # the first time QML is being opened.
        self.port = pyblish_qml.server.first_port
        proc = preload()

        assert proc.poll() is None

    finally:

        os.environ[PYBLISH_CLIENT_PORT] = str(self.port)

        try:
            _serve(self.port)
            log.debug("Integration successful!")

        except:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            message = "".join(traceback.format_exception(
                exc_type, exc_value, exc_traceback))
            log.debug(message)
            log.debug("Integration failed..")


def _serve(port):
    def server():
        """Provide QML with a friend to speak with"""
        pyblish_rpc.server.start_production_server(port)

    def heartbeat_emitter():
        """Let QML know we're still here"""
        proxy = pyblish_qml.client.proxy()

        while True:
            try:
                proxy.heartbeat(port)
                time.sleep(1)
            except (socket.error, socket.timeout):
                pass

    for worker in (server, heartbeat_emitter):
        t = threading.Thread(target=worker, name=worker.__name__)
        t.daemon = True
        t.start()

    log.debug("Server running @ %i" % port)

    return port


def preload():
    console = True if os.environ.get(PYBLISH_QML_CONSOLE) else False
    executable = registered_python_executable() or "python"
    kwargs = {
        "args": [executable, "-m", "pyblish_qml"],
        "creationflags": (
            CREATE_NO_WINDOW
            if os.name == "nt" and not console
            else 0
        )
    }

    process = subprocess.Popen(**kwargs)
    return process


def register_dispatch_wrapper(wrapper):
    pyblish_rpc.register_dispatch_wrapper(wrapper)


def register_python_executable(executable):
    self.executable = executable


def registered_python_executable():
    return self.executable


def echo(text):
    print(text)
