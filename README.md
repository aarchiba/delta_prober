# delta_prober

This is a collection of code for exploring delta printer
calibration. The idea is to use a proper computer to send commands to
the printer, telling it how to move and where to probe, returning the
results to the computer. Then on the machine where this runs you can
use the full tools of modern programming to work with the results:
visualization with matplotlib, numerical optimization with scipy,
additional constraints obtained from measuring test prints specified
by hand, and interactive use with ipython notebooks. The resulting
calibration data can then be transferred to the machine and saved for
use in normal printing.

This is not (yet?) a user-friendly calibration tool.

As currently configured, this tool runs on a user-facing machine and
communicates with the printer by making a telnet (arguably RFC2217)
connection to a port on a printer-control machine that forwards the
serial data back and forth. The code could be modified to communicate
directly over serial with a printer, but I haven't done this because
that would be inconvenient with my setup. In order to make this work,
*on the machine directly connected to the printer*, run
```bash
tcp_serial_redirect.py /dev/ttyACM0 250000
```
or whatever your serial port and baud rate are. This will also echo
all communication to standard output, so you can see what's going
on. You can run this under `dtach`, `tmux`, or `screen`, but it often
needs to be restarted anyway. *Currently this opens port 7777 to all
connections.* If you don't want the whole world to be able to take
your printer for a spin, run this only on an internal network. A
little jiggery-pokery would allow connections only from `localhost`,
which would allow `ssh` forwarding to provide secure access.

So far, the `ipython` notebooks primarily provide demonstrations and
testing for the tools in the Python files. In particular,
`probing.ipynb` demonstrates what can currently be done; simply
clicking on it in Github should allow you to see a rendered version
of the notebook with graphics.
