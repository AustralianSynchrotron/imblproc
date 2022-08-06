#!/bin/bash

printhelp() {
  echo "Usage: $0 [OPTIONS] <X-tract param file> <input dir> <output dir>"
  echo "OPTIONS:"
  echo "  -p STRING           RegExpt for projection files."
  echo "  -r STRING           Prefix for reconstructed files."
  echo "  -s STRING           Prefix for sinogram files."
  echo "  -c FLOAT            Center of rotation correction."
  echo "  -e FLOAT            Energy (kEv)."
  echo "  -a FLOAT            Angle step (deg)."
  echo "  -S FLOAT            Pixel size (mum)."
  echo "  -P BOOL             Perform / not phase extraction (0 for no or 1 for yes)."
  echo "  -d FLOAT            Sample to detector distance (mum)."
  echo "  -D FLOAT            Delta to beta ratio for phase extraction."
  echo "  -R INT              Ring artefact size (odd number, 0 - no ring filter)."
  echo "  -T INT,INT,INT,INT  Sub-region: first X, last X, first Y, last Y."
  echo "  -F INT              CT filter:"
  echo "                        0 - Ramp (standard),"
  echo "                        1 - Shepp-Logan,"
  echo "                        2 - Cosine,"
  echo "                        3 - Hamming,"
  echo "                        4 - Hann."
  echo "  -q                  No output."
  echo "  -v                  Full X-tract output."
  echo "  -h                  Print this help."
}

chkf () {
  if [ ! -e "$1" ] ; then
    echo "ERROR! Non existing" $2 "path: \"$1\"" >&2
    exit 1
  fi
}


qparam=""

projFiles=""
recFiles=""
sinFiles=""
step=""
pixel_size=""
phase_extraction_pbi=""
phase_extraction_pbi_rprime=""
phase_extraction_delta_to_beta=""
ring_filter_sinogram=""
ring_filter_sinogram_size=""
cor=""
recon_filter=""
quiet=false
verbose=false
trim_region=""
energy=""

while getopts "p:r:s:c:e:a:S:P:d:D:R:F:T:hqv" opt ; do
  case $opt in
    p)  projFiles="$OPTARG" ;;
    r)  recFiles="$OPTARG" ;;
    s)  sinFiles="$OPTARG" ;;
    c)  cor="$OPTARG" ; qparam="${qparam} -c $OPTARG " ;;
    e)  energy="$OPTARG" ; qparam="${qparam} -e $OPTARG " ;;
    a)  step="$OPTARG" ; qparam="${qparam} -a $OPTARG " ;;
    S)  pixel_size="$OPTARG" ; qparam="${qparam} -S $OPTARG " ;;
    P)  phase_extraction_pbi="$OPTARG" ; qparam="${qparam} -P $OPTARG " ;;
    d)  phase_extraction_pbi_rprime="$OPTARG" ; qparam="${qparam} -d $OPTARG " ;;
    D)  phase_extraction_delta_to_beta="$OPTARG" ; qparam="${qparam} -D $OPTARG " ;;
    R)  ring_filter_sinogram_size="$OPTARG" ;
        ring_filter_sinogram=$(( $ring_filter_sinogram_size > 0 ? 1 : 0 ))
        qparam="${qparam} -R $OPTARG "
        ;;
    T)  trim_region="$OPTARG" ; qparam="${qparam} -T $OPTARG "  ;; # IFS=',' read startx startY sizeX sizeY <<< "$OPTARG" ;;
    F)  recon_filter="$OPTARG" ; qparam="${qparam} -F $OPTARG " ;;
    q)  quiet=true ;
        if "$verbose" ;then
          echo "Options -q (quiet) and -v (verbose) are incompatible." >&2
          exit 1
        fi
        ;;
    v)  verbose=true ;
        if "$quiet" ;then
          echo "Options -q (quiet) and -v (verbose) are incompatible." >&2
          exit 1
        fi
        ;;
    h)  printhelp ; exit 1 ;;
    \?) echo "Invalid option: -$OPTARG" >&2 ; exit 1 ;;
    :)  echo "Option -$OPTARG requires an argument." >&2 ; exit 1 ;;
  esac
done
shift $(( $OPTIND - 1 ))

xtParamFile="${1}"
if [ -z "${xtParamFile}" ] ; then
  echo "No X-tract parameters file given." >&2
  printhelp >&2
  exit 1
fi
chkf "$xtParamFile" "X-tract parameters"

indir="${2}"
if [ -z "${indir}" ] ; then
  echo "No input directory given." >&2
  printhelp >&2
  exit 1
fi
chkf "$indir" "input directory"

outdir="${3}"
if [ -z "${outdir}" ] ; then
  echo "No output directory given." >&2
  printhelp >&2
  exit 1
fi
if ! mkdir -p "${outdir}" ; then
  echo "Could not create output directory \"${outdir}\"." >&2
  exit 1
fi

if [ -z "$projFiles" ] ; then

  nsplits=$(ls "${indir}" | grep SAMPLE | grep split 2>/dev/null | sed 's .*\(_split[0-9]\+\).* \1 g' | sort | uniq)
  if [ -z "$nsplits" ] && ls "${indir}" | grep -q SAMPLE > /dev/null ; then
    nsplits="_"
  fi

  retnum=0
  for spl in $nsplits ; do
      $(realpath "$0") -p "SAMPLE\w*${spl}\w*.tif" -s "sino${spl}_.tif" -r "recon${spl}_.tif" \
         $qparam "$xtParamFile" "${indir}" "${outdir}"
      if [ "$?" -ne "0" ] ; then
          retnum=1
      fi
  done

  exit $retnum

fi

xparams="$(cat "$(realpath "$xtParamFile")" |
            perl -p -e 's/:\n/ /g' |
            grep -- -- |
            sed 's/.* --/--/g' |
            grep -v 'Not set' |
            grep -v -- --indir |
            grep -v -- --outdir )"
xparams="$xparams"$'\n'"--indir $(realpath ${indir})"
xparams="$xparams"$'\n'"--outdir $(realpath ${outdir})"

setXparam() {
  if [ ! -z "$1" ] && [ ! -z "$2" ] ; then
      xparams=$( grep -v -- --"$2" <<< "$xparams" )$'\n'"--$2 $1"
  fi
}
setXparam "$projFiles" proj
setXparam "$recFiles" file_prefix_ctrecon
setXparam "$sinFiles" file_prefix_sinograms
if [ ! -z "$cor" ] ; then
  setXparam 0 cor_method
  setXparam "$cor" cor_manual
fi
setXparam "$step" angle_step
setXparam "$pixel_size" pixel_size
setXparam "$phase_extraction_pbi" phase_extraction_pbi
setXparam "$phase_extraction_pbi_rprime" phase_extraction_pbi_rprime
setXparam "$phase_extraction_delta_to_beta" phase_extraction_delta_to_beta
setXparam "$ring_filter_sinogram" ring_filter_sinogram
setXparam "$ring_filter_sinogram_size" ring_filter_sinogram_size
setXparam "$recon_filter" recon_filter
setXparam "$trim_region" trim_region



xlog=".xtract_log.txt"
drop_caches
if $quiet ; then
  xlictworkflow_local.sh $xparams >> "$xlog" 2> >(tee -a "$xlog" >&2 )
elif $verbose ; then
  xlictworkflow_local.sh $xparams
else

  nofProj=0
  nofSlic=0
  curProj=
  cntSlic=0

  while read ; do

    echo $REPLY >> "$xlog"
    if grep -q -E 'Process: [0-9]+, Thread: [0-9]+, Projection Volume Dimensions, x = [0-9]+, y = [0-9]+, z = [0-9]+' \
       <<< "$REPLY"
    then
      nofProj=$(echo "$REPLY" | sed 's:.*z = \([0-9]*\).*:\1:g' )
      nofSlic=$(echo "$REPLY" | sed 's:.*y = \([0-9]*\).*:\1:g' )
    
    elif grep -q -E 'Process: [0-9]+, Thread: [0-9]+, Get Projection Slab, pSlab->Get_nSliceOffset\(\) = [0-9]+, pSlab->Get_nSize\(\) = [0-9]+' \
         <<< "$REPLY"
    then
      curProj=$(echo "$REPLY" | sed 's:.*Get_nSliceOffset() = \([0-9]*\).*:\1:g' )
      if (( $curProj )) ; then
        echo "Reading projections: $curProj/$nofProj"
      fi
    
    elif grep -q -E 'Process: [0-9]+, Thread: [0-9]+, Put Sinogram Slab, SliceOffset = 0' \
         <<< "$REPLY"
    then
      echo "Reading projections: $curProj/$nofProj"
      echo "Reading projections: DONE."
    
    elif grep -q -E '<< COR= [0-9]+>>' \
         <<< "$REPLY"
    then
      echo "$REPLY"

    elif grep -q -E   'Process: [0-9]+, Thread: [0-9]+, Get CT Recon Slab, Slice Offset = [0-9]+' \
         <<< "$REPLY"
    then
        echo "Reconstructing volume: 0/$nofProj"
    
    elif grep -q -E 'Process: [0-9]+, Thread: [0-9]+, Reconstructed slice [0-9]+' \
         <<< "$REPLY"
    then
      curSlic=$(echo "$REPLY" | sed 's:.*Reconstructed slice \([0-9]*\).*:\1:g' )
      (( cntSlic++ ))
      echo "Reconstructing volume: $cntSlic/$nofSlic"
    
    elif grep -q -E '>>>>> Progress: OnCompleted' \
         <<< "$REPLY"
    then
      echo "Reconstructing volume: $cntSlic/$nofSlic"
      echo "Reconstructing volume: DONE"

    elif grep -q -E 'Process: [0-9]+, Finalising, Total Time = [.0-9]+ \(s\)' \
         <<< "$REPLY"
    then
      ctTime=$(echo "$REPLY" | sed 's:.*Total Time = \([\.0-9]*\) (s).*:\1:g' )
      echo "CT reconstruction finished in ${ctTime}s."
    fi

  done < <( xlictworkflow_local.sh $xparams  2> >(tee -a "$xlog" >&2 )  )

fi






exit $?

