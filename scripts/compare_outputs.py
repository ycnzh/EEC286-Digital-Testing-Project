import sys

golden = sys.argv[1]
faulty = sys.argv[2]

with open(golden) as fg, open(faulty) as ff:
    g_lines = fg.readlines()
    f_lines = ff.readlines()

detected = False
for g, f in zip(g_lines, f_lines):
    if g.strip() != f.strip():
        detected = True
        break

if detected:
    print("DETECTED")
else:
    print("NOT DETECTED")
