#!/bin/bash

EXEPATH="$(dirname "$(realpath "$0")" )"
PATH="$EXEPATH:$PATH"

printhelp() {
  echo "Usage: $0 [OPTIONS] <original> [shifted] <output>"
  echo "  Performs projection formation in accordance with shift-in-scan approach."
  echo "OPTIONS:"
  echo "  -b PATH           Background image in original position."
  echo "  -B PATH           Background image in shifted position."
  echo "  -d PATH           Dark field image in original position."
  echo "  -D PATH           Dark field image in shifted position."
  echo "  -m PATH           Image containing map of gaps."
  echo "  -a FLOAT          Acquisition step if < 1.0 / projection number at 180 degree if positive int."
  echo "                    This condition also determines meaning of the next two options."
  echo "  -s FLOAT          Starting angle / projection of shifted data set ."
  echo "  -e FLOAT          Angle / number of last projection to process."
  echo "  -g FLOAT:FLOAT    Spatial shift in pixels (X,Y)."
  echo "  -r FLOAT          Deviation of rotation axis from the center of croppped original image."
  echo "  -c T,L,B,R        Crop source images (all INT)."
  echo "  -C T,L,B,R        Crop final image (all INT)."
  echo "     T, L, B and R give cropping from the edges of the images: top, left, bottom, right."
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

wrong_num() {
  opttxt=""
  if [ -n "$3" ] ; then
    opttxt=" given by option $3"
  fi
  echo "String \"$1\"$opttxt $2." >&2
  printhelp >&2
  exit 1
}

chknum () {
  if ! (( $( echo " $1 == $1 " | bc -l 2>/dev/null ) )) ; then
    wrong_num "$1" "is not a number" "$2"
  fi
}

chkint () {
  if ! [ "$1" -eq "$1" ] 2>/dev/null ; then
    wrong_num "$1" "is not an integer" "$2"
  fi
}

chkpos () {
  if (( $(echo "0 >= $1" | bc -l) )); then
    wrong_num "$1" "is not strictly positive" "$2"
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
step=""
start=0
end="180.0"
cent=0
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
    a)  step=$OPTARG
        chknum "$step" "-a"
        chkpos "$step" "-a"
        if (( $(echo "1 <= $step" | bc -l) )); then
          chkint "$step" "-a"
          if [ "$step" -lt "3" ] ; then
            wrong_num "$step" "is less than 3" "-a"
          fi
        fi ;;
    s)  start=$OPTARG
        chknum "$start" "-a"
        chkpos "$start" "-a"
        ;;
    e)  end=$OPTARG
        chknum "$end" "-a"
        chkpos "$end" "-a"
        ;;
    r)  cent=$OPTARG;;
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
shift $((OPTIND-1))

if [ -z "${1}" ] ; then
  echo "No input path was given." >&2
  printhelp >&2
  exit 1
fi
samO="$1"

if [ -z "${2}" ] ; then
  echo "No output path was given." >&2
  printhelp >&2
  exit 1
fi

samS=""
outVol=""
if [ -z "${3}" ] ; then
  samS="$samO"
  outVol="$2"
else
  samS="$2"
  outVol="$3"
fi

if [ -z "$step" ] ; then
  echo "No option -a was given." >&2
  printhelp >&2
  exit 1
fi


roundToInt() {
  printf "%.0f\n" "$1"
}

proj180=""
projShift=""
projMax=""
if (( $(echo "1 < $step" | bc -l) )); then
  proj180="$step"
  projShift="$start"
  projMax="$end"
else
  proj180=$(roundToInt "$( echo "scale=2; 180.0 / $step " | bc )" )
  projShift=$(roundToInt "$( echo "scale=2; $start / $step " | bc )" )
  projMax=$(roundToInt "$( echo "scale=2; $end / $step " | bc )" )
fi


if (( $(echo "180.0 > $end" | bc -l) )); then
  echo "Last projection $end is less than 180deg." >&2
  exit 1
fi

