import prober

conn = prober.Connection("192.168.0.7", 7777)
while True:
    cmd = conn.send_gcode_string("M119")
    s, g = conn.await_response(cmd, "z_min: +(\w+)")
    print(s)
