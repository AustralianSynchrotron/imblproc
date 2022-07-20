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
parser.add_argument('-i', '--info', action='store_true',
                    help='Output only information derived from the log')
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
      if label  and  len(pos[label]) < 2 :
        eprint("Empty set on label " + label + ".")
        sys.exit(1)      
      lres = re.search('\"SAMPLE(.*?)\"', strg) 
      if (not lres):
        eprint("Can't find sample in acquisition string \"" + strg + "\".")
        sys.exit(1)
      label = lres.group(1)
      if label.endswith("_T") :
        label = label[:-2]
      label = label.strip("_")
      if not label:
        label = 'single'
      if label in labels :
        eprint("Label " + label + " already exists. Corrupt log file.")
        sys.exit(1)
      if  args.labels  and not any( lbl in label for lbl in args.labels ) :
        label = ""
      else :
        labels.append(label)
        idx[label] = []
        pos[label] = []

    elif label:
      try :
        stamp, cidx, cpos = strg.split()
        if len(pos[label]) == 0  or  float(cpos) != pos[label][-1] :
          idx[label].append(int(cidx))
          pos[label].append(float(cpos))
      except :
        eprint("Error in log at string %i: %s" %( strcounter, strg))

except EOFError:
  pass

if len(labels) == 0 :
  eprint("Empty or corrupt log.")
  sys.exit(1)

starts = [ pos[label][ 0] for label in labels ]
stops  = [ pos[label][-1] for label in labels ]
pdir = pos[labels[0]][0] < pos[labels[0]][-1]
start = max(starts)  if pdir else  min(starts)
stop  = min(stops)   if pdir else  max(stops)
minPos = min (start, stop)
maxPos = max (start, stop)

for label in labels:
  while not minPos <= pos[label][1] <= maxPos :
    del pos[label][0]
    del idx[label][0]
  while not minPos <= pos[label][-2] <= maxPos :
    del pos[label][-1]
    del idx[label][-1]

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
  res[label] = numpy.interp(samples, pos[label], idx[label])

def printInfo(lbl, strt, rng, pjs, stp) :
  print("# %s: %f %f %i %f" % ( lbl, strt, rng, pjs, stp ) )

print("# Set: start, range, projections, step")
printInfo( "Common", start, stop - start, steps, step)
if len(labels) > 1 :
  for label in labels :
    rangeL = pos[label][-1] - pos[label][0]
    stepsL = idx[label][-1] - idx[label][0]
    printInfo(label, pos[label][0], rangeL, stepsL, rangeL/stepsL)
if args.info :
  sys.exit(0)

upperEnd = steps
if args.max_proj: 
  upperEnd = min(upperEnd, args.max_proj)
if args.max_angle:
  upperEnd = min(upperEnd, int(args.max_angle/step))  

if args.table :
  for cur in range(0, upperEnd):
    for label in labels:  
      print(int(round(res[label][cur])), end = ' ')
    print("")
else:
  for label in labels:
    for cur in range(0, upperEnd):
      print(label, cur, int(round(res[label][cur])))

