#!/bin/bash


printhelp() {
  echo "Usage: $0 [OPTIONS] <X-tract param file> <input dir> <output dir>"
  echo "OPTIONS:"
  echo "  -p STRING         RegExpt for projection files."
  echo "  -r STRING         Prefix for reconstructed files."
  echo "  -s STRING         Prefix for sinogram files."
}

chkf () {
  if [ ! -e "$1" ] ; then
    echo "ERROR! Non existing" $2 "path: \"$1\"" >&2
    exit 1
  fi
}

projFiles=""
recFiles=""
sinFiles=""

while getopts "p:r:s:h" opt ; do
  case $opt in
    p)  projFiles="$OPTARG" ;;
    r)  recFiles="$OPTARG" ;;
    s)  sinFiles="$OPTARG" ;;
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

  nsplits=$(ls "${indir}/"SAMPLE*split* 2>/dev/null | sed 's .*\(_split[0-9]\+\).* \1 g' | sort | uniq)
  if [ -z "$nsplits" ] && ls "${indir}/"SAMPLE*tif > /dev/null ; then
    nsplits="_"
  fi

  retnum=0
  for spl in $nsplits ; do
      $0 -p "SAMPLE\w*${spl}\w*.tif" -s "sino${spl}_.tif" -r "recon${spl}_.tif" \
          "$xtParamFile" "${indir}" "${outdir}" 
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
            grep -v -- --outdir)"
xparams="$xparams"$'\n'"--indir $(realpath ${indir})"
xparams="$xparams"$'\n'"--outdir $(realpath ${outdir})"

if [ ! -z "$recFiles" ] ; then
    xparams=$( grep -v -- --file_prefix_ctrecon <<< "$xparams" )$'\n'"--file_prefix_ctrecon $recFiles"
fi
if [ ! -z "$sinFiles" ] ; then
    xparams=$( grep -v -- --file_prefix_sinograms <<< "$xparams" )$'\n'"--file_prefix_sinograms $sinFiles"
fi
xparams=$( grep -v -- --proj <<< "$xparams" )$'\n'"--proj $projFiles"

drop_caches
xlictworkflow_local.sh $xparams
exit $?

