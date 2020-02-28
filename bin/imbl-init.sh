#!/bin/bash

printhelp() {
  echo "Usage: $0 [OPTIONS] <SAMPLE PATH>"
  echo "OPTIONS:"
  echo "  -o PATH      Path for the output. Default: ./<SAMPLE NAME>"
  echo "  -e           Do not make averaged BG and DF."
  echo "  -y           Treat multiple Y's (if present) as independent scans."
  echo "  -z           Treat multiple Z's (if present) as independent scans."
  echo "  -f           Do not flip-and-stitch in 360deg scan."
  echo "  -l           Use projection positions from the log file."
  echo "  -h           Prints this help."
}


MakeFF=true
Yst=true
Zst=true
Fst=true
opath=""
uselog=false

while getopts "yzfhelo:" opt ; do
  case $opt in
    o) opath="$OPTARG" ;;
    e) MakeFF=false ;;
    y) Yst=false ;;
    z) Zst=false ;;
    f) Fst=false ;;
    l) uselog=true ;;
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

range=$(getfromconfig scan range)
pjs=$(getfromconfig scan ^steps)
step=$( echo "$range / $pjs " | bc )
fshift=0
if (( $(echo "$range >= 360.0" | bc -l) ))  &&  $Fst  ; then
  fshift=$( echo "180 * $pjs / $range" | bc )
fi

logfile="$(sed 's configuration log g' <<< $conffile)" 
if $uselog ; then
  if [ ! -e "$logfile" ] ; then
    echo "No log file \"${ipath}/$logfile\" found in input path." >&2
    exit 1
  fi
  if ! cat "$logfile" | imbl-log.py -i > /dev/null ; then
    echo "Error parsing log file \"${ipath}/$logfile\"." >&2
    exit 1
  fi
fi


initName=".initstitch"
projName=".projections"

outInitFile() {

  hrange=$range
  hpjs=$pjs
  hshift=$fshift
  hstep=$step
  if $uselog ; then
    cat "$logfile" | imbl-log.py ${1} > "${2}/$projName"
    read hrange hpjs hstep <<< $( cat "${2}/$projName" | grep '# Common' | cut -d' ' -f 4- )
    if (( $hshift != 0 )) ; then
      hfshift=$( echo "180 * $hpjs / $hrange" | bc )
    fi
  fi

  echo -e \
      "filemask=\"${1}\"\n" \
      "ipath=\"$ipath\"\n" \
      "opath=\"$opath\"\n" \
      "pjs=$hpjs\n" \
      "scanrange=$hrange\n" \
      "step=$hstep\n" \
      "fshift=$hshift\n" \
      "width=$width\n" \
      "hight=$hight\n" \
      "zs=$Zsteps\n" \
      "ys=$Ysteps\n" \
      "ystitch=$Ysize\n" \
      "zstitch=$Zsize\n" \
    > "${2}/$initName"
  
}

strip_ () {
  sed -e 's:_ *$::g' -e 's:^ *_: :g' <<< $1
}


Sdirs=""
for Ydir in $Ydirs ; do
  for Zdir in $Zdirs ; do

    Sdir="$Ydir/$Zdir"

    if ! mkdir -p "$Sdir/rec32fp" "$Sdir/clean" "$Sdir/rec8int" "$Sdir/tmp" ; then
      echo "Could not create output sub-directories in \"$PWD/$Sdir\"." >&2
      exit 1
    fi

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
    
    outInitFile "$Slist" "$Sdir" 
    
  done
done

subdCount=$( wc -w <<< $Sdirs)
if (( $subdCount > 1 )) ; then
  echo "subdirs=$subdCount" >  "$initName"
  outInitFile "$Sdirs" . 
fi



