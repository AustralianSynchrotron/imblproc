#!/usr/bin/env python3
  
import re
import numpy

labels = []
idx = {}
pos = {}

label = ""
try:
  while True:
    strg = input()
    if "Acquisition finished" in strg :
      if label  and  len(pos[label]) == 0 :
        print("Empty set on label " + label + ".")
        sys.exit(1)
      label = ""
    elif "SAMPLE" in strg and "Acquisition started" in strg:
      lres = re.search('SAMPLE_(.+?)_T', strg)
      if lres:
        if label  and  len(pos[label]) == 0 :
          print("Empty set on label " + label + ".")
          sys.exit(1)
        label = lres.group(1)
        if label in labels :
          print("Label " + label + " already exists. Corrupt log file.")
          sys.exit(1)
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
        print("Err in log at string: " + strg)
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

step = 0
for label in labels:
  step = step + ( pos[label][-1] - pos[label][0] ) / ( idx[label][-1] - idx[label][0] )
step = step / len(labels)
steps = max( [ idx[label][-1] - idx[label][0] for label in labels ] ) 
samples = [ start + step * cur  for cur in range(0, steps)  ]

res = {}
for label in labels:
  res[label] = numpy.interp(samples, pos[label], idx[label])

#for cur in range(0, steps):
#  print(cur, [ int( res[label][cur] ) for label in labels ])
for label in labels:
  for cur in range(0, steps):
    print(label, cur, int(res[label][cur]))
  


#print(step, steps)
#print(len(samples), samples[0], samples[-1])
#for label in labels:
#  print(label)
#  print(int(res[label][0]), int(res[label][-1]))
#  print(len(pos[label]),
#        pos[label][0], pos[label][-1],
#        idx[label][0], idx[label][-1])



