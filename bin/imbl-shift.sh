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

chkhdf () {
  if ((  1 != $(tr -dc ':'  <<< "$1" | wc -c)  )) ; then
    echo "Input ($1) must be of form 'hdfFile:hdfContainer'." >&2
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
step=""
start=0
end=""
cent=0
rotate=0
testme=""
beverbose=false
allargs=""
while getopts "b:B:d:D:m:g:s:e:r:a:c:C:R:t:hv" opt ; do
  allargs=" $allargs -$opt $OPTARG"
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
        chknum "$start" "-s"
        chkpos "$start" "-s"
        ;;
    e)  end=$OPTARG
        chknum "$end" "-e"
        chkpos "$end" "-e"
        ;;
    r)  cent=$OPTARG;;
    c)  crop=$OPTARG;;
    C)  cropFinal=$OPTARG;;
    R)  rotate=$OPTARG;;
    t)  testme="$OPTARG";;
    v)  beverbose=true;;
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
chkhdf "$1"
if [ -z "${2}" ] ; then
  echo "No output path was given." >&2
  printhelp >&2
  exit 1
fi
chkhdf "$2"

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
  chkint "$start"
  projShift="$start"
  if [ -z "$end" ] ; then
    end="$proj180"
  else
    chkint "$end"
  fi
  projMax="$end"
else
  proj180=$(roundToInt "$( echo "scale=2; 180.0 / $step " | bc )" )
  projShift=$(roundToInt "$( echo "scale=2; $start / $step " | bc )" )
  if [ -z "$end" ] ; then
    end="180.0"
  fi
  projMax=$(roundToInt "$( echo "scale=2; $end / $step " | bc )" )
fi
if (( $projMax < $proj180 )) ; then
  echo "Last projection $projMax is less than that at 180deg $proj180." >&2
  exit 1
fi
projShift=$(( $projShift % (2*$proj180) ))

samO=""
samS=""
outVol=""
if [ -z "$3" ] ; then # only 2 input positional arguments
  if (( $projShift <= $proj180 )) ; then
    echo "In case of single input first shifted projection ($projShift) must be" \
         "larger than projection at 180deg ($proj180)." >&2
    exit 1
  fi
  samO="${1}:0-$projMax"
  samS="${1}:${projShift}-$(($projShift + $projMax))"
  outVol="$2"
else # 3 positional arguments
  chkhdf "$3"
  samO="$1"
  samS="$2"
  outVol="$3"
fi

