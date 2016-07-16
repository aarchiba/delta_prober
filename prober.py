#!/usr/bin/env python

from __future__ import division, print_function
import re
import time
import telnetlib
import numpy as np

host = "192.168.0.7"
poprt = 7777
#octoprint_api_key = "DCFD456A8DD54C6B89FD173AB19B57A5"

def checksum_string(s):
    cs = 0
    for c in s:
        if c=='*':
            break
        cs ^= ord(c)
    cs &= 0xff
    return cs

class ResponseNotFound(ValueError):
    pass

class Connection(object):

    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.telnet = telnetlib.Telnet(host, port)
        self.lines = []
        self.line_numbers = []
        self.responses_start = []
        self.responses = []
        self.last_line_number = 0
        self.parsed_protocol = 0
        self.partial_last_line = ''

    def send_gcode_string(self, gcode):
        self.last_line_number += 1
        self.lines.append(gcode)
        self.line_numbers.append(self.last_line_number)
        self.responses_start.append(len(self.responses))
        self._send_line(-1)
        tries = 1
        while self._need_to_resend():
            #print("Resending",repr(self.lines[-1]))
            self._send_line(-1)
            tries += 1
            if tries>=10:
                raise ValueError("Unable to send %s even with %d tries"
                                     % (repr(self.lines[-1]), tries))
        return len(self.lines)-1

    def _send_line(self, n):
        if n<0:
            n += len(self.lines)
        line_number = self.line_numbers[n]
        s = ("N{0} ".format(line_number)
             + self.lines[n])
        s += "*{0}\n".format(checksum_string(s))
        self.responses_start[n] = len(self.responses)
        self.responses.append("Send: " + s)
        self.telnet.write(s.encode("ascii"))

    def check_for_responses(self, timeout=0):
        if timeout>0:
            if self.check_for_responses(timeout=0):
                return True
            s = self.telnet.read_until("\n", timeout=timeout)
            s2 = self.telnet.read_very_eager()
            s += s2
        else:
            s = self.telnet.read_very_eager()
        l = (self.partial_last_line+s.decode("ascii")).split("\n")
        self.partial_last_line = l[-1]
        l = l[:-1]
        if l:
            self.responses.extend(l)
            return True
        else:
            return False

    def _need_to_resend(self):
        self.check_for_responses()
        problem = False
        while True:
            while self.parsed_protocol<len(self.responses):
                r = self.responses[self.parsed_protocol]
                #print("Parsing",repr(r))
                if r == 'ok':
                    self.parsed_protocol += 1
                    #print("Returning",problem)
                    return problem
                elif r.startswith(
                        'Error:Line'):
                    problem = True
                    self.parsed_protocol += 1
                elif r.startswith("Resend:"):
                    g = re.search("Resend: (\d+)", r)
                    if not g:
                        raise ValueError(
                            "Line number response not understood: '%s'"
                            % repr(r))
                    self.last_line_number = int(g.group(1))
                    self.line_numbers[-1] = self.last_line_number
                    self.parsed_protocol += 1
                elif r.startswith(
                        'Error:checksum'):
                    self.parsed_protocol += 1
                    problem = True
                else:
                    self.parsed_protocol += 1
            if not self.check_for_responses(timeout=30.):
                break
        raise ValueError("No acknowledgement received for %s"
                             % repr(self.lines[-1]))


    def _find_forward(self, regex, n):
        while n<len(responses):
            g = re.match(regex,responses[n])
            if g:
                return n, g
            n += 1
        raise ResponseNotFound(regex)

    def responses_to(self, cmd):
        self.check_for_responses()
        return self.responses[self.responses_start[cmd]:]

    def await_response_list(self, cmd, regexes, timeout=30):
        i = self.responses_start[cmd]
        while True:
            while i<len(self.responses):
                for (j,r) in enumerate(regexes):
                    g = re.search(r, self.responses[i])
                    if g:
                        return j, self.responses[i], g
                i += 1
            if not self.check_for_responses(timeout):
                break
        raise ValueError("No response found before timeout")

    def await_response(self, cmd, regex):
        return self.await_response_list(cmd, [regex])[1:]



class Prober(object):

    def __init__(self, conn, height=50., speed=100., probeable_radius=70.):
        self.conn = conn
        self.needs_homing = True
        self.height = height
        self.probes = []
        self.speed = speed
        self.probeable_radius = probeable_radius
        self.permitted_tests = [lambda x,y: np.hypot(x,y)<probeable_radius]

    def home(self):
        self.conn.send_gcode_string("G28")
        self.needs_homing = False

    def on(self):
        # The printer doesn't necessarily need to be homed unless it was off
        # but turning it on is a good sign that the user thought it might be off
        # and expects it to be homed
        self.needs_homing = True
        self.conn.send_gcode_string("M80")
    def off(self):
        self.needs_homing = True
        self.conn.send_gcode_string("M81")

    def move(self, x, y, z):
        self.conn.send_gcode_string("G0 X{0} Y{1} Z{2} F{3}".format(
            x, y, z, 60*self.speed))

    def probe(self, x=0, y=0, force_rehome=False):
        if self.needs_homing or force_rehome:
            self.home()
        self.move(x,y,self.height)
        cmd = self.conn.send_gcode_string("G30 X{0} Y{1} S-1".format(x, y))
        s, g = self.conn.await_response(cmd,
                "Bed X: +([-0-9.]+) +Y: +([-0-9.]+) +Z: +([-0-9.]+)")
        px, py, pz = [float(g.group(i)) for i in [1,2,3]]
        self.probes.append((px,py,pz))

    def clear(self):
        self.probes = []

    def set_restriction(self, lam):
        self.permitted_tests.append(lam)

    def permitted(self, x, y):
        for t in self.permitted_tests:
            if not t(x,y):
                return False
        return True

    def probe_grid(self, n_side, force_rehome=False):
        xs = np.linspace(-self.probeable_radius,
                                 self.probeable_radius,
                                 n_side)
        ys = np.linspace(-self.probeable_radius,
                                    self.probeable_radius,
                                    n_side)
        rs = np.ma.masked_array(np.zeros((n_side,n_side),dtype=float))
        rs[:,:] = np.ma.masked

        for (i,x) in enumerate(xs):
            for (j,y) in enumerate(ys):
                if self.permitted(x,y):
                    self.probe(x,y,force_rehome=force_rehome)
                    rs[i,j] = self.probes[-1][2]

        return xs, ys, rs
