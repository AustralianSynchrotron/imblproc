
#!/bin/bash

EXEPATH="$(dirname "$(realpath "$0")" )"
PATH="$EXEPATH:$PATH"

printhelp() {
  echo "Usage: $0 [OPTIONS] <original> [shifted] <output>"
  echo "  Performs projection formation in accordance with shift-in-scan approach."
  echo "OPTIONS:"
  echo "  -b PATH      Background image in original position."
  echo "  -B PATH      Background image in shifted position."
  echo "  -d PATH      Dark field image in original position."
  echo "  -D PATH      Dark field image in shifted position."
  echo "  -m PATH      Image containing map of gaps."
  echo "  -a INT       Number of frames constituting 180 degree ark."
  echo "  -f INT       First frame in original data set."
  echo "  -F INT       First frame in shifted data set."
  echo "  -s INT       Position of the first frame in shifted data set relative to that in original."
  echo "  -e INT       Number of last projection to process."
  echo "  -g INT:INT   Spatial shift in pixels (X,Y)."
  echo "  -c INT       Deviation of rotation axis from the center of original image."
  echo "  -C T,L,B,R   Crop final image (all INT)."
  echo "     T, L, B and R give cropping from the edges of the images: top, left, bottom, right."
  echo "  -R FLOAT     Rotate projections."
  echo "  -t INT       Test mode: keeps intermediate images for the projection in tmp."
  echo "  -v           Be verbose to show progress."
  echo "  -h           Prints this help."
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

chkNneg () {
  if (( $(echo "0 > $1" | bc -l) )); then
    wrong_num "$1" "is negative" "$2"
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
cropT=0
cropL=0
cropB=0
cropR=0
shiftX=""
shiftY=""
piark=""
firstO=0
firstS=""
delta=""
end=""
cent=0
rotate=0
testme=""
beverbose=false
allargs=""
while getopts "b:B:d:D:m:g:f:F:s:e:c:a:C:R:t:hv" opt ; do
  allargs=" $allargs -$opt $OPTARG"
  case $opt in
    b)  bgO=$OPTARG;;
    B)  bgS=$OPTARG;;
    d)  dfO=$OPTARG;;
    D)  dfS=$OPTARG;;
    m)  gmask=$OPTARG;;
    g)  IFS=',:' read shiftX shiftY <<< "$OPTARG"
        chkint "$shiftX" " from the string '$OPTARG' determined by option -g"
        chkint "$shiftY" " from the string '$OPTARG' determined by option -g"
        ;;
    a)  piark=$OPTARG
        chkint "$piark" "-a"
        chkpos "$piark" "-a"
        if [ "$piark" -lt "3" ] ; then
            wrong_num "$piark" "is less than 3" "-a"
        fi
        ;;
    f)  firstO=$OPTARG
        chkint "$firstO" "-f"
        chkNneg "$firstO" "-f"
        ;;
    F)  firstS=$OPTARG
        chkint "$firstS" "-F"
        chkNneg "$firstS" "-F"
        ;;
    s)  delta=$OPTARG
        chkint "$delta" "-s"
        chkNneg "$delta" "-s"
        ;;
    e)  end=$OPTARG
        chkint "$end" "-e"
        chkpos "$end" "-e"
        ;;
    c)  cent=$OPTARG
        chkint "$cent" "-c"
        ;;
    C)  IFS=',:' read cropT cropL cropB cropR <<< "$OPTARG"
        chkint "$cropT" "-C"
        chkint "$cropL" "-C"
        chkint "$cropB" "-C"
        chkint "$cropR" "-C"
        chkNneg "$cropT" "-C"
        chkNneg "$cropL" "-C"
        chkNneg "$cropB" "-C"
        chkNneg "$cropR" "-C"
        ;;
    R)  rotate=$OPTARG
        chknum "$rotate" "-R"
        ;;
    t)  testme="$OPTARG";;
    v)  beverbose=true;;
    h)  printhelp ; exit 1 ;;
    \?) echo "ERROR! Invalid option: -$OPTARG" >&2 ; exit 1 ;;
    :)  echo "ERROR! Option -$OPTARG requires an argument." >&2 ; exit 1 ;;
  esac
done
shift $((OPTIND-1))

args=""
if [ -n "$bgO" ] ; then
  args="$args -B $bgO"
fi
if [ -n "$bgS" ] ; then
  args="$args -B $bgS"
fi
if [ -n "$dfO" ] ; then
  args="$args -D $dfO"
fi
if [ -n "$dfS" ] ; then
  args="$args -D $dfS"
fi
if [ -n "$gmask" ] ; then
  args="$args -M $gmask"
fi
if [ -n "$testme" ] ; then
  args="$args -t $testme"
fi
if [ "$rotate" !=  "0" ]  ; then
  args="$args -r $rotate"
fi
if $beverbose ; then
  args="$args -v"
fi

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

samO="${1}"
samS=""
outVol=""
if [ -z "$3" ] ; then # 2 positional arguments
  samS="${1}"
  outVol="$2"
  if [ -z "$firstS" ] && [ -z "$delta" ] ; then
    echo "With a single input file either -F or -s options must be provided." >&2
    printhelp >&2
    exit 1
  elif [ -z "$delta" ] ; then
    delta=$(( $firstS - $firstO ))
  elif [ -z "$firstS" ] ; then
    firstS=$(( $firstO + $delta ))
  fi
else # 3 positional arguments
  samS="${2}"
  chkhdf "$3"
  outVol="$3"
  if [ -z "$delta" ] ; then
    delta=0
  fi
  if [ -z "$firstS" ] ; then
    firstS=0
  fi
fi

if [ -z "$piark" ] ; then
  echo "No option -a was given for step angle." >&2
  printhelp >&2
  exit 1
fi
if [ -z "$end" ] ; then
  end="$piark"
fi
if (( $end < $piark )) ; then
  echo "Last projection $end is less than that at 180deg $piark." >&2
  exit 1
fi
delta=$(( $delta % (2*$piark) )) # to make sure it is in [0..360) deg

if [ -z "$shiftX" ] || [ -z "$shiftY" ] ; then
  echo "No option -g was given for spacial shift." >&2
  printhelp >&2
  exit 1
fi


roundToInt() {
  printf "%.0f\n" "$1"
}

abs() {
  echo "${1/#-}"
}

maxNum() {
  echo -e "$1" | tr -d ' ' | sort -n | tail -1
}

minNum() {
  echo -e "$1" | tr -d ' ' | sort -n | head -1
}

norgx=$(  maxNum "0 \n $shiftX \n $((2*$cent-$shiftX))" )
norgxD=$( minNum "0 \n $shiftX" )
norgxF=$( minNum "0 \n $((2*$cent-$shiftX))" )
nendx=$(  minNum "0 \n $shiftX \n $((2*$cent-$shiftX))" )
nendxD=$( maxNum "0 \n $shiftX" )
nendxF=$( maxNum "0 \n $((2*$cent-$shiftX))" )

cropTB=$(abs "$shiftY")
cropD="$(($norgx-$norgxD+$cropL))-$(($nendxD-$nendx+$cropR)),$(($cropTB+$cropT))-$(($cropTB+$cropB))"
cropF="$(($norgx-$norgxF+$cropL))-$(($nendxF-$nendx+$cropR)),$(($cropTB+$cropT))-$(($cropTB+$cropB))"
spshD="$shiftX,$shiftY"
spshF="$((2*$cent-$shiftX)),$shiftY"
argD="-C $cropD -g $spshD"
argF="-C $cropF -f $spshF"


doStitch() {
  stO=$(($firstO+$1))
  stS=$(($firstS+$2))
  toExec="ctas proj $args $4 -o $outVol:$1-$(($1+$3)),$end\
          $samO:$stO-$(($stO+$3))\
          $samS:$stS-$(($stS+$3))"
  if $beverbose ; then
    echo "Executing:"
    echo "  $toExec"
  fi
  eval $toExec
}

if (( $delta == 0 )) ; then
  doStitch 0 0 $end "$argD"
elif (( $delta < $piark  )) ; then
  doStitch 0      $(($piark - $delta)) $(($delta-1))      "$argF"  && \
  doStitch $delta 0                    $(($end - $delta)) "$argD"
else
  projE=$(($delta + $end))
  tailS=$(($projE - 2*$piark))
  doStitch 0      $((2*$piark - $delta)) $(($tailS-1))          "$argD" && \
  doStitch $tailS 0                      $((2*$piark - $delta)) "$argF"
fi

exit $?







