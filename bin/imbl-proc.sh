#!/bin/bash

export PATH="$(dirname "$(realpath "$0")" ):$PATH"

convert_inuse="convert"
if command -v convert.fp &> /dev/null ; then
  convert_inuse="convert.fp"
fi

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
  echo "  -r ANGLE          Rotate projections."
  echo "  -b INT[,INT]      Binning factor(s). If second number is given, then two"
  echo "                    independent binnings in X and Y coordinates; same otherwise."
  echo "  -s INT[,INT...]   Split point(s). If given, then final projection is"
  echo "                    horizontally split and fractions are named with _N postfix."
#  echo "  -n RAD            Reduce noise removing peaks (same as imagick's -median option)."
#  echo "  -i STRING         If given then source images, before any further processing, are"
#  echo "                    piped through imagemagick with this string as the parameters."
#  echo "                    The results are used instead of the original source images."
#  echo "                    Make sure you know how to use it correctly."
  echo "  -m INT            First projection to be processed."
  echo "  -M INT            Last projection to be processed."
  echo "  -d                Does not perform flat field correction on the images."
  echo "  -x STRING         Chain stitching with the X-tract reconstruction with"
  echo "                    the parameters read from the given parameters file."
  echo "  -w                Delete projections folder (clean) after X-tract processing."
  echo "  -t INT            Test mode: keeps intermediate images for the projection in tmp."
  echo "  -v                Verbose mode: show progress."
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
source "$initfile"

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
origin="0,0"
originSecond="0,0"
originFlip="0,0"
split=""
testme=""
ffcorrection=true
#imagick=""
stParam=""
xtParamFile=""
postT=""
minProj=0
maxProj=$(( $pjs - 1 ))
nlen=${#pjs}
wipeClean=false

echo "$allopts" >> ".proc.history"


#while getopts "g:G:f:c:C:r:b:s:n:i:o:x:m:M:dthwvV" opt ; do
while getopts "k:g:G:f:c:C:r:b:s:o:x:m:M:dt:hwvV" opt ; do
  case $opt in
    k)  mask=$OPTARG;;
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
    c)  crop=$OPTARG ;      stParam="$stParam --crop $crop" ;;
    C)  cropFinal=$OPTARG ; stParam="$stParam --crop-final $cropFinal" ;;
    b)  binn=$OPTARG ;      stParam="$stParam --binn $binn" ;;
    s)  splits=$OPTARG
        for sp in $( sed "s:,: :g" <<< $splits )  ; do
          stParam="$stParam --split $sp"
        done
        ;;
    #n)  imagick="$imagick -median $OPTARG" ;;
    #i)  imagick="$imagick $OPTARG" ;;
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
    v)  stParam="$stParam --verbose " ;;
    h)  printhelp ; exit 1 ;;
    \?) echo "Invalid option: -$OPTARG" >&2 ; exit 1 ;;
    :)  echo "Option -$OPTARG requires an argument." >&2 ; exit 1 ;;
  esac
done




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
    echo "Processing subdirectory $subd ..."
    cd $subd
    $0 $@
    cd $OLDPWD
    echo "Finished processing ${subd}."
  done

  exit $?

fi

shift $(( $OPTIND - 1 ))




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

imgbg="$opath/bg.tif"
if [ -e $imgbg ]  &&  $ffcorrection ; then
  stParam="$stParam --bg $imgbg"
fi

imgdf="$opath/df.tif"
if [ -e $imgdf ]  &&  $ffcorrection ; then
  stParam="$stParam --df $imgdf"
fi

imggf="$opath/gf.tif"
if [ -e $imggf ]  &&  $ffcorrection ; then
  stParam="$stParam --dg $imggf"
fi

imgms="$mask"
if [ $imgms ] && [ -e $imgms ] ; then
  stParam="$stParam --mask $mask"
fi

oname="SAMPLE_T@.tif"
if [ $testme ] ; then
  oname="tmp/$oname"  
  stParam="$stParam --test $testme"  
else
  oname="clean/$oname"
fi
stParam="$stParam --output $oname"

if (( maxProj >= $pjs  )) ; then
    maxProj=$(( $pjs - 1 ))
fi  
stParam="$stParam --select ${minProj}-${maxProj}"




flip_shift() {
  lbl=$( sed -e 's:_$::g' -e 's:^_::g' <<< $1 )
  if [ -z "$lbl" ] ; then
    lbl="single"
  fi
  ang=$( ( cat "$projfile" | grep '#' | grep "${lbl}" | cut -d' ' -f 6 ) 2> /dev/null )
  echo "scale=0 ; 180.0 / $ang" | bc
}

imgnum() {
  lbl=$( sed -e 's:_$::g' -e 's:^_::g' <<< $1 )
  if [ -z "$lbl" ] ; then
    lbl="single"
  fi
  inum=$( ( cat "$projfile" | grep -v '#' | grep "${lbl} ${2} " | cut -d' ' -f 3 ) 2> /dev/null )
  if [ -z "${inum}" ] ; then
    inum=${2}
  fi
  echo $inum
  #printf "%0${nlen}i" $inum
}

lsImgs=""
if [ "$format" == "HDF5" ] ; then
  while read imgm ; do
    imgf="$ipath/SAMPLE${imgm}.hdf:$H5data:"
    lsImgs="${lsImgs}${imgf}APPENDHERE${imgm}S "
  done <<< $( echo $imagemask | sed 's: :\n:g' )
  if (( $fshift >= 1 )) ; then
    while read imgm ; do
      imgf="$ipath/SAMPLE${imgm}.hdf:$H5data:"
      lsImgs="${lsImgs}${imgf}APPENDHERE${imgm}F "
    done <<< $( echo $imagemask | sed 's: :\n:g' )
  fi
fi





declare -a idxs
declare -a srcf
cpr=0
while read imgm ; do
  lbl=$( sed -e 's:_$::g' -e 's:^_::g' <<< $imgm )
  if [ -z "$lbl" ] ; then
    lbl="single"
  fi
  if [ "$format" == "HDF5" ] ; then
    srcf[$cpr]="$ipath/SAMPLE${imgm}.hdf:$H5data:"
  else 
    srcf[$cpr]="$ipath/SAMPLE${imgm}T%0${nlen}i.tif"
  fi
  idxs[$cpr]=$( ( cat "$projfile" | grep -v '#' | grep "${lbl}" | cut -d' ' -f 3 | head -n $pjs) 2> /dev/null )
  ((cpr++))
done <<< $( echo $imagemask | sed 's: :\n:g' )
if (( $fshift >= 1 )) ; then
  while read imgm ; do
    lbl=$( sed -e 's:_$::g' -e 's:^_::g' <<< $imgm )
    if [ -z "$lbl" ] ; then
      lbl="single"
    fi
    if [ "$format" == "HDF5" ] ; then
      srcf[$cpr]="$ipath/SAMPLE${imgm}.hdf:$H5data:"
    else 
      srcf[$cpr]="$ipath/SAMPLE${imgm}T%0${nlen}i.tif"
    fi    
    idxs[$cpr]=$( ( cat "$projfile" | grep -v '#' | grep "${lbl}" | cut -d' ' -f 3 | tail -n +$fshift | head -n $pjs) 2> /dev/null )
    ((cpr++))
  done <<< $( echo $imagemask | sed 's: :\n:g' )
fi

declare -a clmn
for ((ccpr=0 ; ccpr < $cpr ; ccpr++)) ; do
  if [ "$format" == "HDF5" ] ; then
    clmn[$ccpr]="${srcf[$ccpr]}$(tr '\n' ',' <<< ${idxs[$ccpr]})"
  else
    format="${srcf[$ccpr]}"    
    clmn[$ccpr]="$(printf "$format\n" "${idxs[@]}")"
  fi
done
tmp=""
for cl in "${clmn[@]}"; do
  tmp=$(paste -d' ' <(echo -e "$tmp") <( echo -e "$cl"))
done


echo "$tmp" | ctas proj $stParam ||
  ( echo "There was an error executing:" >&2
    echo "  echo $tmp | ctas proj $stParam" >&2 )



if [ -z "$xtParamFile" ] ; then
  exit $?
fi
echo "Starting CT reconstruction in $PWD"
addOpt=""
if [ ! -z "$step" ] ; then
  addOpt=" -a $step "
fi
imbl-xtract-wrapper.sh $addOpt "$xtParamFile" clean rec
xret="$?"
if [ "$xret" -eq "0" ] && $wipeClean ; then
    mv clean/SAMPLE*$(printf \%0${nlen}i $minProj).tif .
    mv clean/SAMPLE*$(printf \%0${nlen}i $maxProj).tif .
    mv clean/SAMPLE*$(printf \%0${nlen}i $(( ( $minProj + $maxProj ) / 2 )) ).tif .
    rm -rf clean/*
fi
exit $xret

