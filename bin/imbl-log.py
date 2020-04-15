#!/usr/bin/env python3

import sys
import re
import numpy
import argparse

parser = argparse.ArgumentParser(description=
 'Parses log file produced by the IMBL\'s ctgui to recalculate proper rotation positions.'
  ' The file is read from the standart input and the result is sent to the standart output.')
parser.add_argument('labels', type=str, nargs='*', default="",
                    help='Parse only given labels.')
parser.add_argument('-i', '--info', action='store_true',
                    help='Output only information derived from the log')
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
        print("Empty set on label " + label + ".")
        sys.exit(1)
      label = ""

    elif "SAMPLE" in strg and "Acquisition started" in strg:
      lres = re.search('SAMPLE_(.*?)_*T', strg)
      if lres:
        if label  and  len(pos[label]) < 2 :
          print("Empty set on label " + label + ".")
          sys.exit(1)
        label = lres.group(1)
        if not label:
          label = 'single'
        if label in labels :
          print("Label " + label + " already exists. Corrupt log file.")
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
        print("Error in log at string %i: %s" %( strcounter, strg))

except EOFError:
  pass

if len(labels) == 0 :
  print("Empty or corrupt log.")
  sys.exit(1)

starts = [ pos[label][ 0] for label in labels ]
stops  = [ pos[label][-1] for label in labels ]
pdir = pos[labels[0]][0] < pos[labels[0]][-1]
start = max(starts)  if pdir else  min(starts)
stop  = min(stops)   if pdir else  max(stops)
minPos = min (start, stop)
maxPos = max (start, stop)

for label in labels:
  while not minPos <= pos[label][0] <= maxPos :
    del pos[label][0]
    del idx[label][0]
  while not minPos <= pos[label][-1] <= maxPos :
    del pos[label][-1]
    del idx[label][-1]

step = args.step
if not step :
  for label in labels:
    step = step + ( pos[label][-1] - pos[label][0] ) / ( idx[label][-1] - idx[label][0] )
  step = step / len(labels)
steps = max( [ idx[label][-1] - idx[label][0] for label in labels ] )
samples = [ start + step * cur  for cur in range(0, steps)  ]

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
if not args.info :
  for label in labels:
    upperEnd = steps
    if args.max_proj:
      upperEnd = min(upperEnd, args.max_proj)
    if args.max_angle:
      upperEnd = min(upperEnd, int(args.max_angle/step))
    for cur in range(0, upperEnd+1):
      print(label, cur, int(res[label][cur]))
