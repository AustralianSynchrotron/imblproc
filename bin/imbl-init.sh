#!/bin/bash

printhelp() {
  echo "Usage: $0 [OPTIONS] <SAMPLE PATH>"
  echo "OPTIONS:"
  echo "  -o PATH      Path for the output. Default: ./<SAMPLE NAME>"
  echo "  -e           Do not make averaged BG and DF."
  echo "  -y           Treat multiple Y's (if present) as independent scans."
  echo "  -z           Treat multiple Z's (if present) as independent scans."
  echo "  -f           Do not flip-and-stitch in 360deg scan."
  echo "  -h           Prints this help."
}


MakeFF=true
Yst=true
Zst=true
Fst=true
opath=""

while getopts "yzfheo:" opt ; do
  case $opt in
    o) opath="$OPTARG" ;;
    e) MakeFF=false ;;
    y) Yst=false ;;
    z) Zst=false ;;
    f) Fst=false ;;
    h) printhelp ; exit 0 ;;
    \?) echo "Invalid option: -$OPTARG" >&2 ; exit 1 ;;
    :)  echo "Option -$OPTARG requires an argument." >&2 ; exit 1 ;;
  esac
done
shift $(( $OPTIND - 1 ))


if [ -z "${1}" ] ; then
  echo "No input path to the sample was given." >&2
  printhelp >&2
  exit 1
fi
if [ ! -e "$1" ] ; then
  echo "Input path \"$1\" does not exist." >&2
  exit 1
fi

ipath="$(realpath $1)"
sample=$(basename "$ipath")
if [ -z "${opath}" ] ; then
  opath="$PWD/$sample"
fi
opath="$(realpath $opath)"

if ! mkdir -p "${opath}" ; then
  echo "Could not create output directory \"${opath}\"." >&2
  exit 1
fi

cd "${opath}"

ls -c "$ipath/" > .listinput

conffile="$ipath/$( cat .listinput | egrep 'acquisition.*config.*' | sort -V | tail -n 1 )"
if [ ! -e "$conffile" ] ; then
  echo "No configuration file \"${ipath}/acquisition.\*config\*\" found in input path." >&2
  exit 1
fi

getfromconfig () {
  cat "$conffile" | egrep "${2}|\[${1}\]" | grep "\[${1}\]" -A 1 | grep "${2}" | cut -d'=' -f 2
}

ctversion=$(getfromconfig General version)
if [ -z "$ctversion" ] ; then
    echo "Old version of the CT experiment detected." >&2
    echo "Use imbl4massive utilities to process" >&2
    exit 1
fi

range=$(getfromconfig scan range)
pjs=$(getfromconfig scan ^steps)

fshift=0
if (( $(echo "$range >= 360.0" | bc -l) ))  &&  $Fst  ; then
  fshift=$( echo "180 * $pjs / $range" | bc )
fi

Ysteps=0
Zsteps=0
if [ "$(getfromconfig General doserialscans)" == "true" ] ; then
  Ysteps=$(getfromconfig serial outerseries\\\\nofsteps)
  if [ "$(getfromconfig serial 2d)" == "true" ] ; then
    Zsteps=$(getfromconfig serial innearseries\\\\nofsteps)
  fi
fi

if $MakeFF || [ ! -e "bg.tif" ] ; then
  convert $(cat .listinput | grep '^BG' | sed "s BG ${ipath}/BG g") \
          -quiet -evaluate-sequence Mean "bg.tif"
  convert $(cat .listinput | grep '^DF' | sed "s DF ${ipath}/DF g") \
          -quiet -evaluate-sequence Mean "df.tif"
fi

width=0
hight=0
if [ -e "bg.tif" ] ; then
  read width hight <<< $(identify "${opath}/bg.tif" | cut -d' ' -f 3 | sed 's/x/ /g')
fi


Zlist=""
Zdirs="."
if (( $Zsteps > 1 )) ; then
  while read Zcur ; do
    Zlist="$Zlist Z$Zcur"
  done < <(seq -w 0 $(( $Zsteps - 1 )) )
  if ! $Zst ; then
    Zdirs="$Zlist"
    Zlist="_"
  fi
fi
Zsize=$( wc -w <<< $Zlist )

Ylist=""
Ydirs="."
if (( $Ysteps > 1 )) ; then
  while read Ycur ; do
    Ylist="$Ylist Y$Ycur"
  done < <(seq -w 0 $(( $Ysteps - 1 )) )
  if ! $Yst ; then
    Ydirs="$Ylist"
    Ylist="_"
  fi
fi
Ysize=$( wc -w <<< $Ylist )


outInitFile() {
  echo "filemask=\"${1}\""
  echo "ipath=\"$ipath\""
  echo "opath=\"$opath\""
  echo "pjs=$pjs"
  echo "scanrange=$range"
  echo "fshift=$fshift"
  echo "width=$width"
  echo "hight=$hight"
  echo "zs=$Zsteps"
  echo "ys=$Ysteps"
  echo "ystitch=$Ysize"
  echo "zstitch=$Zsize"
}


Sdirs=""
initName=".initstitch"

strip_ () {
  sed -e 's:_ *$::g' -e 's:^ *_: :g' <<< $1
}

for Ydir in $Ydirs ; do
  for Zdir in $Zdirs ; do

    Sdir="$Ydir/$Zdir"

    if ! mkdir -p "$Sdir/rec32fp" "$Sdir/clean" "$Sdir/rec8int" "$Sdir/tmp" ; then
      echo "Could not create output sub-directories in \"$PWD/$Sdir\"." >&2
      exit 1
    else

      Sdirs="$Sdirs $(realpath $Sdir --relative-to='.')"
      Slist=""
      for Ycur in $Ylist ; do
        if [ -z "$Zlist" ] ; then
          Slist="$Slist $(strip_ ${Ydir}${Ycur})"
        else
          for Zcur in $Zlist ; do
            Slist="$Slist $(strip_ ${Ydir}${Ycur}_${Zdir}${Zcur})"
          done
        fi
      done
      Slist="$( sed -e 's:\.::g' -e 's:__:_:g' <<< $Slist)"

      initfile="$Sdir/$initName"
      cat /dev/null > "$initfile"
      outInitFile "$Slist" >>  "$initfile"

    fi

  done
done

subdCount=$( wc -w <<< $Sdirs)
initfile="$initName"
if (( $subdCount > 1 )) ; then
  cat /dev/null > "$initfile"
  echo "subdirs=$subdCount" >>  "$initName"
  outInitFile "$Sdirs" >>  "$initName"
fi



