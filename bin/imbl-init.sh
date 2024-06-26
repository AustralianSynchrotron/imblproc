#!/bin/bash

export PATH="$(dirname "$(realpath "$0")" ):$PATH"

convert_inuse="convert"
if command -v convert.fp &> /dev/null ; then
  convert_inuse="convert.fp"
fi


printhelp() {
  echo "Usage: $0 [OPTIONS] <SAMPLE PATH>"
  echo "OPTIONS:"
  echo "  -o PATH      Path for the output. Default: ./<SAMPLE NAME>"
  echo "  -e           Do not make averaged BG and DF."
  echo "  -y           Treat multiple Y's (if present) as independent scans."
  echo "  -z           Treat multiple Z's (if present) as independent scans."
  echo "  -f           Do not flip-and-stitch in 360deg scan."
  echo "  -l           Use projection positions from the log file."
  echo "  -L           Restrict processing to given labels."
  echo "  -v           Be verbose."
  echo "  -h           Prints this help."
}


MakeFF=true
Yst=true
Zst=true
Fst=true
opath=""
uselog=false
uselabels=""
beverbose=false
H5data="/entry/data/data"

while getopts "vyzfhelo:L:" opt ; do
  case $opt in
    o) opath="$OPTARG" ;;
    e) MakeFF=false ;;
    y) Yst=false ;;
    z) Zst=false ;;
    f) Fst=false ;;
    l) uselog=true ;;
    L) uselabels="$OPTARG" ;;
    v) beverbose=true ;;
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

listfile=".listinput"
if $MakeFF || [ ! -e "$listfile" ] ; then
  ls -c "$ipath/" > "$listfile"
fi

conffile="$ipath/$( cat "$listfile" | grep -E 'acquisition.*config.*' | sort -V | tail -n 1 )"
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


format=$(getfromconfig General imageFormat)
if [ "$format" == 'HDF&5' ] ; then # to correct the bug in the data acquisition software
  format="HDF5"
fi

toHDFctas() {
  listfmt=""
  while read fl ; do
    if [ "$format" == "HDF5" ] ; then
      listfmt="$listfmt $fl:$H5data:$1 "
    else
      listfmt="$listfmt $fl "
    fi
  done
  echo $listfmt
}

makeauximg() {
  if ! $MakeFF  &&  [ -e "$1" ] ; then
    return
  fi
  listi="$( cat "$listfile" | grep "^$2" | sed "s $2 ${ipath}/$2 g" | toHDFctas )"
  if [ -z "$listi" ] ; then
    return
  fi
  vparam=""
  if $beverbose ; then
    vparam=" -v "
    echo "Making $1:"
    prntlist="$listi"
    if [ "$format" != "HDF5" ] ; then
      prntlist="${ipath}/$2"'*.tif'
    fi
    echo "  ctas v2v -o "$1" -b 1,1,0 $vparam $prntlist"
  fi
  ctas v2v -o "$1" -b 1,1,0 $vparam $listi
}
makeauximg "bg.tif" "BG"
makeauximg "df.tif" "DF"
makeauximg "dg.tif" "DG"

width=0
hight=0
if [ -e "bg.tif" ] ; then
  read width hight <<< $(identify "${opath}/bg.tif" | cut -d' ' -f 3 | sed 's/x/ /g')
fi

Ysteps=0
Zsteps=0
if [ "$(getfromconfig General doserialscans)" == "true" ] ; then
  Ysteps=$(getfromconfig serial outerseries\\\\nofsteps)
  if [ "$(getfromconfig serial 2d)" == "true" ] ; then
    Zsteps=$(getfromconfig serial innearseries\\\\nofsteps)
  fi
fi

logfile="$(sed 's configuration log g' <<< $conffile)"
logi=""
if $uselog ; then
  if [ ! -e "$logfile" ] ; then
    echo "No log file \"$logfile\" found in input path." >&2
    exit 1
  fi
  logi=$(cat $(dirname $logfile)/acquisition*log | imbl-log.py $uselabels | sed -e '1,2d' )
  #logi=$(cat "$logfile" | imbl-log.py $uselabels)
  if (( "$?" )) ; then
    echo "Error parsing log file \"$logfile\"." >&2
    exit 1
  fi
elif (( $Ysteps > 0 )) ; then
  while read Ycur ; do
    ylabel="Y$Ycur"
    if (( $Zsteps > 0 )) ; then
      while read Zcur ; do
        label="${ylabel}_Z${Zcur}"
        if [ -z "$uselabels" ]  ||  grep -q "$label" <<< "$uselabels" ; then
          logi="$logi$label"$'\n'
        fi
      done < <(seq -w 0 $(( $Zsteps - 1 )) )
    elif [ -z "$uselabels" ]  ||  grep -q "$label" <<< "$uselabels" ; then
      logi="$logi""$ylabel"$'\n'
    fi
  done < <(seq -w 0 $(( $Ysteps - 1 )) )
fi

Zlist=""
Zdirs="."
if (( $Zsteps > 1 )) ; then
  Zlist="$( sed -e 's :  g' -e 's .*\(Z[0-9]*\).* \1 g' <<< "$logi" | sort | uniq )"
  if ! $Zst ; then
    Zdirs="$Zlist"
    Zlist="_"
  fi
fi
Zsize=$( wc -w <<< $Zlist )

Ylist=""
Ydirs="."
if (( $Ysteps > 1 )) ; then
  Ylist="$( sed -e 's :  g' -e 's .*\(Y[0-9]*\).* \1 g' <<< "$logi" | sort | uniq )"
  if ! $Yst ; then
    Ydirs="$Ylist"
    Ylist="_"
  fi
fi
Ysize=$( wc -w <<< $Ylist )

range=$(getfromconfig scan range)
pjs=$(getfromconfig scan ^steps)
step=$( echo " scale=6 ; $range / $pjs " | bc | sed 's 0*$  g')
fshift=0
if (( $(echo "$range >= 360.0" | bc -l) ))  &&  $Fst  ; then
  fshift=$( echo "180 * $pjs / $range" | bc )
fi

initName=".initstitch"
projName=".projections"


outInitFile() {

  hmask="${1}"
  hrange=$range
  hpjs=$pjs
  hshift=$fshift
  hstep=$step
  if $uselog ; then
    #cat "$logfile" | imbl-log.py --all $hmask > "${2}/$projName"
    cat $(dirname $logfile)/acquisition*log | imbl-log.py --all $hmask > "${2}/$projName"

    read hrange hpjs hstep <<< $( cat "${2}/$projName" | grep '# Common' | cut -d' ' -f 4- )
    if (( $hshift != 0 )) ; then
      hfshift=$( echo "180 * $hpjs / $hrange" | bc )
    fi
  else
    echo "# Set: start, range, projections, step" > "${2}/$projName"
    echo "# Common: 0.0 $hrange $hpjs $hstep" >> "${2}/$projName"
    for msk in $hmask ; do
      echo "# $msk: 0.0 $hrange $hpjs $hstep" >> "${2}/$projName"
    done
    pmask="$hmask"
    if [ -z "$pmask" ] ; then
      pmask="single"
    fi
    for msk in $pmask ; do
      seq 0 $hpjs | sed "s:^\(.*\):$msk \1 \1:g" >> "${2}/$projName"
    done
  fi

  filemask="$hmask"
  if [ ! -z "$3" ] ; then
    filemask="${3}"
  fi


  echoInfo() {
    echo "filemask=\"$filemask\""
    echo "ipath=\"$ipath\""
    echo "opath=\"$opath\""
    echo "pjs=$hpjs"
    echo "scanrange=$hrange"
    echo "step=$hstep"
    echo "fshift=$hshift"
    echo "width=$width"
    echo "hight=$hight"
    echo "zs=$Zsteps"
    echo "ys=$Ysteps"
    echo "ystitch=$Ysize"
    echo "zstitch=$Zsize"
    echo "format=\"$format\""
    echo "H5data=\"$H5data\""
  }

  echoInfo > "${2}/$initName"

}

strip_ () {
  sed -e 's:_ *$::g' -e 's:^ *_: :g' <<< $1
}

Sdirs=""
for Ydir in $Ydirs ; do
  for Zdir in $Zdirs ; do
    Sdir="$Ydir/$Zdir"

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

    NSlist=""
    for comp in $( sed -e 's:\.::g' -e 's:__:_:g' <<< $Slist) ; do
      if [ -z "$uselabels" ] || grep -q $comp <<< "${uselabels}" ; then
        NSlist="$NSlist $comp"
      fi
    done

    if [ -n "$NSlist" ] ; then
      if ! mkdir -p "$Sdir" ; then
        echo "Could not create output output directory \"$PWD/$Sdir\"." >&2
        exit 1
      fi
      outInitFile "$NSlist" "$Sdir"
    fi
    Sdirs="$Sdirs $(realpath $Sdir --relative-to='.' 2> /dev/null )"

  done
done

subdCount=$( echo $Sdirs | tr -d '.' | wc -w )
if (( $subdCount > 0 )) ; then
  outInitFile "$uselabels" . "$Sdirs"
  echo "subdirs=$subdCount" >>  "$initName"
elif ! (( $Zsteps + $Ysteps )) ; then # single scan
  outInitFile "" . ""
fi


