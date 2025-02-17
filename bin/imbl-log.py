#!/usr/bin/env python3

from __future__ import print_function
import sys
import re
import numpy
import argparse

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


parser = argparse.ArgumentParser(description=
 'Parses log file produced by the IMBL\'s ctgui to recalculate proper rotation positions.'
  ' The file is read from the standart input and the result is sent to the standart output.')
parser.add_argument('labels', type=str, nargs='*', default="",
                    help='Parse only given labels.')
parser.add_argument('-a', '--all', action='store_true',
                    help='Output full information derived from the log')
parser.add_argument('-t', '--table', action='store_true',
                    help='Output data in the new table format')
parser.add_argument('-s', '--step', type=float, default=0,
                    help='Use the step size matching the configuration file.' +
                         ' By default it uses the step derived from the log file.')
parser.add_argument('-m', '--max_angle', type=float, default=0,
                    help='Output only projections up to the given angle.')
parser.add_argument('-M', '--max_proj', type=int, default=0,
                    help='Output only projections up to the given number.')
args = parser.parse_args()


labels = []
idx = {}
pos = {}

strcounter = 0
label = ""
try:
  while True:

    strcounter = strcounter + 1
    strg = input()

    if "Acquisition finished" in strg :
      if label  and  len(pos[label]) == 0 :
        eprint("Warning: empty set on label " + label + ".")
        labels.pop(-1)
        idx.pop(label)
        pos.pop(label)
      label = ""

    elif "SAMPLE" in strg and "Acquisition started" in strg:
      if label  and  len(pos[label]) < 4 : # check previously filled label
        eprint(f"Warning! Too small ({len(pos[label])}) set on label \"{label}\". Will be disregarded.")
        labels.pop(-1)
        idx.pop(label)
        pos.pop(label)
        continue
      lres = re.search('\"SAMPLE(.*?)\"', strg)
      if not lres:
        eprint(f"Warning! Can't find label in acquisition string \"{strg}\".")
        label = ""
        continue
      label = lres.group(1)
      if label.endswith("_T") :
        label = label[:-2]
      label = label.strip("_")
      if not label:
        label = 'single'
      if  args.labels  and not any( lbl in label for lbl in args.labels ) :
        label = ""
      else :
        if label in labels :
          eprint(f"Warning! Label \"{label}\" already exists. Will overwrite previous.")
        else :
          labels.append(label)
        idx[label] = []
        pos[label] = []

    elif label:
      try :
        stamp, cidx, cpos = strg.split()[0:3]
        if len(pos[label]) == 0  or  float(cpos) != pos[label][-1] :
          idx[label].append(int(cidx))
          pos[label].append(float(cpos))
      except :
        eprint(f"Error in log at string {strcounter}: \"{strg}\"")

except EOFError:
  pass

if len(labels) == 0 :
  eprint("Error! Empty or corrupt log.")
  sys.exit(1)

starts = {label: pos[label][ 0] for label in labels }
stops  = {label: pos[label][-1] for label in labels }
pdir = pos[labels[0]][0] < pos[labels[0]][-1]
start = max(starts.values())  if pdir else  min(starts.values())
stop  = min(stops.values())   if pdir else  max(stops.values())
minPos = min (start, stop)
maxPos = max (start, stop)

good_labels = []
for lbl in labels:
  while len(pos[lbl]) > 3 and not minPos <= pos[lbl][1] <= maxPos :
    del pos[lbl][0]
    del idx[lbl][0]
  while len(pos[lbl]) > 3 and not minPos <= pos[lbl][-2] <= maxPos :
    del pos[lbl][-1]
    del idx[lbl][-1]
  if len(pos[lbl]) < 4 :
    eprint(f"Warning! Corrupt log or incomplete scan on label \"{lbl}\". Will be disregarded.")
  else :
    good_labels.append(lbl)
labels = good_labels

step = args.step
if not step :
  for label in labels:
    step = step + ( pos[label][-1] - pos[label][0] ) / ( idx[label][-1] - idx[label][0] )
  step = step / len(labels)
samples = []
cpos = start
while minPos <= cpos <= maxPos :
  samples.append(cpos)
  cpos = start + step * len(samples)
steps = len(samples)
res = {}
for label in labels:
  resf = numpy.interp(samples, pos[label], idx[label])
  resi = [ int(round(x)) for x in resf ]
  for cur in range(1, len(resi)-1):
    if 2 == resi[cur+1] - resi[cur-1] and resi[cur] != resi[cur-1]+1 :
      resi[cur] = resi[cur-1]+1
    #if resi[cur] == resi[cur-1] and resi[cur]+2 == resi[cur+1]:
    #  resi[cur] += 1
    #elif resi[cur] == resi[cur+1] and resi[cur]-2 == resi[cur-1]:
    #  resi[cur] -= 1
  res[label] = resi

print( "# Set: start, range, projections, step (full scan)")
print(f"# Common: {start:.3f} {stop - start:.3f} {steps} {step:.6f}")
#if len(labels) > 1 :
for label in labels :
  rangeL = pos[label][-1] - pos[label][0]
  stepsL = idx[label][-1] - idx[label][0]
  print(f"# {label}: {pos[label][0]: .3f} {rangeL: .3f} {stepsL} {rangeL/stepsL:.6f}"
        f" ({starts[label]: .3f} ... {stops[label]: .3f})")
if not args.all :
  sys.exit(0)

upperEnd = steps
if args.max_proj:
  upperEnd = min(upperEnd, args.max_proj)
if args.max_angle:
  upperEnd = min(upperEnd, int(args.max_angle/step))

if args.table :
  for cur in range(0, upperEnd):
    for label in labels:
      print(res[label][cur], end = ' ')
    print("")
else:
  for label in labels:
    for cur in range(0, upperEnd):
      print(label, cur, int(round(res[label][cur])))

