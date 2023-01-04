#!/bin/bash

EXEPATH="$(dirname "$(realpath "$0")" )"
PATH="$EXEPATH:$PATH"
#convert_inuse="convert"
#if command -v convert.fp &> /dev/null ; then
#  convert_inuse="convert.fp"
#fi

printhelp() {
  echo "Usage: $0 [OPTIONS] [PROJECTION]"
  echo "OPTIONS:"
  echo "Stitching options."
  echo "  -g X,Y            Origin of the first stitch."
  echo "  -G X,Y            Origin of the second stitch (in 2D scans)."
  echo "  -f X,Y            Origin of the flip-and-stitch (in 360deg scans)."
  echo "     X and Y numbers are  the origin of the second image in the coordinate system of"
  echo "     the first one. Same as produced by the pairwise-stitching plugin of ImageJ."
  echo "  -c T,L,B,R        Crop source images."
  echo "  -C T,L,B,R        Crop final image."
  echo "     T, L, B and R numbers give cropping from the edges of the images:"
  echo "     top,left,bottom,right."
  echo "Other options."
  echo "  -i PATH           Path to the image mask used in projection formation."
  echo "  -r ANGLE          Rotate projections."
  echo "  -E INT            Thickness in pixels of edge transition."
  echo "  -n INT            Peak removal radius."
  echo "  -N FLOAT          Peak removal threshold: absolute if positive, relative if negative."
  echo "  -b INT[,INT]      Binning factor(s). If second number is given, then two"
  echo "                    independent binnings in X and Y coordinates; same otherwise."
  echo "  -s INT[,INT...]   Split point(s). If given, then final projection is"
  echo "                    horizontally split and fractions are named with _N postfix."
  echo "  -m INT            First projection to be processed."
  echo "  -M INT            Last projection to be processed."
  echo "  -d                Does not perform flat field correction on the images."
  echo "  -x STRING         Chain stitching with the X-tract reconstruction with"
  echo "                    the parameters read from the given parameters file."
  echo "  -w                Delete projections folder (clean) after X-tract processing."
  echo "  -R                Do NOT check results after processing is complete."
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

format="TIFF" # default
projfile=".projections"
initfile=".initstitch"
chkf "$initfile" init
source "${initfile}"

nofSt=$(wc -w <<< $filemask )
if (( $nofSt == 0 )) ; then
  nofSt=1
fi
secondsize=$(( $zstitch > 1 ? $ystitch : 0 ))
allopts="$@"
gmask=""
crop="0,0,0,0"
cropFinal="0,0,0,0"
binn=1
rotate=0
edge=0
peakThr=0
peakRad=0
origin="0,0"
originSecond="0,0"
originFlip="0,0"
split=""
doCheck=true
testme=""
ffcorrection=true
stParam=""
xtParamFile=""
minProj=0
maxProj=$(( $pjs - 1 ))
nlen=${#pjs}
wipeClean=false
beverbose=false

while getopts "i:g:G:f:c:C:r:b:s:x:m:M:E:n:N:dt:hwvR" opt ; do
  case $opt in
    i)  gmask=$OPTARG;;
    g)  origin=$OPTARG
        if (( $nofSt < 2 )) ; then
          echo "ERROR! Accordingly to the init file there is nothing to stitch." >&2
          echo "       Thus, -g option is meaningless. Exiting." >&2
          exit 1
        fi
        ;;
    G)  originSecond=$OPTARG
        if (( $secondsize < 2 )) ; then
          echo "ERROR! Accordingly to the init file there is no second stitch." >&2
          echo "       Thus, -G option is meaningless. Exiting." >&2
          exit 1
        fi
        ;;
    f)  originFlip=$OPTARG
        if (( $fshift < 1 )) ; then
          echo "ERROR! Accordingly to the init file there is no flip-and-stitch." >&2
          echo "       Thus, -f option is meaningless. Exiting." >&2
          exit 1
        fi
        ;;
    r)  rotate=$OPTARG ;    stParam="$stParam --rotate $rotate" ;;
    E)  edge=$OPTARG ;      stParam="$stParam --edge $edge" ;;
    n)  peakRad=$OPTARG ;   stParam="$stParam --noise-rad $peakRad" ;;
    N)  peakThr=$OPTARG ;   stParam="$stParam --noise-thr $peakThr" ;;
    c)  crop=$OPTARG ;      stParam="$stParam --crop $crop" ;;
    C)  cropFinal=$OPTARG ; stParam="$stParam --crop-final $cropFinal" ;;
    b)  binn=$OPTARG ;      stParam="$stParam --binn $binn" ;;
    s)  splits=$OPTARG
        for sp in $( sed "s:,: :g" <<< $splits )  ; do
          stParam="$stParam --split $sp"
        done
        ;;
    m)  minProj=$OPTARG
        if [ ! "$minProj" -eq "$minProj" ] 2> /dev/null ; then
          echo "ERROR! -m argument \"$minProj\" is not an integer." >&2
          exit 1
        fi
        if [ "$minProj" -lt 0 ] ; then
          minProj=0
        fi
        ;;
    M)  maxProj=$OPTARG
        if [ ! "$maxProj" -eq "$maxProj" ] 2> /dev/null ; then
          echo "ERROR! -M argument \"$maxProj\" is not an integer." >&2
          exit 1
        fi
        ;;
    x)  xtParamFile="$OPTARG"
        chkf "$xtParamFile" "X-tract parameters"
        ;;
    w)  wipeClean=true ;;
    d)  ffcorrection=false ;;
    t)  testme="$OPTARG" ;;
    R)  doCheck=false ;;
    v)  beverbose=true ;;
    h)  printhelp ; exit 1 ;;
    \?) echo "ERROR! Invalid option: -$OPTARG" >&2 ; exit 1 ;;
    :)  echo "ERROR! Option -$OPTARG requires an argument." >&2 ; exit 1 ;;
  esac
done

if [ -z "$PROCRECURSIVE" ] ; then
  echo "$allopts" >> ".proc.history"
fi

if [ ! -z "$subdirs" ] ; then

  if [ $testme ] ; then
    echo "ERROR! Multiple sub-samples processing cannot be done in test mode." >&2
    echo "       cd into one of the following sub-sample directories and test there:" >&2
    for subd in $filemask ; do
      echo "       $subd" >&2
    done
    exit 1
  fi

  for subd in $filemask ; do
    if $beverbose ; then
      echo "Processing subdirectory $subd ... "
      echo "    cd $(realpath $subd)"
    fi
    cd $subd
    if $beverbose ; then
      echo "    $0 $@"
    fi
    $0 $@
    if $beverbose ; then
      echo "    cd $(realpath $OLDPWD)"
    fi
    cd $OLDPWD
    if $beverbose ; then
      echo "Finished processing ${subd}."
    fi
  done

  exit $?

fi

shift $(( $OPTIND - 1 ))
export PROCRECURSIVE=true



if (( $nofSt > 1 )) ; then
  stParam="$stParam --origin $origin"
  if (( $secondsize > 1 )) ; then
    stParam="$stParam --second-origin $originSecond"
    stParam="$stParam --second-size $secondsize"
  fi
fi

if (( $fshift >= 1 )) ; then
  nofSt=$(( 2 * $nofSt ))
  pjs=$(( $pjs - $fshift ))
  stParam="$stParam --flip-origin $originFlip"
fi

if $beverbose ; then
  stParam="$stParam --verbose "
fi

imgbg="$opath/bg.tif"
if [ -e "$imgbg" ]  &&  $ffcorrection ; then
  stParam="$stParam --bg $imgbg"
fi

imgdf="$opath/df.tif"
if [ -e "$imgdf" ]  &&  $ffcorrection ; then
  stParam="$stParam --df $imgdf"
fi

imggf="$opath/gf.tif"
if [ -e "$imggf" ]  &&  $ffcorrection ; then
  stParam="$stParam --dg $imggf"
fi

imgms="$gmask"
if [ $imgms ] && [ -e "$imgms" ] ; then
  stParam="$stParam --mask $gmask"
fi

oname="SAMPLE_T@.tif"
if [ $testme ] ; then
  oname="tmp/$oname"
  stParam="$stParam --test $testme"
else
  oname="clean/$oname"
fi
stParam="$stParam --output $oname"

if [ -z "$1" ] ; then
  if (( maxProj >= $pjs  )) ; then
    maxProj=$(( $pjs - 1 ))
  fi
  stParam="$stParam --select ${minProj}-${maxProj}"
elif [ "$1" != "check" ] ; then
  stParam="$stParam --select $1"
else

  prelist="$(seq ${minProj} ${maxProj})"
  ls clean | sed 's SAMPLE clean/SAMPLE g' > ".listclean"
  exsplits="$( cat .listclean | sed 's .*\(split.*\)\..* \1 g' | sort | uniq )"
  nofimgs=$(grep split -c <<< "$exsplits")
  canonszs=""
  if (( $nofimgs == 0 )) ; then
    nofimgs=1
    canonszs=$( identify  $(cat .listclean | head -n 1) | cut -d' ' -f 3 | tr -d "\n ")
  else
    canonszs=$( \
      for exsplit in $exsplits ; do
        identifyout="$(identify $(cat .listclean | grep $exsplit | head ) )"
        szs=$( cut -d' ' -f 3 <<< "$identifyout"  | sort | uniq )
        nofszs=$(grep -c x <<< "$szs" )
        if (( $nofszs == 1 )) ; then
          echo $szs
        elif (( $nofszs == 2 )) ; then
          for sz in $szs ; do
            szcnt=$( grep -c $sz <<< "$identifyout" )
            echo $szcnt $sz
          done | sort -g -r -t' ' -k 1,1 | head -n 1 | cut -d' ' -f 2
        else
          echo "Inconsistent output image sizes." >&2
          exit 1
        fi
      done | tr -d '\n ' )
  fi

  while

    ls clean | sed 's SAMPLE clean/SAMPLE g' > ".listclean"
    paropt=""
    if $beverbose ; then
      paropt=" --eta "
      echo "Starting check for corrupt data in results:"
    fi
    badlist=$( echo $prelist | tr ', ' '\n' |
      parallel $paropt \
         ' imgs=$( grep $(printf "_T%0'${nlen}'i" {})  ".listclean" ) ; '`
        `' nofex=$( grep -c SAMPLE <<< "$imgs" ) ; '`
        `' if [ -z "$imgs" ]  || '`
        `'    [ "'${nofimgs}'" != "$nofex" ]  || '`
        `'    ! identout=$(identify $imgs 2>&1) || '`
        `'    grep -q identify <<< "$identout" || '`
        `'    [ "'${canonszs}'" !=  "$( cut -d" " -f 3 <<< "$identout" | tr -d "\n " )" ] ; '`
        `' then echo {} ; fi ' |
      sort -g | tr '\n' ',' )

    if [ "," = "${badlist:0-1}" ] ; then # remove last comma if present
      badlist="${badlist::-1}"
    fi
    if [ "$badlist" = "$prelist" ] ; then
      echo "No improvement after re-processing. Exiting." >&2
      exit 1
    fi
    [ ! -z "$badlist" ]  &&  [ "$badlist" != "$prelist" ]

  do
    prelist="$badlist"
    echo "Found bad projections to (re-)process: ${badlist}." >&2
    hallopts="$( sed 's:check::g' <<< $allopts )"
    if $beverbose ; then
      echo "    $0 $hallopts $badlist"
    fi
    $0 $hallopts $badlist
  done
  exit 0

fi


compact_seq() {
  pidx=""
  sseq=""
  while read idx ; do
    if [ -z "$sseq" ] ; then
      sseq=$idx
    elif (( $idx - $pidx != 1 )) ; then
      echo -n "$sseq"
      if (( $sseq != $pidx )) ; then
        echo -n "-${pidx}"
      fi
      echo -n ','
      sseq=${idx}
    fi
    pidx=$idx
  done
  echo -n "${sseq}"
  if (( $pidx != $sseq )) ; then
    echo -n "-$pidx"
  fi
  echo
}


imagemask="$(echo $filemask | sed 's: :\n:g' | sed -r 's ^(.+) _\1 g')"
rm .idxs* 2> /dev/null
while read imgm ; do

  header=""
  fprint=""
  if [ "$format" == "HDF5" ] ; then
    header="$ipath/SAMPLE${imgm}.hdf:$H5data:"
    fprint="%i,"
  else
    header=""
    fprint="$ipath/SAMPLE${imgm}_T%0${nlen}i.tif\n"
  fi
  lbl=$( sed -e 's:_$::g' -e 's:^_::g' <<< $imgm )
  if [ -z "$lbl" ] ; then
    lbl="single"
  fi

  idxfl=".idxs${imgm}.o"
  echo -n "$header" > "$idxfl"
  cat "$projfile" | grep -v '#' | grep "${lbl}" | cut -d' ' -f 3  \
    | head -n $pjs | compact_seq >> "$idxfl"
  if (( $fshift >= 1 )) ; then
    idxfl=".idxs${imgm}.f"
    echo -n "$header" > "$idxfl"
    cat "$projfile" | grep -v '#' | grep "${lbl}" | cut -d' ' -f 3 \
      | tail -n +$fshift \
      | head -n $pjs | perl -pe 'chomp if eof' | xargs printf "$fprint" >> "$idxfl"
  fi

done <<< "$imagemask"
#idxslist="$( (ls .idxs*o ; ls .idxs*f) 2> /dev/null | tr '\n' ' ' )"
paste -d' ' $( (ls .idxs*o ; ls .idxs*f) 2> /dev/null ) > ".idxsall"
rm .idxs*o .idxs*f 2> /dev/null

exit 0


if $beverbose ; then
  echo "Starting frame formation in $PWD."
  echo "  ctas proj $stParam < .idxsall"
fi
ctas proj $stParam < .idxsall  ||
  ( echo "There was an error executing:" >&2
    echo -e "ctas proj $stParam < .idxsall"  >&2
    exit 1 )






if [ "$testme" ] ; then
  exit 0
fi
if $doCheck  &&  [ -z "$1" ] ; then
  export AMCHECKING=true
  # -R to make sure it won't enter here and unset AMCHECKING
  $0 $allopts -R check
  unset AMCHECKING
fi

if [ -z "$xtParamFile" ]  ||  [ ! -z ${AMCHECKING+x} ] ; then
  exit $?
fi
addOpt=""
if [ ! -z "$step" ] ; then
  addOpt=" -a $step "
fi
if $beverbose ; then
  echo "Starting CT reconstruction in $PWD."
  echo "   imbl-xtract-wrapper.sh $addOpt "$xtParamFile" clean rec"
fi
imbl-xtract-wrapper.sh $addOpt "$xtParamFile" clean rec
xret="$?"
if [ "$xret" -eq "0" ] && $wipeClean ; then
    mv clean/SAMPLE*$(printf \%0${nlen}i $minProj)*.tif . &> /dev/null
    mv clean/SAMPLE*$(printf \%0${nlen}i $maxProj)*.tif . &> /dev/null
    mv clean/SAMPLE*$(printf \%0${nlen}i $(( ( $minProj + $maxProj ) / 2 )) )*.tif . &> /dev/null
    rm -rf clean/* &> /dev/null
fi
exit $xret

