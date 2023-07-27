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
  echo "  -z INT            Projections binning factor."
  echo "  -m INT            First projection to be processed."
  echo "  -M INT            Last projection to be processed."
  echo "  -d                Does not perform flat field correction on the images."
  echo "  -t INT            Test mode: keeps intermediate images for the projection in tmp."
  echo "  -s                Don't save stitched volume in storage (if created in memory)."
  echo "  -w                Don't wipe stitched volume from memory."
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
zinn=1
rotate=0
edge=0
peakThr=0
peakRad=0
origin="0,0"
originSecond="0,0"
originFlip="0,0"
testme=""
ffcorrection=true
stParam=""
minProj=0
maxProj=$(( $pjs - 1 ))
volStore=true # save in storage
volWipe=true # wipe from memory
beverbose=false

while getopts "i:g:G:f:c:C:r:b:z:m:M:E:n:N:dt:swhv" opt ; do
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
    z)  zinn=$OPTARG ;      stParam="$stParam --zinn $zinn" ;;
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
    d)  ffcorrection=false ;;
    s)  volStore=false ;;
    w)  volWipe=false ;;
    t)  testme="$OPTARG" ;;
    v)  beverbose=true ;;
    h)  printhelp ; exit 1 ;;
    \?) echo "ERROR! Invalid option: -$OPTARG" >&2 ; exit 1 ;;
    :)  echo "ERROR! Option -$OPTARG requires an argument." >&2 ; exit 1 ;;
  esac
done


if [ -z "$PROCRECURSIVE" ] ; then
  echo "$0" "$allopts" >> ".proc.history"
fi

if [ -n "$subdirs" ] ; then

  if [ -n "$testme" ] ; then
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
      echo "    cd $(realpath "$subd")"
    fi
    cd "$subd"
    if $beverbose ; then
      echo "    $0 $@"
    fi
    $0 $@
    if $beverbose ; then
      echo "    cd $(realpath "$OLDPWD")"
    fi
    cd "$OLDPWD"
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
if (( maxProj >= $pjs  )) ; then
  maxProj=$(( $pjs - 1 ))
fi
ppjs=$(( $maxProj - $minProj + 1 ))
nlen=${#ppjs}

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

if [ -n "$1" ] ; then
  stParam="$stParam --select $1"
fi


prepare_seq() {
  if [ "$format" == "HDF5" ] ; then
    echo -n "$1"
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
  else
    perl -pe 'chomp if eof' | xargs printf "$1"
  fi
}

rm .idxs* 2> /dev/null
imagemask="$(echo $filemask | sed 's: :\n:g' | sed -r 's ^(.+) _\1 g')"
while read imgm ; do
  lbl=$( sed -e 's:_$::g' -e 's:^_::g' <<< $imgm )
  if [ -z "$lbl" ] ; then
    lbl="single"
  fi
  seqarg=""
  if [ "$format" == "HDF5" ] ; then
    seqarg="$ipath/SAMPLE${imgm}.hdf:$H5data:"
  else
    seqarg="$ipath/SAMPLE${imgm}_T%0${nlen}i.tif\n"
  fi
  cat "$projfile" | grep -v '#' | grep "${lbl}" | cut -d' ' -f 3  \
    | head -n $pjs | head -n $(( $maxProj + 1 )) | tail -n+$(( $minProj + 1 )) \
    | prepare_seq "$seqarg" >> ".idxs${imgm}.o"
  if (( $fshift >= 1 )) ; then
    cat "$projfile" | grep -v '#' | grep "${lbl}" | cut -d' ' -f 3 \
      | tail -n +$fshift | head -n $pjs | head -n $(( $maxProj + 1 )) | tail -n+$(( $minProj + 1 )) \
      | prepare_seq "$seqarg" >> ".idxs${imgm}.f"
  fi
done <<< "$imagemask"

idxsallf=".idxsall"
paste -d' ' $( (ls .idxs*o ; ls .idxs*f) 2> /dev/null ) > "$idxsallf"
if (( $(wc -w <<< "$filemask") > 1 )) ; then # purely for easy reading
  sed -zi 's \n \n\n g' "$idxsallf"
fi
rm .idxs*o .idxs*f 2> /dev/null


if ! mkdir -p "tmp" ; then
  echo "Could not create output sub-directory $(realpath "tmp"). Aborting."  >&2
  exit 1
fi
tstfl="SAMPLE_T"
tstParam=" --output tmp/${tstfl}@.tif --test $( [ -n "$testme" ] && echo "$testme" || echo "0" )"
if $beverbose ; then
  echo "Running test:"
  echo "  ctas proj $stParam $tstParam < $idxsallf"
fi
tstOut="$(ctas proj $stParam $tstParam < $idxsallf)"
if (($?)) ; then
  echo "There was an error executing ctas proj. Exiting." >&2
  exit 1
fi
if [ "$testme" ] ; then
  echo "$tstOut"
  exit 0
fi
read z y x testOFl <<< "$tstOut"
if [ -z "$testOFl" ] ; then
  echo "ERROR! Test failed." >&2
  exit 1
fi

cleanPath="clean.hdf"
if ( ! $volWipe || ! $volStore ) ; then # create file in memory
  volSize=$(( 4 * $x * $y * $z ))
  hVolSize="${x}x${y}x${z} $(numfmt --to=iec <<< $volSize)B"
  memSize=$(free -bw | sed 's:  *: :g' | cut -d' ' -f 8 | sed '2q;d')
  if (( $volSize > $( echo " scale=0 ; $memSize * 4 / 5 " | bc )  )) ; then
    echo "WARNING! Not enough available memory $(numfmt --to=iec <<< $memSize)B to allow" \
         " processing $hVolSize volume. Will use file storage for interim data, what can" \
         " be significantly slower."  >&2
  else
    crFilePrefix="/dev/shm/imblproc_$(realpath $PWD | sed 's / _ g')_"
    #flfix=$( basename "$testOFl" | sed 's '${tstfl}'[0-9]*  g' )
    #flfix="${flfix%.*}"
    #tpnm="${crFilePrefix}clean${flfix}.hdf"
    tpnm="${crFilePrefix}${cleanPath}"
    if $beverbose ; then
      echo "Creating in memory interim file $tpnm for $hVolSize volume."
    fi
    if ! ctas v2v "$testOFl" -o "${tpnm}:/data:-$(( $z - 1 ))" \
       ||
       ! (
         vsize=$( du --block-size=1 "$tpnm" | cut -d$'\t' -f1 )
         esize=$(( 4 * x * y * z ))
         if (( $vsize  <  $esize )) ; then
           cp --sparse=never "$tpnm" "${tpnm}.tmp"  &&  mv "${tpnm}.tmp" "$tpnm"
         fi
       )
    then
      echo "WARNING! Could not create or allocate in memory interim file $tpnm for" \
           " $hVolSize volume. Will use file storage for interim data, what can be" \
           " significantly slower." >&2
      rm -rf "$crFilePrefix"*
    else
      cleanPath="$tpnm"
    fi
  fi
fi


cleanPath="${crFilePrefix}clean.hdf"
outFile="$(realpath "${cleanPath}")"
outParam=" --output ${outFile}:/data"
if $beverbose ; then
  echo "Starting frame formation in $PWD."
  echo "  ctas proj $stParam $outParam < $idxsallf"
fi
ctas proj $stParam $outParam < "$idxsallf"  ||
  ( echo "There was an error executing:" >&2
    echo -e "ctas proj $stParam $outParam < $idxsallf"  >&2
    echo -e "Removing incomplete file(s): ${outFile%.*}"'*'  >&2
    rm "${outFile%.*}"'*'
    exit 1 )


if [ -n "$crFilePrefix" ] ; then # file is in memory
  #trgnm="$opath/clean.hdf"
  if $volWipe || $volStore; then
    if $beverbose ; then
      echo "Copying in-memory interim file $cleanPath to $PWD/clean.hdf."
    fi
    cp "$cleanPath" "clean.hdf"
    if $volWipe ; then
      rm "$cleanPath"
    fi
  fi
fi

