#!/bin/bash

EXEPATH="$(dirname "$(realpath "$0")" )"
PATH="$EXEPATH:$PATH"

printhelp() {
  echo "Usage: $0 [OPTIONS] <original> [shifted] <output>"
  echo "  Performs projection formation in accordance with shift-in-scan approach."
  echo "OPTIONS:"
  echo "Stitching options."
  echo "  -b PATH           Background image in original position."
  echo "  -B PATH           Background image in shifted position."
  echo "  -d PATH           Dark field image in original position."
  echo "  -D PATH           Dark field image in shifted position."
  echo "  -m PATH           Image containing map of gaps."
  echo "  -g FLOAT:FLOAT    Spatial shift in pixels (X,Y)."
  echo "  -s FLOAT          Starting angle of shifted data set."
  echo "  -e FLOAT          Angular position of the last projection to process."
  echo "  -r FLOAT          Scan rotation axis after source cropping."
  echo "  -a FLOAT          Step angle between two consecutive frames."
  echo "  -c T,L,B,R        Crop source images (all INT)."
  echo "  -C T,L,B,R        Crop final image (all INT)."
  echo "     T, L, B and R numbers give cropping from the edges of the images:"
  echo "     top,left,bottom,right."
  echo "  -R FLOAT          Rotate projections."
  echo "  -t INT            Test mode: keeps intermediate images for the projection in tmp."
  echo "  -v                Be verbose to show progress."
  echo "  -h                Prints this help."
}

chkf () {
  if [ ! -e "$1" ] ; then
    echo "ERROR! Non existing $2 path: \"$1\"" >&2
    exit 1
  fi
}

bgO=""
bgS=""
dfO=""
dfS=""
gmask=""
crop="0,0,0,0"
cropFinal="0,0,0,0"
shift="0,0"
start=0
end="180.0"
cent=0
step=0
rotate=0
testme=""
beverbose=false
while getopts "b:B:d:D:m:g:s:e:r:a:c:C:R:t:hv" opt ; do
  case $opt in
    b)  bgO=$OPTARG;;
    B)  bgS=$OPTARG;;
    d)  dfO=$OPTARG;;
    D)  dfS=$OPTARG;;
    m)  gmask=$OPTARG;;
    g)  shift=$OPTARG;;
    s)  start=$OPTARG;;
    e)  end=$OPTARG;;
    r)  cent=$OPTARG;;
    a)  step=$OPTARG;;
    c)  crop=$OPTARG;;
    C)  cropFinal=$OPTARG;;
    R)  rotate=$OPTARG;;
    t)  testme="$OPTARG" ;;
    v)  beverbose=true ;;
    h)  printhelp ; exit 1 ;;
    \?) echo "ERROR! Invalid option: -$OPTARG" >&2 ; exit 1 ;;
    :)  echo "ERROR! Option -$OPTARG requires an argument." >&2 ; exit 1 ;;
  esac
done